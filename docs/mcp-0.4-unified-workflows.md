# MCP 0.4.0 unified workflows

[MCP 0.4.0](https://github.com/DeepAgentLabs/mcp-server/releases/tag/v0.4.0) ships the first Phase 4 unified workflows: `core.compare_runs`, a fail-closed `core.release_check`, `core.incident_summary` and `core.export_report`. MCP judges nothing itself; it composes Lens comparisons, the Evals release gate and Chaos run reports, and missing, malformed or failed-call evidence blocks readiness.

## What MCP reads

- `evaluation_report` must be a native Evals report (`schema_version: "1.0"`).
  It is validated against the bundled Evals 0.9.0 schema, then judged by
  `evaluate_gate` with `GateConfig.model_validate(thresholds)`.
- The gate's `reasons` and `observed` values and the effective `thresholds` are
  returned under the `evaluation` gate.

## Thresholds

- The Evals default applies when `thresholds` is omitted: `min_pass_rate` is 1.0
  and unavailable judgments fail (`max_judge_unavailable_scores: 0`).
- Every `GateConfig` field is accepted, including tag/metric floors, judge cost and
  agreement, and live-target timeout/error limits.
- `GateConfig` ignores unknown keys, so MCP rejects them before calling the gate.

## Compatibility

No Evals API change, dependency bump or release. Invalid reports block the
release as an `invalid` gate instead of passing.

See the [MCP unified workflows guide](https://github.com/DeepAgentLabs/mcp-server/blob/v0.4.0/docs/unified-workflows.md).
