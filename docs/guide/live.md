# Run live and async evaluations

Reference examples below show API composition and configuration fragments. Start with the complete quickstart before adapting these to your application.

## Live-target retries and timeouts

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

## Async evaluators and targets

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
