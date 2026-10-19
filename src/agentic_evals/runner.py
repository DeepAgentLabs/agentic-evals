import asyncio
import json
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, SchemaError
from referencing import Registry
from referencing.exceptions import Unresolvable

from agentic_evals._version import __version__
from agentic_evals.evaluators import EvaluationContext, EvaluatorRegistry
from agentic_evals.judging import is_judge_score, is_unavailable
from agentic_evals.live import LiveCall, acall_target, async_caller, call_target, sync_caller
from agentic_evals.models import (
    CaseEvaluation,
    EvaluationReport,
    EvaluationSample,
    EvaluationSummary,
    EvaluatorConfig,
    JudgeSummary,
    LiveSummary,
    LiveTarget,
    MetricSummary,
    Score,
    TagSummary,
    TestCase,
    TestSuite,
)
from agentic_evals.reliability import RetryPolicy
from agentic_evals.scorers.text import REFERENCE_SCORER_NAMES

TraceAdapter = Callable[[Any], Any]

#: `Score.evaluator` for the checks `evaluate_suite` runs itself (exact match,
#: contains, tool and threshold checks). Their `evaluator_version` is this
#: package's version, since that is what defines their logic.
BUILTIN_EVALUATOR = "agentic_evals.builtin"


def _stamp_builtin(scores: list[Score]) -> list[Score]:
    return [
        score
        if score.evaluator
        else score.model_copy(
            update={"evaluator": BUILTIN_EVALUATOR, "evaluator_version": __version__}
        )
        for score in scores
    ]


def _load_data(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)


def load_suite(path: Path) -> TestSuite:
    return TestSuite.model_validate(_load_data(path))


def load_samples(
    path: Path, *, trace_adapter: TraceAdapter | None = None
) -> list[EvaluationSample]:
    """Load samples from a JSON, JSONL or YAML file.

    `trace_adapter`, if given, is applied to each sample's raw `trace` value
    before validation -- callers whose trace payloads predate or otherwise
    don't match `EvalTrace`'s shape can normalize them here instead of
    having them silently validate with defaulted-out fields.
    """
    if path.suffix.lower() == ".jsonl":
        data = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    data.append(json.loads(line))
                except ValueError as exc:
                    raise ValueError(f"{path}: invalid JSON on line {number}: {exc}") from exc
    else:
        data = _load_data(path)
    items = data["samples"] if isinstance(data, dict) and "samples" in data else data
    if not isinstance(items, list):
        raise ValueError("samples must be a list or an object containing a samples list")
    if trace_adapter is not None:
        items = [
            {**item, "trace": trace_adapter(item["trace"])} if "trace" in item else item
            for item in items
        ]
    return [EvaluationSample.model_validate(item) for item in items]


def _lookup_path(payload: Any, dotted_path: str) -> tuple[bool, Any]:
    current = payload
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return True, current


def _schema_validator(schema: dict[str, Any]) -> Any:
    dialect = schema.get("$schema", "https://json-schema.org/draft/2020-12/schema")
    if dialect != "https://json-schema.org/draft/2020-12/schema":
        raise ValueError("output_json_schema supports JSON Schema Draft 2020-12 only")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ValueError(f"Invalid output_json_schema: {exc.message}") from exc
    # Resolve embedded references only; never fetch schemas from the network.
    return Draft202012Validator(schema, registry=Registry())


def _validate_json_schema(payload: Any, schema: dict[str, Any]) -> tuple[bool, str]:
    validator = _schema_validator(schema)
    try:
        error = next(validator.iter_errors(payload), None)
    except Unresolvable as exc:
        raise ValueError(f"Unresolvable output_json_schema reference: {exc}") from exc
    if error is not None:
        return False, f"Output violates JSON Schema at {error.json_path}: {error.message}"
    return True, "Output matches the configured JSON Schema Draft 2020-12."


def _reject_json_constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON constant {value} is not allowed")


def _turn_count(sample: EvaluationSample) -> int | None:
    metadata_turns = sample.trace.metadata.get("turn_count")
    if isinstance(metadata_turns, int) and metadata_turns > 0:
        return metadata_turns
    return None


