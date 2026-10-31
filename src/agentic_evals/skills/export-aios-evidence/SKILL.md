---
name: export-aios-evidence
description: Attach evaluation results to an AI Operations Specification Run as evaluation evidence, with every judgment tied to the Run object it judged.
---

# Export AIOS evidence

## Trigger

Use this when an `EvaluationReport` has to travel with the operational
record of the run it scored: a Run exported by Agentic Chaos or AgenticLens,
a run Control Tower ingests, or an artifact checked with MCP's
`spec.validate_artifact`. Use it after `report-eval-results`, not instead
of it: the native report and `GateDecision` remain the source of truth.

## Do

1. Decide what each case judged before exporting. Write `targets` as a
   mapping of case ID to the Step ID (or AIOS reference such as
   `{"id": "model-1", "type": "model_interaction"}`) whose output it
   scored. Use `default_target={"id": run_id, "type": "run"}` only when a
   case really judged the whole Run.
2. Call `to_aios_evidence(report, run_id=..., targets=..., gate=decision)`,
   then `attach_aios_evidence(run, export)`, or use
   `agentic-evals aios export REPORT --run run.json --targets targets.yaml`.
3. Let a missing mapping fail. If some cases genuinely have no target in
   this Run, pass `allow_unmapped=True` (`--allow-unmapped`) and report
   `export.unmapped_cases` alongside the artifact.
4. Validate the merged Run with `spec.validate_artifact` and keep its
   `conformance.aligned` result and claim with the artifact.
5. When two reports of the same suite judge one Run (a retry, a second
   judge), give each export its own `id_prefix`.

## Avoid

- Don't point every case at the Run to make the export succeed. That
  states a judgment about the whole Run the report never made.
- Don't drop skipped or `unavailable` evaluations, and don't read them as
  passes; they are exported with their own result and no score value.
- Don't treat an aligned Run as a passing one. Alignment is structural; the
  `release_gate` evaluation and the native `GateDecision.passed` say
  whether the release is ready.

## Check

- Every exported evaluation has at least one `evaluates` target that
  resolves in the Run, or is marked `external: true` (rule `AIOS-0.4-P08`).
- `unmapped_cases`, `skipped_scores` and `unavailable_scores` are reported
  wherever the artifact is shared.
- `spec.validate_artifact` reports `conformance.aligned = true`.

## Risk

Evidence attached to the wrong Step looks just as valid as evidence attached
to the right one. A guessed mapping turns a correct score into a false
statement about a different part of the run, and downstream incident or
release reviews will cite it.
