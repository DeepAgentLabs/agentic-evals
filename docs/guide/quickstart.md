# Quickstart

Run a complete local evaluation before connecting a real agent. This example requires no API key.

## Install

```
python -m pip install agentic-evals
```

## Create the evaluation

first_eval.py · complete file

```python
from agentic_evals import Eval, equals


def answer(country):
    return {"France": "Paris", "Japan": "Tokyo"}[country]


Eval(
    "first-evaluation",
    data=[{"input": "France", "expected": "Paris"}, {"input": "Japan", "expected": "Tokyo"}],
    task=answer,
    scores=[equals],
)
```

[Download first_eval.py](examples/first_eval.py)

## Run it

```
python first_eval.py
```

**Expected:** both cases pass because the local function returns the expected capitals. This proves the scoring path, not the behavior of a real model.

[Use your own data →](custom-data.md)[Use existing traces →](existing-traces.md)
