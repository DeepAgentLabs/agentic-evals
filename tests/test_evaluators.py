import pytest

from agentic_evals import CallableEvaluator, EvaluatorRegistry, Score


def _score(context) -> Score:
    return Score(name="ok", value=1.0, passed=True, explanation="fine")


def test_register_and_get_evaluator() -> None:
    registry = EvaluatorRegistry()
    registry.register(CallableEvaluator("scorer", _score))

    assert registry.names() == ("scorer",)
    assert registry.get("scorer").name == "scorer"


def test_register_duplicate_name_rejected_unless_replace() -> None:
    registry = EvaluatorRegistry()
    registry.register(CallableEvaluator("scorer", _score))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(CallableEvaluator("scorer", _score))

    registry.register(CallableEvaluator("scorer", _score), replace=True)


def test_get_unknown_evaluator_raises() -> None:
    registry = EvaluatorRegistry()

    with pytest.raises(ValueError, match="is not registered"):
        registry.get("missing")


def test_callable_evaluator_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        CallableEvaluator("", _score)
