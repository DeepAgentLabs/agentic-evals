# Agentic Evals

## Agentic Evals overview

Did the recorded behavior meet our quality requirements?

Test cases, actual outputs, normalized traces, and optional judge callbacks. Per-case scores, summary metrics, and a separate release-gate decision.

**When to start here**

Evaluate two recorded answers, then add tool evidence.

## Inputs and outputs

| You provide | You receive |
| --- | --- |
| Test cases, actual outputs, normalized traces, and optional judge callbacks. | Per-case scores, summary metrics, and a separate release-gate decision. |

## Execution boundary

A report is not a release approval. Tool checks require complete tool evidence; optional model judges need your provider integration.

[Start the Agentic Evals quickstart →](guide/quickstart.md)

## Capabilities

Use these capabilities to address evaluate tasks in your application.

| Capability | What it provides |
| --- | --- |
| Deterministic scoring | Check text, JSON, numeric values, required fields, and explicit expectations. |
| Tool behavior | Inspect required/forbidden tools, typed arguments, first-call order, and trajectory metrics. |
| Custom evaluators | Register project-specific business rules with explanations. |
| LLM rubric judges | Supply your model callback, rubric, retry policy, and repeated judging requirements. |
| Saved and live suites | Score recorded observations or invoke a Python/HTTP target. |
| Release gates | Apply overall, metric-specific, and tag-specific policy to native reports. |

## Supported scope

A report is not a release approval. Tool checks require complete tool evidence; optional model judges need your provider integration.

## Core concepts

| Concept | Meaning |
| --- | --- |
| TestCase | Defines input and expectations; it is not generated from the answer being scored. |
| EvaluationSample | Matches a case ID to observed output and an EvalTrace. |
| EvalTrace / EvalSpan | Minimal normalized evidence, including tool name, arguments, latency, cost and metadata. |
| Score | A named result with a numeric value, pass/fail outcome, explanation, and evaluator identity. |
| Report vs gate | A report records scores; a GateConfig decides whether that evidence meets release policy. |
| Skipped vs unavailable | Not-applicable scoring is different from a judge that failed to deliver a verdict. |

## Recommended workflow

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

## Next steps

Evaluate two recorded answers, then add tool evidence.

[Open the developer quickstart →](guide/quickstart.md)
