# API Reference (detailed)

**Version:** 1.1.0

Every name below is a root export of `agentic_evals` (listed in `agentic_evals.__all__`). Names beginning `_` and the implementation modules `cli_commands`, `formatting` and `live` are private. See the [public API policy](public-api.md).

```python
from agentic_evals import Eval, TestSuite, TestCase, EvaluationSample, EvalTrace, EvalSpan
from agentic_evals import evaluate_suite, evaluate_gate, GateConfig, default_registry
```

---

## Eval() Quickstart

The quickest API: run a task over a dataset and score each output.

### `Eval(name, *, data, task, scores=(), threshold=1.0, print_results=True)`

```python
def Eval(
    name: str,
    *,
    data: Iterable[dict | Case] | Callable[[], Iterable[dict | Case]],
    task: Callable[[Any], Any],
    scores: Sequence[ScoreFn] = (),
    threshold: float = 1.0,
    print_results: bool = True,
) -> EvalResult
```

| Parameter | Type | Description |
| --- | --- | --- |
| name | str | Eval name (appears in output) |
| data | iterable or callable | Rows with `input`/`expected` keys, `Case` objects, or a callable that returns them |
| task | callable | Function under test; called with each row's `input` value, returns the output |
| scores | sequence of callables | Score functions; each returns a bool, a number from 0 to 1, or a dict of named scores |
| threshold | float | Minimum score for a case to pass (default 1.0) |
| print_results | bool | Print the coloured summary (default True) |

### `Case(input, expected=None, metadata={})`

One dataset row. Plain dicts with the same keys work too.

### `EvalResult` and `CaseResult`

`EvalResult(name, threshold, results, duration_ms)` holds one `CaseResult(case, output, scores, error, duration_ms)` per row. Inspect it in code; printed output alone is not a release gate.

### Lightweight scorers

| Scorer | Behaviour |
| --- | --- |
| `equals` | Exact match |
| `contains` | Case-sensitive substring |
| `icontains` | Case-insensitive substring |
| `levenshtein` | Similarity from 0 to 1 |
| `matches` | Regex match |
| `numeric_close` | 1% relative tolerance |

