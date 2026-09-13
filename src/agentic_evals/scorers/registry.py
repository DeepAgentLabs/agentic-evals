from collections.abc import Callable

from agentic_evals.evaluators import CallableEvaluator, EvaluationContext, EvaluatorRegistry
from agentic_evals.models import Score
from agentic_evals.scorers.text import (
    contains_all,
    contains_any,
    embedding_similarity,
    exact_match,
    json_diff,
    levenshtein_similarity,
    numeric_diff,
    valid_json,
)
from agentic_evals.scorers.trajectory import (
    no_redundant_tool_calls,
    tool_call_precision,
    tool_call_recall,
    trajectory_efficiency,
)

_BUILTIN_SCORERS: dict[str, Callable[[EvaluationContext], Score]] = {
    "exact_match": exact_match,
    "contains_all": contains_all,
    "contains_any": contains_any,
    "levenshtein_similarity": levenshtein_similarity,
    "embedding_similarity": embedding_similarity,
    "valid_json": valid_json,
    "json_diff": json_diff,
    "numeric_diff": numeric_diff,
    "tool_call_precision": tool_call_precision,
    "tool_call_recall": tool_call_recall,
    "no_redundant_tool_calls": no_redundant_tool_calls,
    "trajectory_efficiency": trajectory_efficiency,
}


def default_registry() -> EvaluatorRegistry:
    """A fresh `EvaluatorRegistry` pre-populated with every built-in scorer.

    LLM-graded rubric scorers (`agentic_evals.scorers.rubric`) aren't
    included here since they need a caller-supplied `complete_fn` to do
    anything -- register an `LLMRubricEvaluator` instance for those
    explicitly once you have a model call to give it.
    """
    registry = EvaluatorRegistry()
    for name, function in _BUILTIN_SCORERS.items():
        registry.register(CallableEvaluator(name, function, evaluator_type="builtin"))
    return registry


def builtin_scorer_names() -> tuple[str, ...]:
    return tuple(sorted(_BUILTIN_SCORERS))
