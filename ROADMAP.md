# agentic-evals — Roadmap

`agentic-evals` is the **EVALUATE** layer of the DeepAgentLabs ecosystem: a
standalone, framework-agnostic engine that scores LLM and agent outputs and
turns the scores into release-gate decisions. This roadmap lists what has
shipped and the releases planned next. Every planned release has concrete
deliverables, acceptance criteria and sibling dependencies.

## Release Status

- **v0.1** ✅ Complete — Standalone evaluation engine extracted from AgenticLens (`0.1.0`, `0.1.1`)
- **v0.2** ✅ Complete — Built-in scorer library: text, rubric, trajectory (`0.2.0`)
- **v0.3** ✅ Complete — Methodology skills and runnable eval packs (`0.3.0`)
- **v0.4** ✅ Complete — `Eval()` quickstart API and `agentic-evals run` CLI (`0.4.0`)
- **v0.5** ✅ Complete — Expanded scorers, rubric templates and the full skills lifecycle (`0.5.0`)
- **v0.6** ✅ Complete — Gate defaults and scorer correctness fixes (`0.6.0`)
- **v0.7** ✅ Complete — Metric/tag breakdowns, tool-argument expectations, score provenance and concurrent live runs (`0.7.0`, `0.7.1`)
- **v0.7.x** ✅ Complete — Published report and gate contract (JSON Schema, `0.7.2`)
- **v0.8** ✅ Complete — Suite, pack and gate CLI for CI (`0.8.0`)
- **v0.9** ✅ Complete — Judge reliability, cost and live-target resilience (`0.9.0`)
- **v0.10** 🚧 Planned — AI Operations Specification evaluation evidence export
- **v0.11** ⛔ Blocked — Adversarial containment scoring (needs Sidecar, Chaos, MCP and Lens evidence)
- **v1.0** 🚧 Planned — Stable API and report schema

Current release: `0.9.0` (2026-10-19). See [CHANGELOG.md](CHANGELOG.md) for
what each version shipped.

## Scope

**Owns:** scoring (deterministic checks, scorers, LLM-as-judge and custom
evaluators), evaluation reports and their breakdowns, and release-gate
computation from a report.

**Does not own:**

- Trace capture, instrumentation and retrospective diagnosis: these belong to
  `agenticlens`.
- Fault injection and attack execution: `agentic-chaos`.
- Runtime decision supervision and enforcement: `agentic-sidecar`.
- The canonical artifact model: `ai-operations-spec`.
- MCP exposure: `deep-agentic-core-mcp`.
- Fleet presentation: `agenticops-control-tower`.

Evals scores the observations it is given. It does not run agents beyond its
live-target harness, inject faults, enforce permissions, or prove behavior it
did not observe.

## Cross-Project Dependencies

| Project | Relationship | Releases |
|---|---|---|
| `agenticlens` | Consumes Evals for scoring (`agenticlens>=0.6.0` requires `agentic-evals>=0.7.1`). Lens owns datasets, calibration, experiments and diagnosis. Lens 0.7.0 registers its trace-aware evaluators next to Evals' built-in scorers and reports judge cost and evaluator disagreement from Evals `Score` metadata; Evals 0.9.0 writes the same `judge_*` keys for its own judges. | v0.7.x, v0.9 ✅ |
| `agenticops-control-tower` | Tower 0.6.1 validates complete native reports/gates against published Evals 0.7.2 schemas before evidence projection and staging recovery verification; its 0.9.0-schema sync is a patch release. Normative AIOS mappings remain future work. | v0.7.x, v0.9, v1.0 |
| `ai-operations-spec` | Defines the `evaluation` evidence object and the `evaluates` relationship (v0.4 rule `AIOS-0.4-P08`) that report exports must follow | v0.10 |
| `deep-agentic-core-mcp` | MCP 0.3.8 exposes native `evals.validate_artifact` and validates Lens report consumers; its bundled schemas sync to Evals 0.9.0 in a patch release. `spec.validate_artifact` remains the separate AIOS evidence validator. | v0.9, v0.10 |
| `agentic-sidecar` | Its v0.9 compares Agent Alone vs. Agent + Sidecar and uses Evals for generic scoring. Sidecar keeps supervision scenarios. | v0.11 |
| `agentic-chaos` | Its adversarial containment work scores with Evals, and attacks run on isolated targets. Chaos 0.6.0 contracts (`pytest --chaos`) are per-run resilience checks over a `ChaosReport`, not scores or release gates; gate computation stays here. | v0.11 |