def _graded_against_expected_output(case: TestCase) -> bool:
    """True when a reference scorer on the case grades against `expected_output` itself."""
    return any(
        config.name in REFERENCE_SCORER_NAMES and not config.config.get("reference")
        for config in case.evaluators
    )


def _score_tool_order(required_order: list[str], sample: EvaluationSample) -> Score:
    """Each tool in `required_order` is first called before the next one is.

    Calls to other tools in between are fine; what fails is a listed tool
    that was never called, or one whose first call came ahead of a tool
    listed before it.
    """
    called = [span.tool_name for span in sample.trace.spans if span.tool_name]
    first_call = {tool: called.index(tool) for tool in required_order if tool in called}
    missing = [tool for tool in required_order if tool not in first_call]
    out_of_order = [
        (earlier, later)
        for earlier, later in zip(required_order, required_order[1:], strict=False)
        if earlier in first_call and later in first_call and first_call[earlier] > first_call[later]
    ]
    passed = not missing and not out_of_order
    if passed:
        explanation = f"Tools were first called in the required order {required_order}."
    elif missing:
        explanation = f"Required order {required_order} not met: {missing} never called."
    else:
        earlier, later = out_of_order[0]
        explanation = (
            f"Required order {required_order} not met: {later!r} was called before {earlier!r}."
        )
    return Score(name="tool_order", value=float(passed), passed=passed, explanation=explanation)


