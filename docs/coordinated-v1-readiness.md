# Coordinated v1.0 engineering readiness

Evals 0.12.0 remains the scoring/report/gate baseline. The coordinated
candidate acceptance runner installs source-built wheels together with Lens
0.14.0, Sidecar/Tower 0.11.0 and MCP 0.8.0, and verifies that unavailable judge
observations never become successful verification signals. Existing native
report/gate schema 1.0, public API and 0.4-draft evaluation evidence export are
unchanged. Evals does not gain a second judge/verifier contract or perform
runtime enforcement. No Evals dependency floor or patch release is required.

The reproducible matrix, held evidence and release eligibility checks live in
the organization repository's [candidate matrix](https://github.com/DeepAgentLabs/.github/blob/feat/coordinated-v1-readiness/release/candidate.json),
[acceptance runner](https://github.com/DeepAgentLabs/.github/blob/81343e3/scripts/accept_ecosystem.py)
and [readiness gate](https://github.com/DeepAgentLabs/.github/blob/81343e3/scripts/release_readiness.py).
These artifacts are introduced in [organization PR 67](https://github.com/DeepAgentLabs/.github/pull/67);
the matrix branch tracks the reviewed source pins while the scripts above are revision-pinned. Internal
wheel acceptance is separate from independent review and live-provider evidence.
The actual coordinated 1.x consumer acceptance remains a future gate until
review permits the stable schema/API freeze.

Independent acceptance, live/deployment evidence and the stable freeze remain
separate gates. See the [shared release policy](https://github.com/DeepAgentLabs/.github/blob/main/profile/RELEASE_POLICY.md).

## Coordinated 1.0.0 milestone

Version 1.0.0 marks the coordinated DeepAgentLabs milestone on 2026-11-05.
Development and roadmap delivery continue after this release. Existing draft
and candidate schema markers retain their maturity; package versions do not
certify AIOS conformance or production deployment readiness. Independent review,
independent implementations, security/deployment acceptance, live-provider
validation and the stable contract freeze remain tracked follow-up work.
See the [ecosystem release policy](https://github.com/DeepAgentLabs/.github/blob/main/profile/RELEASE_POLICY.md).