Each release below records its links as:

- **Depends on:** a sibling capability that must exist first.
- **Coordinate with:** a sibling to update in the same window.
- **Validate in:** sibling readers, fixtures or tests to check before closing the item.

## Definition of Done

A roadmap item is done only when all applicable work is complete:

- implementation is merged and reachable through the public Python API, the CLI,
  or an exported artifact
- tests cover the behavior, including deliberately failing fixtures for gates
  and scorers
- README examples and the relevant `skills/` playbooks are added or updated
- reports saved by earlier versions still load, or the change is called out as
  breaking in the changelog
- sibling dependency checks listed under **Validate in** have been run
- release metadata (`pyproject.toml`, `src/agentic_evals/_version.py`,
  `CHANGELOG.md`) is updated for release-ready work

---

## Shipped

### v0.1 — Standalone evaluation engine ✅ (`0.1.0`, `0.1.1`)

- [x] `EvalTrace`/`EvalSpan`, `Score`, `Evaluator`/`EvaluatorRegistry`,
      `TestCase`/`TestSuite`, `evaluate_suite`
- [x] `run_live_suite` for Python and HTTP live targets
- [x] `GateConfig`/`evaluate_gate`
- [x] zero dependency on AgenticLens or any other DeepAgentLabs project
- [x] `trace_adapter` hook for traces that don't match `EvalTrace` (`0.1.1`)

### v0.2 — Built-in scorer library ✅ (`0.2.0`)

- [x] `scorers.text` (deterministic), `scorers.rubric` (provider-neutral
      LLM-graded) and `scorers.trajectory` (reads spans)
- [x] `default_registry()` with every built-in scorer under a stable name

### v0.3 — Skills and eval packs ✅ (`0.3.0`)

- [x] `agentic_evals.skills` methodology playbooks
- [x] `agentic_evals.packs` with validated `load_pack()`/`load_builtin_pack()`
      and three built-in packs

### v0.4 — Quickstart API and CLI ✅ (`0.4.0`)

- [x] `Eval(name, data=..., task=..., scores=[...])`
- [x] `agentic-evals run` discovers eval files and exits non-zero on failure

### v0.5 — Scorer and skills expansion ✅ (`0.5.0`)

- [x] four new text scorers, five new rubric templates and two quickstart scorers
- [x] skills cover the full eval lifecycle (17 playbooks)

### v0.6 — Gate defaults and correctness ✅ (`0.6.0`)

- [x] `GateConfig` thresholds other than `min_pass_rate` default to "not
      checked"
- [x] fixes to `numeric_diff`, empty-trace trajectory scorers and judge-verdict
      parsing

### v0.7 — Breakdowns, tool expectations and provenance ✅ (`0.7.0`, `0.7.1`)

- [x] per-metric and per-tag summaries, `Score.metric`, `Score.skip()`
- [x] tag and metric pass-rate gates
- [x] expected tool-argument values and tool-call order checks; `make_rubric()`
- [x] `Score.evaluator`/`evaluator_version`, cost provenance
      (`cost_source`, `priced_cases`), `sample_available` (`0.7.1`)
- [x] `run_live_suite(..., max_workers=N)` and Python/HTTP parity tests (`0.7.1`)

The repository also carries a worked example, `voice-agent-evals/`: a
simulated voice support agent evaluated end to end.

---

## Planned

### v0.7.x — Published report and gate contract ✅ (`0.7.2`)

