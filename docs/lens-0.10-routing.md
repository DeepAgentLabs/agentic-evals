# Lens routing integration boundary

## AgenticLens 0.10.0 routing compatibility

AgenticLens 0.10.0 implements roadmap v0.8: evidence-based runtime model
selection, fail-closed routing constraints, bounded provider failover,
confidence/escalation handoffs, shadow/canary modes and a local routing journal.
The default is advisory; execution uses explicit caller-owned callbacks.
MCP 0.3.12 exposes read-only `lens.routing_decide` and pins hosted Lens 0.10.0.
See the [routing guide](https://github.com/DeepAgentLabs/agenticlens/blob/v0.10.0/docs/routing.md)
and [offline example](https://github.com/DeepAgentLabs/agenticlens/blob/v0.10.0/examples/routing_demo.py).

Lens retains `agentic-evals>=0.7.1,<1`, which covers current Evals 0.8.0.
Standalone scoring and release-gate computation remain Evals-owned. Routing
outcomes do not redefine native evaluation reports or gate decisions. No dependency
change or Evals patch release is required.
