# Advanced evaluation

## Advanced Topics

### Custom Evaluators

Write your own evaluation logic with full access to the test case, output, and trace.

```python
from agentic_evals import (
    LLMJudgeEvaluator,
    CallableEvaluator,
    EvaluationContext,
    Score,
    EvaluatorRegistry,
)


# LLM-based judge
def my_judge(context: EvaluationContext) -> Score:
    output = context.sample.output
    expected = context.case.expected_output

    # Call your LLM here
    judgment = your_llm_model(f"Is this output correct? {output} vs {expected}")

    return Score(
        name="llm_judgment",
        value=1.0 if judgment else 0.0,
        passed=judgment,
        explanation="LLM agrees" if judgment else "LLM disagrees",
    )


registry = EvaluatorRegistry()
registry.register(LLMJudgeEvaluator("my_judge", my_judge))
```

Then use it in your test case:

```python
case = TestCase(
    id="case-1",
    name="Custom judge",
    evaluators=[EvaluatorConfig(name="my_judge", threshold=0.8)],
)
```

### Eval Packs

Bundle a TestSuite with the scorers it needs into one shareable YAML/JSON file:

```yaml
name: my-eval-pack
description: Checks answers for factual consistency.
required_scorers:
  - factuality

suite:
  name: my-eval-pack
  version: "1"
  cases:
    - id: case-1
      name: Check if output is factual
      input: What is the capital of France?
      evaluators:
        - name: factuality
          threshold: 0.8
          config:
            reference: Paris is the capital of France.
```

Load and use it:

```python
from pathlib import Path

from agentic_evals import (
    FACTUALITY,
    LLMRubricEvaluator,
    default_registry,
    evaluate_suite,
    load_pack,
)

registry = default_registry()
registry.register(LLMRubricEvaluator("factuality", FACTUALITY, complete_fn=your_model_call))

pack = load_pack(Path("path/to/pack.yaml"), registry=registry)
report = evaluate_suite(pack.to_suite(), samples, registry=registry)
```

**Built-in packs:**

* `tool-use-correctness` — Evaluate tool selection and arguments
* `json-output-contract` — Validate JSON structure
* `factual-qa` — QA with a caller-registered `factuality` rubric evaluator
* `adversarial-containment` — Bounded authenticated observation scenarios; requires a host-configured verifier

```python
from agentic_evals import load_builtin_pack

pack = load_builtin_pack("tool-use-correctness")
```

### Evaluator Registry

Manage evaluators centrally so test cases can reference them by name:

```python
from agentic_evals import EvaluatorRegistry, default_registry, LLMJudgeEvaluator, CallableEvaluator

# Start with defaults
registry = default_registry()


# Add custom evaluators
def my_rule(context):
    return Score(...)


registry.register(CallableEvaluator("my_rule", my_rule))

# Get an evaluator
evaluator = registry.get("my_rule")
```

## Pack loading and dependencies

`list_builtin_packs()` lists all four installed bundles. `load_builtin_pack(name, *, registry=None)` and `load_pack(path, *, registry=None)` check `required_scorers` against the supplied registry or a new `default_registry()`. `EvalPack.to_suite()` returns its runnable suite. Loading factual-QA needs `LLMRubricEvaluator("factuality", FACTUALITY, complete_fn=...)` registered first; merely naming a scorer does not create a model callback.

Containment is present in the default registry with no trusted verifier. Loading the `adversarial-containment` pack can therefore succeed while its evaluations fail closed until the host replaces that evaluator with a trusted one. See [containment trust setup](containment.md). CLI `pack show` inspects pack data without judge credentials; it does not run the evaluation or establish trust.

See the [complete scorer/rubric catalog](scorers.md) for all registry names, callback requirements, template verdicts and case-expectation interactions. The [public API policy](public-api.md) distinguishes reviewed exports from implementation helpers.
