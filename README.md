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
quickstart API, and the `agentic-evals` CLI) is real, tested code — see the
[changelog](CHANGELOG.md) for what shipped in each release. The API may
still move between minor versions ahead of a 1.0; pin a version in
production and read the changelog before upgrading.

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
registry.register(LLMJudgeEvaluator("answer_quality_judge", judge))

case = TestCase(
    id="case-1",
    name="Answer quality",
    evaluators=[EvaluatorConfig(name="answer_quality_judge", threshold=0.8)],
)
```

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

Never fabricates a value it can't back up: `total_cost_usd` on a summary or
gate decision stays `None` unless every case in scope has a known cost —
an incomplete cost picture is reported as unavailable, not `$0.00`.

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
own API. 17 skills cover the eval lifecycle end to end:

- **Frame**: `define-an-eval-objective`, `elicit-eval-criteria`
- **Build data**: `build-an-eval-dataset`, `size-a-test-suite`
- **Score**: `write-a-scorer`, `choose-a-rubric-template`, `validate-a-scorer`
- **Run**: `instrument-a-trace`, `run-a-live-suite`
- **Experiment**: `design-an-eval-experiment`, `analyze-an-eval-experiment`
- **Investigate**: `discover-failure-modes`, `red-team-an-agent-suite`,
  `debug-a-flaky-llm-judge`
- **Operate**: `define-a-release-gate`, `report-eval-results`,
  `monitor-evals-in-production`

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
this engine, not the engine.

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
Remote collection and operator posture views remain planned; these local
readers do not establish end-to-end integration or stable AIOS conformance.
