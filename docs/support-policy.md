# Support and release compatibility

Evals 0.12 supports CPython 3.10, 3.11, 3.12, 3.13 and 3.14. Every pull request
runs lint, typing, schema drift checks and the offline suite on all five versions.
Wheels are pure Python; platform-specific live targets remain caller-owned.
Removing a supported Python version requires release notes and a minor release.
No end-of-support date is promised for the beta line.

Runtime dependencies stay minimal; no sibling is required. Existing consumer
ranges accepting 0.11 also accept 0.12. The optional `integrity` extra requires
Lens >=0.12,<1. The native report/gate schema remains 1.0, byte-for-byte identical
to 0.11. AIOS exports remain `0.4-draft`.

## Candidate validation matrix

The required downstream workflow installs the candidate distribution over each
consumer's locked environment, verifies its version in an isolated interpreter,
and runs the listed integration tests on Python 3.12. Consumer source revisions
are pinned below and in `.github/workflows/compatibility.yml` for reproducibility.
This tests 0.12 readiness; it is not a v1.0 release-candidate matrix.

| Consumer | Version / revision | Coverage |
| --- | --- | --- |
| agenticlens | 0.12.1 / `5c28ccf0da03` | `tests/test_evaluation.py tests/test_trace_evaluators.py tests/test_calibration.py tests/test_experiments.py tests/test_experiments_v04.py` |
| agenticops-control-tower | 0.9.1 / `fea7c3e06679` | `tests/test_evals_contract.py tests/test_evidence_posture.py tests/test_runbooks.py` |
| mcp-server | 0.6.1 / `ebb78df292be` | `tests/test_evals_contract.py tests/test_evals_aios_evidence.py tests/test_unified.py` |

Chaos 0.10.0, Sidecar 0.9.2 and AIOS repository 0.7.0 retain their existing
native contracts and optional dependency ranges. Evals does not take over fault
execution, runtime supervision or normative schema ownership. Those projects
receive integration notes; documentation-only updates need no package release.
The organization profile records the readiness status.

## Local reproduction

From each consumer checkout, sync its dev environment, then install the local
candidate without replacing the consumer's lock:

```bash
uv sync --extra dev
uv pip install --python .venv/bin/python --no-deps ../agentic-evals
uv run --no-sync pytest tests/test_evals_contract.py --no-cov
```

For Lens use the evaluation/calibration/experiment paths in the table. The
candidate override is deliberate: ordinary `uv run` would restore the locked
published version and accidentally test the previous release. Use `--no-sync`.

## Coordinated major release gates

A future `agentic-evals>=1.0,<2` downstream compatibility run and the coordinated
Lens/Tower/MCP 1.0 release-candidate matrix remain open until those packages
exist. v0.12 completes candidate implementation and current-version evidence;
it does not certify these future gates. Keep the frozen candidate baselines,
publish deprecations for at least one subsequent minor release, and include
migration notes before any report 2.0 change.

See [the public API candidate](public-api.md), [report contract](report-contract.md)
and [executable example index](../examples/README.md).
