# Security Policy

## Supported versions

Security fixes are provided for the latest released version.

| Version | Supported   |
| ------- | ----------- |
| Latest  | Yes         |
| Older   | Best effort |

## Reporting a vulnerability

Please report security issues privately using GitHub's private
vulnerability reporting feature on this repository.

Include:

- Affected version or commit
- Reproduction steps
- Impact assessment
- Any suggested mitigation

Please do not open a public issue for suspected vulnerabilities until the
issue has been reviewed.

## Scope

This library scores LLM/agent outputs and traces you supply in-process —
it does not store API keys, manage cloud credentials, or make network
calls on its own. `LLMJudgeEvaluator`/`LLMRubricEvaluator` and
`embedding_similarity` all take a caller-supplied function (`complete_fn`/
`embed_fn`); this package never calls a model or embedding provider
itself.

`run_live_suite()`'s `PythonTarget` executes a caller-specified local
Python callable, and `HTTPTarget` sends requests to a caller-specified
URL. Both are intentionally powerful, developer-facing integrations —
only point them at trusted suite files and trusted target definitions.
This is documented behavior, not a vulnerability, but please report any
way it could be triggered from untrusted input.
