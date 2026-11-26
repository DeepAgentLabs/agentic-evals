# Agentic Evals

Did the recorded behavior meet our quality requirements?

## What it does

Per-case scores, summary metrics and a separate release-gate decision, grouped by area below. Each area links to its detailed guide; for runnable commands, see the [developer guide](developer-guide.md).

### 1. Writing evals

- **Quick `Eval()` API**
    - `Eval(name, data=..., task=..., scores=...)` with `Case` rows or a data loader
    - Six lightweight checks: `equals`, `contains`, `icontains`, `levenshtein`, `matches`, `numeric_close`
    - Custom score functions returning booleans, numbers or named score dictionaries
    - Coloured terminal summary and an inspectable `EvalResult`
- **Structured suites**
    - `TestSuite` / `TestCase` definitions in Python, JSON or YAML (`load_suite`)
    - Recorded `EvaluationSample` outputs from JSON or JSONL (`load_samples`), matched by case ID
    - Missing samples fail their cases; duplicate or unknown case IDs are errors
- **Traces**
    - Normalized `EvalTrace` / `EvalSpan` model: tool calls, attributes, latency, cost and metadata
    - `trace_adapter=` hook to normalize older or external trace payloads
    - No dependency on any tracing tool

Guides: [Core concepts](core-concepts.md) · [Custom data](guide/custom-data.md) · [Existing traces](guide/existing-traces.md)

### 2. Case expectations

- **Output**
    - Exact or substring output, nested required fields
    - Draft 2020-12 JSON Schema validation (no remote schema fetches)
- **Tools**
    - Required and forbidden tools
    - Required or exact tool arguments, required tool order
- **Budgets**
    - Maximum latency, cost and turns per case

