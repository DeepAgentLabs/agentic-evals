"""Judge reliability: usage recording, bounded retries and repeated judging.

`LLMJudgeEvaluator` and `LLMRubricEvaluator` run their judge through a
`JudgeRunner`, which

- measures each judge call and records its usage on the score under the same
  metadata keys AgenticLens uses (`judge_cost_usd`, `judge_cost_source`,
  `judge_input_tokens`, `judge_output_tokens`, `judge_latency_ms`,
  `judge_model`, `judge_provider`);
- retries a failing call under a `RetryPolicy`, and when the attempts run
  out returns an explicit *unavailable* score (`judge_status:
  "unavailable"`) that never passes, instead of raising or guessing;
- with `samples=N`, judges the case N times and reports how often the judge
  agreed with itself (`judge_agreement`), so a flaky judge shows up in the
  report rather than being averaged away.
"""

import asyncio
from collections import Counter
from collections.abc import Callable
from typing import Any, cast

from pydantic import BaseModel, Field

from agentic_evals import _async
from agentic_evals.models import CostSource, Score
from agentic_evals.reliability import (
    Attempted,
    RetryPolicy,
    acall_with_retry,
    call_with_retry,
    describe_error,
)

#: `Score.evaluator_type` values produced by model-graded evaluators.
JUDGE_EVALUATOR_TYPES = frozenset({"llm_judge", "llm_rubric"})

#: `Score.metadata["judge_status"]` values.
JUDGE_OK = "ok"
JUDGE_UNAVAILABLE = "unavailable"

#: How many failure messages an unavailable score keeps.
_MAX_RECORDED_ERRORS = 5


class JudgeAttemptError(ValueError):
    """A judge call that answered but could not be used, with what it consumed.

    Raised for a rubric completion with no parseable verdict, so the usage
    of that attempt is still added to the score's judge cost and tokens.
    """

    def __init__(self, message: str, *, usage: dict[str, Any]) -> None:
        super().__init__(message)
        self.usage = usage


class JudgeResponse(BaseModel):
    """A judge completion plus what the call consumed.

    A rubric `complete_fn` may return this instead of a plain string, so the
    score records the judge's tokens, cost and identity. Leave a field
    `None` when the provider did not report it; nothing is estimated here.
    A cost without a `cost_source` is recorded as `estimated`.
    """

    text: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    cost_source: CostSource | None = None
    model: str | None = None
    provider: str | None = None

    def usage_metadata(self) -> dict[str, Any]:
        recorded: dict[str, Any] = {}
        if self.input_tokens is not None:
            recorded["judge_input_tokens"] = self.input_tokens
        if self.output_tokens is not None:
            recorded["judge_output_tokens"] = self.output_tokens
        if self.cost_usd is not None:
            recorded["judge_cost_usd"] = self.cost_usd
            recorded["judge_cost_source"] = self.cost_source or "estimated"
        if self.model:
            recorded["judge_model"] = self.model
        if self.provider:
            recorded["judge_provider"] = self.provider
        return recorded


def is_judge_score(score: Score) -> bool:
    return score.evaluator_type in JUDGE_EVALUATOR_TYPES


def is_unavailable(score: Score) -> bool:
    return score.metadata.get("judge_status") == JUDGE_UNAVAILABLE


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _summed(samples: list[Score], key: str) -> float | None:
    """Sum of `key` over every sample, or `None` if any sample lacks it."""
    values = [_number(sample.metadata.get(key)) for sample in samples]
    if any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


_USAGE_TOTALS = ("judge_cost_usd", "judge_input_tokens", "judge_output_tokens")


def _failed_usage(outcomes: list[Attempted[Any]]) -> dict[str, Any]:
    """Usage reported by attempts that answered but failed (`JudgeAttemptError`).

    Attempts that raised without reporting usage, such as connection errors,
    add nothing: their cost is unknown, not zero.
    """
    totals: dict[str, Any] = {}
    sources: set[Any] = set()
    for outcome in outcomes:
        for failure in outcome.failures:
            usage = getattr(failure, "usage", None)
            if not isinstance(usage, dict):
                continue
            for key in _USAGE_TOTALS:
                value = _number(usage.get(key))
                if value is not None:
                    totals[key] = totals.get(key, 0) + value
            if "judge_cost_usd" in usage:
                sources.add(usage.get("judge_cost_source"))
    if "judge_cost_usd" in totals:
        totals["judge_cost_source"] = "measured" if sources == {"measured"} else "estimated"
    for key in ("judge_input_tokens", "judge_output_tokens"):
        if key in totals:
            totals[key] = int(totals[key])
    return totals


def _add_usage(metadata: dict[str, Any], wasted: dict[str, Any]) -> dict[str, Any]:
    """Add failed-attempt usage to a delivered score's own usage.

    Only totals the score already records are increased, so a score whose
    successful call reported no cost never shows a cost covering only the
    failed attempts.
    """
    merged = dict(metadata)
    for key in _USAGE_TOTALS:
        current = _number(merged.get(key))
        if key in wasted and current is not None:
            total = current + wasted[key]
            merged[key] = int(total) if key != "judge_cost_usd" else total
    if "judge_cost_usd" in wasted and _number(metadata.get("judge_cost_usd")) is not None:
        both = {metadata.get("judge_cost_source"), wasted["judge_cost_source"]}
        merged["judge_cost_source"] = "measured" if both == {"measured"} else "estimated"
    return merged


def _verdict_key(score: Score) -> Any:
    return score.metadata.get("verdict", score.value)


