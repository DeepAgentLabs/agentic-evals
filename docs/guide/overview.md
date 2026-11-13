# Agentic Evals overview

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

[Start the Agentic Evals quickstart →](quickstart.md)
