from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from agentic_evals import _async
from agentic_evals.judging import JudgeRunner
from agentic_evals.models import (
    EvaluationSample,
    EvaluatorConfig,
    Score,
    TestCase,
)
from agentic_evals.reliability import RetryPolicy


@dataclass(frozen=True)
class EvaluationContext:
    case: TestCase
    sample: EvaluationSample
    config: EvaluatorConfig


class Evaluator(Protocol):
    @property
    def name(self) -> str: ...

    def evaluate(self, context: EvaluationContext) -> list[Score]: ...


class AsyncEvaluator(Protocol):
    """An evaluator that can also be awaited.

    `aevaluate_suite` and `arun_live_suite` await `aevaluate` when an
    evaluator has one, and run a plain `evaluate` in a worker thread
    otherwise. `CallableEvaluator` and its subclasses implement both.
    """

    @property
    def name(self) -> str: ...

    def evaluate(self, context: EvaluationContext) -> list[Score]: ...

    async def aevaluate(self, context: EvaluationContext) -> list[Score]: ...


EvaluationFunction = Callable[
    [EvaluationContext], Score | list[Score] | Awaitable[Score | list[Score]]
]


class CallableEvaluator:
    """Adapt a trusted Python function to the unified evaluator contract.

    `version` identifies the evaluator's logic (for a judge: its prompt and
    model). It is stamped onto every score as `Score.evaluator_version`, so
    a report shows which version of the rule produced each judgment.

    `function` may be `async def`. `aevaluate()` awaits it; the synchronous
    `evaluate()` runs it to completion with `asyncio.run`, which is not
    possible inside a running event loop -- use `aevaluate_suite` there.
    """

    def __init__(
        self,
        name: str,
        function: EvaluationFunction,
        *,
        evaluator_type: str = "custom",
        version: str | None = None,
    ) -> None:
        if not name:
            raise ValueError("evaluator name must not be empty")
        if version is not None and not version.strip():
            raise ValueError("evaluator version must not be blank")
        self._name = name
        self._function = function
        self._evaluator_type = evaluator_type
        self._version = version

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str | None:
        return self._version

    def _call(self, context: EvaluationContext) -> Any:
        return _async.resolve(self._function(context))

    async def _acall(self, context: EvaluationContext) -> Any:
        return await _async.call(self._function, context)

    def evaluate(self, context: EvaluationContext) -> list[Score]:
        return self._finish(context, self._call(context))

    async def aevaluate(self, context: EvaluationContext) -> list[Score]:
        return self._finish(context, await self._acall(context))

    def _finish(self, context: EvaluationContext, result: Any) -> list[Score]:
        scores = result if isinstance(result, list) else [result]
        provenance = {
            "evaluator_type": self._evaluator_type,
            "evaluator": self._name,
            "evaluator_version": self._version,
        }
        return [
            score.model_copy(
                update=provenance
                if score.skipped
                else {
                    **provenance,
                    # An unavailable judgment never passes, whatever the threshold.
                    "passed": score.value >= context.config.threshold
                    and score.metadata.get("judge_status") != "unavailable",
                    "required": context.config.required,
                }
            )
            for score in scores
        ]


class LLMJudgeEvaluator(CallableEvaluator):
    """Provider-neutral adapter for an application-supplied LLM judge function.

    The judge runs under `retry` (default: one attempt). A judge that raises
    on every attempt yields an explicit unavailable score -- value 0, never
    passing, `metadata["judge_status"] == "unavailable"` -- instead of
    aborting the suite. With `samples=N` the judge is called N times; the
    score's value is the mean, its verdict the most common one, and
    `metadata["judge_agreement"]` the share of samples that agreed. Every
    score records `judge_status`, `judge_attempts` and `judge_latency_ms`.
    """

    def __init__(
        self,
        name: str,
        judge: EvaluationFunction,
        *,
        version: str | None = None,
        retry: RetryPolicy | None = None,
        samples: int = 1,
        evaluator_type: str = "llm_judge",
    ) -> None:
        super().__init__(name, judge, evaluator_type=evaluator_type, version=version)
        self._runner = JudgeRunner(name, retry=retry, samples=samples)

    def _call(self, context: EvaluationContext) -> Any:
        return self._runner.run(self._function, context)

    async def _acall(self, context: EvaluationContext) -> Any:
        return await self._runner.arun(self._function, context)


class BusinessRuleEvaluator(CallableEvaluator):
    """Named helper for application-specific pass/fail logic."""

    def __init__(self, name: str, rule: EvaluationFunction, *, version: str | None = None) -> None:
        super().__init__(name, rule, evaluator_type="business_rule", version=version)


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, Evaluator] = {}

    def register(self, evaluator: Evaluator, *, replace: bool = False) -> None:
        if evaluator.name in self._evaluators and not replace:
            raise ValueError(f"evaluator {evaluator.name!r} is already registered")
        self._evaluators[evaluator.name] = evaluator

    def get(self, name: str) -> Evaluator:
        try:
            return self._evaluators[name]
        except KeyError as exc:
            raise ValueError(f"evaluator {name!r} is not registered") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._evaluators))
