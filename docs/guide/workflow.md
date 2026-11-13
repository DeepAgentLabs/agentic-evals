# Recommended workflow

## Choose evidence before choosing a scorer

| You need to check | Provide | Use |
| --- | --- | --- |
| Exact contract | Expected answer, JSON shape, or typed value | Deterministic checks |
| Tool behavior | Complete actual tool calls and arguments | Tool expectations and trajectory scorers |
| Qualitative answer quality | Relevant input/reference/context plus output | A calibrated rubric judge |
| Business policy | Facts needed to decide the rule | A custom evaluator |

## Evaluate recorded runs

Start with independently reviewed cases. Map output and trace fields into native samples. Run the suite, inspect failure explanations, then apply the gate. Do not repair historical observations just to obtain a pass.

## Evaluate a changed agent

Invoke the actual candidate against the same task set. Saved old traces cannot establish that new code improved. Preserve task IDs and compare matched cases.

## Build useful coverage

- Include ordinary tasks, ambiguous requests, tool failures, and cases that require restraint.
- Keep a held-out review set when changing prompts or criteria.
- Inspect failures by metric and tag; an overall mean can hide a critical subset.
- Keep unknown duration or cost distinguishable from actual zero measurements.
