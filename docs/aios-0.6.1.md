# AIOS v0.6.1 compatibility

AI Operations Specification repository v0.6.1 adds the first v0.6.x drafts:

- [provenance records](https://github.com/DeepAgentLabs/ai-operations-spec/blob/v0.6.1/specification/v0.6/provenance.md): a
  `spec_version: "0.6-draft"`, `artifact_type: "provenance"` companion artifact
  with subjects, source references, derived findings and evidence lineage;
- a [portable conformance suite](https://github.com/DeepAgentLabs/ai-operations-spec/tree/v0.6.1/specification/v0.6/conformance-suite)
  with expected outcomes and rule citations;
- [naming conventions](https://github.com/DeepAgentLabs/ai-operations-spec/blob/v0.6.1/specification/v0.6/naming-conventions.md).

Run and Workflow artifacts stay `0.4-draft`; the v0.4 schemas and
`AIOS-0.4-*` rule catalog are unchanged, so existing exports remain valid.
Consumers that do not check `0.6-draft` must reject provenance records under
`AIOS-0.5-V03` rather than validate them against v0.4.

## Agentic Evals

The 0.10 `evaluation` evidence export stays `0.4-draft`. An exported evaluation can be an `aios_object` source of a provenance finding, but a gate decision is not a provenance finding and a cited score proves nothing about the finding. Evals does not emit provenance records.

## Dependencies

No runtime dependency floor changes and no package release are needed for
this documentation alignment. Independent review is still pending; passing the
suite or holding a verified provenance record is not stable conformance and
does not show that any artifact or finding is true. See the
[AIOS ecosystem guide](https://github.com/DeepAgentLabs/ai-operations-spec/blob/v0.6.1/docs/v0.6.1-ecosystem.md).
