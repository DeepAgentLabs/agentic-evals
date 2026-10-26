# Agentic Evals Use Cases

Practical, end-to-end walkthroughs for scoring agents and gating their releases.
Every use case below was run against **agentic-evals 0.9.0** from PyPI and
lists the exact versions it was tested with. None of them needs a model, an
API key or a network connection.

## Catalog

| Use case | Summary | Difficulty | Capabilities | Verified version |
|---|---|---|---|---|
| [Block a release when one safety case fails](block-an-unsafe-release.md) | A faster candidate passes 5 of 6 cases, clearing an 80% floor. A per-tag floor still blocks it, because the one failure is a refund it was never allowed to make. | Beginner | [Declarative CLI](https://deepagentlabs.io/agentic-evals/docs/cli/), [Tag breakdowns](https://deepagentlabs.io/agentic-evals/docs/core-concepts/#breakdowns-by-metric-and-tag), [Release gates](https://deepagentlabs.io/agentic-evals/docs/api-reference/#release-gates) | 0.9.0 |
| [Catch a right reply reached the wrong way](right-reply-wrong-trajectory.md) | Four refund runs send the same reply and pass every text check. Their traces show a skipped identity check, a $499.90 refund and a loop. | Intermediate | [Tool expectations](https://deepagentlabs.io/agentic-evals/docs/core-concepts/#testsuite-and-testcase), [Trajectory scorers](https://deepagentlabs.io/agentic-evals/docs/api-reference/#trajectory-scorers-trace-aware) | 0.9.0 |
| [Don't let a flaky LLM judge approve a release](gate-on-judge-reliability.md) | Judge each answer three times with retries. A timed-out judgment, an undecided judge and incomplete judge cost each fail the gate. | Intermediate | [Judge reliability](https://deepagentlabs.io/agentic-evals/docs/judge-reliability/), [Rubric scorers](https://deepagentlabs.io/agentic-evals/docs/api-reference/#rubric-scorers-llm-graded) | 0.9.0 |

The three cover a CI gate you can copy today, scoring what an agent did and
not only what it said, and keeping an LLM judge honest.

## Verified package version

- **Package version:** agentic-evals 0.9.0 from PyPI
- **Environment:** Python 3.12.3 on Linux, base dependencies only
- **Verification date:** 2026-10-26
- **Scope:** every command and script in the walkthroughs was run and its output
  copied into the page. The same examples run in this repository's test suite
  ([`tests/test_usecases.py`](../tests/test_usecases.py)), so a change that
  alters their output fails CI.

## Quick navigation

- [Agentic Evals documentation](https://deepagentlabs.io/agentic-evals/docs/)
- [Agentic Evals product page](https://deepagentlabs.io/agentic-evals/)
- [Source on GitHub](https://github.com/DeepAgentLabs/agentic-evals)
