# Write custom scorers

Extend the default registry with a business rule. Download these files alongside the trace fixtures from [the existing-trace workflow](existing-traces.md).

custom_registry.py · complete file

```python
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
```

[Download custom_registry.py](examples/custom_registry.py)

add_custom_check.py · complete file

```python
import json
from pathlib import Path
from agentic_evals import EvaluatorConfig, load_suite

suite = load_suite("suite.traces.yaml")
for case in suite.cases:
    case.evaluators.append(EvaluatorConfig(name="short_answer", threshold=1.0))
Path("suite.custom-check.json").write_text(
    suite.model_dump_json(indent=2), encoding="utf-8"
)
```

[Download add_custom_check.py](examples/add_custom_check.py)

```
python add_custom_check.py
agentic-evals evaluate suite.custom-check.json samples.traces.jsonl --registry custom_registry --out report.custom-check.json
```

The new character-limit score does not hide the existing forbidden-tool failure. Use score explanations to keep each rule inspectable.
