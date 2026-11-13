# Configure reliable judges

Reference examples below show API composition and configuration fragments. Start with the complete quickstart before adapting these to your application.

## Judge cost and latency

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

## Retries and the unavailable outcome

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

`value` 0, `passed` false at any threshold, `metadata.judge_status:

"unavailable"`,` judge_error `(the last error) and` judge_errors` (the last few).

`summary.judge.unavailable_scores` counts them and `unavailable_cases` names

the cases.

`GateConfig.max_judge_unavailable_scores` defaults to `0`, so the default

gate fails on an unavailable judgment even when that judge was optional

(`required: false`), and the reason names the cases. Set it to `None` only

when an unavailable judge is acceptable evidence for your release.

raise when the judge function raised or a completion could not be parsed,

aborting `evaluate_suite`. They now return the unavailable score above.

## Repeated judging and agreement

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