def _builtin_scores(case: TestCase, sample: EvaluationSample) -> list[Score]:
    scores: list[Score] = []
    output = sample.output.strip()
    if case.expected_output is not None and not _graded_against_expected_output(case):
        passed = output == case.expected_output.strip()
        scores.append(
            Score(
                name="exact_match",
                value=float(passed),
                passed=passed,
                explanation="Output exactly matches the reference."
                if passed
                else "Output does not exactly match the reference.",
            )
        )
    for expected in case.expected_contains:
        passed = expected.casefold() in output.casefold()
        scores.append(
            Score(
                name=f"contains:{expected}",
                metric="contains",
                value=float(passed),
                passed=passed,
                explanation=f"Output contains required text: {expected!r}."
                if passed
                else f"Output is missing required text: {expected!r}.",
            )
        )
    parsed_output: Any | None = None
    output_json_error: str | None = None
    if case.output_json_schema is not None or case.required_output_fields:
        try:
            parsed_output = json.loads(output, parse_constant=_reject_json_constant)
        except ValueError as exc:
            output_json_error = str(exc)
    if case.output_json_schema is not None:
        if output_json_error is not None:
            scores.append(
                Score(
                    name="json_schema",
                    value=0.0,
                    passed=False,
                    explanation=f"Output is not valid JSON: {output_json_error}.",
                )
            )
        else:
            valid, reason = _validate_json_schema(parsed_output, case.output_json_schema)
            scores.append(
                Score(
                    name="json_schema",
                    value=float(valid),
                    passed=valid,
                    explanation=reason,
                )
            )
    for field_path in case.required_output_fields:
        exists = (
            output_json_error is None
            and parsed_output is not None
            and _lookup_path(parsed_output, field_path)[0]
        )
        scores.append(
            Score(
                name=f"required_field:{field_path}",
                metric="required_field",
                value=float(exists),
                passed=exists,
                explanation=f"Output contains required field {field_path!r}."
                if exists
                else (
                    "Output is not valid JSON, so required field "
                    f"{field_path!r} could not be checked."
                    if output_json_error is not None
                    else f"Output is missing required field {field_path!r}."
                ),
            )
        )

    tools = {span.tool_name for span in sample.trace.spans if span.tool_name}
    for tool in case.required_tools:
        passed = tool in tools
        scores.append(
            Score(
                name=f"required_tool:{tool}",
                metric="required_tool",
                value=float(passed),
                passed=passed,
                explanation=f"Required tool {tool!r} was called."
                if passed
                else f"Required tool {tool!r} was not called.",
            )
        )
    for tool in case.forbidden_tools:
        passed = tool not in tools
        scores.append(
            Score(
                name=f"forbidden_tool:{tool}",
                metric="forbidden_tool",
                value=float(passed),
                passed=passed,
                explanation=f"Forbidden tool {tool!r} was not called."
                if passed
                else f"Forbidden tool {tool!r} was called.",
            )
        )
    for tool_name, required_args in case.required_tool_arguments.items():
        matching_spans = [span for span in sample.trace.spans if span.tool_name == tool_name]
        args_present = False
        for span in matching_spans:
            tool_args = span.attributes.get("tool_args")
            if isinstance(tool_args, dict) and all(arg in tool_args for arg in required_args):
                args_present = True
                break
        scores.append(
            Score(
                name=f"tool_args:{tool_name}",
                metric="tool_args",
                value=float(args_present),
                passed=args_present,
                explanation=f"Tool {tool_name!r} included required arguments {required_args}."
                if args_present
                else f"Tool {tool_name!r} did not include required arguments {required_args}.",
            )
        )
    for tool_name, expected_args in case.expected_tool_arguments.items():
        calls = [
            span.attributes.get("tool_args")
            for span in sample.trace.spans
            if span.tool_name == tool_name
        ]
        values_match = any(
            isinstance(tool_args, dict)
            and all(
                arg in tool_args and tool_args[arg] == value for arg, value in expected_args.items()
            )
            for tool_args in calls
        )
        scores.append(
            Score(
                name=f"tool_arg_values:{tool_name}",
                metric="tool_arg_values",
                value=float(values_match),
                passed=values_match,
                explanation=f"Tool {tool_name!r} was called with {expected_args}."
                if values_match
                else (
                    f"Tool {tool_name!r} was called with {calls}, not {expected_args}."
                    if calls
                    else f"Tool {tool_name!r} was not called, so {expected_args} was not passed."
                ),
            )
        )
    if case.required_tool_order:
        scores.append(_score_tool_order(case.required_tool_order, sample))
    if case.max_latency_ms is not None:
        passed = sample.trace.total_latency_ms <= case.max_latency_ms
        scores.append(
            Score(
                name="latency_threshold",
                value=float(passed),
                passed=passed,
                explanation=(
                    f"Latency {sample.trace.total_latency_ms:.1f} ms "
                    f"{'meets' if passed else 'exceeds'} the "
                    f"{case.max_latency_ms:.1f} ms limit."
                ),
            )
        )
    if case.max_cost_usd is not None:
        cost = sample.trace.estimated_cost_usd
        passed = cost is not None and cost <= case.max_cost_usd
        scores.append(
            Score(
                name="cost_threshold",
                value=float(passed),
                passed=passed,
                explanation=(
                    f"Cost ${cost:.6f} meets the ${case.max_cost_usd:.6f} limit."
                    if passed and cost is not None
                    else "Cost is unavailable or exceeds the configured limit."
                ),
            )
        )
    if case.max_turns is not None:
        turns = _turn_count(sample)
        passed = turns is not None and turns <= case.max_turns
        scores.append(
            Score(
                name="turn_count_threshold",
                value=float(passed),
                passed=passed,
                explanation=(
                    f"Turn count {turns} {'meets' if passed else 'exceeds'} the "
                    f"{case.max_turns} turn limit."
                    if turns is not None
                    else (
                        "Trace metadata is missing a positive integer turn_count, "
                        "so the max_turns check could not be evaluated."
                    )
                ),
            )
        )
    return _stamp_builtin(scores)


def _evaluator_calls(
    case: TestCase, sample: EvaluationSample, registry: EvaluatorRegistry | None
) -> list[tuple[EvaluatorConfig, Any, EvaluationContext]]:
    calls = []
    for evaluator_config in case.evaluators:
        if registry is None:
            raise ValueError(
                f"test case {case.id!r} requires evaluator {evaluator_config.name!r}, "
                "but no evaluator registry was supplied"
            )
        evaluator = registry.get(evaluator_config.name)
        calls.append(
            (
                evaluator_config,
                evaluator,
                EvaluationContext(case=case, sample=sample, config=evaluator_config),
            )
        )
    return calls


def _with_provenance(
    evaluator: Any, config: EvaluatorConfig, custom_scores: list[Score]
) -> list[Score]:
    # The registry entry is the producer of record: stamp its name and
    # declared version over whatever the evaluator put on the score.
    declared_version = getattr(evaluator, "version", None)
    provenance = {
        "evaluator": config.name,
        "evaluator_version": declared_version if isinstance(declared_version, str) else None,
    }
    return [score.model_copy(update=provenance) for score in custom_scores]


