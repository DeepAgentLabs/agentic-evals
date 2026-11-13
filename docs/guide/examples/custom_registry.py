"""A fully local business-rule evaluator; no model or API key."""
from agentic_evals import CallableEvaluator, Score, default_registry

def short_answer(context):
    length = len(context.sample.output)
    passed = length <= 240
    return Score(
        name="short_answer", metric="short_answer",
        value=1.0 if passed else 0.0, passed=passed,
        explanation=f"Answer has {length} characters; maximum is 240.",
    )

def build_registry():
    registry = default_registry()
    registry.register(CallableEvaluator("short_answer", short_answer, version="1"))
    return registry

