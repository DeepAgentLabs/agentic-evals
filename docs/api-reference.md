# API reference

## APIs

### Eval() Quickstart

The fastest, most opinionated API. Perfect for simple cases.

```python
def Eval(
    name: str,
    data: list[dict] | Callable[[], list[dict]],
    task: Callable[[Any], str],
    scores: list[Callable],
    threshold: float = 1.0,
) -> EvalResult
```

**Parameters:**

| Parameter | Type | Description |
| --- | --- | --- |
| name | str | Eval name (appears in output) |
| data | list[dict] or callable | Test data with "input"/"expected" keys, or callable that returns it |
| task | callable | Function under test; called with each row's `input` value, returns the output |
| scores | list[callable] | Scorer functions; each returns 0-1 or bool |
| threshold | float | Min score for a case to pass (default 1.0) |

**Built-in scorers for Eval():**

* `equals` — Exact match
* `contains` — Case-sensitive substring
* `icontains` — Case-insensitive substring
* `levenshtein` — Similarity (0-1)
* `matches` — Regex match
* `numeric_close` — 1% relative tolerance

### TestSuite API

More structured, trace-aware evaluation with custom expectations.

```python
def evaluate_suite(
    suite: TestSuite,
    samples: list[EvaluationSample],
    registry: EvaluatorRegistry | None = None,
) -> EvaluationReport
```

Returns a full `EvaluationReport` with per-case scores, summary metrics, pass rates, cost/latency, and [breakdowns by metric and tag](core-concepts.md#scores-and-reports).

### Scorers Library

Pre-built evaluators organized by type:

#### Text Scorers (No LLM)

```python
from agentic_evals import scorers

# Deterministic checks
scorer = scorers.text.exact_match
scorer = scorers.text.levenshtein_similarity
scorer = scorers.text.valid_json
scorer = scorers.text.json_diff
scorer = scorers.text.regex_match
```

#### Rubric Scorers (LLM-Graded)

```python
from agentic_evals import LLMRubricEvaluator, FACTUALITY, default_registry

# Register an LLM rubric evaluator
registry = default_registry()
registry.register(
    LLMRubricEvaluator(
        "factuality_check",
        FACTUALITY,
        complete_fn=your_model_call,  # Your function to call LLM
    )
)
```

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

#### Trajectory Scorers (Trace-Aware)

```python
from agentic_evals import scorers

scorer = scorers.trajectory.tool_call_precision
scorer = scorers.trajectory.tool_call_recall
scorer = scorers.trajectory.no_redundant_tool_calls
scorer = scorers.trajectory.trajectory_efficiency
```

### Release Gates

Turn an evaluation report into a pass/fail CI decision:

```python
def evaluate_gate(
    report: EvaluationReport,
    config: GateConfig,
) -> GateDecision
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

A gate can hold one slice of the report to a stricter bar than the suite as a whole, keyed by case tag or by `Score.metric`:

```python
GateConfig(
    min_pass_rate=0.95,
    min_tag_pass_rate={"safety": 1.0},  # Every safety-tagged case passes
    min_metric_pass_rate={"forbidden_tool": 1.0},  # No forbidden tool call, anywhere
)
```

A tag or metric named in the config but missing from the report fails the gate, so a renamed tag cannot quietly switch a check off.

Since 0.9.0 the gate also reads judge and live-target outcomes. A judge that never delivered a verdict fails the default gate (`max_judge_unavailable_scores=0`):

```python
GateConfig(
    min_judge_agreement=0.8,  # every case judged with samples=N
    max_judge_cost_usd=2.50,  # fails when any judge score has no cost
    max_timed_out_cases=0,  # live runs: timeouts, apart from wrong answers
)
```

### Live Targets

Run a suite against a real system (trusted code or HTTP endpoint) instead of pre-recorded samples:

```python
def run_live_suite(
    suite: TestSuite,
    target: LiveTarget,
    *,
    registry: EvaluatorRegistry | None = None,
    trace_adapter: TraceAdapter | None = None,
    max_workers: int = 1,
    retry: RetryPolicy | None = None,
) -> EvaluationReport
```

**Python Target (executes local code):**

```python
from agentic_evals import PythonTarget, run_live_suite

report = run_live_suite(
    suite,
    PythonTarget(callable_path="my_module:my_agent"),
    # my_module.py must have a my_agent(input, case=None) function
)
```

**HTTP Target (calls a remote endpoint):**

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

**Retries, timeouts and async (0.9.0):** a call that raises or times out is retried under `retry`; a case whose calls all fail is reported with `target_status` `"timed_out"` or `"error"` instead of aborting the run. `arun_live_suite` awaits `async def` targets and cancels them at an explicit `timeout_seconds`.

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

### AIOS Evidence Export

Export a report as AI Operations Specification `0.4-draft` evaluation evidence (0.10.0) and attach it to an existing Run artifact:

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

A string target is a Step ID; a dict is an AIOS reference (`id`, `type`, optional `external`). Missing mappings, unknown case IDs and unresolved targets raise `AIOSExportError` (a `ValueError`). See [the AIOS evidence guide](aios-evidence.md).
