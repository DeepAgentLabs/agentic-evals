# Judge reliability, cost and live-target resilience (0.9.0)

Agentic Evals 0.9.0 makes LLM-judged and live-target evaluations dependable
and accounted for. Every judge score records what it cost and whether the
judge actually delivered a verdict. Live runs record, per case, whether the
target answered, timed out or failed. Nothing is guessed: a judgment that
could not be made is reported as unavailable and never counts as a pass.

Runnable offline walkthroughs:

- [`examples/judge_reliability.py`](../examples/judge_reliability.py):
  judge cost, a retried call, an unavailable judge and low agreement
- [`examples/async_live_target.py`](../examples/async_live_target.py): an
  `async def` target with retries and a cancelled timeout

## Judge cost and latency

`LLMRubricEvaluator`'s `complete_fn` may return a `JudgeResponse` instead of
a string, carrying what the provider reported:

```python
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

## Retries and the unavailable outcome

```python
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
`value` 0, `passed` false at any threshold, `metadata.judge_status:
"unavailable"`, `judge_error` (the last error) and `judge_errors` (the last few).
`summary.judge.unavailable_scores` counts them and `unavailable_cases` names
the cases.

`GateConfig.max_judge_unavailable_scores` defaults to `0`, so the default
gate fails on an unavailable judgment even when that judge was optional
(`required: false`), and the reason names the cases. Set it to `None` only
when an unavailable judge is acceptable evidence for your release.

> **Changed in 0.9.0:** `LLMJudgeEvaluator` and `LLMRubricEvaluator` used to
> raise when the judge function raised or a completion could not be parsed,
> aborting `evaluate_suite`. They now return the unavailable score above.

## Repeated judging and agreement

```python
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

## Live-target retries and timeouts

```python
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

> **Changed in 0.9.0:** a target exception (including an unreachable HTTP
> target) used to abort `run_live_suite`, and `agentic-evals live` exited 2
> with no report. It is now reported on its case and the run continues.

## Async evaluators and targets

```python
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

## CLI

```bash
agentic-evals live suite.yaml --target my_agent:run_case \
  --retries 2 --retry-backoff 1 --timeout-seconds 20 --out report.json
agentic-evals gate report.json --config gate.yaml
```

`--retries N` allows N extra attempts per case. `--retry-backoff` sets the
first wait in seconds, which doubles after each retry. `--timeout-seconds`
now applies to Python targets as well when it is given. Gate configs accept
the new fields, for example:

```yaml
min_pass_rate: 0.95
max_judge_unavailable_scores: 0   # the default
min_judge_agreement: 0.8
max_judge_cost_usd: 2.50
max_timed_out_cases: 0
```

## Report contract

All new fields are optional additions to report schema `1.0`. Reports saved
by earlier versions load unchanged, with `summary.judge`, `summary.live` and
`target_status` left `null`. Version 0.9.0 reports validate against the
frozen 0.7.1 schema too, so readers that bundle the 0.7.2 schemas keep
accepting them. See the [contract policy](report-contract.md).

## Sibling ownership

| Project | Relationship |
| --- | --- |
| AgenticLens | Lens 0.7.0+ already records and reads these `judge_*` keys in `analyze_scores()`; Evals now records them for its own judges and totals them in `summary.judge`. Calibration, experiments and judge disagreement across evaluators stay in Lens. `agentic-evals>=0.7.1,<1` already allows 0.9.0. |
| Control Tower | Validates native reports against bundled schemas; the 0.9.0 schemas add optional judge and live fields that Tower can project. |
| MCP | `evals.validate_artifact` validates native reports and gates offline against bundled schemas, now synced to 0.9.0. |
| Sidecar, Chaos | Not affected. Supervision and resilience outcomes stay theirs; live-target `timed_out` is an evaluation-harness outcome, not a chaos fault or a containment verdict. |
| AI Operations Specification | No change in 0.9.0. Evals 0.10.0 adds the AIOS evaluation evidence export ([guide](aios-evidence.md)). |
