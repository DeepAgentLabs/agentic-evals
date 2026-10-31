# AI Operations Specification v0.4-draft fixtures

Copied from [`ai-operations-spec`](https://github.com/DeepAgentLabs/ai-operations-spec)
at commit `091a0fc` so the AIOS evidence export tests validate offline:

- `run.schema.json` and `common.schema.json` from `specification/v0.4/schemas/`
- `run.json` from `specification/v0.4/examples/valid/`

The specification is normative. `tests/test_aios_export.py` compares these
copies with a sibling `ai-operations-spec` checkout (or `AIOS_SPEC_PATH`)
when one is present, so drift fails locally. Do not edit them by hand;
copy them again from the specification.