**Goal:** let consumers such as Control Tower, Lens and MCP validate Evals
output against a published contract instead of mirroring the pydantic models.

**Deliverables:**

- [x] JSON Schema documents for `EvaluationReport` (`schema_version` `1.0`) and
      `GateDecision`, generated from the models and shipped as package data
- [x] `agentic_evals.report_schema()` / `gate_decision_schema()` accessors
- [x] tests that fail if the models and the shipped schemas drift
- [x] a checked-in sample report and gate decision under `examples/` that
      validate against the schemas
- [x] README section describing the report contract and its additive-only
      change policy within `1.x`

**Acceptance criteria:**

- every report written by `0.7.1` validates against the published schema
- a field change that would break an older reader fails CI

**Coordinate with:** `agenticops-control-tower` (native report reader).
**Validate in:** Tower's Evals reader tests and Lens's `agentic-evals` integration.

Implemented in [report-contract.md](docs/report-contract.md); the wire shape is unchanged.

### v0.8 — Suite, pack and gate CLI for CI ✅ (`0.8.0`)

**Goal:** make the declarative `TestSuite` and gate path usable from CI without
writing Python, alongside `run`, which covers `Eval()` files.

**Deliverables:**

- [x] `agentic-evals evaluate SUITE SAMPLES --out report.json` (YAML/JSON suites,
      JSON/JSONL samples, optional `--registry` module for custom evaluators)
- [x] `agentic-evals live SUITE --target ...` wrapping `run_live_suite`,
      including `--max-workers`
- [x] `agentic-evals gate REPORT --config gate.yaml` with documented exit codes
      (0 pass, 1 gate failed, 2 usage or input error)
- [x] `agentic-evals pack list` / `pack show NAME` for the built-in packs
- [x] CI output formats: JUnit XML and a Markdown summary
      (`--format junit|markdown|json`)
- [x] a GitHub Actions example under `examples/ci/`

**Acceptance criteria:**

- a deliberately failing fixture suite makes `gate` exit 1 in CI
- the CLI produces the same report as the equivalent Python call
- JUnit output loads in a standard JUnit reader

**Depends on:** v0.7.x report schema (for `--format json` output).
**Validate in:** the `voice-agent-evals/` example converted to the CLI path.

Implemented in [the CLI guide](docs/cli.md), with passing and failing CI fixtures,
Python/HTTP parity tests and the voice example exercised by tests. Native schema
1.0 is unchanged; no sibling runtime dependency floor increase is required.

### v0.9 — Judge reliability, cost and live-target resilience ✅ (`0.9.0`)

**Goal:** make LLM-judged and live-target evaluations dependable and accounted
for.

**Deliverables:**

- [x] judge cost and latency recorded on each judge `Score` (tokens, cost,
      `cost_source`) and summed into `EvaluationSummary`
- [x] judge retry policy with bounded attempts, and an explicit "judge
      unavailable" outcome that is never silently scored as a pass
- [x] repeated judging (`samples=N`) with agreement reported per case, so a
      flaky judge can be detected rather than averaged away
- [x] live-target retries with backoff, and per-case timeout reporting
      (`timed_out` distinguished from failed)
- [x] async evaluators and async Python targets alongside the existing
      thread-based concurrency

**Acceptance criteria:**

- a judge that errors on some calls produces a report that names the affected
  cases and does not pass the gate by default
- judge cost totals match the per-score values in tests

**Coordinate with:** `agenticlens` (its v0.5 judge cost recording and
calibration consume these fields). Scoring stays in Evals; Lens owns
calibration. Lens 0.7.0 already records judge usage on `Score.metadata`
(`judge_cost_usd`, `judge_cost_source`, `judge_input_tokens`,
`judge_output_tokens`, `judge_latency_ms`, `judge_model`, `judge_provider`)
and sums it in `analyze_scores()`; adopting the same keys here keeps one
contract instead of two.
**Validate in:** Lens calibration and experiment tests against the new fields.

