from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from agentic_evals.models import (
    EvaluationSample,
    EvaluatorConfig,
    Score,
    TestCase,
)


@dataclass(frozen=True)
class EvaluationContext:
    case: TestCase
    sample: EvaluationSample
    config: EvaluatorConfig


class Evaluator(Protocol):
    @property
    def name(self) -> str: ...

    def evaluate(self, context: EvaluationContext) -> list[Score]: ...


EvaluationFunction = Callable[[EvaluationContext], Score | list[Score]]


class CallableEvaluator:
    """Adapt a trusted Python function to the unified evaluator contract.

    `version` identifies the evaluator's logic (for a judge: its prompt and
    model). It is stamped onto every score as `Score.evaluator_version`, so
    a report shows which version of the rule produced each judgment.
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

    def evaluate(self, context: EvaluationContext) -> list[Score]:
        result = self._function(context)
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
                    "passed": score.value >= context.config.threshold,
                    "required": context.config.required,
                }
            )
            for score in scores
        ]


class LLMJudgeEvaluator(CallableEvaluator):
    """Provider-neutral adapter for an application-supplied LLM judge function."""

    def __init__(self, name: str, judge: EvaluationFunction, *, version: str | None = None) -> None:
        super().__init__(name, judge, evaluator_type="llm_judge", version=version)


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
