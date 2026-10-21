# Getting started

A standalone, framework-agnostic evaluation and scoring engine for LLM and agent outputs.

## What is agentic-evals?

agentic-evals is a Python package for evaluating the quality of LLM and agent outputs programmatically. It runs standalone and is not tied to any agent framework or tracing format.

You provide:

* **Test cases** — expectations (exact match, substring, JSON Schema, tool calls, latency, etc.)
* **Evaluation samples** — actual outputs and execution traces
* **Custom evaluators** (optional) — your own scoring logic or LLM judges

agentic-evals returns:

* **Per-case scores** — individual judgments with explanations
* **Summary metrics** — pass rate, average score, cost, latency, broken down by metric and by tag
* **Pass/fail gates** — CI-ready exit codes for release decisions

## Installation

```bash
pip install agentic-evals
```

Optional: for voice agent evaluation examples with FastAPI:

```bash
pip install "agentic-evals[voice]"
```

## Your first eval in 60 seconds

The simplest way to write an eval:

```python
from agentic_evals import Eval, equals


def my_agent(country: str) -> str:
    return {"France": "Paris", "Japan": "Tokyo"}[country]


Eval(
    "my_first_eval",
    data=[
        {"input": "France", "expected": "Paris"},
        {"input": "Japan", "expected": "Tokyo"},
    ],
    task=my_agent,
    scores=[equals],
)
```

Save as `my_eval.py` and run:

```bash
python my_eval.py
```

Or discover and run all eval files:

```bash
agentic-evals run
```

## Expected result

Both country cases match their expected capitals. This example uses a local function and does not require an API key.

## Next steps

[Understand the core concepts](core-concepts.md) or [run evaluations from the CLI](cli.md).