Implemented in [the judge reliability guide](docs/judge-reliability.md):
`JudgeResponse` usage and `summary.judge`, `RetryPolicy`, unavailable judge
scores that fail the default gate (`max_judge_unavailable_scores=0`),
`samples=N` with `min_judge_agreement`, per-case `target_status` with
`summary.live`, and `aevaluate_suite`/`arun_live_suite`. Both acceptance criteria
are covered by tests (`tests/test_judge_reliability.py`). Report schema 1.0 gains
optional fields only. Lens 0.10.0's full test suite passes against 0.9.0 with
no change, and its `>=0.7.1,<1` range already allows it. MCP and Control Tower
sync their bundled schemas to 0.9.0 in patch releases.

### v0.10 — AI Operations Specification evaluation evidence export

**Goal:** make evaluation results portable as shared operational evidence.

**Deliverables:**

- [ ] `to_aios_evidence(report, run_id=..., targets=...)` producing AIOS
      v0.4-draft `evaluation` evidence objects. Each object carries criterion,
      method (scorer/evaluator and version), result and score in `attributes`,
      and `evaluates` relationships to the run or step it judged.
- [ ] merge helper that attaches the evidence to an existing AIOS `run` artifact
- [ ] the export states only what the report records: a skipped score is not
      exported as a pass, and an unmapped target is reported, not guessed
- [ ] tests that validate exports against the published v0.4 schema and the
      spec's semantic checks (rule `AIOS-0.4-P08`: every evaluation has an
      `evaluates` target) when an `ai-operations-spec` checkout is present

**Acceptance criteria:**

- an exported run passes `deep-agentic-core-mcp`'s `spec.validate_artifact`
  with `conformance.aligned = true`
- a report scored with no target mapping fails loudly instead of producing
  orphaned evidence

**Depends on:** `ai-operations-spec` v0.4-draft evidence model and the v0.5.1
conformance catalog.
**Coordinate with:** `agentic-chaos` (its run export provides the target steps)
and `agenticlens`.
**Validate in:** `deep-agentic-core-mcp` `spec.validate_artifact`.

### v0.11 — Adversarial containment scoring ⛔ Blocked

**Goal:** score whether an agent stayed contained after stop, revoke or deny
instructions. This is scored separately from task success, using observed
evidence rather than claims.

**Deliverables:**

- [ ] Provide a reusable containment eval pack covering denied tools, stop/revoke
      acknowledgements, subsequent dispatch, authority and fail-closed gate failures.
- [ ] Assert against actual dispatch/completion events; a BLOCK verdict or a safe
      answer alone is not proof of containment.
- [ ] Consume correlated Sidecar/Chaos/MCP observations through optional adapters;
      coordinate common event semantics with AI Operations Specification.
- [ ] Fail gates on missing required evidence, policy versions or event coverage;
      preserve integrity verification status supplied by Lens.
- [ ] Provide zero-violation gates per scenario and configurable acknowledgement
      latency limits; score containment separately from task success.
- [ ] Publish passing and deliberately failing fixtures for post-stop dispatch,
      revoked access, injected instructions and incomplete traces.

**Acceptance criteria:**

- the deliberately bypassed-enforcement negative control fails the gate
- missing evidence fails the gate instead of passing it

**Blocked by:**

- `agentic-sidecar` v0.9: lifecycle and dispatch evidence, and revoked-authority fixtures
- `agentic-chaos` adversarial workflows on isolated targets
- `deep-agentic-core-mcp` revocation and dispatch evidence (its Phase 5 hosted access-control items, moved from Phase 4)
- `agenticlens` integrity verification, still open on its roadmap

**Validate in:** Control Tower's zero-violation gate checks and Sidecar's
Agent Alone vs. Agent + Sidecar fixtures.

Evals scores observations; it does not inject attacks, enforce permissions or
prove unobserved behavior.

### v1.0 — Stable API and report schema

