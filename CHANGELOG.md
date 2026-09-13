# Changelog

All notable changes to this project will be documented here.

This project follows [Semantic Versioning](https://semver.org/).

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
