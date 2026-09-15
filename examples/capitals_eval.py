"""The 60-second on-ramp: `Eval(name, data=..., task=..., scores=[...])`.

Run directly:      python examples/capitals_eval.py
Or via the CLI:     agentic-evals run examples/
                     (the CLI discovers this file because it's named
                     `*_eval.py` -- see `agentic_evals.cli`)
"""

from agentic_evals import Eval, contains

CAPITALS = {"France": "Paris", "Japan": "Tokyo", "Peru": "Lima"}


def my_agent(country: str) -> str:
    """Stand-in for whatever's actually under test -- an LLM call, an agent, anything."""
    return f"The capital of {country} is {CAPITALS.get(country, 'unknown')}."


Eval(
    "capitals",
    data=[
        {"input": "France", "expected": "Paris"},
        {"input": "Japan", "expected": "Tokyo"},
        {"input": "Germany", "expected": "Berlin"},  # deliberately not in CAPITALS
    ],
    task=my_agent,
    scores=[contains],
    threshold=1.0,
)


def custom_scorer(input: str, output: str, expected: str) -> float:
    """Scorers can name any of input/output/expected -- called by keyword."""
    return 1.0 if expected in output else 0.0


Eval(
    "capitals-custom-scorer",
    data=[{"input": "Peru", "expected": "Lima"}],
    task=my_agent,
    scores=[custom_scorer],
)
