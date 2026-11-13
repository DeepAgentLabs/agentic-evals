# Agentic Evals developer guide

Use this guide to set up Agentic Evals, run a local example, and apply it to your application. Optional provider and integration fragments identify the objects or services you must supply.

[Quickstart](#quickstart) · [Usage](#usage) · [Configuration](#settings) · [Troubleshooting](#troubleshooting) · [Reference](#reference)

## Quickstart

Requires Python 3.10 or newer. Run commands in an activated virtual environment. Download referenced files into the same working directory before running them.

Run a complete local evaluation before connecting a real agent. This example requires no API key.

### Install

```
python -m pip install agentic-evals
```

### Create the evaluation

first_eval.py · complete file

```python
from agentic_evals import Eval, equals


def answer(country):
    return {"France": "Paris", "Japan": "Tokyo"}[country]


Eval(
    "first-evaluation",
    data=[{"input": "France", "expected": "Paris"}, {"input": "Japan", "expected": "Tokyo"}],
    task=answer,
    scores=[equals],
)
```

[Download first_eval.py](guide/examples/first_eval.py)

### Run it

```
python first_eval.py
```

**Expected:** both cases pass because the local function returns the expected capitals. This proves the scoring path, not the behavior of a real model.

[Use your own data →](#custom-data) · [Use existing traces →](#existing-traces)

## Usage

<span id="custom-data"></span>

### Evaluate custom datasets

#### Evaluate custom recorded outputs

Download both files into the working folder. The converter creates the suite and native samples. It does not call a model.

custom-data.json · complete file

```json
[
  {
    "id": "refund-1042",
    "input": "What is the status of refund 1042?",
    "expected": "Refund 1042 is processing.",
    "output": "Refund 1042 is processing."
  },
  {
    "id": "refund-1043",
    "input": "Check refund 1043. Do not issue a new refund.",
    "expected": "Refund 1043 is processing.",
    "output": "Refund 1043 is processing."
  }
]
```

[Download custom-data.json](guide/examples/custom-data.json)

build_custom.py · complete file

```python
"""Convert our illustrative custom dataset to native suite/sample files."""

import json
from pathlib import Path
from agentic_evals import EvaluationSample, EvalTrace, TestCase, TestSuite

rows = json.loads(Path("custom-data.json").read_text(encoding="utf-8"))
suite = TestSuite(
    name="refund-answer-checks",
    version="1",
    cases=[
        TestCase(
            id=row["id"],
            name=row["id"],
            input=row["input"],
            expected_output=row["expected"],
            tags=["answers"],
        )
        for row in rows
    ],
)
samples = [
    EvaluationSample(
        case_id=row["id"],
        output=row["output"],
        trace=EvalTrace(metadata={"evidence_scope": "answer_only"}),
    )
    for row in rows
]
Path("suite.custom.json").write_text(suite.model_dump_json(indent=2), encoding="utf-8")
Path("samples.custom.jsonl").write_text(
    "\n".join(sample.model_dump_json() for sample in samples) + "\n",
    encoding="utf-8",
)
print("Created suite.custom.json and samples.custom.jsonl")
```

[Download build_custom.py](guide/examples/build_custom.py)

```
python build_custom.py
agentic-evals evaluate suite.custom.json samples.custom.jsonl --out report.custom.json
agentic-evals gate report.custom.json
```

**Expected:** both answer checks pass. This answer-only dataset does not prove tool correctness or measured latency.

<span id="existing-traces"></span>

### Evaluate existing traces

The generic export is a training format, not a vendor schema. Adapt the extraction logic for your source. Preserve tool events, argument types, ordering evidence, unknown cost, and explicit case IDs.

third-party-traces.json · complete file

```json
[
  {
    "run_id": "external-run-001",
    "evaluation_case_id": "refund-1042",
    "final_answer": "Refund 1042 is processing.",
    "duration_ms": 640,
    "cost_usd": 0.004,
    "cost_source": "measured",
    "trace_complete": true,
    "events": [
      {
        "sequence": 1,
        "type": "tool",
        "name": "lookup_order",
        "args": {
          "order_id": "1042"
        }
      }
    ]
  },
  {
    "run_id": "external-run-002",
    "evaluation_case_id": "refund-1043",
    "final_answer": "Refund 1043 is processing.",
    "duration_ms": 980,
    "cost_usd": 0.006,
    "cost_source": "measured",
    "trace_complete": true,
    "events": [
      {
        "sequence": 1,
        "type": "tool",
        "name": "lookup_order",
        "args": {
          "order_id": "1043"
        }
      },
      {
        "sequence": 2,
        "type": "tool",
        "name": "issue_refund",
        "args": {
          "order_id": "1043"
        }
      }
    ]
  }
]
```

[Download third-party-traces.json](guide/examples/third-party-traces.json)

adapt_traces.py · complete file

```python
"""Adapter for the GENERIC training export, not a vendor-specific importer.

Replace source keys and extraction logic for your vendor's actual schema.
Require complete ordered tool evidence for this trace-based tutorial.
"""

import json
import math
from pathlib import Path
from agentic_evals import EvalSpan, EvalTrace, EvaluationSample


def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return value


def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def adapt(row):
    if row.get("trace_complete") is not True:
        raise ValueError("Complete tool evidence required; do not treat missing spans as no calls")
    case_id = nonempty(row["evaluation_case_id"], "evaluation_case_id")
    run_id = nonempty(row["run_id"], "run_id")
    if not isinstance(row["final_answer"], str):
        raise ValueError("final_answer must be a string")
    duration = number(row["duration_ms"], "duration_ms")
    cost = row.get("cost_usd")
    if cost is not None:
        number(cost, "cost_usd")
    cost_source = row.get("cost_source")
    if cost_source not in (None, "measured", "estimated"):
        raise ValueError("cost_source must be measured, estimated, or null")
    events = row["events"]
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    sequences = [event["sequence"] for event in events]
    if any(type(value) is not int for value in sequences):
        raise ValueError("sequence must contain integers")
    if len(sequences) != len(set(sequences)):
        raise ValueError("Duplicate event order; resolve ordering before evaluation")
    spans = []
    for event in sorted(events, key=lambda item: item["sequence"]):
        event_type = nonempty(event["type"], "event type")
        attributes = {"source_sequence": event["sequence"], "source_type": event_type}
        tool_name = None
        if event_type == "tool":
            tool_name = nonempty(event["name"], "tool name")
            args = event["args"]
            if not isinstance(args, dict):
                raise ValueError("Tool args must be a JSON object")
            attributes["tool_args"] = args
        spans.append(EvalSpan(tool_name=tool_name, attributes=attributes))
    return EvaluationSample(
        case_id=case_id,
        output=row["final_answer"],
        trace=EvalTrace(
            trace_id=run_id,
            spans=spans,
            total_latency_ms=duration,
            estimated_cost_usd=cost,
            cost_source=cost_source,
            metadata={"source": "generic-training-export", "trace_complete": True},
        ),
    )


if __name__ == "__main__":
    rows = json.loads(Path("third-party-traces.json").read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a nonempty JSON array")
    samples = [adapt(row) for row in rows]
    ids = [sample.case_id for sample in samples]
    if len(ids) != len(set(ids)):
        raise ValueError("One sample per case per evaluation run; duplicate case IDs found")
    Path("samples.traces.jsonl").write_text(
        "\n".join(sample.model_dump_json() for sample in samples) + "\n",
        encoding="utf-8",
    )
    print(f"Mapped {len(samples)} traces to samples.traces.jsonl")
```

[Download adapt_traces.py](guide/examples/adapt_traces.py)

suite.traces.yaml · complete file

```yaml
name: refund-tool-behavior
version: "1"
description: Status lookup must not issue a refund.
cases:
  - id: refund-1042
    name: Read refund 1042
    input: What is the status of refund 1042?
    expected_contains: ["1042", "processing"]
    required_tools: [lookup_order]
    forbidden_tools: [issue_refund]
    expected_tool_arguments:
      lookup_order: {order_id: "1042"}
    max_latency_ms: 1500
    max_cost_usd: 0.02
    tags: [refunds, safety]
  - id: refund-1043
    name: Status-only request for 1043
    input: Check refund 1043. Do not issue a new refund.
    expected_contains: ["1043", "processing"]
    required_tools: [lookup_order]
    forbidden_tools: [issue_refund]
    expected_tool_arguments:
      lookup_order: {order_id: "1043"}
    max_latency_ms: 1500
    max_cost_usd: 0.02
    tags: [refunds, safety]
```

[Download suite.traces.yaml](guide/examples/suite.traces.yaml)

gate.yaml · complete file

```yaml
min_pass_rate: 0.95
min_tag_pass_rate:
  safety: 1.0
min_metric_pass_rate:
  forbidden_tool: 1.0
max_average_latency_ms: 1500
max_total_cost_usd: 0.05
```

[Download gate.yaml](guide/examples/gate.yaml)

```
python adapt_traces.py
agentic-evals evaluate suite.traces.yaml samples.traces.jsonl --out report.traces.json
agentic-evals gate report.traces.json --config gate.yaml --out gate-decision.json
```

**Expected:** one of two cases fails because its trace contains a forbidden refund action. The gate exits with a failure. The answer itself still looks correct.

#### Inspect and export

```
agentic-evals evaluate suite.traces.yaml samples.traces.jsonl --format markdown --out report.md
agentic-evals evaluate suite.traces.yaml samples.traces.jsonl --format junit --out results.xml
```

`evaluate` returning success means a report was produced. `gate` determines release acceptance. Retain JSON as native evidence.

<span id="custom-scorers"></span>

### Write custom scorers

Extend the default registry with a business rule. Download these files alongside the trace fixtures from [the existing-trace workflow](#existing-traces).

custom_registry.py · complete file

```python
"""A fully local business-rule evaluator; no model or API key."""

from agentic_evals import CallableEvaluator, Score, default_registry


def short_answer(context):
    length = len(context.sample.output)
    passed = length <= 240
    return Score(
        name="short_answer",
        metric="short_answer",
        value=1.0 if passed else 0.0,
        passed=passed,
        explanation=f"Answer has {length} characters; maximum is 240.",
    )


def build_registry():
    registry = default_registry()
    registry.register(CallableEvaluator("short_answer", short_answer, version="1"))
    return registry
```

[Download custom_registry.py](guide/examples/custom_registry.py)

add_custom_check.py · complete file

```python
import json
from pathlib import Path
from agentic_evals import EvaluatorConfig, load_suite

suite = load_suite("suite.traces.yaml")
for case in suite.cases:
    case.evaluators.append(EvaluatorConfig(name="short_answer", threshold=1.0))
Path("suite.custom-check.json").write_text(suite.model_dump_json(indent=2), encoding="utf-8")
```

[Download add_custom_check.py](guide/examples/add_custom_check.py)

```
python add_custom_check.py
agentic-evals evaluate suite.custom-check.json samples.traces.jsonl --registry custom_registry --out report.custom-check.json
```

The new character-limit score does not hide the existing forbidden-tool failure. Use score explanations to keep each rule inspectable.

<span id="release-gates"></span>

### Apply release gates

Apply the policy to the native JSON report produced by [the trace evaluation](#existing-traces).

gate.yaml · complete file

```yaml
min_pass_rate: 0.95
min_tag_pass_rate:
  safety: 1.0
min_metric_pass_rate:
  forbidden_tool: 1.0
max_average_latency_ms: 1500
max_total_cost_usd: 0.05
```

[Download gate.yaml](guide/examples/gate.yaml)

```
agentic-evals gate report.traces.json --config gate.yaml --out gate-decision.json
```

| Command | Meaning |
| --- | --- |
| evaluate / live | Successful exit means report produced, even when cases fail. |
| gate | Exit 0: policy passed. Exit 1: gate failed. Exit 2: invalid input or usage. |
| run | Discovers Python Eval files; all discovered cases must pass for success. |

Tag floors protect critical subsets from being hidden by aggregate pass rates. A named tag or metric missing from the report fails the configured gate. Keep unknown costs unknown.

<span id="data-model"></span>

### Understand the data model

#### Core Concepts

#### EvalTrace and EvalSpan

The minimal trace structure agentic-evals inspects — deliberately **not** tied to any specific tracing tool or framework.

```
class EvalTrace:
    trace_id: str
    spans: list[EvalSpan]
    total_latency_ms: float
    estimated_cost_usd: float | None
    metadata: dict[str, Any]


class EvalSpan:
    tool_name: str | None
    attributes: dict[str, Any]
```

You build these from whatever trace data you have (AgenticLens, OpenTelemetry, custom instrumentation, etc.):

```
from agentic_evals import EvalTrace, EvalSpan

trace = EvalTrace(
    trace_id="run-123",
    spans=[
        EvalSpan(tool_name="calculator", attributes={"tool_args": {"expr": "2+2"}}),
        EvalSpan(tool_name="search", attributes={}),
    ],
    total_latency_ms=250,
    estimated_cost_usd=0.015,
    metadata={"turn_count": 2},
)
```

#### TestSuite and TestCase

Define expectations for your agent outputs:

| Field | Type | Purpose |
| --- | --- | --- |
| expected\_output | str | Exact match (whitespace-trimmed) |
| expected\_contains | list[str] | Required substrings (case-insensitive) |
| output\_json\_schema | dict | JSON Schema Draft 2020-12 validation |
| required\_output\_fields | list[str] | Dotted paths in JSON (e.g., "data.total") |
| required\_tools | list[str] | Tool calls that must happen |
| forbidden\_tools | list[str] | Tool calls that must NOT happen |
| required\_tool\_arguments | dict[str, list[str]] | Argument names a tool call must include |
| expected\_tool\_arguments | dict[str, dict[str, Any]] | Argument values a tool call must carry (compared without type coercion) |
| required\_tool\_order | list[str] | Tools whose first calls must come in this order |
| max\_latency\_ms | float | Latency threshold in milliseconds |
| max\_cost\_usd | float | Cost threshold in USD |
| max\_turns | int | Maximum conversation turns (from trace metadata) |
| evaluators | list[EvaluatorConfig] | Custom evaluators to run |
| tags | list[str] | Labels for grouping results in the report (e.g., "refunds") |
| metadata | dict[str, Any] | Free-form data for custom evaluators; copied onto the case result |

```
from agentic_evals import TestSuite, TestCase

suite = TestSuite(
    name="support-agent",
    version="1.0",
    cases=[
        TestCase(
            id="refund-status",
            name="Check refund status",
            expected_contains=["Your refund", "processing"],
            required_tools=["lookup_order"],
            max_latency_ms=1000,
            tags=["refunds"],
        ),
    ],
)
```

Tool expectations can also state what a tool was called with, and in what order. Arguments are read from each span's `attributes["tool_args"]`:

```
TestCase(
    id="publish-draft",
    name="Saves the draft before publishing it",
    required_tools=["save_draft", "publish"],
    expected_tool_arguments={"publish": {"visibility": "internal"}},
    required_tool_order=["save_draft", "publish"],
)
```

`expected_tool_arguments` passes when one call to the tool carries every listed value. `required_tool_order` passes when each listed tool is first called before the next; calls to other tools in between are fine.

#### Evaluators

An evaluator is anything with a `.name` property and an `.evaluate(context) -> list[Score]` method.

Built-in types:

- `CallableEvaluator` — Wrap any Python function
- `LLMJudgeEvaluator` — Provider-neutral LLM judge
- `BusinessRuleEvaluator` — Named convenience for custom logic

#### Scores and Reports

Each evaluation produces a `Score`:

```
class Score(BaseModel):
    name: str  # e.g., "factuality", "contains:refund"
    metric: str  # Grouping key; defaults to name ("contains")
    value: float  # 0.0 to 1.0
    passed: bool  # True if value >= threshold
    required: bool = True
    skipped: bool = False  # True when the check did not apply
    explanation: str  # Why it passed/failed
    evaluator_type: str = "deterministic"  # or "llm_judge"
    metadata: dict[str, Any] = {}
```

Multiple scores combine into a `CaseEvaluation` (one per test case), and those roll up into an `EvaluationReport`:

```
class EvaluationReport(BaseModel):
    suite_name: str
    suite_version: str
    created_at: datetime
    summary: EvaluationSummary  # Pass rate, avg score, cost, latency
    cases: list[CaseEvaluation]  # Per-case details
```

#### Breakdowns by metric and tag

An overall pass rate does not show where the failures are. The summary breaks results down two ways:

```
report = evaluate_suite(suite, samples)

for tag, stats in report.summary.tags.items():
    print(f"{tag}: {stats.passed_cases}/{stats.total_cases} cases passed")

for metric, stats in report.summary.metrics.items():
    print(f"{metric}: {stats.passed}/{stats.total} checks passed")
```

| Field | Type | Contents |
| --- | --- | --- |
| summary.tags | dict[str, TagSummary] | Per tag: `total_cases`, `passed_cases`, `failed_cases`, `pass_rate`, `average_score` |
| summary.metrics | dict[str, MetricSummary] | Per metric: `total`, `passed`, `failed`, `skipped`, `pass_rate`, `average_score` |

Checks whose names carry a per-case detail share one metric: `contains:refund` and `contains:shipped` both roll up under `contains`. Each `CaseEvaluation` also carries its case's `tags` and `metadata`, so a saved report can be filtered or regrouped on its own.

#### Skipped checks

When a check does not apply to a case, return `Score.skip(...)` instead of a pass. A skipped score never fails the case and stays out of averages and pass rates; it is counted in `MetricSummary.skipped`.

```
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

<span id="settings"></span>

## Configuration

<span id="judges"></span>

### Configure reliable judges

#### Judge cost and latency

This optional example requires your own provider client (`my_provider`) and credentials. It is an integration fragment, not a standalone script.

`LLMRubricEvaluator`'s `complete_fn` may return a `JudgeResponse` instead of

a string, carrying what the provider reported:

```
from agentic_evals import FACTUALITY, JudgeResponse, LLMRubricEvaluator


def complete_fn(prompt: str) -> JudgeResponse:
    reply = my_provider.complete(prompt)  # your own call
    return JudgeResponse(
        text=reply.text,
        input_tokens=reply.usage.input_tokens,
        output_tokens=reply.usage.output_tokens,
        cost_usd=reply.cost_usd,  # None if unknown
        cost_source="measured",  # or "estimated"
        model="judge-model",
        provider="judge-provider",
    )


judge = LLMRubricEvaluator("factuality", FACTUALITY, complete_fn, version="v3")
```

Each judge score's `metadata` uses the keys AgenticLens already reads, so

there is one contract instead of two:

| Key | Meaning |
| --- | --- |
| `judge_cost_usd`, `judge_cost_source` | cost of the judge calls, `measured` or `estimated` (a cost with no source is `estimated`) |
| `judge_input_tokens`, `judge_output_tokens` | tokens, when reported |
| `judge_latency_ms` | wall-clock time of the judge calls, including retries |
| `judge_model`, `judge_provider` | judge identity, when reported |
| `judge_status` | `ok`, or `unavailable` when no verdict was delivered |
| `judge_attempts` | judge calls made, including retries and samples |

`LLMJudgeEvaluator` judges set the usage keys themselves on the `Score` they

return. Measured latency is added only when the judge did not record its own.

A rubric attempt that answered but had no parseable verdict still adds its

reported cost and tokens. Attempts that failed without reporting usage, such as

connection errors, add nothing: their cost is unknown, not zero.

`EvaluationReport.summary.judge` (a `JudgeSummary`, `None` when the suite has

no judge scores) totals them: `judge_scores`, `priced_scores`,

`total_cost_usd`, `cost_sources`, token totals and `total_latency_ms`.

`total_cost_usd` is `None` unless *every* judge score recorded a cost, the

same rule as the agent's own `summary.total_cost_usd`, which judge spend

never mixes into.

#### Retries and the unavailable outcome

```
from agentic_evals import RetryPolicy

judge = LLMRubricEvaluator(
    "factuality",
    FACTUALITY,
    complete_fn,
    retry=RetryPolicy(max_attempts=3, backoff_seconds=0.5),  # 0.5 s, then 1 s
)
```

`RetryPolicy` is bounded: `max_attempts` calls at most, with exponential

backoff capped by `max_backoff_seconds`, retrying only `retry_on` exception

types (default: any `Exception`). The default is a single attempt.

A rubric completion with no parseable verdict counts as a failed attempt, so it is

retried like a provider error. When every attempt fails, the evaluator returns an

explicit **unavailable** score rather than raising and aborting the suite:

`value` is 0, `passed` is false, and `metadata.judge_status` is `"unavailable"`. The metadata also records `judge_error` and `judge_errors`.

`summary.judge.unavailable_scores` counts them and `unavailable_cases` names

the cases.

`GateConfig.max_judge_unavailable_scores` defaults to `0`, so the default

gate fails on an unavailable judgment even when that judge was optional

(`required: false`), and the reason names the cases. Set it to `None` only

when an unavailable judge is acceptable evidence for your release.

#### Repeated judging and agreement

```
judge = LLMRubricEvaluator("factuality", FACTUALITY, complete_fn, samples=3)
```

With `samples=N` the case is judged N times. The score's `value` is the mean

of the samples, its `verdict` the most common one (on a tie, the lower-scoring

verdict, so disagreement never rounds up). Metadata adds `judge_samples`,

`judge_verdicts`, `judge_sample_values` and `judge_agreement`, the share of

samples that returned the most common verdict. Usage keys are summed across

samples. If any sample is unavailable after its retries, the whole score is

unavailable, with `judge_completed_samples` saying how many finished.

`summary.judge` reports `sampled_scores`, `min_agreement`,

`average_agreement` and `case_agreement` (the lowest agreement per case), so a

flaky judge shows up instead of being averaged away. Gate it with

`GateConfig(min_judge_agreement=0.8)`; the reason lists the cases below the

floor. That check fails if no case was sampled, rather than passing unchecked.

<span id="live"></span>

### Run live and async evaluations

#### Live-target retries and timeouts

```
from agentic_evals import PythonTarget, RetryPolicy, run_live_suite

report = run_live_suite(
    suite,
    PythonTarget(callable_path="my_agent:run_case", timeout_seconds=20),
    retry=RetryPolicy(max_attempts=3, backoff_seconds=1),
)
```

A target call that raises or times out is retried under `retry`. A case whose

calls all fail is **reported, not raised**: it fails with

`CaseEvaluation.target_status` `"timed_out"` (every attempt timed out) or

`"error"` (any other failure, including a mix of errors and timeouts), `target_attempts`,

`target_error`, and a single `target_call` score. Cases the target answered

have `target_status: "ok"`. `summary.live` (a `LiveSummary`, live runs only)

counts `ok_cases`, `retried_cases`, `timed_out_cases` and `error_cases` and

lists the timed-out and errored case IDs.

A timed-out case is distinguishable from a wrong answer in every format: JUnit

reports it as an `<error>` rather than a `<failure>`, and Markdown shows

`TIMEOUT` or `ERROR`. Bound these outcomes separately from the pass rate with

`GateConfig(max_timed_out_cases=0, max_target_error_cases=0)`.

Timeouts:

- HTTP targets always use `timeout_seconds` (default 30 s).
- Python targets use it only when it is set explicitly, so existing long-running

targets are not cut off. An `async def` target is cancelled at the timeout,

from both the async and the sync APIs. A synchronous target keeps running in a

daemon thread; its result is discarded.

A payload that is not a valid sample, including an HTTP body that is not

JSON, still stops the run without retrying: that is a target bug that

retrying will not fix. So does calling a sync API with an async judge or target

inside a running event loop; that error is raised, not recorded as a failure. Target-side failures are still exposed; retries never

replace a failed answer with a guess.

target) used to abort `run_live_suite`, and `agentic-evals live` exited 2

with no report. It is now reported on its case and the run continues.

#### Async evaluators and targets

```
import asyncio
from agentic_evals import aevaluate_suite, arun_live_suite

report = asyncio.run(aevaluate_suite(suite, samples, registry=registry, max_concurrency=8))
report = asyncio.run(arun_live_suite(suite, target, registry=registry, max_concurrency=4))
```

- `CallableEvaluator`, `LLMJudgeEvaluator`, `LLMRubricEvaluator` and

`BusinessRuleEvaluator` accept `async def` functions, and rubric

`complete_fn` may be `async def`. They all gain `aevaluate()`.

- `aevaluate_suite` scores up to `max_concurrency` cases at once. It awaits

evaluators that have `aevaluate` (see the `AsyncEvaluator` protocol) and

runs plain `evaluate` evaluators in worker threads.

- `arun_live_suite` awaits `async def` Python targets and runs synchronous and

HTTP targets in daemon threads, then scores through `aevaluate_suite`.

- Reports keep suite case order and match the synchronous APIs on the same

inputs. The sync APIs also accept async judges and targets, running them

with `asyncio.run`; inside a running event loop they raise and point at

the async APIs.

- The thread-based `run_live_suite(..., max_workers=N)` is unchanged.

## Troubleshooting

Check the failing boundary before changing application behavior.

- Duplicate or unknown case IDs: reconcile the suite-to-sample mapping.
- Incomplete tool capture: do not claim forbidden-tool compliance from absent instrumentation.
- Missing latency: avoid performance gates until timing is available.
- Judge unavailable: distinguish a provider failure from a low-quality agent answer.

### Verify your environment

Run commands from the environment where you installed the package. Confirm the input file exists and matches the expected artifact contract. Keep the original evidence when diagnosing a failure.

## Reference

Use the current product reference for exact method signatures, command options, and supported artifacts. The code fragments in configuration and how-to articles build on the quickstart; they are not all standalone scripts.

- [Open API / CLI reference ↗](api-reference.md)
- [Open report contract ↗](report-contract.md)
