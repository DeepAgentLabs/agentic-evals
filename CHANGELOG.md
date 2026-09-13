# Changelog

All notable changes to this project will be documented here.

This project follows [Semantic Versioning](https://semver.org/).

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
