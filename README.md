# agentic-evals

**A standalone, framework-agnostic evaluation and scoring engine for LLM and
agent outputs.**

Extracted from [AgenticLens](https://github.com/DeepAgentLabs/agenticlens)'s
proven evaluation module — the same engine, usable on its own. It scores
whatever trace-shaped data you give it (see `EvalTrace`/`EvalSpan` below);
it has no dependency on any specific tracing/observability tool, and no
dependency on AgenticLens itself.

## Status

**Alpha.** The engine (deterministic checks, LLM-as-judge and custom
evaluators, a release gate, live Python/HTTP targets) is real, tested code
lifted directly from AgenticLens's evaluation module. No PyPI release yet.

## Why a separate package

AgenticLens's evaluation module was never actually AgenticLens-specific —
scoring an LLM/agent output against expectations doesn't need AgenticLens's
full trace schema, CLI, or dashboards. Pulling it out means:

- `agentic-sidecar`, `agentic-chaos`, or any other project can score outputs
  without depending on all of AgenticLens.
- Anyone with *any* trace-shaped data — not just AgenticLens users — can use
  it, the same way Braintrust's `autoevals` doesn't care what produced the
  string it's scoring.

## Install

```bash
pip install agentic-evals
```

## Core concepts

- **`EvalTrace`/`EvalSpan`** — the minimal trace shape the engine inspects:
  a trace id, spans (each optionally naming a `tool_name` and carrying
  arbitrary `attributes`), total latency, estimated cost, and metadata.
  Deliberately not tied to any specific instrumentation format — build one
  from whatever you already have.
- **`Score`** — a single named judgment (0-1 value, pass/fail, explanation).
- **`Evaluator`** — anything with a `.name` and an `.evaluate(context) ->
  list[Score]`. `CallableEvaluator` adapts a plain Python function;
  `LLMJudgeEvaluator` and `BusinessRuleEvaluator` are named convenience
  subclasses for readability/reporting.
- **`TestCase`/`TestSuite`** — declarative expectations (exact match,
  substring, JSON Schema, required fields, required/forbidden tool calls,
  required tool arguments, latency/cost/turn-count thresholds, or a named
  custom evaluator) plus the cases that make up a suite.
- **`evaluate_suite`** — runs a suite against supplied `EvaluationSample`s
  and returns an `EvaluationReport` (per-case scores plus a pass-rate/cost/
  latency summary).
- **`GateConfig`/`evaluate_gate`** — turn an `EvaluationReport` into a
  pass/fail release decision on configurable thresholds.

## Quickstart

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

Never fabricates a value it can't back up: `total_cost_usd` on a summary or
gate decision stays `None` unless every case in scope has a known cost —
an incomplete cost picture is reported as unavailable, not `$0.00`.

## Built-in scorers

`agentic_evals.scorers` ships ready-to-use scorers so you don't have to
hand-write a `CallableEvaluator` for common checks:

- **`scorers.text`** (deterministic, no LLM): `exact_match`, `contains_all`,
  `contains_any`, `levenshtein_similarity`, `embedding_similarity`,
  `valid_json`, `json_diff`, `numeric_diff`.
- **`scorers.rubric`** (LLM-graded, provider-neutral): `RubricTemplate` +
  `LLMRubricEvaluator`, with built-in templates `FACTUALITY`, `CLOSED_QA`,
  `SUMMARY_QUALITY`, `BATTLE` (pairwise A/B), `MODERATION`. Like
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
Trigger/Do/Avoid/Check/Risk), not runnable code: `write-a-scorer`,
`define-a-release-gate`, `size-a-test-suite`, `instrument-a-trace`. These
document how to use this package well and are meant to be read directly,
or picked up by a coding agent's own skill mechanism -- distinct from
"packs" above, which are runnable configuration.

## Using it with AgenticLens's own traces

If you already have an AgenticLens `Run` (from its instrumentation API or
OTLP ingestion), AgenticLens itself provides the adapter —
`agenticlens.evaluation.to_eval_trace(run)` — so you don't have to hand-build
an `EvalTrace`. This package has no dependency in the other direction.

## What's deliberately not here

Dataset versioning/splitting, judge calibration, and HTML report rendering
stay in AgenticLens for now — those are product features built *on top of*
this engine (the same way Braintrust's dataset/experiment platform is
separate from the `autoevals` library itself), not the engine.

## License

MIT
