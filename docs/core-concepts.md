# Core concepts

## Core Concepts

### EvalTrace and EvalSpan

The minimal trace structure agentic-evals inspects — deliberately **not** tied to any specific tracing tool or framework.

```python
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

```python
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

### TestSuite and TestCase

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

```python
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

```python
TestCase(
    id="publish-draft",
    name="Saves the draft before publishing it",
    required_tools=["save_draft", "publish"],
    expected_tool_arguments={"publish": {"visibility": "internal"}},
    required_tool_order=["save_draft", "publish"],
)
```

`expected_tool_arguments` passes when one call to the tool carries every listed value. `required_tool_order` passes when each listed tool is first called before the next; calls to other tools in between are fine.

### Evaluators

An evaluator is anything with a `.name` property and an `.evaluate(context) -> list[Score]` method.

Built-in types:

* `CallableEvaluator` — Wrap any Python function
* `LLMJudgeEvaluator` — Provider-neutral LLM judge
* `BusinessRuleEvaluator` — Named convenience for custom logic

### Scores and Reports

Each evaluation produces a `Score`:

```python
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

```python
class EvaluationReport(BaseModel):
    suite_name: str
    suite_version: str
    created_at: datetime
    summary: EvaluationSummary  # Pass rate, avg score, cost, latency
    cases: list[CaseEvaluation]  # Per-case details
```

#### Breakdowns by metric and tag

An overall pass rate does not show where the failures are. The summary breaks results down two ways:

```python
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