# Native report and gate contract (1.0)

Agentic Evals 0.7.2 ships Draft 2020-12 JSON Schemas as package data:

- `agentic_evals/schemas/evaluation-report-1.0.schema.json`
- `agentic_evals/schemas/gate-decision-1.0.schema.json`

Use `report_schema()` and `gate_decision_schema()` from `agentic_evals` to
read fresh dictionaries offline. The published documents are generated from
`EvaluationReport` and `GateDecision` in validation mode, preserving optional
fields/defaults for earlier JSON writers. Serialize models with
`model_dump(mode="json")` or `model_dump_json()`; Python-mode datetime objects
are not JSON values. Reports carry `schema_version: "1.0"`; gate decisions
retain their existing unversioned envelope and use the schema document's version.
The schema IDs point at immutable release-tagged documents.

```python
import json
from jsonschema import Draft202012Validator, FormatChecker
from agentic_evals import report_schema, gate_decision_schema

with open("examples/report-contract/evaluation-report.json") as source:
    report = json.load(source)
Draft202012Validator(report_schema(), format_checker=FormatChecker()).validate(report)
with open("examples/report-contract/gate-decision.json") as source:
    gate = json.load(source)
Draft202012Validator(gate_decision_schema()).validate(gate)
```

Install `jsonschema[format-nongpl]` to enforce date-time formats with
`FormatChecker`; JSON Schema format annotations alone do not enforce formats.
Schema validation checks artifact structure, types and declared bounds. It does
not recompute scores, verify summary arithmetic, establish evidence integrity,
or turn a failing gate into a pass. Consumers must inspect `GateDecision.passed`
and retain `reasons`, null cost/provenance and missing-sample information.
`EvalResult` from the quickstart API is a separate format, not this contract.

## Compatibility policy

Within contract `1.x`, changes are additive only: existing fields, types,
constraints and meanings remain compatible; new fields must be optional.
Readers must tolerate unknown properties, including nested properties. Producers
must keep existing fields for at least one minor package release after a
deprecation notice. Removing/renaming fields, adding required fields or changing
existing wire types/semantics requires a `2.0` contract and migration notes.
Package versions and contract versions are independent.

CI compares packaged schemas with current models and checks existing shapes
against frozen schemas from the actual `v0.7.1` tag. Historical fixtures must
not be regenerated to hide a breaking change. To regenerate current schemas:

```bash
uv run python scripts/generate_schemas.py
uv run python examples/report-contract/generate.py
uv run pytest tests/test_report_contract.py
```

The example deliberately contains missing evidence and a failed gate. The
baseline fixtures cover passing, failing and missing samples, metric/tag
breakdowns, nullable costs and provenance. Both built distributions must include
the packaged schemas; CI exercises accessors from an installed wheel.

## Sibling ownership and dependencies

| Consumer | Integration and dependency policy |
|---|---|
| AgenticLens | Its existing Evals dependency accepts 0.7.2. Trace adapters, calibration and diagnosis remain Lens-owned. |
| Control Tower | Reads native reports/gates; validated artifacts retain the same reader shape and native verdict. No new runtime dependency is required. |
| MCP | The schemas describe native Evals output; `spec.validate_artifact` remains AIOS validation and is not a native Evals validator. |
| AI Operations Specification | This package-local contract is not normative AIOS evidence; evaluation evidence export remains Evals v0.10. |
| Sidecar | Supervision outcomes remain distinct from scores. Schema publication does not implement containment scoring. |
| Chaos | Resilience outcomes remain Chaos-owned. Evals retains score and release-gate computation. |

No sibling minimum versions change merely because Evals publishes schemas.
Use `agentic-evals>=0.7.2` only when directly importing the new accessors.