def _score_case(
    case: TestCase,
    sample: EvaluationSample,
    registry: EvaluatorRegistry | None,
) -> list[Score]:
    scores = _builtin_scores(case, sample)
    for config, evaluator, context in _evaluator_calls(case, sample, registry):
        scores.extend(_with_provenance(evaluator, config, evaluator.evaluate(context)))
    return scores


async def _ascore_case(
    case: TestCase,
    sample: EvaluationSample,
    registry: EvaluatorRegistry | None,
) -> list[Score]:
    scores = _builtin_scores(case, sample)
    for config, evaluator, context in _evaluator_calls(case, sample, registry):
        aevaluate = getattr(evaluator, "aevaluate", None)
        if aevaluate is not None:
            custom_scores = await aevaluate(context)
        else:
            custom_scores = await asyncio.to_thread(evaluator.evaluate, context)
        scores.extend(_with_provenance(evaluator, config, custom_scores))
    return scores


def _sample_from_payload(
    payload: Any, case_id: str, trace_adapter: TraceAdapter | None
) -> EvaluationSample:
    if not isinstance(payload, dict):
        raise ValueError(
            f"live target returned {type(payload).__name__} for case {case_id!r}; "
            "expected an object with output and trace"
        )
    if trace_adapter is not None and "trace" in payload:
        payload = {**payload, "trace": trace_adapter(payload["trace"])}
    return EvaluationSample.model_validate({**payload, "case_id": case_id})


def _live_samples(
    suite: TestSuite,
    calls: list[LiveCall],
    trace_adapter: TraceAdapter | None,
    validated: dict[str, EvaluationSample],
) -> list[EvaluationSample]:
    return [
        validated.get(case.id) or _sample_from_payload(call.payload, case.id, trace_adapter)
        for case, call in zip(suite.cases, calls, strict=True)
        if call.status == "ok"
    ]


def run_live_suite(
    suite: TestSuite,
    target: LiveTarget,
    *,
    registry: EvaluatorRegistry | None = None,
    trace_adapter: TraceAdapter | None = None,
    max_workers: int = 1,
    retry: RetryPolicy | None = None,
) -> EvaluationReport:
    """Run a trusted live target against every case in a suite.

    Live targets are intentionally powerful developer-facing integrations:
    Python targets execute local code and HTTP targets can reach arbitrary URLs.
    Only use trusted suite files and trusted target definitions.

    `trace_adapter`, if given, is applied to each result's raw `trace` value
    before validation -- callers whose target implementations return trace
    payloads that don't match `EvalTrace`'s shape can normalize them here
    instead of having them silently validate with defaulted-out fields.

    `max_workers` above 1 calls the target for several cases at once on a
    thread pool. Results keep the suite's case order either way, so the
    report matches a sequential run that produced the same outputs. Only
    raise it for targets that are safe to call concurrently.

    `retry` retries a target call that raises or times out (default: one
    attempt). A case whose calls all fail is reported, not raised: it fails
    with `target_status` `timed_out` or `error` and a `target_call` score,
    and the report's `summary.live` counts each outcome. A payload that is
    not a valid sample still stops the run, since that is a target bug that
    retrying will not fix. An `async def` Python target is awaited on its
    own event loop; inside a running loop, use `arun_live_suite`.
    """
    if max_workers < 1:
        raise ValueError("max_workers must be at least 1")
    policy = retry or RetryPolicy()
    call_case = sync_caller(target)
    validated: dict[str, EvaluationSample] = {}
    if max_workers == 1:
        # Validate each result before calling the target for the next case, so
        # an invalid payload stops the run without further target side effects.
        calls = []
        for case in suite.cases:
            call = call_target(call_case, case, policy)
            if call.status == "ok":
                validated[case.id] = _sample_from_payload(call.payload, case.id, trace_adapter)
            calls.append(call)
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            calls = list(pool.map(lambda case: call_target(call_case, case, policy), suite.cases))
    samples = _live_samples(suite, calls, trace_adapter, validated)
    return _evaluate(suite, samples, registry=registry, calls=calls)