Guides: [All TestCase fields](core-concepts.md#testsuite-and-testcase) · [How scorers compose with expectations](scorers.md#case-expectations-and-named-scorers)

### 3. Built-in scorers

- **Text**
    - `exact_match`, `contains_all`, `contains_any`, `starts_with`, `ends_with`, `regex_match`
    - `levenshtein_similarity`, and `embedding_similarity` with your own `embed_fn`
- **Structured output**
    - `valid_json` and `json_diff` (first differing path)
- **Numeric**
    - `numeric_range` and `numeric_diff` (absolute or relative tolerance)
- **Trajectory (tool use)**
    - `tool_call_precision` and `tool_call_recall`
    - `no_redundant_tool_calls`
    - `trajectory_efficiency` against a measured baseline latency or cost

Guides: [Scorer and rubric catalog](scorers.md)

### 4. LLM-as-judge

- **Rubric templates**
    - Ten ready-made templates: `FACTUALITY`, `CLOSED_QA`, `SUMMARY_QUALITY`, `TRANSLATION`, `SQL_CORRECTNESS`, `SECURITY`, `MODERATION`, `PII_LEAKAGE`, `BATTLE`, `POSSIBLE`
    - Custom criteria and verdict scales with `make_rubric()`, optionally with a reference answer
- **Running judges**
    - `LLMRubricEvaluator` and `LLMJudgeEvaluator` with your own sync or async completion callback
    - `JudgeResponse` to report tokens, cost, model and provider
- **Reliability**
    - Bounded retries with backoff (`RetryPolicy`)
    - A judge that fails after its retries gives an explicit unavailable score that never passes
    - Repeated judging (`samples=N`) with per-case agreement
- **Accounting**
    - Judge cost, tokens and latency per score, totalled in `summary.judge`
    - Judge cost kept separate from agent cost

Guides: [Judge reliability](judge-reliability.md) · [Judges tutorial](guide/judges.md)

### 5. Custom evaluators

- **Evaluator types**
    - `CallableEvaluator`, `BusinessRuleEvaluator`, `LLMJudgeEvaluator`
    - Sync or `async def` callbacks (`AsyncEvaluator`)
- **Registries**
    - `default_registry()` with every built-in scorer, extended through `EvaluatorRegistry.register()`
    - Trusted `--registry module:factory` for the CLI
- **Provenance**
    - Each score records the evaluator, its type and its version

Guides: [Custom evaluators and packs](advanced.md) · [Custom scorers tutorial](guide/custom-scorers.md)

### 6. Live targets

- **Targets**
    - Trusted Python callables (`PythonTarget`) and HTTP endpoints (`HTTPTarget`)
    - `run_live_suite()` and the async `arun_live_suite()`
- **Resilience**
    - Parallel workers, per-call timeouts and retries
    - Timeouts and target errors reported apart from wrong answers (`target_status`, `summary.live`)
- **Async evaluation**
    - `aevaluate_suite()` for recorded samples with async evaluators
    - Bounded concurrency and cancellation

Guides: [Live tutorial](guide/live.md) · [Live target retries and timeouts](judge-reliability.md#live-target-retries-and-timeouts)

### 7. Reports, costs and breakdowns

- **Report contents**
    - Per-case scores with explanations, evaluator identity and required/skipped state
    - Suite summary: pass rate, average score, latency and cost
    - Breakdowns by metric and by tag
    - Judge and live-target summaries
- **Cost honesty**
    - Unknown cost stays unknown; it is never reported as $0
    - Cost provenance per case: measured, estimated or unspecified (`cost_source`)
- **Formats**
    - Native JSON, JUnit XML and Markdown

Guides: [Scores and reports](core-concepts.md#scores-and-reports) · [Data model tutorial](guide/data-model.md)

### 8. Release gates

- **Suite thresholds**
    - Pass rate, average score and failed-case count
    - Average latency and total cost
- **Slices**
    - Stricter pass rates per tag (`min_tag_pass_rate`) or per metric (`min_metric_pass_rate`)
    - A slice named in the gate but missing from the report fails the gate
- **Judges**
    - Unavailable judge scores (zero allowed by default), minimum agreement and judge cost
- **Live runs**
    - Maximum timed-out cases and target-error cases
- **Decision**
    - `GateDecision` with pass/fail, reasons and observed values

Guides: [Release gates API](api-reference.md#release-gates) · [CI policy examples](guide/release-gates.md)

### 9. Eval packs

- **Built-in packs**
    - `tool-use-correctness`, `json-output-contract`, `factual-qa`, `adversarial-containment`
- **Custom packs**
    - One YAML/JSON file bundling a suite and its required scorers (`load_pack`)
    - Required scorers checked against your registry when the pack loads

Guides: [Eval packs](advanced.md#eval-packs)

### 10. Adversarial containment scoring

- **Scenarios**
    - Stop, revoke, denied tool, authority, injected instruction, fail closed
- **Evidence**
    - Authenticated dispatch, denial and acknowledgement records, checked by a host-configured verifier
    - Optional AgenticLens verification (`lens_verifier`, `[integrity]` extra)
- **Fail closed**
    - Missing evidence, missing policy versions and bypassed enforcement fail
    - The default registry has no trusted verifier and refuses unauthenticated evidence
    - Containment is scored separately from task success

Guides: [Authenticated containment scoring](containment.md)

### 11. CLI

- **Commands**
    - `run`: discover and run Python eval files
    - `evaluate`: score saved samples against a suite
    - `live`: run a suite against a trusted target
    - `gate`: apply release thresholds to a saved report
    - `pack list` / `pack show`: browse built-in packs
    - `aios export`: export AIOS evaluation evidence
- **CI**
    - `--format json|junit|markdown`
    - Gate exit codes: 0 pass, 1 failed gate, 2 input or usage error

Guides: [CLI reference and CI](cli.md)

### 12. Contracts and interoperability

- **Native schemas**
    - Offline JSON Schemas for the report and gate decision (`report_schema()`, `gate_decision_schema()`)
- **AIOS evidence**
    - Map scores and gate results to AIOS `0.4-draft` targets (`to_aios_evidence`)
    - Attach them to an existing Run (`attach_aios_evidence`)
- **Ecosystem**
    - Report fields that AgenticLens, Control Tower, MCP, Sidecar and Chaos read

Guides: [Native report contract](report-contract.md) · [AIOS evidence](aios-evidence.md) · [Public API](public-api.md)

### 13. Methodology playbooks

- **19 guidance cards** (methodology, not runnable code)
    - Frame: define an objective, elicit criteria
    - Build data: build a dataset, size a suite
    - Score: write, choose and validate scorers and rubrics
    - Run: instrument a trace, run a live suite
    - Experiment: design and analyze experiments
    - Investigate: discover failure modes, red-team a suite, debug a flaky judge
    - Operate: define a gate, report results, monitor in production, evaluate containment, export AIOS evidence

Guides: [Methodology playbooks](methodology.md)

## What you need

Test cases, actual outputs, normalized traces, and optional judge callbacks.

## Start here

Evaluate two recorded answers, then add tool evidence: [follow the quickstart](developer-guide.md#quickstart).

## Limits

- A report is not a release approval; run an explicit gate.
- Tool checks need complete tool evidence in the trace.
- Model judges need your own provider integration; the package ships no model client.
- Containment scoring needs a trusted verifier from the host; it neither enforces runtime behavior nor proves exhaustive capture.

See [Limitations](limitations.md).

## Documentation

- [Developer Guide (simple)](developer-guide.md): short task workflows and a capability index
- [API Reference (detailed)](api-reference.md): exact Python functions, parameters and return values
- [AI Readable Documentation](ai-reference-index.md): the full reference as one file for AI tools, with source declarations and schemas
