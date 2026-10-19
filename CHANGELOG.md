# Changelog

All notable changes to this project will be documented here.

This project follows [Semantic Versioning](https://semver.org/).

## 0.9.0 - 2026-10-19

### Added

- Judge cost and latency on every judge score, under the `judge_*` metadata
  keys AgenticLens already reads (`judge_cost_usd`, `judge_cost_source`,
  `judge_input_tokens`, `judge_output_tokens`, `judge_latency_ms`,
  `judge_model`, `judge_provider`), plus `judge_status` and `judge_attempts`.
  A rubric `complete_fn` reports usage by returning a `JudgeResponse`.
- `EvaluationSummary.judge` (`JudgeSummary`): judge scores, unavailable scores
  and the cases they belong to, retries, cost total (only when every judge score
  is priced), cost sources, tokens, latency and sampling agreement. Judge spend
  stays separate from the evaluated system's `total_cost_usd`.
- `RetryPolicy`: bounded attempts with capped exponential backoff, used by
  judges (`retry=` on `LLMJudgeEvaluator`/`LLMRubricEvaluator`) and live
  targets (`retry=` on `run_live_suite`/`arun_live_suite`).
- An explicit unavailable judge outcome: when every attempt fails, the score
  has value 0, never passes at any threshold, and records `judge_error`.
- Repeated judging with `samples=N`: mean value, most common verdict (ties go
  to the lower verdict), `judge_verdicts` and `judge_agreement` per score, and
  `min_agreement`/`case_agreement` in `summary.judge`.
- Live-target outcomes per case: `CaseEvaluation.target_status` (`ok`,
  `timed_out`, `error`), `target_attempts` and `target_error`, a `target_call`
  score, and `EvaluationSummary.live` (`LiveSummary`).
- Python target timeouts when `timeout_seconds` is set explicitly; `async def`
  targets are cancelled, synchronous ones are abandoned in daemon threads.
- Async evaluation: `aevaluate_suite`, `arun_live_suite`, `aevaluate()` on
  `CallableEvaluator` and its subclasses, the `AsyncEvaluator` protocol, and
  `async def` judges, rubric `complete_fn`s and Python targets (also accepted
  by the sync APIs outside a running event loop).
- Gate checks: `max_judge_unavailable_scores` (default 0), `max_judge_cost_usd`,
  `min_judge_agreement`, `max_timed_out_cases` and `max_target_error_cases`.
  Reasons name the affected cases.
- CLI `live --retries`, `--retry-backoff`, and `--timeout-seconds` for Python
  targets. JUnit reports timed-out/errored live cases as `<error>`; Markdown
  shows `TIMEOUT`/`ERROR` and judge/live summaries.
- `docs/judge-reliability.md`, offline `examples/judge_reliability.py` and
  `examples/async_live_target.py`, a judged live contract example, and
  updated skills for flaky judges, live suites and release gates.

### Changed

- A judge that raises, or a rubric completion with no parseable verdict, now
  yields an unavailable score instead of raising out of `evaluate_suite`.
- A live-target call that raises or times out (including an unreachable HTTP
  target) is reported on its case instead of aborting `run_live_suite`;
  `agentic-evals live` writes the report and exits 0. A case is `timed_out` only
  when every attempt timed out. An invalid target payload, including a non-JSON
  HTTP body, still stops the run without retrying (exit 2).
- Usage reported by a rubric attempt with no parseable verdict is added to the
  score's judge cost and tokens.
- The default gate fails when any judge score is unavailable, even for an
  optional evaluator. Set `max_judge_unavailable_scores: null` to opt out.
- `LLMRubricEvaluator` now subclasses `LLMJudgeEvaluator`.

### Compatibility

- Report schema 1.0 gains optional fields only (`summary.judge`, `summary.live`,
  `cases[].target_*`); packaged schema IDs now point at `v0.9.0`. Reports saved
  by earlier versions load unchanged, and 0.9.0 reports validate against the
  frozen 0.7.1 schemas, so readers bundling 0.7.2 schemas keep working.
- Lens's `agentic-evals>=0.7.1,<1` range already covers 0.9.0 and its tests pass
  unchanged. MCP and Control Tower sync their bundled schemas and test pins to
  0.9.0 in patch releases. AIOS evidence export remains v0.10.

## 0.8.0 - 2026-10-17

### Added

- Declarative `evaluate`, Python/HTTP `live`, and `gate` commands with explicit
  exit codes, custom registry imports, concurrency and JSONL samples.
- Built-in `pack list` and `pack show`, including plain suite export without
  requiring judge credentials for inspection.
- Native JSON, JUnit XML and escaped Markdown output for reports and gates.
- Passing/failing CI fixtures, a GitHub Actions workflow, CLI documentation and
  voice-agent dataset export with the same custom evaluators as the Python path.
- CLI parity, process exit-code, malformed-input and presentation tests.

### Compatibility

- Existing `run` behavior and Python scoring/gating APIs are preserved. Native
  report schema 1.0 and gate wire shapes are unchanged from 0.7.2.
- `evaluate`/`live` return 0 when evidence is produced; use `gate` to fail CI
  according to policy (0 pass, 1 failed gate, 2 input/usage error).
- Sibling runtime dependency floors are unchanged; Lens, MCP and Tower consume
  native JSON. AIOS evidence export remains future work.

## 0.7.2 - 2026-10-17

### Added

- Published Draft 2020-12 report/gate schemas as package data with offline
  `report_schema()` and `gate_decision_schema()` public accessors.
- Frozen 0.7.1 fixtures and wire-shape compatibility checks, model/schema drift
  detection, invalid-artifact tests and installed-wheel contract checks.
- Runnable passing/missing-evidence report and failing gate examples, contract
  evolution policy and ecosystem compatibility documentation.

### Compatibility

- Existing native model fields and serialization remain unchanged. Contract
  1.x evolves additively; no sibling dependency floors are increased.

## 0.7.1 - 2026-10-12

### Added

- `Score.evaluator` and `Score.evaluator_version`: every score in a report
  names what produced it. Built-in checks are stamped with
  `BUILTIN_EVALUATOR` (`"agentic_evals.builtin"`) and this package's
  version; registered evaluators with their registry name and their
  `version` attribute. `CallableEvaluator`, `LLMJudgeEvaluator`,
  `BusinessRuleEvaluator` and `LLMRubricEvaluator` accept `version=`.
- `EvalTrace.cost_source` (`"measured"` or `"estimated"`), carried onto
  `CaseEvaluation.cost_source`, plus `EvaluationSummary.priced_cases` and
  `EvaluationSummary.cost_sources` so a report states how complete its
  cost data is and where the numbers came from.
- `CaseEvaluation.sample_available`: `False` when no sample was supplied
  for a case, so an empty `trace_id` is distinguishable from a lost one.
- `run_live_suite(..., max_workers=N)`: call a live target for several
  cases at once. Reports keep suite case order.

### Tests

- Python/HTTP live-target parity on one suite, against a local HTTP server.

## 0.7.0 - 2026-10-03

### Added

- `EvaluationSummary.metrics` and `EvaluationSummary.tags`: every report
  now breaks its results down by metric (`MetricSummary`: checks passed,
  failed and skipped, pass rate, average score) and by case tag
  (`TagSummary`: case counts, pass rate, average score).
- `Score.metric`: a stable key that reports group by. It defaults to
  `Score.name`; the implicit checks whose names carry a per-case detail
  (`contains:<text>`, `required_field:<path>`, `required_tool:<tool>`,
  `forbidden_tool:<tool>`, `tool_args:<tool>`) share the metric named by
  their prefix. `Score.name` is unchanged.
- `Score.skip(name, explanation)` and `Score.skipped`: an evaluator can
  record that a check did not apply to a case. A skipped score never
  fails the case, is left out of `average_score` and pass rates, and is
  counted in `MetricSummary.skipped`. `Eval()` ignores a skipped `Score`
  returned by a scorer.
- `CaseEvaluation.tags` and `CaseEvaluation.metadata`, copied from the
  `TestCase`, so a report can be filtered or regrouped on its own.
- `GateConfig.min_tag_pass_rate` and `GateConfig.min_metric_pass_rate`:
  pass-rate floors for one tag or one metric, applied on top of
  `min_pass_rate`. A tag or metric named in the config but absent from
  the report fails the gate. Observed values are reported under
  `tag_pass_rate:<tag>` and `metric_pass_rate:<metric>`.
- `TestCase.expected_tool_arguments`: expected argument values per tool.
  Passes when one call to the tool carries every listed argument with an
  equal value (no type coercion). Scored as `tool_arg_values:<tool>`.
- `TestCase.required_tool_order`: tools whose first calls must come in
  the listed order. Scored as `tool_order`.
- `make_rubric(name, criteria, levels=..., with_reference=...)`: builds a
  `RubricTemplate` from criteria written in plain language, with a
  pass/fail scale by default or a caller-supplied graded scale.

All of the above are additive: reports saved by earlier versions still
load, and `schema_version` stays `1.0`.

### Fixed

- `evaluate_suite` no longer raises `ZeroDivisionError` when no case
  produces a score (for example, every evaluator returned an empty list);
  `average_score` is reported as `0.0`.

## 0.6.0 - 2026-10-03

### Changed

- `GateConfig.min_average_score` and `GateConfig.max_failed_cases` now
  default to `None` (not checked) instead of `1.0` and `0`. The default
  gate is still strict -- `min_pass_rate=1.0` requires every case to pass
  -- but `GateConfig(min_pass_rate=0.95)` now tolerates the failures it
  names, and a graded score below 1.0 on a passing case no longer fails
  the gate. Set either field explicitly to keep the previous behaviour.
- `evaluate_suite` no longer adds its implicit exact-match check when a
  case configures a reference scorer (`levenshtein_similarity`,
  `embedding_similarity`, `json_diff`, `numeric_diff`, `starts_with`,
  `ends_with`) that grades against `expected_output`. The check still
  runs when the scorer has its own `reference` in its config.

### Fixed

- `numeric_diff` scores 1.0 for an output within `rel_tol`/`abs_tol`.
  Previously it scored just under 1.0, so the default threshold of 1.0
  failed every non-identical value and the tolerance had no effect.
- `tool_call_precision` scores 0.0 and `no_redundant_tool_calls` scores
  1.0 on a trace with no tool calls, instead of raising and aborting the
  whole suite run.
- `RubricTemplate.parse_verdict` reads the verdict a judge states
  ("Verdict: D", "(D)", a leading or trailing token) instead of the first
  standalone letter in the completion, which read the article in
  "A contradiction ... Verdict: D" as verdict A. A completion with no
  verdict, or several candidates, raises `ValueError`.

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
