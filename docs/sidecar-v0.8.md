# Sidecar 0.8 integration boundary

## Sidecar 0.8 interoperability

Evals 0.7.1 retains standalone scoring and release-gate ownership. Sidecar
supervision outcomes and private-context lifecycle validation are not scores;
broader Agent Alone vs Agent + Sidecar evidence remains Sidecar v0.9 work.

Sidecar 0.8 provides Shared/Exclusive context-only, guardrails-only or combined
configuration, explicit host context delivery and mandatory guardrail composition.
Exclusive rules cannot weaken shared restrictions. Cross-framework privacy,
revocation and delegated authority remain v0.9 validation; stable schemas remain
v1.0. Native correlated Lens readback requires Lens 0.7.1. All sibling packages
stay optional; no dependency floor is increased without a runtime requirement.
See the [Sidecar integration contract](https://github.com/DeepAgentLabs/agentic-sidecar/blob/main/docs/integrations.md).