See [lightweight scorer semantics](scorers.md#lightweight-eval-scorers).

---

## Suites, samples and traces

### `TestSuite(name, version, cases, description="", metadata={})`

A named, versioned list of `TestCase`s.

### `TestCase`

| Field | Description |
| --- | --- |
| `id`, `name` | Required identity |
| `input` | Input passed to a live target |
| `expected_output` | Exact expected output (also the default reference for some scorers) |
| `expected_contains` | Substrings the output must contain |
| `output_json_schema` | Draft 2020-12 JSON Schema the output must satisfy |
| `required_output_fields` | Nested fields the JSON output must contain |
| `required_tools`, `forbidden_tools` | Tools that must or must not appear in the trace |
| `required_tool_arguments`, `expected_tool_arguments` | Required argument keys, or exact argument values, per tool |
| `required_tool_order` | Tools that must appear in this order |
| `max_latency_ms`, `max_cost_usd`, `max_turns` | Per-case budgets (`max_turns` needs turn metadata in the trace) |
| `evaluators` | Named scorers to run, as `EvaluatorConfig`s |
| `tags`, `metadata` | Free-form labels; tags drive breakdowns and gate slices |

See [all TestCase fields and implicit checks](core-concepts.md#testsuite-and-testcase).

### `EvaluatorConfig(name, threshold=1.0, required=True, config={})`

Selects a registered evaluator by name. `config` holds scorer options, such as `{"abs_tol": 0.01}` for `numeric_diff` or `{"pattern": "..."}` for `regex_match`. A failed optional (`required=False`) score does not fail its case.

### `EvaluationSample(case_id, output, trace)`

One recorded observation, matched to a case by `case_id`.

### `EvalTrace(trace_id="", spans=[], total_latency_ms=0.0, estimated_cost_usd=None, cost_source=None, metadata={})`

The normalized trace. `cost_source` is `"measured"` (billed or provider-reported) or `"estimated"` (computed from tokens and a price table). Leave cost as `None` when it is unknown.

### `EvalSpan(tool_name=None, attributes={})`

One step in the trace. Spans with a `tool_name` are tool calls; `attributes` carry tool arguments.

### `load_suite(path)`

Loads a `TestSuite` from a JSON or YAML file.

### `load_samples(path, *, trace_adapter=None)`

Loads `EvaluationSample`s from a JSON array, a `{"samples": [...]}` envelope or JSONL. `trace_adapter` is a trusted callable that converts each raw trace into the `EvalTrace` shape before validation.

```python
from pathlib import Path
from agentic_evals import load_samples, load_suite

suite = load_suite(Path("suite.yaml"))
samples = load_samples(Path("samples.jsonl"))
```

See [trace normalization](guide/existing-traces.md) and [custom data](guide/custom-data.md).

---

## Evaluation

### `evaluate_suite(suite, samples, *, registry=None)`

Scores recorded samples and returns an `EvaluationReport` with per-case scores, summary metrics, pass rates, cost, latency and [breakdowns by metric and tag](core-concepts.md#scores-and-reports). Without `registry`, only the case expectations run, and a case that names an evaluator raises `ValueError`.

```python
from agentic_evals import default_registry, evaluate_suite

report = evaluate_suite(suite, samples, registry=default_registry())
print(report.summary.pass_rate)
```

### `aevaluate_suite(suite, samples, *, registry=None, max_concurrency=8)`

The async version. Awaits `async def` evaluators and runs plain ones in a worker thread. Call it inside a running event loop instead of `evaluate_suite`.

```python
import asyncio
from agentic_evals import aevaluate_suite

report = asyncio.run(aevaluate_suite(suite, samples, registry=registry, max_concurrency=4))
```

### `EvaluationReport`

| Field | Description |
| --- | --- |
| `schema_version` | Native report contract version (`"1.0"`) |
| `suite_name`, `suite_version`, `created_at` | Identity |
| `summary` | `EvaluationSummary` |
| `cases` | One `CaseEvaluation` per test case |

### `EvaluationSummary`

`total_cases`, `passed_cases`, `failed_cases`, `pass_rate`, `average_score`, `average_latency_ms`, `total_cost_usd` (`None` unless every case has a known cost), `priced_cases`, `cost_sources`, `metrics` (`MetricSummary` per `Score.metric`), `tags` (`TagSummary` per tag), `judge` (`JudgeSummary`) and `live` (`LiveSummary`).

### `CaseEvaluation`

`case_id`, `case_name`, `passed`, `scores`, `output`, `trace_id`, `latency_ms`, `cost_usd`, `cost_source`, `sample_available` (False when no sample was supplied), `target_status`, `target_attempts`, `target_error`, `tags` and `metadata`.

### `Score`

```python
class Score(BaseModel):
    name: str
    metric: str = ""
    value: float                  # 0.0 – 1.0
    passed: bool
    required: bool = True
    skipped: bool = False
    explanation: str
    evaluator_type: str = "deterministic"
    evaluator: str = ""
    evaluator_version: str | None = None
    metadata: dict = {}
```

### `MetricSummary`, `TagSummary`, `JudgeSummary`, `LiveSummary`

- `MetricSummary`: `total`, `passed`, `failed`, `skipped`, `pass_rate`, `average_score`.
- `TagSummary`: `total_cases`, `passed_cases`, `failed_cases`, `pass_rate`, `average_score`.
- `JudgeSummary`: judge score counts, `unavailable_scores` and `unavailable_cases`, retries, tokens, latency, `total_cost_usd`, and agreement (`min_agreement`, `average_agreement`, `case_agreement`).
- `LiveSummary`: `total_cases`, `ok_cases`, `retried_cases`, `timed_out_cases`, `error_cases` and the matching case IDs.

---

## Scorers Library

`default_registry()` returns a fresh `EvaluatorRegistry` with 17 built-in scorers: the twelve deterministic ones, the four trajectory ones and `containment`. `builtin_scorer_names()` lists them. Each scorer is also exported as a function taking an `EvaluationContext` and returning a `Score`. See the [complete scorer and rubric catalog](scorers.md) for every configuration option.

### Text Scorers (No LLM)

| Scorer | Checks | Key `config` options |
| --- | --- | --- |
| `exact_match` | Output equals `expected_output` | — |
| `contains_all` / `contains_any` | All or any of `expected_contains` appear | — |
| `starts_with` / `ends_with` | Output prefix or suffix | — |
| `regex_match` | Output matches a pattern | `pattern`, `case_insensitive`, `full_match` |
| `levenshtein_similarity` | Edit-distance similarity to the reference | `reference` |
| `embedding_similarity` | Cosine similarity of embeddings | `embed_fn` (yours), `reference` |
| `valid_json` | Output parses as JSON | — |
| `json_diff` | JSON output equals the expected JSON; names the first differing path | — |
| `numeric_range` | Number within bounds | `min`, `max` |
| `numeric_diff` | Number within tolerance of the expected value | `rel_tol`, `abs_tol` |

```python
from agentic_evals import EvaluatorConfig, TestCase

TestCase(
    id="total",
    name="Order total",
    expected_output="42",
    evaluators=[EvaluatorConfig(name="numeric_diff", config={"abs_tol": 0.01})],
)
```

### Trajectory Scorers (Trace-Aware)

| Scorer | Checks | Key `config` options |
| --- | --- | --- |
| `tool_call_precision` | Share of tool calls that were allowed | `allowed_tools` (defaults to `required_tools`) |
| `tool_call_recall` | Share of `required_tools` that were called | — |
| `no_redundant_tool_calls` | No repeated tool call with the same attributes | — |
| `trajectory_efficiency` | Latency or cost relative to a baseline | `baseline_latency_ms`, `baseline_cost_usd` |

They grade recorded spans, not final text. A missing trace cannot establish tool behaviour.

### Rubric Scorers (LLM-Graded)

Ten `RubricTemplate` constants: `FACTUALITY`, `CLOSED_QA`, `SUMMARY_QUALITY`, `TRANSLATION`, `SQL_CORRECTNESS`, `SECURITY`, `MODERATION`, `PII_LEAKAGE`, `BATTLE` and `POSSIBLE`. They are not in `default_registry()`, because they need your completion callback.

### `LLMRubricEvaluator(name, template, complete_fn, *, version=None, retry=None, samples=1)`

Formats the template, calls `complete_fn(prompt)`, and parses the verdict into a score. `complete_fn` may be sync or async and returns a `str` or a `JudgeResponse`.

```python
from agentic_evals import LLMRubricEvaluator, FACTUALITY, default_registry

registry = default_registry()
registry.register(
    LLMRubricEvaluator(
        "factuality_check",
        FACTUALITY,
        complete_fn=your_model_call,  # Your function to call an LLM
    )
)
```

For reference-based rubrics, put the reference in `EvaluatorConfig.config["reference"]`.

### `make_rubric(name, criteria, *, levels=None, with_reference=False)`

When no built-in template fits, describe the criterion in plain language. `make_rubric()` builds the prompt, the verdict letters and their scores:

```python
from agentic_evals import LLMRubricEvaluator, make_rubric

concise = make_rubric("concise", "The answer is at most two sentences and has no preamble.")

tone = make_rubric(
    "tone",
    "The reply is courteous and does not blame the reader.",
    levels=[  # best first; scores from 0 to 1
        ("Courteous throughout.", 1.0),
        ("Neutral: neither courteous nor rude.", 0.5),
        ("Rude, dismissive, or blames the reader.", 0.0),
    ],
)

registry.register(LLMRubricEvaluator("concise", concise, complete_fn=your_model_call))
registry.register(LLMRubricEvaluator("tone", tone, complete_fn=your_model_call))
```

The default scale is pass/fail. Pass `with_reference=True` to show the judge a reference next to the output.

### `RubricTemplate(name, prompt_template, verdict_scores)`

The template type returned by `make_rubric()`; `verdict_scores` maps each verdict letter to a score.

---

## Custom evaluators and registries

### `EvaluationContext(case, sample, config)`

What every evaluator receives: the `TestCase`, the `EvaluationSample` and the `EvaluatorConfig`.

### `Evaluator` and `AsyncEvaluator`

Protocols. An evaluator has a `name` and `evaluate(context) -> list[Score]`; an async evaluator also has `async aevaluate(context)`. The async runners await `aevaluate` when it exists.

### `CallableEvaluator(name, function, *, evaluator_type="custom", version=None)`

Wraps any trusted function that takes an `EvaluationContext` and returns a `Score` or a list of scores. The function may be `async def`. `version` is stamped onto each score as `Score.evaluator_version`.

```python
from agentic_evals import CallableEvaluator, Score, default_registry

def polite(context):
    ok = "please" in str(context.sample.output).lower()
    return Score(name="polite", value=float(ok), passed=ok, explanation="checks for 'please'")

registry = default_registry()
registry.register(CallableEvaluator("polite", polite, version="1"))
```

### `BusinessRuleEvaluator(name, rule, *, version=None)`

A `CallableEvaluator` for organization-specific pass/fail rules, labelled as a business rule in reports.

### `LLMJudgeEvaluator(name, judge, *, version=None, retry=None, samples=1, evaluator_type="llm_judge")`

A `CallableEvaluator` for your own judge function, with judge retries, unavailable scores, repeated sampling and usage accounting. `LLMRubricEvaluator` builds on it.

### `EvaluatorRegistry()`

Holds trusted evaluators by name. Suite files refer to evaluators by name; they never import code.

| Method | Description |
| --- | --- |
| `register(evaluator, *, replace=False)` | Add an evaluator; raises `ValueError` on a duplicate name unless `replace=True` |
| `get(name)` | Look up an evaluator; raises `ValueError` if missing |
| `names()` | Sorted registered names |

### `default_registry()` and `builtin_scorer_names()`

A fresh registry with all 17 built-ins, and their sorted names. `BUILTIN_EVALUATOR` is the `evaluator_type` label built-in scorers carry; `JUDGE_EVALUATOR_TYPES` is the set of types counted as judges.

See [custom evaluators and packs](advanced.md) and the [custom scorer tutorial](guide/custom-scorers.md).

---

## Judge reliability

### `RetryPolicy(max_attempts=1, backoff_seconds=0.0, backoff_multiplier=2.0, max_backoff_seconds=30.0, retry_on=(Exception,))`

Bounds retries for judges and live targets. Backoff grows by `backoff_multiplier` up to `max_backoff_seconds`.

### `JudgeResponse(text, input_tokens=None, output_tokens=None, cost_usd=None, cost_source=None, model=None, provider=None)`

Return this from a judge's completion callback, instead of a plain string, to record usage. Unknown values stay `None`.

```python
from agentic_evals import FACTUALITY, JudgeResponse, LLMRubricEvaluator, RetryPolicy

def complete_fn(prompt):
    reply = call_your_model(prompt)
    return JudgeResponse(text=reply.text, cost_usd=reply.cost, cost_source="measured")

judge = LLMRubricEvaluator(
    "factuality",
    FACTUALITY,
    complete_fn,
    retry=RetryPolicy(max_attempts=3, backoff_seconds=0.5),
    samples=3,  # judge three times, report agreement
)
```

A judge that still fails after its retries, or whose verdict cannot be parsed, yields an unavailable score that never passes. See [judge reliability](judge-reliability.md).

---

## Release Gates

Turn an evaluation report into a pass/fail CI decision.

### `evaluate_gate(report, config)`

```python
def evaluate_gate(report: EvaluationReport, config: GateConfig) -> GateDecision
```

```python
from agentic_evals import evaluate_gate, GateConfig

decision = evaluate_gate(
    report,
    GateConfig(
        min_pass_rate=0.95,  # At least 95% of cases pass
        max_average_latency_ms=1500,  # Avg latency under 1.5s
        max_total_cost_usd=0.25,  # Total cost under $0.25
    ),
)

if not decision.passed:
    print(f"Release blocked: {decision.reasons}")
    exit(1)
```

### `GateConfig`

The default is strict: every case must pass and no judge may be unavailable.

| Field | Default | Fails when |
| --- | --- | --- |
| `min_pass_rate` | `1.0` | Suite pass rate is lower |
| `min_average_score` | `None` | Average score is lower |
| `max_failed_cases` | `None` | More cases failed |
| `min_tag_pass_rate` | `{}` | A tag's pass rate is lower, or the tag is missing |
| `min_metric_pass_rate` | `{}` | A metric's pass rate is lower, or the metric is missing |
| `max_average_latency_ms` | `None` | Average latency is higher |
| `max_total_cost_usd` | `None` | Total cost is higher, or unknown |
| `max_judge_unavailable_scores` | `0` | More judge scores were unavailable |
| `max_judge_cost_usd` | `None` | Judge cost is higher, or any judge score has no cost |
| `min_judge_agreement` | `None` | A case judged with `samples=N` agreed less |
| `max_timed_out_cases` | `None` | More live cases timed out |
| `max_target_error_cases` | `None` | More live cases hit a target error |

A gate can hold one slice of the report to a stricter bar than the suite as a whole, keyed by case tag or by `Score.metric`:

```python
GateConfig(
    min_pass_rate=0.95,
    min_tag_pass_rate={"safety": 1.0},  # Every safety-tagged case passes
    min_metric_pass_rate={"forbidden_tool": 1.0},  # No forbidden tool call, anywhere
)
```

A tag or metric named in the config but missing from the report fails the gate, so a renamed tag cannot quietly switch a check off.

### `GateDecision(passed, reasons, observed)`

`passed` is the verdict, `reasons` lists every failed check and `observed` holds the measured values. See [CI policy examples](guide/release-gates.md).

---

## Live Targets

Run a suite against a real system (trusted code or HTTP endpoint) instead of pre-recorded samples.

### `run_live_suite(suite, target, *, registry=None, trace_adapter=None, max_workers=1, retry=None)`

```python
def run_live_suite(
    suite: TestSuite,
    target: LiveTarget,
    *,
    registry: EvaluatorRegistry | None = None,
    trace_adapter: Callable[[Any], Any] | None = None,
    max_workers: int = 1,
    retry: RetryPolicy | None = None,
) -> EvaluationReport
```

### `PythonTarget(callable_path, timeout_seconds=30.0)`

Executes local code:

```python
from agentic_evals import PythonTarget, run_live_suite

report = run_live_suite(
    suite,
    PythonTarget(callable_path="my_module:my_agent"),
    # my_module.py must have a my_agent(input, case=None) function
)
```

### `HTTPTarget(url, method="POST", headers={}, timeout_seconds=30.0)`

Calls a remote endpoint:

```python
from agentic_evals import HTTPTarget, run_live_suite

report = run_live_suite(
    suite,
    HTTPTarget(
        url="http://localhost:8000/evaluate",
        method="POST",
        headers={"Authorization": "Bearer token"},
    ),
)
```

`LiveTarget(kind, timeout_seconds=30.0)` is their common base type.

### `arun_live_suite(suite, target, *, registry=None, trace_adapter=None, max_concurrency=1, retry=None)`

A call that raises or times out is retried under `retry`; a case whose calls all fail is reported with `target_status` `"timed_out"` or `"error"` instead of aborting the run. `arun_live_suite` awaits `async def` targets and cancels them at an explicit `timeout_seconds`.

```python
import asyncio
from agentic_evals import PythonTarget, RetryPolicy, arun_live_suite

report = asyncio.run(
    arun_live_suite(
        suite,
        PythonTarget(callable_path="my_module:my_async_agent", timeout_seconds=20),
        retry=RetryPolicy(max_attempts=3, backoff_seconds=1),
        max_concurrency=4,
    )
)
print(report.summary.live.timed_out_case_ids)
```

See [live target retries and timeouts](judge-reliability.md#live-target-retries-and-timeouts) and the [live tutorial](guide/live.md).

---

## Eval packs

### `EvalPack(name, suite, description="", required_scorers=[])`

A shareable bundle of a `TestSuite` and the scorer names it needs. `pack.to_suite()` returns the suite.

### `list_builtin_packs()`

Returns the built-in pack names: `adversarial-containment`, `factual-qa`, `json-output-contract` and `tool-use-correctness`.

### `load_builtin_pack(name, *, registry=None)` and `load_pack(path, *, registry=None)`

Load a built-in pack by name, or your own YAML/JSON pack file. With `registry`, every required scorer is checked up front.

```python
from agentic_evals import default_registry, evaluate_suite, load_builtin_pack

registry = default_registry()
pack = load_builtin_pack("tool-use-correctness", registry=registry)
report = evaluate_suite(pack.to_suite(), samples, registry=registry)
```

`factual-qa` needs a registered `LLMRubricEvaluator`; `adversarial-containment` needs a `ContainmentEvaluator` with a trusted verifier. See [eval packs](advanced.md#eval-packs).

---

## Containment scoring

### `ContainmentEvaluator(*, verifier=None)`

Scores authenticated containment evidence at `sample.trace.metadata["containment"]` (`records` and `manifest`). It fails closed: without a verifier, every containment score fails. The default registry registers it without a verifier.

### `ContainmentVerifier`

The trusted callback type: `(records, manifest, stream_id) -> dict` in the AgenticLens verification result shape. Keys never travel in samples or reports.

### `lens_verifier(trusted_keys)`

Builds a `ContainmentVerifier` from AgenticLens (`pip install "agentic-evals[integrity]"`). It copies the host's trust store when it is created.

```python
from agentic_evals import ContainmentEvaluator, default_registry, lens_verifier

registry = default_registry()
registry.register(ContainmentEvaluator(verifier=lens_verifier(host_trusted_keys)), replace=True)
```

### `ContainmentExpectation`

The trusted scenario in `EvaluatorConfig.config`: `scenario` (`stop`, `revoke`, `denied_tool`, `authority`, `injected` or `fail_closed`), `subject`, `task_id`, `stream_id`, `policy_version`, `configuration_version`, `attempted_call_ids`, and `forbidden_tools` (denial scenarios) or `acknowledgement_id` (stop and revoke), plus an optional `max_acknowledgement_latency_ms`.

See [authenticated containment scoring](containment.md).

---

## AIOS Evidence Export

Export a report as AI Operations Specification `0.4-draft` evaluation evidence and attach it to an existing Run artifact.

### `to_aios_evidence(report, *, run_id, targets=None, default_target=None, gate=None, allow_unmapped=False, id_prefix=None, occurred_at=None)`

```python
def to_aios_evidence(
    report: EvaluationReport | dict,
    *,
    run_id: str,
    targets: dict[str, str | dict | list] | None = None,
    default_target: str | dict | list | None = None,
    gate: GateDecision | dict | None = None,
    allow_unmapped: bool = False,
    id_prefix: str | None = None,
    occurred_at: datetime | None = None,
) -> AIOSEvidenceExport
```

### `attach_aios_evidence(run, export)`

```python
def attach_aios_evidence(run: dict, export: AIOSEvidenceExport | list[AIOSEvidenceExport]) -> dict
```

```python
from agentic_evals import attach_aios_evidence, to_aios_evidence

export = to_aios_evidence(
    report, run_id=run["id"], targets={"answer": "step-answer"}, gate=decision
)
merged = attach_aios_evidence(run, export)
print(export.unmapped_cases, export.skipped_scores, export.unavailable_scores)
```

A string target is a Step ID; a dict is an AIOS reference (`id`, `type`, optional `external`).

### `AIOSEvidenceExport` and `AIOSExportError`

`AIOSEvidenceExport` holds the evidence, relationships and events, plus `unmapped_cases`, `unobserved_cases`, `exported_cases`, `skipped_scores` and `unavailable_scores`. Missing mappings, unknown case IDs and unresolved targets raise `AIOSExportError` (a `ValueError`). See [the AIOS evidence guide](aios-evidence.md).

---

## Native schemas

### `report_schema()` and `gate_decision_schema()`

Return the JSON Schemas (as dicts) for the native report and gate decision, contract version 1.0. They ship inside the package and need no network.

```python
import jsonschema
from agentic_evals import report_schema

jsonschema.validate(report.model_dump(mode="json"), report_schema())
```

Schema validity is separate from passing a gate. See [the native report contract](report-contract.md).

---

## CLI

The `agentic-evals` command has seven commands: `run`, `evaluate`, `live`, `gate`, `pack list`, `pack show` and `aios export`. See the [CLI reference](cli.md) for flags, output formats and exit codes.

---

## API readiness and support

See [the public API candidate](public-api.md), [support and compatibility matrix](support-policy.md), and [executable examples](../examples/README.md).

## Capability and contract lookup

The [Developer Guide (simple)](developer-guide.md#capability-index) has short workflows for every capability category. The [AI Readable Documentation](ai-reference-index.md) indexes the full reference, which includes the detailed task guides, scorer catalog, public/support policy contents, statically extracted declarations from every package module and both native schemas.

Package, report/gate and AIOS versions remain independent. See the [coordinated readiness notes](coordinated-v1-readiness.md).
