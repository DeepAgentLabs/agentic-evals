# Agentic Evals Roadmap

## Current baseline

As of 2026-10-11, deterministic tool expectations, custom scorers, live targets
and release gates exist. See [README.md](README.md) and [CHANGELOG.md](CHANGELOG.md).

## Adversarial containment scoring (planned; version not assigned)

- [ ] Provide a reusable containment eval pack covering denied tools, stop/revoke
      acknowledgements, subsequent dispatch, authority and fail-closed gate failures.
- [ ] Assert against actual dispatch/completion events; a BLOCK verdict or a safe
      answer alone is not proof of containment.
- [ ] Consume correlated Sidecar/Chaos/MCP observations through optional adapters;
      coordinate common event semantics with AI Operations Specification.
- [ ] Fail gates on missing required evidence, policy versions or event coverage;
      preserve integrity verification status supplied by Lens.
- [ ] Provide zero-violation gates per scenario and configurable acknowledgement
      latency limits; score containment separately from task success.
- [ ] Publish passing and deliberately failing fixtures for post-stop dispatch,
      revoked access, injected instructions and incomplete traces.

Dependencies: Sidecar lifecycle/adapters, Chaos adversarial workflows, MCP
revocation evidence and Lens verification. Evals scores observations; it does
not inject attacks, enforce permissions or prove unobserved behavior.