**Goal:** a public API and report format others can depend on without pinning
minor versions.

**Deliverables:**

- [ ] audit and freeze the public API (`__all__`), and mark internal modules
      private
- [ ] report schema `1.x` with an additive-only policy, a deprecation window of
      at least one minor release, and migration notes for any `2.0` change
- [ ] documentation site covering the declarative API, CLI, scorers, gates and
      skills, with every example executed in CI
- [ ] support policy: Python versions and the sibling versions validated per
      release

**Acceptance criteria:**

- a downstream project pinned to `agentic-evals>=1.0,<2` keeps working across
  `1.x` releases in compatibility tests
- Lens, Tower and MCP integrations pass against the `1.0` release candidate

**Depends on:** v0.7.x, v0.8 and v0.9 complete; v0.10 complete or explicitly
deferred.

---

## Release process

See [CONTRIBUTING.md](CONTRIBUTING.md#releases): bump `_version.py`, add a dated
`CHANGELOG.md` section, merge, then push a `vX.Y.Z` tag. `release-pypi.yml`
publishes to PyPI from the tag. When a release closes a roadmap item, update the
Release Status above and tick its deliverables in the same change.

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

## Control Tower 0.6.0 integration

Tower Phase 6 and 6A ship together in 0.6.0 with MCP 0.3.6: evidence-cited
investigation, exact-preview human approval and verified deterministic staging
recovery. Native producer outcomes and package ownership remain unchanged.
See [compatibility, examples and dependency matrix](docs/control-tower-0.6.md).
This is documentation alignment; no package release or dependency bump is needed.

## Native consumer validation

MCP 0.3.8 adds `evals.validate_artifact` and validates Lens report inputs and
produced SLO gates. Control Tower 0.6.1 validates complete reports and supplied
gates before evidence projection. Both bundle exact Evals 0.7.2 schemas for
offline, sibling-independent validation. See [the consumer matrix](docs/report-contract.md).

## AgenticLens 0.8.0 suite management

AgenticLens 0.8.0 delivers its v0.6 milestone: `agenticlens.suites` and
`agenticlens suite` build regression suites from CSV/JSON imports, production
traces and user feedback. It masks PII by default before storage (`--no-mask`
opts out), detects duplicates and
conflicting labels, adds synthetic variations and stable splits, records
reviews, and approves suites into immutable, hash-verified versions that CI
verifies, exports and evaluates. Suites stay plain agentic-evals `TestSuite`
files.

Evals runs these suites unchanged with `evaluate_suite` and `run_live_suite`.
Lens keeps management state (lineage, review status, domain, split) in
`TestCase.metadata` and `tags`, and an exported approved version adds
`metadata.agenticlens_suite_version` (name, version, SHA-256, approver).
Suite approval is not a release gate: scoring and gate computation stay in
Evals. No Evals change or release is needed.

See the [suite management guide](https://github.com/DeepAgentLabs/agenticlens/blob/v0.8.0/docs/suite-management.md).

## AgenticLens 0.9.0 ModelFit

AgenticLens 0.9.0 delivers its v0.7 milestone: `agenticlens.modelfit` and
`agenticlens modelfit` recommend a model per task category from recorded
experiment reports, under hard quality, cost, latency, safety, provider and
deployment constraints that fail closed. Each recommendation carries a
confidence level with reasons, an explanation, alternatives, a fallback
(on a different provider when one is feasible), savings against a reference variant tied to the
experiment evidence, and quality risks, plus a task-level model matrix.

Evals is unchanged. ModelFit reads the native evaluation reports that Lens
experiments embed per trial (`cases[].passed`, `latency_ms`, `cost_usd`,
`tags`, `metadata`) and computes no release gate; scoring and gate
computation stay in Evals. Lens keeps its `agentic-evals>=0.7.1,<1`
dependency. No Evals change or release is needed.

See the [ModelFit guide](https://github.com/DeepAgentLabs/agenticlens/blob/v0.9.0/docs/modelfit.md).

## Chaos 0.7.0 interoperability

Chaos 0.7.0 adds sequential fault cascades, deterministic monotonic breaking-point
search, synthetic response poisoning (including prompt/tool-response instruction
and policy-bypass payloads), and explicit-price retry cost estimates. Native
child event IDs and fault types remain intact; cascade IDs/stages and poisoning
strategy/payload/seed are additive event detail. Existing report readers and
AIOS exports remain compatible.

See the [v0.7 guide and offline synthetic example](https://github.com/DeepAgentLabs/agentic-chaos/blob/v0.7.0/docs/v0.7.md).
The example includes observed synthetic dispatches and a bypassed negative
control. Injection or recovery alone does not prove containment. No new shared
schema, automatic adapter, hosted execution capability or containment guarantee
is introduced.

Scores and release gates remain owned by Evals; Chaos contracts and threshold trials are per-campaign evidence. Convert observations to native EvaluationSamples explicitly. No runtime dependency or patch release is needed.

## Control Tower 0.7.0 fleet operations

Tower 0.7.0 adds frozen environment/capability targeting, bulk desired settings,
separate approval, durable per-target results and bounded stop/MCP-revocation
acknowledgement through Python, HTTP and CLI. No fleet atomicity or automatic
rollback/resume is claimed. Timed-out/requested commands need host reconciliation.

Evals retains scoring and native report/gate decisions. Bulk execution does not recompute gates or equate passing evaluation with deployment health or containment.

Existing optional dependency ranges remain sufficient. No sibling runtime or
native evidence schema changes are required; this documentation alignment needs
no patch release. See the [operator guide](https://github.com/DeepAgentLabs/agenticops-control-tower/blob/v0.7.0/docs/fleet-operations.md).

See the [local Tower compatibility guide](docs/tower-0.7-fleet-operations.md) for the operator workflow and package boundaries.

## AgenticLens 0.10.0 routing compatibility

See the [local integration boundary guide](docs/lens-0.10-routing.md).

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

## Chaos 0.8.0 interoperability

Chaos 0.8.0 adds:

- multi-stage chaos workflows: steps, steady-state health checks, parallel
  branches, approval gates that can be resumed, and reusable templates
- declarative YAML/JSON/TOML experiments, with validation that never executes
  targets and cron schedule previews
- `Scope` explosion-radius control (steps, providers and exclusions) on every
  built-in fault and `cascade()`; custom faults get it by calling
  `BaseFault.__init__`, setting `scope` or overriding `in_scope()`
- a topology fuzzer that weights fault placement by fan-out

Native event IDs and fault types are unchanged. Workflow provenance
(`detail.workflow`) and an optional `ChaosReport.workflow` summary are
additive. A workflow's steps merge into one native report for contracts and
AIOS export.

See the [v0.8 guide](https://github.com/DeepAgentLabs/agentic-chaos/blob/v0.8.0/docs/v0.8.md)
and the [offline examples](https://github.com/DeepAgentLabs/agentic-chaos/tree/v0.8.0/examples/workflows).
Workflow statuses, health checks and fuzz outcomes are resilience evidence.
They are not scores, release gates or proof of containment. No new shared
schema, automatic adapter or hosted execution capability is introduced.

Workflow statuses and per-step contracts are per-run resilience checks, not Evals scores or release gates. Convert observed outputs to native EvaluationSamples explicitly. No adapter, runtime dependency or Evals patch release is needed.

## MCP 0.4.0 unified release checks

MCP 0.4.0's `core.release_check` uses `evaluate_gate` and `GateConfig` unchanged,
rejecting unknown threshold keys on its side. No Evals runtime change or release.
AIOS evaluation evidence export (v0.10) remains the next Evals milestone.
See [the compatibility guide](docs/mcp-0.4-unified-workflows.md)
and the [MCP guide](https://github.com/DeepAgentLabs/mcp-server/blob/v0.4.0/docs/unified-workflows.md).
