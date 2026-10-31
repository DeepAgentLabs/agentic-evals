# agentic-evals

[![PyPI](https://img.shields.io/pypi/v/agentic-evals)](https://pypi.org/project/agentic-evals/)
[![Python versions](https://img.shields.io/pypi/pyversions/agentic-evals)](https://pypi.org/project/agentic-evals/)
[![CI](https://github.com/DeepAgentLabs/agentic-evals/actions/workflows/ci.yml/badge.svg)](https://github.com/DeepAgentLabs/agentic-evals/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**A standalone, framework-agnostic evaluation and scoring engine for LLM and
agent outputs.**

Extracted from [AgenticLens](https://github.com/DeepAgentLabs/agenticlens)'s
proven evaluation module — the same engine, usable on its own. It scores
whatever trace-shaped data you give it (see `EvalTrace`/`EvalSpan` below);
it has no dependency on any specific tracing/observability tool, and no
dependency on AgenticLens itself.

## Status

**Published on PyPI.** The engine (deterministic checks, LLM-as-judge and
custom evaluators, a release gate, live Python/HTTP targets, the `Eval()`
quickstart API, the `agentic-evals` CLI and AIOS evidence export) is real, tested code — see the
[changelog](CHANGELOG.md) for what shipped in each release. The API may
still move between minor versions ahead of a 1.0; pin a version in
production and read the changelog before upgrading.

## Use cases

[Step-by-step use cases](https://deepagentlabs.io/agentic-evals/usecases/), each
verified against 0.9.0 with no model or API key: block an unsafe release with a
tag floor, catch a right reply reached the wrong way, and gate on whether the LLM
judge itself held up. Their files are in [examples/usecases](examples/usecases/).

## AIOS evaluation evidence (0.10.0)

Attach evaluation results to the AI Operations Specification Run they judged,
for example a Run exported by Agentic Chaos or AgenticLens:

```python
from agentic_evals import attach_aios_evidence, to_aios_evidence

export = to_aios_evidence(
    report,
    run_id=run["id"],
    targets={"grounded-answer": "step-answer", "refund-tool": "step-refund"},
    gate=decision,  # optional: exported as a release-readiness evaluation of the Run
)
merged = attach_aios_evidence(run, export)
```

```bash
agentic-evals aios export report.json --run run.json --targets targets.yaml \
  --gate gate-decision.json --out run-with-evaluations.json
```

- Every score, case verdict and gate decision becomes an AIOS `0.4-draft`
  `evaluation` with its criterion, method (evaluator and version), result and
  score, plus an `evaluates` link to the Step or object you mapped it to.
- Nothing is guessed: no mapping, an unmapped case or a target missing from
  the Run raises `AIOSExportError` instead of producing orphaned evidence.
- A skipped score is exported as `skipped` and an undelivered judgment as
  `unavailable`, never as a pass.

The merged Run validates with MCP's `spec.validate_artifact`
(`conformance.aligned = true`). See the [AIOS evidence guide](docs/aios-evidence.md)
and the [runnable example](examples/aios/). The native report schema 1.0 is
unchanged.

## Judge reliability and live resilience (0.9.0)

LLM-judged and live evaluations now say what they cost and whether they
actually happened:

```python
from agentic_evals import FACTUALITY, JudgeResponse, LLMRubricEvaluator, RetryPolicy

judge = LLMRubricEvaluator(
    "factuality",
    FACTUALITY,
    complete_fn,  # may return JudgeResponse(text=..., cost_usd=...)
    retry=RetryPolicy(max_attempts=3, backoff_seconds=0.5),
    samples=3,  # judge three times, report agreement
)
```

- Judge cost, tokens and latency are recorded on each judge `Score` under the
  `judge_*` keys AgenticLens already reads, and totalled in `summary.judge`.
- A judge that fails after its retries yields an explicit **unavailable** score
  that never passes; the default gate fails and names the cases.
- `samples=N` reports per-case agreement; `GateConfig(min_judge_agreement=...)`
  catches a flaky judge.
- Live targets retry with backoff and report `timed_out` separately from failed
  (`CaseEvaluation.target_status`, `summary.live`, JUnit `<error>`).
- `aevaluate_suite` / `arun_live_suite` await `async def` evaluators and targets.

See the [judge reliability guide](docs/judge-reliability.md) and the offline
[judge](examples/judge_reliability.py) and [async target](examples/async_live_target.py)
examples. Report schema 1.0 gains optional fields only.

## Declarative CLI (0.8.0)

Run saved suites and samples, then apply an explicit release gate:

```bash
agentic-evals evaluate examples/ci/suite.yaml examples/ci/samples.jsonl --out report.json
agentic-evals gate report.json --config examples/ci/gate.yaml
agentic-evals pack list
agentic-evals live examples/ci/suite.yaml --target my_agent:run --max-workers 4 --out live.json
```

`evaluate` and `live` exit 0 when a report is produced, including failing cases.
`gate` exits 0 for pass, 1 for a failed gate, and 2 for input or usage errors.
Use `--format json|junit|markdown` for native evidence, JUnit or job summaries.
See the [CLI guide](docs/cli.md), [CI workflow](examples/ci/evaluate.yml), and
[voice-agent CLI example](voice-agent-evals/README.md#declarative-cli-080).
The native report and gate contracts remain compatible with 0.7.2 consumers.

## Why a separate package

AgenticLens's evaluation module was never actually AgenticLens-specific —
scoring an LLM/agent output against expectations doesn't need AgenticLens's
full trace schema, CLI, or dashboards. Pulling it out means:

- `agentic-sidecar`, `agentic-chaos`, or any other project can score outputs
  without depending on all of AgenticLens.
- Anyone with *any* trace-shaped data — not just AgenticLens users — can use
  it; scoring a string doesn't need to care what produced it.

## Install

```bash
pip install agentic-evals
```

## Quickstart in under a minute

The fast path in -- no `TestSuite`, no `TestCase`, no trace object. Write a
file, run it:

```python
# capitals_eval.py
from agentic_evals import Eval, equals


def my_agent(country: str) -> str:
    return {"France": "Paris", "Japan": "Tokyo"}[country]


Eval(
    "capitals",
    data=[
        {"input": "France", "expected": "Paris"},
        {"input": "Japan", "expected": "Tokyo"},
    ],
    task=my_agent,
    scores=[equals],
)
```

```bash
$ python capitals_eval.py
agentic-evals :: capitals
--------------------------
  [PASS] France  equals=1.00
  [PASS] Japan  equals=1.00

  equals                       avg 1.000

  2/2 passed  (100.0%)  in 0ms
```

Or let the CLI find every eval file in a directory and roll them into one
CI-friendly exit code -- `0` if every case in every file passed, `1`
otherwise, no config file required:

```bash
pip install agentic-evals
agentic-evals run                 # discovers *_eval.py / eval_*.py / *.eval.py
```

A scorer is any function that returns a `float`/`bool` (0-1), a `Score`, or
`{"score": ..., "name": ...}` -- called with whichever of `input`, `output`,
`expected` it declares as parameters:

```python
def contains_the_total(output: str, expected: str) -> bool:
    return expected in output
```

Six ready-made scorers ship for this API: `equals`, `contains`,
`icontains`, `levenshtein`, `matches` (regex), `numeric_close` (tolerance-
based). `Eval()` also accepts `threshold=` (default
`1.0`) -- a case passes when every one of its scores clears it -- and
`data=` may be a zero-argument callable for data you'd rather build lazily.

This is deliberately the *simple* surface. Everything below -- trace-aware
scorers, JSON Schema/tool-call expectations, eval packs, cost/latency
release gates -- is the same engine underneath, for when a plain
`input`/`output`/`expected` row isn't enough.

## The declarative API

For trace-aware expectations (tool calls, latency/cost thresholds, JSON
Schema) and CI release gates, use `TestSuite`/`TestCase`/`evaluate_suite`
directly -- the engine `Eval()` above is a thin, opinionated front end for.

### Core concepts

- **`EvalTrace`/`EvalSpan`** — the minimal trace shape the engine inspects:
  a trace id, spans (each optionally naming a `tool_name` and carrying
  arbitrary `attributes`), total latency, estimated cost, and metadata.
  Deliberately not tied to any specific instrumentation format — build one
  from whatever you already have.
- **`Score`** — a single named judgment (0-1 value, pass/fail, explanation),
  with a stable `metric` key that reports group by. `Score.skip(...)` records
  a check that did not apply to a case.
- **`Evaluator`** — anything with a `.name` and an `.evaluate(context) ->
  list[Score]`. `CallableEvaluator` adapts a plain Python function;
  `LLMJudgeEvaluator` and `BusinessRuleEvaluator` are named convenience
  subclasses for readability/reporting.
- **`TestCase`/`TestSuite`** — declarative expectations (exact match,
  substring, JSON Schema, required fields, required/forbidden tool calls,
  tool arguments and their values, tool call order, latency/cost/turn-count
  thresholds, or a named custom evaluator) plus the cases that make up a
  suite.
- **`evaluate_suite`** — runs a suite against supplied `EvaluationSample`s
  and returns an `EvaluationReport` (per-case scores plus a pass-rate/cost/
  latency summary, broken down by metric and by tag).
- **`GateConfig`/`evaluate_gate`** — turn an `EvaluationReport` into a
  pass/fail release decision on configurable thresholds, for the whole
  suite or for a single tag or metric.

### TestSuite quickstart

```python
from agentic_evals import (
    EvalSpan,
    EvalTrace,
    EvaluationSample,
    TestCase,
    TestSuite,
    evaluate_suite,
)

suite = TestSuite(
    name="support-answers",
    version="1",
    cases=[
        TestCase(
            id="case-1",
            name="Answer contains the right total",
            expected_contains=["42"],
            required_tools=["calculator"],
            max_latency_ms=2000,
        )
    ],
)

sample = EvaluationSample(
    case_id="case-1",
    output="The combined total is 42.",
    trace=EvalTrace(
        trace_id="trace-1",
        total_latency_ms=350,
        spans=[EvalSpan(tool_name="calculator")],
    ),
)

report = evaluate_suite(suite, [sample])
print(report.summary.pass_rate)  # 1.0
```

### Breakdowns by metric and tag

An overall pass rate hides where the failures are. Tag your cases, and the
report's summary breaks results down two ways:

```python
suite = TestSuite(
    name="support-answers",
    version="1",
    cases=[
        TestCase(
            id="r1",
            name="Refund status",
            tags=["refunds"],
            expected_contains=["refund"],
            required_tools=["lookup_order"],
        ),
        TestCase(id="t1", name="Order tracking", tags=["tracking"], expected_contains=["shipped"]),
    ],
)
report = evaluate_suite(suite, samples)

for tag, stats in report.summary.tags.items():
    print(f"{tag}: {stats.passed_cases}/{stats.total_cases} cases passed")

for metric, stats in report.summary.metrics.items():
    print(f"{metric}: {stats.passed}/{stats.total} checks passed")
```

- **`summary.tags`** — one `TagSummary` per tag: case counts, pass rate and
  average score for the cases carrying that tag.
- **`summary.metrics`** — one `MetricSummary` per metric: how many checks
  passed, failed or were skipped, plus pass rate and average score. Checks
  such as `contains:refund` and `contains:shipped` roll up under the single
  metric `contains`; the detailed name stays on `Score.name`.
- Each `CaseEvaluation` carries its case's `tags` and `metadata`, so a
  report can be filtered or regrouped without the original suite.

A custom evaluator can mark a check as not applicable instead of passing or
failing it. A skipped score never fails the case and stays out of averages
and pass rates; it is counted separately in `MetricSummary.skipped`:

```python
def cites_order_id(context: EvaluationContext) -> Score:
    order_id = context.case.metadata.get("order_id")
    if order_id is None:
        return Score.skip("cites_order_id", "Case has no order id to cite.")
    cited = order_id in context.sample.output
    return Score(
        name="cites_order_id",
        value=float(cited),
        passed=cited,
        explanation=f"Order id {order_id} cited: {cited}.",
    )
```

### Tool call expectations

Beyond which tools were called, a case can state what they were called
with and in what order. Tool arguments are read from each span's
`attributes["tool_args"]`:

```python
TestCase(
    id="publish-draft",
    name="Saves the draft before publishing it",
    required_tools=["save_draft", "publish"],
    forbidden_tools=["delete_document"],
    required_tool_arguments={"publish": ["document_id"]},  # keys present
    expected_tool_arguments={"publish": {"visibility": "internal"}},  # exact values
    required_tool_order=["save_draft", "publish"],  # first calls in order
)
```

- **`expected_tool_arguments`** passes when at least one call to the tool
  carries every listed argument with an equal value. Values are compared
  as given, without type coercion (`5` is not `"5"`).
- **`required_tool_order`** passes when each listed tool is first called
  before the next one in the list. Calls to other tools in between are
  fine; a listed tool that is never called fails the check.

## LLM-as-judge

```python
from agentic_evals import (
    EvaluationContext,
    EvaluatorConfig,
    EvaluatorRegistry,
    LLMJudgeEvaluator,
    Score,
    TestCase,
)


def judge(context: EvaluationContext) -> Score:
    # Call whatever model/provider you like here.
    correct = "42" in context.sample.output
    return Score(
        name="answer_quality",
        value=0.95 if correct else 0.1,
        passed=correct,
        explanation="Judged against the rubric in context.config.config.",
    )


registry = EvaluatorRegistry()
registry.register(LLMJudgeEvaluator("answer_quality_judge", judge, version="quality-prompt-v2"))

case = TestCase(
    id="case-1",
    name="Answer quality",
    evaluators=[EvaluatorConfig(name="answer_quality_judge", threshold=0.8)],
)
```

### Which evaluator produced each score

Every `Score` in a report names what produced it. `evaluate_suite` stamps
`Score.evaluator` and `Score.evaluator_version`:

| Score source | `evaluator` | `evaluator_version` |
| --- | --- | --- |
| Built-in checks (exact match, contains, tools, thresholds) | `"agentic_evals.builtin"` (`BUILTIN_EVALUATOR`) | this package's `__version__` |
| A registered evaluator | its registry name | its `version` attribute (`version=` on `CallableEvaluator`, `LLMJudgeEvaluator`, `BusinessRuleEvaluator`, `LLMRubricEvaluator`) |

A `None` version means the evaluator did not declare one. Version a judge
whenever its prompt or model changes, so two reports can be compared only
when they were graded by the same judge.

### Judge cost, retries and agreement

`LLMJudgeEvaluator` and `LLMRubricEvaluator` take `retry=RetryPolicy(...)` and
`samples=N`. Every judge score records `judge_status` (`ok` or
`unavailable`), `judge_attempts` and `judge_latency_ms`, plus any usage the
judge reported (`judge_cost_usd`, `judge_cost_source`, tokens, model,
provider). A rubric `complete_fn` reports usage by returning a
`JudgeResponse`. A judge that raises, or a rubric completion that cannot be parsed,
no longer aborts the suite. After the last attempt it becomes an unavailable score:
value 0 and never passing, with the error recorded.
`summary.judge` totals judge cost apart from the agent's cost, and lists
unavailable cases and per-case agreement. See the
[judge reliability guide](docs/judge-reliability.md).

## Release gates

```python
from agentic_evals import GateConfig, evaluate_gate

decision = evaluate_gate(
    report,
    GateConfig(min_pass_rate=0.95, max_average_latency_ms=1500, max_total_cost_usd=0.25),
)
if not decision.passed:
    raise SystemExit(f"Release gate failed: {decision.reasons}")
```

A gate can hold one slice of the report to a stricter bar than the suite
as a whole, keyed by case tag or by `Score.metric`:

```python
GateConfig(
    min_pass_rate=0.95,
    min_tag_pass_rate={"safety": 1.0},  # every safety-tagged case must pass
    min_metric_pass_rate={"forbidden_tool": 1.0},  # no forbidden tool call, anywhere
)
```

A tag or metric named in the config but missing from the report fails the
gate, so a renamed tag cannot quietly switch a check off.

Judge and live-target checks (0.9.0):

```python
GateConfig(
    max_judge_unavailable_scores=0,  # the default: an unavailable judge fails the gate
    min_judge_agreement=0.8,  # every case judged with samples=N
    max_judge_cost_usd=2.50,  # fails when any judge score has no cost
    max_timed_out_cases=0,  # live runs: timeouts, apart from wrong answers
    max_target_error_cases=0,
)
```

Never fabricates a value it can't back up: `total_cost_usd` on a summary or
gate decision stays `None` unless every case in scope has a known cost —
an incomplete cost picture is reported as unavailable, not `$0.00`.

Cost provenance travels with the numbers. Set `EvalTrace.cost_source` to
`"measured"` (billed or provider-reported) or `"estimated"` (computed from
token counts and a price table); each `CaseEvaluation.cost_source` carries
it, and the summary reports `priced_cases` and `cost_sources` (priced cases
per provenance, with `"unspecified"` for traces that did not say). A case
with no sample at all has `sample_available=False`, so its empty `trace_id`
reads as "no trace exists" rather than "trace ID lost".

## Built-in scorers

`agentic_evals.scorers` ships ready-to-use scorers so you don't have to
hand-write a `CallableEvaluator` for common checks:

- **`scorers.text`** (deterministic, no LLM): `exact_match`, `contains_all`,
  `contains_any`, `levenshtein_similarity`, `embedding_similarity`,
  `valid_json`, `json_diff`, `numeric_diff`, `regex_match`, `starts_with`,
  `ends_with`, `numeric_range`.
- **`scorers.rubric`** (LLM-graded, provider-neutral): `RubricTemplate` +
  `LLMRubricEvaluator`, with built-in templates `FACTUALITY`, `CLOSED_QA`,
  `SUMMARY_QUALITY`, `BATTLE` (pairwise A/B), `MODERATION`, `TRANSLATION`,
  `SECURITY`, `SQL_CORRECTNESS`, `POSSIBLE`, `PII_LEAKAGE`, plus
  `make_rubric()` to build one from your own criteria. Like
  `LLMJudgeEvaluator`, this package never calls a model itself -- you pass
  a `complete_fn: Callable[[str], str]`.
- **`scorers.trajectory`** (reads the trace, not just the output text --
  the part a plain text-scoring library has no equivalent for):
  `tool_call_precision`, `tool_call_recall`, `no_redundant_tool_calls`,
  `trajectory_efficiency`.

```python
from agentic_evals import (
    EvalTrace,
    EvaluationSample,
    EvaluatorConfig,
    TestCase,
    TestSuite,
    default_registry,
    evaluate_suite,
)

suite = TestSuite(
    name="support-answers",
    version="1",
    cases=[
        TestCase(
            id="case-1",
            name="Answer is close to the reference",
            expected_output="The combined total is 42.",
            evaluators=[EvaluatorConfig(name="levenshtein_similarity", threshold=0.9)],
        )
    ],
)
sample = EvaluationSample(case_id="case-1", output="The combined total is 42.", trace=EvalTrace())

report = evaluate_suite(suite, [sample], registry=default_registry())
```

`default_registry()` covers every `text`/`trajectory` scorer under a
stable name. Rubric scorers need a `complete_fn`, so register an
`LLMRubricEvaluator` instance yourself:

```python
from agentic_evals import FACTUALITY, LLMRubricEvaluator, default_registry

registry = default_registry()
registry.register(LLMRubricEvaluator("factuality", FACTUALITY, complete_fn=call_your_model))
```

When no built-in template fits, describe the criterion in plain language
and `make_rubric()` builds the template — the prompt, the verdict letters
and their scores:

```python
from agentic_evals import LLMRubricEvaluator, make_rubric

concise = make_rubric("concise", "The answer is at most two sentences and has no preamble.")

tone = make_rubric(
    "tone",
    "The reply is courteous and does not blame the reader.",
    levels=[  # best first; scores in [0, 1]
        ("Courteous throughout.", 1.0),
        ("Neutral: neither courteous nor rude.", 0.5),
        ("Rude, dismissive, or blames the reader.", 0.0),
    ],
)

registry.register(LLMRubricEvaluator("concise", concise, complete_fn=call_your_model))
registry.register(LLMRubricEvaluator("tone", tone, complete_fn=call_your_model))
```

The default scale is pass/fail. Pass `with_reference=True` to show the
judge a reference next to the output; it is read from
`EvaluatorConfig.config["reference"]`, as with the built-in templates.

## Live targets

Point a suite at a real running system (a trusted Python callable, or an
HTTP endpoint) instead of pre-recorded samples:

```python
from agentic_evals import PythonTarget, run_live_suite

report = run_live_suite(suite, PythonTarget(callable_path="my_module:run_case"))
```

`run_live_suite(..., max_workers=4)` calls the target for several cases at
once on a thread pool. The report keeps suite case order, so it matches a
sequential run that produced the same outputs. Only raise `max_workers` for
targets that are safe to call concurrently. Python and HTTP targets go
through the same scoring path; the test suite checks that both produce the
same report for the same outputs.

`retry=RetryPolicy(max_attempts=3, backoff_seconds=1)` retries a call that
raises or times out. A case whose calls all fail is reported on the case
(`target_status` `timed_out` or `error`, `target_attempts`, `target_error`)
instead of aborting the run, and `summary.live` counts each outcome. HTTP
targets always apply `timeout_seconds`; Python targets apply it when it is set
explicitly, cancelling `async def` targets. `arun_live_suite(...,
max_concurrency=N)` awaits async targets and evaluators; `aevaluate_suite`
does the same for saved samples.

Live targets are intentionally powerful developer-facing integrations —
Python targets execute local code and HTTP targets can reach arbitrary
URLs. Only point them at trusted suite files and trusted target
definitions.

## Eval packs

A pack bundles a `TestSuite` with the scorer names it needs into one
shareable YAML/JSON file:

```python
from agentic_evals import (
    EvalSpan,
    EvalTrace,
    EvaluationSample,
    default_registry,
    evaluate_suite,
    load_builtin_pack,
)

pack = load_builtin_pack("tool-use-correctness")  # validates required_scorers up front
sample = EvaluationSample(
    case_id="refund-status-lookup",
    output="Your refund is on its way.",
    trace=EvalTrace(spans=[EvalSpan(tool_name="lookup_refund")]),
)
report = evaluate_suite(pack.to_suite(), [sample], registry=default_registry())
```

Ships 3 built-in packs (`list_builtin_packs()`): `tool-use-correctness`,
`json-output-contract` (both runnable with `default_registry()`), and
`factual-qa` (needs a registry with an `LLMRubricEvaluator` registered,
since it uses the `FACTUALITY` rubric). Load your own with `load_pack(path)`.

## Skills

`agentic_evals/skills/` ships methodology playbooks (`SKILL.md` cards --
Trigger/Do/Avoid/Check/Risk), not runnable code, scoped to this package's
own API. 18 skills cover the eval lifecycle end to end:

- **Frame**: `define-an-eval-objective`, `elicit-eval-criteria`
- **Build data**: `build-an-eval-dataset`, `size-a-test-suite`
- **Score**: `write-a-scorer`, `choose-a-rubric-template`, `validate-a-scorer`
- **Run**: `instrument-a-trace`, `run-a-live-suite`
- **Experiment**: `design-an-eval-experiment`, `analyze-an-eval-experiment`
- **Investigate**: `discover-failure-modes`, `red-team-an-agent-suite`,
  `debug-a-flaky-llm-judge`
- **Operate**: `define-a-release-gate`, `report-eval-results`,
  `monitor-evals-in-production`, `export-aios-evidence`

These document how to use this package well and are meant to be read
directly, or picked up by a coding agent's own skill mechanism -- distinct
from "packs" above, which are runnable configuration.

## Using it with AgenticLens's own traces

If you already have an AgenticLens `Run` (from its instrumentation API or
OTLP ingestion), AgenticLens itself provides the adapter —
`agenticlens.evaluation.to_eval_trace(run)` — so you don't have to hand-build
an `EvalTrace`. This package has no dependency in the other direction.

## What's deliberately not here

Dataset versioning/splitting, judge calibration, and HTML report rendering
stay in AgenticLens for now — those are product features built *on top of*
this engine, not the engine. So do trace-aware evaluators (tool trajectory,
handoffs, retrieval groundedness), failure diagnosis, and the analysis of
judge cost and evaluator disagreement that AgenticLens 0.7.0 runs over this
package's `EvaluationReport`.

## License

MIT

## Control Tower integration boundary

AgenticOps Control Tower owns deployment registration, heartbeat, fleet
inventory and operator workflows. AgenticLens owns observability and analysis;
Agentic Evals owns scoring and release-gate computation; Agentic Sidecar owns
decision supervision (SUPERVISE); Agentic Chaos owns fault injection and
resilience experiments. AI Operations Specification owns shared semantics and
is currently draft.

Tower's native artifact readers consume existing producer outputs using an
explicit deployment/evidence link. They do not change producer behavior or
convert a failed run, failed gate, blocked action or injected fault into fleet
health. This link is a Tower-local contract, not a normative AIOS schema.
See [Control Tower's evidence contract](https://github.com/DeepAgentLabs/agenticops-control-tower/blob/main/docs/ecosystem-alignment.md).
Tower 0.5 introduced pushed evidence posture; 0.6.0 adds cited investigation
and approved deterministic staging recovery. Pull collection and production runtime adapters
remain planned; native interoperability does not establish stable AIOS conformance.

## Operational safety roadmap

See [planned safety acceptance criteria](ROADMAP.md) for responsibilities and
dependencies. These additions do not claim implemented end-to-end containment
or integrity protection.

## Sidecar 0.8 interoperability

Evals 0.7.1 retains standalone scoring and release-gate ownership. Sidecar
supervision outcomes and private-context lifecycle validation are not scores;
broader Agent Alone vs Agent + Sidecar evidence remains Sidecar v0.9 work.

Sidecar 0.8 provides Shared/Exclusive context-only, guardrails-only or combined
configuration, explicit host context delivery and mandatory guardrail composition.
Exclusive rules cannot weaken shared restrictions. Cross-framework privacy,
revocation and delegated authority remain v0.9 validation; stable schemas remain
v1.0. Native correlated Lens readback requires Lens 0.7.1. All sibling packages
stay optional; no dependency floor is increased without a runtime requirement.
See the [Sidecar integration contract](https://github.com/DeepAgentLabs/agentic-sidecar/blob/main/docs/integrations.md).

## Control Tower 0.6.0 integration

Tower Phase 6 and 6A ship together in 0.6.0 with MCP 0.3.6: evidence-cited
investigation, exact-preview human approval and verified deterministic staging
recovery. Native producer outcomes and package ownership remain unchanged.
See [compatibility, examples and dependency matrix](docs/control-tower-0.6.md).
This is documentation alignment; no package release or dependency bump is needed.

## Published report and gate contract

As of **0.7.2**, native `EvaluationReport` (schema version `1.0`) and
`GateDecision` JSON Schemas ship in the package and are available offline:

```python
from jsonschema import Draft202012Validator
from agentic_evals import report_schema, gate_decision_schema

# report and decision are the results of evaluate_suite/evaluate_gate.
Draft202012Validator(report_schema()).validate(report.model_dump(mode="json"))
Draft202012Validator(gate_decision_schema()).validate(decision.model_dump(mode="json"))
```

Contract `1.x` changes are additive only; readers must tolerate unknown fields.
See [contract policy and sibling compatibility](docs/report-contract.md) and
[validated JSON examples](examples/report-contract/). The quickstart `EvalResult`
is a separate format. Native schema validation does not establish AIOS conformance.

## Native consumer validation

MCP 0.3.8 adds `evals.validate_artifact` and validates Lens report inputs and
produced SLO gates. Control Tower 0.6.1 validates complete reports and supplied
gates before evidence projection. Both bundle exact Evals 0.7.2 schemas for
offline, sibling-independent validation. See [the consumer matrix](docs/report-contract.md).

## AgenticLens 0.8.0 suite management

AgenticLens 0.8.0 delivers its v0.6 milestone: `agenticlens.suites` and
`agenticlens suite` build regression suites from CSV/JSON imports, production
traces and user feedback. It masks PII by default before storage (`--no-mask`
opts out), detects duplicates and
conflicting labels, adds synthetic variations and stable splits, records
reviews, and approves suites into immutable, hash-verified versions that CI
verifies, exports and evaluates. Suites stay plain agentic-evals `TestSuite`
files.

Evals runs these suites unchanged with `evaluate_suite` and `run_live_suite`.
Lens keeps management state (lineage, review status, domain, split) in
`TestCase.metadata` and `tags`, and an exported approved version adds
`metadata.agenticlens_suite_version` (name, version, SHA-256, approver).
Suite approval is not a release gate: scoring and gate computation stay in
Evals. No Evals change or release is needed.

See the [suite management guide](https://github.com/DeepAgentLabs/agenticlens/blob/v0.8.0/docs/suite-management.md).

## AgenticLens 0.9.0 ModelFit

AgenticLens 0.9.0 delivers its v0.7 milestone: `agenticlens.modelfit` and
`agenticlens modelfit` recommend a model per task category from recorded
experiment reports, under hard quality, cost, latency, safety, provider and
deployment constraints that fail closed. Each recommendation carries a
confidence level with reasons, an explanation, alternatives, a fallback
(on a different provider when one is feasible), savings against a reference variant tied to the
experiment evidence, and quality risks, plus a task-level model matrix.

Evals is unchanged. ModelFit reads the native evaluation reports that Lens
experiments embed per trial (`cases[].passed`, `latency_ms`, `cost_usd`,
`tags`, `metadata`) and computes no release gate; scoring and gate
computation stay in Evals. Lens keeps its `agentic-evals>=0.7.1,<1`
dependency. No Evals change or release is needed.

See the [ModelFit guide](https://github.com/DeepAgentLabs/agenticlens/blob/v0.9.0/docs/modelfit.md).

## Chaos 0.7.0 interoperability

Chaos 0.7.0 adds sequential fault cascades, deterministic monotonic breaking-point
search, synthetic response poisoning (including prompt/tool-response instruction
and policy-bypass payloads), and explicit-price retry cost estimates. Native
child event IDs and fault types remain intact; cascade IDs/stages and poisoning
strategy/payload/seed are additive event detail. Existing report readers and
AIOS exports remain compatible.

See the [v0.7 guide and offline synthetic example](https://github.com/DeepAgentLabs/agentic-chaos/blob/v0.7.0/docs/v0.7.md).
The example includes observed synthetic dispatches and a bypassed negative
control. Injection or recovery alone does not prove containment. No new shared
schema, automatic adapter, hosted execution capability or containment guarantee
is introduced.

Scores and release gates remain owned by Evals; Chaos contracts and threshold trials are per-campaign evidence. Convert observations to native EvaluationSamples explicitly. No runtime dependency or patch release is needed.

## Control Tower 0.7.0 fleet operations

Tower 0.7.0 adds frozen environment/capability targeting, bulk desired settings,
separate approval, durable per-target results and bounded stop/MCP-revocation
acknowledgement through Python, HTTP and CLI. No fleet atomicity or automatic
rollback/resume is claimed. Timed-out/requested commands need host reconciliation.

Evals retains scoring and native report/gate decisions. Bulk execution does not recompute gates or equate passing evaluation with deployment health or containment.

Existing optional dependency ranges remain sufficient. No sibling runtime or
native evidence schema changes are required; this documentation alignment needs
no patch release. See the [operator guide](https://github.com/DeepAgentLabs/agenticops-control-tower/blob/v0.7.0/docs/fleet-operations.md).

See the [local Tower compatibility guide](docs/tower-0.7-fleet-operations.md) for the operator workflow and package boundaries.

## AgenticLens 0.10.0 routing compatibility

See the [local integration boundary guide](docs/lens-0.10-routing.md).

AgenticLens 0.10.0 implements roadmap v0.8: evidence-based runtime model
selection, fail-closed routing constraints, bounded provider failover,
confidence/escalation handoffs, shadow/canary modes and a local routing journal.
The default is advisory; execution uses explicit caller-owned callbacks.
MCP 0.3.12 exposes read-only `lens.routing_decide` and pins hosted Lens 0.10.0.
See the [routing guide](https://github.com/DeepAgentLabs/agenticlens/blob/v0.10.0/docs/routing.md)
and [offline example](https://github.com/DeepAgentLabs/agenticlens/blob/v0.10.0/examples/routing_demo.py).

Lens retains `agentic-evals>=0.7.1,<1`, which covers current Evals 0.8.0.
Standalone scoring and release-gate computation remain Evals-owned. Routing
outcomes do not redefine native evaluation reports or gate decisions. No dependency
change or Evals patch release is required.

## Chaos 0.8.0 interoperability

Chaos 0.8.0 adds:

- multi-stage chaos workflows: steps, steady-state health checks, parallel
  branches, approval gates that can be resumed, and reusable templates
- declarative YAML/JSON/TOML experiments, with validation that never executes
  targets and cron schedule previews
- `Scope` explosion-radius control (steps, providers and exclusions) on every
  built-in fault and `cascade()`; custom faults get it by calling
  `BaseFault.__init__`, setting `scope` or overriding `in_scope()`
- a topology fuzzer that weights fault placement by fan-out

Native event IDs and fault types are unchanged. Workflow provenance
(`detail.workflow`) and an optional `ChaosReport.workflow` summary are
additive. A workflow's steps merge into one native report for contracts and
AIOS export.

See the [v0.8 guide](https://github.com/DeepAgentLabs/agentic-chaos/blob/v0.8.0/docs/v0.8.md)
and the [offline examples](https://github.com/DeepAgentLabs/agentic-chaos/tree/v0.8.0/examples/workflows).
Workflow statuses, health checks and fuzz outcomes are resilience evidence.
They are not scores, release gates or proof of containment. No new shared
schema, automatic adapter or hosted execution capability is introduced.

Workflow statuses and per-step contracts are per-run resilience checks, not Evals scores or release gates. Convert observed outputs to native EvaluationSamples explicitly. No adapter, runtime dependency or Evals patch release is needed.

## MCP 0.4.0 unified release checks

[MCP 0.4.0](https://github.com/DeepAgentLabs/mcp-server/releases/tag/v0.4.0) completes Phase 4 with its unified workflows: `core.compare_runs`, a fail-closed `core.release_check`, `core.incident_summary` and `core.export_report`. MCP judges nothing itself; it composes Lens comparisons, the Evals release gate and Chaos run reports. Malformed or failed-call evidence always blocks readiness, and so does missing evidence of a required kind; all three kinds are required by default and `required_evidence` narrows that.

`core.release_check` judges a native Evals report with `evaluate_gate`: the report
is schema-validated against the bundled 0.9.0 contract, every `GateConfig`
threshold applies (including judge and live-target limits), and with no thresholds
the strict default applies (every case must pass). Because `GateConfig` ignores
unknown keys, MCP rejects them so a misspelt threshold cannot pass silently. The
gate's reasons and observed values are returned per gate. No Evals change,
dependency bump or release is needed.
See [the compatibility guide](docs/mcp-0.4-unified-workflows.md).

## Sidecar 0.9.0 interoperability

Task-authority/delegation and reader-safe summaries are available in Sidecar.
See [compatibility and ownership boundaries](docs/sidecar-0.9.md). Existing
native decisions/correlation stay compatible; no new normative schema is claimed.

## AIOS v0.6 examples and extension guidance

See [AIOS v0.6 compatibility](docs/aios-v0.6.md) for canonical examples,
namespace rules and native contract boundaries. AIOS artifacts remain
`0.4-draft`; no runtime dependency bump or package release is required.

## Control Tower 0.8.0 live operations

See [operator compatibility and ownership](docs/tower-0.8-live-operations.md) for
periodic detection, durable alerts, acknowledgements and joined incident console
views. Existing native contracts and optional dependency ranges remain compatible;
no runtime or patch release is required here.