async def arun_live_suite(
    suite: TestSuite,
    target: LiveTarget,
    *,
    registry: EvaluatorRegistry | None = None,
    trace_adapter: TraceAdapter | None = None,
    max_concurrency: int = 1,
    retry: RetryPolicy | None = None,
) -> EvaluationReport:
    """Async `run_live_suite`: awaits `async def` targets and evaluators.

    Up to `max_concurrency` cases call the target at once. An `async def`
    Python target is cancelled when its explicit `timeout_seconds` elapses;
    synchronous targets run in daemon threads. Scoring then runs through
    `aevaluate_suite` with the same concurrency limit. The report has the
    same shape and case order as the synchronous run.
    """
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")
    policy = retry or RetryPolicy()
    call_case = async_caller(target)
    semaphore = asyncio.Semaphore(max_concurrency)

    async def one(case: TestCase) -> LiveCall:
        async with semaphore:
            return await acall_target(call_case, case, policy)

    validated: dict[str, EvaluationSample] = {}
    if max_concurrency == 1:
        calls = []
        for case in suite.cases:
            call = await one(case)
            if call.status == "ok":
                validated[case.id] = _sample_from_payload(call.payload, case.id, trace_adapter)
            calls.append(call)
    else:
        calls = list(await asyncio.gather(*(one(case) for case in suite.cases)))
    return await _aevaluate(
        suite,
        _live_samples(suite, calls, trace_adapter, validated),
        registry=registry,
        calls=calls,
        max_concurrency=max_concurrency,
    )


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _score_values(results: list[CaseEvaluation]) -> list[float]:
    """Values of every score that was actually evaluated (skipped ones excluded)."""
    return [score.value for result in results for score in result.scores if not score.skipped]


def _summarize_metrics(results: list[CaseEvaluation]) -> dict[str, MetricSummary]:
    by_metric: dict[str, list[Score]] = {}
    for result in results:
        for score in result.scores:
            by_metric.setdefault(score.metric, []).append(score)
    summaries: dict[str, MetricSummary] = {}
    for metric in sorted(by_metric):
        scored = [score for score in by_metric[metric] if not score.skipped]
        passed = sum(score.passed for score in scored)
        summaries[metric] = MetricSummary(
            total=len(scored),
            passed=passed,
            failed=len(scored) - passed,
            skipped=len(by_metric[metric]) - len(scored),
            pass_rate=passed / len(scored) if scored else None,
            average_score=_mean([score.value for score in scored]),
        )
    return summaries


def _count_cost_sources(results: list[CaseEvaluation]) -> dict[str, int]:
    """Priced cases per cost provenance; `unspecified` when the trace did not say."""
    counts: dict[str, int] = {}
    for result in results:
        if result.cost_usd is not None:
            key = result.cost_source or "unspecified"
            counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _summarize_tags(results: list[CaseEvaluation]) -> dict[str, TagSummary]:
    by_tag: dict[str, list[CaseEvaluation]] = {}
    for result in results:
        for tag in dict.fromkeys(result.tags):
            by_tag.setdefault(tag, []).append(result)
    summaries: dict[str, TagSummary] = {}
    for tag in sorted(by_tag):
        tagged = by_tag[tag]
        passed = sum(result.passed for result in tagged)
        summaries[tag] = TagSummary(
            total_cases=len(tagged),
            passed_cases=passed,
            failed_cases=len(tagged) - passed,
            pass_rate=passed / len(tagged),
            average_score=_mean(_score_values(tagged)),
        )
    return summaries


