# Coordinated v1.0 engineering readiness

Evals 0.12.0 remains the scoring/report/gate baseline. The coordinated
candidate acceptance runner installs source-built wheels together with Lens
0.14.0, Sidecar/Tower 0.11.0 and MCP 0.8.0, and verifies that unavailable judge
observations never become successful verification signals. Existing native
report/gate schema 1.0, public API and 0.4-draft evaluation evidence export are
unchanged. Evals does not gain a second judge/verifier contract or perform
runtime enforcement. No Evals dependency floor or patch release is required.

The reproducible matrix, held evidence and release eligibility checks live in
the organization repository's release/candidate.json and scripts/. Internal
wheel acceptance is separate from independent review and live-provider evidence.
The actual coordinated 1.x consumer acceptance remains a future gate until
review permits the stable schema/API freeze.

Independent acceptance, live/deployment evidence and the stable freeze remain
separate gates. See the [shared release policy](https://github.com/DeepAgentLabs/.github/blob/main/profile/RELEASE_POLICY.md).
