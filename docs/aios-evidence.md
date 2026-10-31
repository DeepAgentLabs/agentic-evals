# AIOS evaluation evidence export (0.10.0)

Agentic Evals 0.10.0 exports evaluation results as
[AI Operations Specification](https://github.com/DeepAgentLabs/ai-operations-spec)
`0.4-draft` `evaluation` evidence. The evidence attaches to a Run artifact that
another tool produced, such as Agentic Chaos `to_aios_run`, an AgenticLens
export or your own recorder, so a judgment travels with the run it judged.

The native `EvaluationReport` and `GateDecision` stay the source of truth. The
export is derived from them and states only what they record.

## What is exported

| Native result | AIOS evidence (`type: evaluation`) | Event |
|---|---|---|
| each `Score` | `criterion` = `Score.metric`; `method` = evaluator, version and type; `result`; `score` | `aiops.evaluation.completed` |
| a skipped `Score` | `result: "skipped"`, no `score` | none, because nothing was judged |
| an unavailable judge `Score` | `result: "unavailable"`, no `score` | `aiops.evaluation.failed` |
| each `CaseEvaluation` | `criterion: "case_verdict"`, `result` from `passed` | `aiops.evaluation.completed` |
| an optional `GateDecision` | `criterion: "release_gate"`, `reasons`, `observed`; it evaluates the Run | `aiops.evaluation.completed` |

Each object's `status` equals its `result`. `attributes` also carry the score
name, `required`, the explanation, suite name and version, case ID and name,
trace ID and the score metadata (for example the `judge_*` usage keys).
Producer details are in the `io.deepagentlabs.agentic-evals` extension. Every
evaluation has one `evaluates` relationship per target, as rule
`AIOS-0.4-P08` requires.

## Map cases to targets

The report does not know which Step of a Run produced each output, so you
supply the mapping:

```yaml
# targets.yaml: case ID -> what that case judged
grounded-answer: step-answer               # a string is a Step ID
refund-tool:
  - step-refund
  - {id: tool-1, type: tool_invocation}    # any AIOS v0.4 reference
lens-replay:
  - {id: trace-9, type: run, external: true}  # an object outside this Run
```

`default_target` covers cases the mapping does not name. Use
`{"id": run_id, "type": "run"}` (`--default-run` on the CLI) only when those
cases really judged the whole Run.

The export fails loudly instead of guessing:

- no `targets` and no `default_target` raises `AIOSExportError`, because
  every evaluation would be orphaned
- a case with no target raises and names the case. With
  `allow_unmapped=True` the case is left out and listed in `unmapped_cases`
- a `targets` key that is not a case in the report raises (it is usually a typo)
- a reference type outside the AIOS v0.4 vocabulary raises

## Python

```python
import json

from agentic_evals import GateConfig, attach_aios_evidence, evaluate_gate, to_aios_evidence

gate = evaluate_gate(report, GateConfig())
run = json.load(open("run.json"))  # an AIOS 0.4-draft run artifact

export = to_aios_evidence(
    report,
    run_id=run["id"],
    targets={"grounded-answer": "step-answer", "refund-tool": "step-refund"},
    gate=gate,
)
merged = attach_aios_evidence(run, export)  # a new dict; `run` is unchanged
```

`attach_aios_evidence` checks that the export's `run_id` matches the Run, that
every non-external target exists in the Run with the declared type, and that
no evidence, relationship or event ID is already taken. It accepts a list of
exports. Give two exports of the same suite (a retry or a second judge)
distinct `id_prefix` values.

## CLI

```bash
agentic-evals aios export report.json \
  --run run.json --targets targets.yaml --gate gate-decision.json \
  --out run-with-evaluations.json
```

Without `--run`, the command prints the evidence (`--run-id` is then
required). `--default-target STEP_ID`, or a JSON reference or list, and
`--default-run` set the fallback target, and `--allow-unmapped` lists the
left-out cases on stderr. Mapping, validation and merge errors exit 2; a
failing gate is exported as a failed `release_gate` evaluation and still
exits 0. Use `agentic-evals gate` to block a release.

## Validate the result

Evals does not ship an AIOS validator. Validate the merged Run with
`deep-agentic-core-mcp`'s `spec.validate_artifact`, which applies the schemas
and semantic rules published by `ai-operations-spec`:

```python
from deep_agentic_core_mcp.adapters.ai_operations_spec import validate_artifact

result = validate_artifact(merged)
assert result["conformance"]["aligned"]
```

Alignment is structural. It does not mean the evaluation passed, the target
mapping was right, or the scored behavior was correct. Read the `result` of
each evaluation and the native `GateDecision.passed`.

The [runnable example](https://github.com/DeepAgentLabs/agentic-evals/tree/main/examples/aios)
scores a support conversation, gates it and attaches the evidence to
`run.json`. Its merged `run-with-evaluations.json` is aligned under MCP 0.4,
and its gate stays failed because the refund call is missing its order ID.
Regenerate it with `uv run python examples/aios/generate.py`.

## Compatibility

- AIOS `spec_version` `0.4-draft` only. This is draft alignment, not stable
  conformance; consumers must validate before treating an artifact as aligned.
- The native report schema stays `1.0` and is unchanged. Sibling runtime
  dependencies are unchanged, and the export imports no sibling package.
- Producers of the Run (Chaos, Lens) keep owning steps, occurrences and
  run status. Evals adds evidence, relationships and events only.
- Containment scoring is still roadmap v0.11. An exported pass is not proof of
  containment or safety.