class JudgeRunner:
    """Runs one judge function with retries and optional repeated sampling."""

    def __init__(self, name: str, *, retry: RetryPolicy | None = None, samples: int = 1) -> None:
        if samples < 1:
            raise ValueError("samples must be at least 1")
        self.name = name
        self.retry = retry or RetryPolicy()
        self.samples = samples

    def _single(self, result: Any) -> Any:
        if self.samples == 1:
            return result
        if isinstance(result, list):
            if len(result) != 1:
                raise TypeError("a judge sampled more than once must return a single Score")
            result = result[0]
        if not isinstance(result, Score):
            raise TypeError("a judge must return a Score")
        return result

    def run(self, function: Callable[[Any], Any], context: Any) -> Score | list[Score]:
        outcomes: list[Attempted[Any]] = []
        for _ in range(self.samples):
            outcome = call_with_retry(
                lambda: self._single(_async.resolve(function(context))),
                self.retry,
                propagate=(_async.EventLoopMisuseError,),
            )
            outcomes.append(outcome)
            if not outcome.ok:
                break
        return self._finish(outcomes)

    async def arun(self, function: Callable[[Any], Any], context: Any) -> Score | list[Score]:
        async def attempt() -> Any:
            return self._single(await _async.call(function, context))

        outcomes = await asyncio.gather(
            *(
                acall_with_retry(attempt, self.retry, propagate=(_async.EventLoopMisuseError,))
                for _ in range(self.samples)
            )
        )
        return self._finish(list(outcomes))

    def _finish(self, outcomes: list[Attempted[Any]]) -> Score | list[Score]:
        attempts = sum(outcome.attempts for outcome in outcomes)
        elapsed = round(sum(outcome.elapsed_ms for outcome in outcomes), 3)
        failed = [outcome for outcome in outcomes if not outcome.ok]
        wasted = _failed_usage(outcomes)
        if failed:
            score = self._unavailable(outcomes, failed, attempts, elapsed)
            return score.model_copy(update={"metadata": {**score.metadata, **wasted}})
        if self.samples == 1:
            result: Any = outcomes[0].value
            scores: list[Score] = result if isinstance(result, list) else [result]
            stamped = [
                score.model_copy(
                    update={
                        "metadata": _add_usage(
                            {
                                "judge_latency_ms": elapsed,
                                **score.metadata,
                                "judge_status": JUDGE_OK,
                                "judge_attempts": attempts,
                            },
                            wasted,
                        )
                    }
                )
                for score in scores
            ]
            return stamped if isinstance(result, list) else stamped[0]
        samples: list[Score] = [cast(Score, outcome.value) for outcome in outcomes]
        aggregate = self._aggregate(samples, attempts, elapsed)
        return aggregate.model_copy(update={"metadata": _add_usage(aggregate.metadata, wasted)})

    def _unavailable(
        self,
        outcomes: list[Attempted[Any]],
        failed: list[Attempted[Any]],
        attempts: int,
        elapsed: float,
    ) -> Score:
        errors = [error for outcome in failed for error in outcome.errors]
        last = failed[-1].error
        message = describe_error(last) if last is not None else "unknown error"
        metadata: dict[str, Any] = {
            "judge_status": JUDGE_UNAVAILABLE,
            "judge_attempts": attempts,
            "judge_error": message,
            "judge_errors": errors[-_MAX_RECORDED_ERRORS:],
            "judge_latency_ms": elapsed,
        }
        if self.samples > 1:
            metadata["judge_samples"] = self.samples
            metadata["judge_completed_samples"] = sum(outcome.ok for outcome in outcomes)
        return Score(
            name=self.name,
            value=0.0,
            passed=False,
            explanation=f"Judge unavailable after {attempts} attempt(s): {message}",
            metadata=metadata,
        )

    def _aggregate(self, samples: list[Score], attempts: int, elapsed: float) -> Score:
        keys = [_verdict_key(sample) for sample in samples]
        counts = Counter(keys)
        top = max(counts.values())
        tied = [key for key in counts if counts[key] == top]

        def mean_value(key: Any) -> float:
            values = [s.value for s, k in zip(samples, keys, strict=True) if k == key]
            return sum(values) / len(values)

        # On a tie the lower-scoring verdict wins: disagreement must not round up.
        modal = min(tied, key=mean_value)
        representative = samples[keys.index(modal)]
        agreement = round(top / len(samples), 6)
        value = sum(sample.value for sample in samples) / len(samples)
        metadata: dict[str, Any] = {
            key: item
            for key, item in representative.metadata.items()
            if key
            not in {
                "judge_cost_usd",
                "judge_cost_source",
                "judge_input_tokens",
                "judge_output_tokens",
                "judge_latency_ms",
            }
        }
        recorded_latency = _summed(samples, "judge_latency_ms")
        metadata.update(
            {
                "judge_status": JUDGE_OK,
                "judge_attempts": attempts,
                "judge_samples": len(samples),
                "judge_verdicts": [
                    key if isinstance(key, (str, int, float)) else str(key) for key in keys
                ],
                "judge_sample_values": [sample.value for sample in samples],
                "judge_agreement": agreement,
                "judge_latency_ms": round(recorded_latency, 3)
                if recorded_latency is not None
                else elapsed,
            }
        )
        cost = _summed(samples, "judge_cost_usd")
        if cost is not None:
            sources = {sample.metadata.get("judge_cost_source") for sample in samples}
            metadata["judge_cost_usd"] = cost
            metadata["judge_cost_source"] = "measured" if sources == {"measured"} else "estimated"
        for key in ("judge_input_tokens", "judge_output_tokens"):
            total = _summed(samples, key)
            if total is not None:
                metadata[key] = int(total)
        return representative.model_copy(
            update={
                "value": value,
                "explanation": (
                    f"Judged {len(samples)} times; {top}/{len(samples)} agreed on "
                    f"{modal!r} (agreement {agreement:.0%}). {representative.explanation}"
                ),
                "metadata": metadata,
            }
        )
