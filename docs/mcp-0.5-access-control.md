# MCP 0.5.0 hosted access control

[MCP 0.5.0](https://github.com/DeepAgentLabs/mcp-server/releases/tag/v0.5.0) completes MCP Phase 5 with hosted access control. Each hosted key can carry allow and deny tool globs, an expiry and a task scope. The server enforces them at dispatch, outside the model: before each hosted handler runs, it re-authenticates the key and reloads its policy. Revocation, a narrower policy or expiry therefore stops queued calls, retries and calls on existing connections. Calls already running finish. Denied calls return an MCP-local `mcp.access-decision.v1` record, and every hosted call logs `dispatch`/`completion` records that share a `correlation_id`. These records are not AIOS artifacts. `core.access_status` reports a key's effective policy, and operators use `deep-agentic-core-mcp-admin` to narrow or revoke a key by user ID.

## What changes for Evals

- `evals.validate_artifact`, `core.release_check` and the other hosted tools are
  subject to a key's policy. A release bot can be limited to, for example,
  `core.*` and `evals.validate_artifact`.
- The Evals release gate and report schema 1.0 are unchanged. MCP still
  delegates the gate decision to Evals.
- MCP-side denial, revocation-acknowledgement and dispatch/completion evidence
  now exists, but only as the MCP-local `mcp.access-decision.v1` record. Evals
  v0.11 adversarial containment scoring still waits on a shared AIOS evidence
  format and on Sidecar, Chaos and Lens evidence.

## Compatibility

No Evals API change, dependency bump or release. MCP's hosted pins stay at
`agentic-evals==0.10.0`.

See the [MCP hosted access control guide](https://github.com/DeepAgentLabs/mcp-server/blob/v0.5.0/docs/access-control.md).