def _count(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _summarize_judges(results: list[CaseEvaluation]) -> JudgeSummary | None:
    judged = [
        (result.case_id, score)
        for result in results
        for score in result.scores
        if is_judge_score(score)
    ]
    if not judged:
        return None
    active = [(case_id, score) for case_id, score in judged if not score.skipped]
    unavailable = [case_id for case_id, score in active if is_unavailable(score)]
    costs: list[float] = []
    cost_sources: dict[str, int] = {}
    input_tokens = output_tokens = 0
    latency = 0.0
    agreements: list[float] = []
    case_agreement: dict[str, float] = {}
    retried = 0
    for case_id, score in active:
        meta = score.metadata
        cost = meta.get("judge_cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            costs.append(float(cost))
            source = meta.get("judge_cost_source")
            key = source if source in ("measured", "estimated") else "unspecified"
            cost_sources[key] = cost_sources.get(key, 0) + 1
        input_tokens += _count(meta.get("judge_input_tokens"))
        output_tokens += _count(meta.get("judge_output_tokens"))
        elapsed = meta.get("judge_latency_ms")
        if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool) and elapsed >= 0:
            latency += float(elapsed)
        attempts = meta.get("judge_attempts")
        samples = meta.get("judge_samples", 1)
        if isinstance(attempts, int) and isinstance(samples, int) and attempts > samples:
            retried += 1
        agreement = meta.get("judge_agreement")
        if isinstance(agreement, (int, float)) and not isinstance(agreement, bool):
            agreements.append(float(agreement))
            case_agreement[case_id] = min(case_agreement.get(case_id, 1.0), float(agreement))
    return JudgeSummary(
        judge_scores=len(active),
        unavailable_scores=len(unavailable),
        unavailable_cases=list(dict.fromkeys(unavailable)),
        retried_scores=retried,
        priced_scores=len(costs),
        total_cost_usd=sum(costs) if active and len(costs) == len(active) else None,
        cost_sources=dict(sorted(cost_sources.items())),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_latency_ms=round(latency, 3),
        sampled_scores=len(agreements),
        min_agreement=min(agreements) if agreements else None,
        average_agreement=_mean(agreements),
        case_agreement=case_agreement,
    )


def _summarize_live(results: list[CaseEvaluation]) -> LiveSummary:
    timed_out = [r.case_id for r in results if r.target_status == "timed_out"]
    errored = [r.case_id for r in results if r.target_status == "error"]
    return LiveSummary(
        total_cases=len(results),
        ok_cases=sum(r.target_status == "ok" for r in results),
        retried_cases=sum((r.target_attempts or 1) > 1 for r in results),
        timed_out_cases=len(timed_out),
        error_cases=len(errored),
        timed_out_case_ids=timed_out,
        error_case_ids=errored,
    )


def _index_samples(
    suite: TestSuite, samples: list[EvaluationSample]
) -> dict[str, EvaluationSample]:
    case_ids = [case.id for case in suite.cases]
    if not case_ids or len(case_ids) != len(set(case_ids)):
        raise ValueError("suite must contain nonempty, unique case IDs")
    for case in suite.cases:
        if case.output_json_schema is not None:
            _schema_validator(case.output_json_schema)
    by_case: dict[str, EvaluationSample] = {}
    expected = set(case_ids)
    for supplied in samples:
        if supplied.case_id in by_case:
            raise ValueError(f"Duplicate sample case ID: {supplied.case_id!r}")
        if supplied.case_id not in expected:
            raise ValueError(f"Unknown sample case ID: {supplied.case_id!r}")
        by_case[supplied.case_id] = supplied
    return by_case


def _unscored_result(case: TestCase, call: LiveCall | None) -> CaseEvaluation:
    """A case with nothing to score: no sample supplied, or the live target failed."""
    if call is None or call.status == "ok":
        score = Score(
            name="sample_available",
            value=0,
            passed=False,
            explanation="No evaluation sample was supplied for this test case.",
        )
    else:
        outcome = "timed out" if call.status == "timed_out" else "failed"
        score = Score(
            name="target_call",
            value=0,
            passed=False,
            explanation=f"Live target {outcome} after {call.attempts} attempt(s): {call.error}",
            metadata={"status": call.status, "attempts": call.attempts, "error": call.error},
        )
    return CaseEvaluation(
        case_id=case.id,
        case_name=case.name,
        passed=False,
        scores=_stamp_builtin([score]),
        output="",
        trace_id="",
        latency_ms=0,
        sample_available=False,
        target_status=call.status if call is not None else None,
        target_attempts=call.attempts if call is not None else None,
        target_error=call.error if call is not None else None,
        tags=case.tags,
        metadata=case.metadata,
    )


def _scored_result(
    case: TestCase, sample: EvaluationSample, scores: list[Score], call: LiveCall | None
) -> CaseEvaluation:
    return CaseEvaluation(
        case_id=case.id,
        case_name=case.name,
        passed=all(score.passed or not score.required or score.skipped for score in scores),
        scores=scores,
        output=sample.output,
        trace_id=sample.trace.trace_id,
        latency_ms=sample.trace.total_latency_ms,
        cost_usd=sample.trace.estimated_cost_usd,
        cost_source=(
            sample.trace.cost_source if sample.trace.estimated_cost_usd is not None else None
        ),
        target_status="ok" if call is not None else None,
        target_attempts=call.attempts if call is not None else None,
        tags=case.tags,
        metadata=case.metadata,
    )


def _report(suite: TestSuite, results: list[CaseEvaluation], *, live: bool) -> EvaluationReport:
    passed = sum(result.passed for result in results)
    all_scores = _score_values(results)
    costs = [result.cost_usd for result in results if result.cost_usd is not None]
    return EvaluationReport(
        suite_name=suite.name,
        suite_version=suite.version,
        summary=EvaluationSummary(
            total_cases=len(results),
            passed_cases=passed,
            failed_cases=len(results) - passed,
            pass_rate=passed / len(results),
            average_score=_mean(all_scores) or 0.0,
            total_cost_usd=sum(costs) if len(costs) == len(results) else None,
            priced_cases=len(costs),
            cost_sources=_count_cost_sources(results),
            average_latency_ms=sum(result.latency_ms for result in results) / len(results),
            metrics=_summarize_metrics(results),
            tags=_summarize_tags(results),
            judge=_summarize_judges(results),
            live=_summarize_live(results) if live else None,
        ),
        cases=results,
    )


def _evaluate(
    suite: TestSuite,
    samples: list[EvaluationSample],
    *,
    registry: EvaluatorRegistry | None,
    calls: list[LiveCall] | None = None,
) -> EvaluationReport:
    by_case = _index_samples(suite, samples)
    by_call = dict(zip((case.id for case in suite.cases), calls or [], strict=False))
    results: list[CaseEvaluation] = []
    for case in suite.cases:
        sample, call = by_case.get(case.id), by_call.get(case.id)
        if sample is None:
            results.append(_unscored_result(case, call))
        else:
            results.append(_scored_result(case, sample, _score_case(case, sample, registry), call))
    return _report(suite, results, live=calls is not None)


async def _aevaluate(
    suite: TestSuite,
    samples: list[EvaluationSample],
    *,
    registry: EvaluatorRegistry | None,
    calls: list[LiveCall] | None = None,
    max_concurrency: int,
) -> EvaluationReport:
    by_case = _index_samples(suite, samples)
    by_call = dict(zip((case.id for case in suite.cases), calls or [], strict=False))
    semaphore = asyncio.Semaphore(max_concurrency)

    async def one(case: TestCase) -> CaseEvaluation:
        sample, call = by_case.get(case.id), by_call.get(case.id)
        if sample is None:
            return _unscored_result(case, call)
        async with semaphore:
            scores = await _ascore_case(case, sample, registry)
        return _scored_result(case, sample, scores, call)

    results = list(await asyncio.gather(*(one(case) for case in suite.cases)))
    return _report(suite, results, live=calls is not None)


def evaluate_suite(
    suite: TestSuite,
    samples: list[EvaluationSample],
    *,
    registry: EvaluatorRegistry | None = None,
) -> EvaluationReport:
    """Score `samples` against `suite`; cases without a sample fail as unavailable."""
    return _evaluate(suite, samples, registry=registry)


async def aevaluate_suite(
    suite: TestSuite,
    samples: list[EvaluationSample],
    *,
    registry: EvaluatorRegistry | None = None,
    max_concurrency: int = 8,
) -> EvaluationReport:
    """Async `evaluate_suite`: scores up to `max_concurrency` cases at once.

    Evaluators with an `aevaluate` method (every `CallableEvaluator`) are
    awaited; others run their `evaluate` in a worker thread. The report
    matches `evaluate_suite` on the same inputs, in suite case order.
    """
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")
    return await _aevaluate(suite, samples, registry=registry, max_concurrency=max_concurrency)
