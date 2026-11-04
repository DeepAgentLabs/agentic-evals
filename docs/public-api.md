# Public API candidate

For v0.12, the names in `agentic_evals.__all__` are the reviewed root API
candidate. The checked-in `tests/fixtures/v0.12/public-api.json` records their
origin and function parameter shapes. CI rejects removed names, changed import
origins, removed parameters, changed parameter kinds and new required arguments.
Existing documented imports from `models`, `evaluators`, `gate`, `runner`,
`scorers`, `packs`, `skills`, `simple`, `judging`, `reliability`, `containment`,
`aios` and `report_contract` continue to work.

Modules and names starting with `_` are private. `cli_commands`, `formatting`
and `live` are implementation modules; use the root run APIs and console CLI.
No existing modules are renamed or removed in this release, preserving sibling
imports. New internal modules must use a leading underscore. Public re-exports
do not make every helper inside their implementation module public.

Deprecations must name a replacement and first removal version in the changelog,
documentation and runtime warning when feasible. Keep a deprecated API for at
least one subsequent minor package release before removal. No API is deprecated
in v0.12. The candidate freeze is checked in CI; stable guarantees remain gated
on the coordinated ecosystem v1.0 release.

The report contract has its own [compatibility policy](report-contract.md).
Before any schema 2.0 change, publish migration notes with old/new JSON examples,
a field mapping, reader/writer upgrade order and overlap period. Preserve 1.x
readers during the transition; never silently reinterpret a 1.0 artifact.
