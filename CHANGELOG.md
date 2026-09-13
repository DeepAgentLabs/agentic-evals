# Changelog

All notable changes to this project will be documented here.

This project follows [Semantic Versioning](https://semver.org/).

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
