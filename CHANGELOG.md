# Changelog

All notable changes to this project will be documented here.

This project follows [Semantic Versioning](https://semver.org/).

## 0.5.0 - 2026-09-15

### Added

- Four new deterministic `scorers.text` checks: `regex_match` (with
  `full_match`/`case_insensitive` options), `starts_with`, `ends_with`,
  `numeric_range` (one- or two-sided `min`/`max`). All registered under
  `default_registry()` like the existing text scorers.
- Five new `scorers.rubric` templates, autoevals-style: `TRANSLATION`,
  `SECURITY` (code/output vulnerability review), `SQL_CORRECTNESS`
  (semantic equivalence against a reference query, not textual
  similarity), `POSSIBLE` (fabricate-vs-refuse on unanswerable requests),
  `PII_LEAKAGE`.
- Two new zero-setup scorers for the `Eval()` API: `matches` (regex
  search) and `numeric_close` (1% relative tolerance).
- Thirteen new methodology skills, bringing `agentic_evals/skills/` from 4
  to 17 and covering the full eval lifecycle end to end (Frame/Build data/
  Score/Run/Experiment/Investigate/Operate), scoped to this package's own
  API: `define-an-eval-objective`,
  `elicit-eval-criteria`, `build-an-eval-dataset`, `choose-a-rubric-template`,
  `validate-a-scorer`, `run-a-live-suite`, `design-an-eval-experiment`,
  `analyze-an-eval-experiment`, `discover-failure-modes`,
  `red-team-an-agent-suite`, `debug-a-flaky-llm-judge`,
  `report-eval-results`, `monitor-evals-in-production`.

## 0.4.0 - 2026-09-14

### Added

- `Eval(name, data=..., task=..., scores=[...])`: a one-call entry point
  alongside the existing `TestSuite`/`TestCase`/`evaluate_suite` API, for
  the same "install and run a first eval in a minute" experience popular
  eval SDKs offer. Takes plain dicts (`{"input": ..., "expected":
  ...}`), any callable as the task under test, and scorer functions that
  return a float/bool/`Score`/`{"score": ...}`; prints a pass/fail table
  and returns an `EvalResult` (`bool(result)` is the overall verdict).
- `agentic-evals run [paths...]`: a CLI (`pip install agentic-evals` now
  also installs this command) that discovers `*_eval.py` / `eval_*.py` /
  `*.eval.py` files, runs every `Eval(...)` call in them, and exits
  non-zero if any case failed -- drop-in for CI, no config file needed.
- Four zero-setup scorers for the new `Eval()` API: `equals`, `contains`,
  `icontains`, `levenshtein`. (The existing `scorers.text`/`scorers.rubric`/
  `scorers.trajectory` library is unchanged and still the deeper,
  trace-aware option for `TestSuite`-based evaluation.)

## 0.3.0 - 2026-09-13

### Added

- `agentic_evals.skills`: methodology playbooks (`SKILL.md` cards --
  Trigger/Do/Avoid/Check/Risk), scoped to this package's own API:
  `write-a-scorer`, `define-a-release-gate`, `size-a-test-suite`,
  `instrument-a-trace`. These are guidance documents, not runnable code --
  consumable by a human or by a coding agent's own skill mechanism.
- `agentic_evals.packs`: runnable eval-config bundles -- a `TestSuite`
  paired with the scorer names it needs, loaded from a single YAML/JSON
  file. `load_pack()`/`load_builtin_pack()` validate that every
  `required_scorers` entry resolves in the registry before returning.
  Ships 3 built-in packs: `tool-use-correctness`, `factual-qa`,
  `json-output-contract`.

### Fixed

- `LLMRubricEvaluator` now reads its reference material (the expert
  answer for `FACTUALITY`, candidate B for `BATTLE`) from
  `EvaluatorConfig.config["reference"]` instead of `case.expected_output`.
  Reusing `expected_output` collided with `evaluate_suite`'s hardcoded
  exact-match check, which fires whenever that field is set -- silently
  forcing every rubric-graded case to also require a literal string match.

## 0.2.0 - 2026-09-13

### Added

- `agentic_evals.scorers`: a built-in scorer library.
  - `scorers.text` (deterministic, no LLM): `exact_match`, `contains_all`,
    `contains_any`, `levenshtein_similarity`, `embedding_similarity`
    (provider-neutral -- pass an `embed_fn`, this package makes no
    embedding calls itself), `valid_json`, `json_diff`, `numeric_diff`.
  - `scorers.rubric` (LLM-graded, provider-neutral): `RubricTemplate` and
    `LLMRubricEvaluator` (pass a `complete_fn`; this package never calls a
    model itself). Ships `FACTUALITY`, `CLOSED_QA`, `SUMMARY_QUALITY`,
    `BATTLE` (pairwise A/B), and `MODERATION` templates.
  - `scorers.trajectory` (reads `EvalTrace`/`EvalSpan` directly):
    `tool_call_precision`, `tool_call_recall`, `no_redundant_tool_calls`,
    `trajectory_efficiency`.
  - `default_registry()` returns an `EvaluatorRegistry` pre-populated with
    every `text`/`trajectory` scorer under a stable name, ready to pass to
    `evaluate_suite(suite, samples, registry=default_registry())`.
  - All of the above are re-exported from the package root.

## 0.1.1 - 2026-09-13

### Added

- `load_samples()` and `run_live_suite()` accept an optional `trace_adapter`
  callable, applied to each sample/result's raw `trace` value before
  validation. Lets callers whose trace payloads predate or otherwise don't
  match `EvalTrace`'s shape (e.g. AgenticLens's own `Run`-shaped live
  targets and saved sample files) normalize them at the call site instead
  of having them silently validate with latency/cost defaulted to 0/None.

## 0.1.0 - 2026-09-13

### Added

- Initial extraction of AgenticLens's evaluation engine into a standalone,
  framework-agnostic package: `EvalTrace`/`EvalSpan` (a minimal, tool-agnostic
  trace shape), `Score`, `Evaluator`/`EvaluatorRegistry`/`CallableEvaluator`/
  `LLMJudgeEvaluator`/`BusinessRuleEvaluator`, `TestCase`/`TestSuite`,
  `evaluate_suite` (deterministic JSON Schema/field/tool/latency/cost/
  turn-count checks plus custom evaluators), `run_live_suite` (Python/HTTP
  live targets), and `GateConfig`/`evaluate_gate`.
- Zero dependency on AgenticLens or any other DeepAgentLabs project —
  depends only on `pydantic`, `pyyaml`, `jsonschema`, and `referencing`.
