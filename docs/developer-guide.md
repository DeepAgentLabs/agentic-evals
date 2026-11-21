# Agentic Evals developer guide

Use this simple guide to choose a capability and run a local evaluation. The [AI Reference (robust)](https://deepagentlabs.io/agentic-evals/docs/llms-full.md) includes detailed workflows, the complete scorer/rubric catalog, current declarations from every package module, and both native schemas. Producing a report and passing a release gate are separate outcomes.

[Capability index](#capability-index) · [Quickstart](#quickstart) · [Configuration](#settings) · [Troubleshooting](#troubleshooting) · [Reference](#reference)

## Capability index

Each row links to a short workflow below, with detailed references for inputs, options and limits.

| Capability | What you can do |
| --- | --- |
| [Quick Eval API](#simple) | Evaluate local datasets with lightweight score functions and inspect EvalResult. |
| [Structured suites and recorded samples](#custom-data) | Define expectations and evaluate JSON, YAML or JSONL samples by case ID. |
| [Normalized traces and adapters](#existing-traces) | Normalize tool spans, latency, cost and provenance from caller-owned trace data. |
| [Built-in case expectations](#expectations) | Check output/schema/fields, tool arguments/order, turns, latency and cost. |
| [Deterministic scorers](#text-scorers) | Use all twelve named text, numeric, structural and embedding-assisted scorers. |
| [Trajectory scorers](#trajectory) | Score tool precision/recall, duplicate calls and baseline-relative efficiency. |
| [Rubric templates and custom criteria](#rubrics) | Choose ten model-graded templates or build a verdict scale with make_rubric. |
| [Custom evaluators and registries](#custom-scorers) | Register callable, business-rule, judge or async evaluators with provenance. |
| [Evaluation packs](#packs) | Load built-in or custom bundles with required scorer validation. |
| [Judge reliability](#judges) | Bound retries, preserve usage, and report unavailable judgments explicitly. |
| [Repeated judging and agreement](#agreement) | Measure repeated verdict agreement separately from score averages. |
| [Reports, costs and breakdowns](#data-model) | Inspect per-case scores, judge/live summaries and metric/tag aggregates. |
| [Release gates](#release-gates) | Gate quality, tag/metric slices, cost, latency, unavailable judges and target outcomes. |
| [Live Python and HTTP targets](#live) | Run trusted targets with concurrency, timeout and retry controls. |
| [Async evaluation](#async) | Await async evaluators/targets with bounded concurrency and cancellation. |
| [CLI file discovery](#discovery) | Discover and execute Python Eval files for a CI pass/fail result. |
| [Declarative CLI and report formats](#cli) | Evaluate/live/gate from files and export JSON, JUnit or Markdown. |
| [Authenticated containment scoring](#containment) | Score trusted, scoped dispatch/denial observations using a host-configured verifier. |
| [AIOS evidence export](#aios) | Map native report/gate judgments to draft AIOS targets and attach them to Runs. |
| [Native report and gate schemas](#schemas) | Validate native JSON with two offline schema accessors and independent contract versions. |
| [Public API and compatibility](#compatibility) | Distinguish reviewed exports from implementation helpers and track support/migration policy. |
| [Methodology playbooks](#methodology) | Use 19 bundled guidance cards for evaluation design, validation, reporting and monitoring. |
| [Configuration and limitations](#settings) | Choose explicit registries, callbacks, trust, thresholds and host-owned execution boundaries. |

## Quickstart

Requires Python 3.10 or newer in an activated virtual environment. No API key is needed for this local example:

```bash
python -m pip install agentic-evals
```

Save this complete file as `first_eval.py`:

```python
from agentic_evals import Eval, equals


def answer(country):
    return {"France": "Paris", "Japan": "Tokyo"}[country]


Eval(
    "first-evaluation",
    data=[{"input": "France", "expected": "Paris"}, {"input": "Japan", "expected": "Tokyo"}],
    task=answer,
    scores=[equals],
)
```

[Download first_eval.py](guide/examples/first_eval.py)

```bash
python first_eval.py
agentic-evals run first_eval.py
```

Both cases pass because the fixture returns the expected capitals. This verifies the local scoring path, not model behavior.

## Usage

Repository examples require a source checkout and run from its root. Other named files, registries, target endpoints and evidence are inputs you supply. Callbacks in provider/host integration guides require the corresponding application objects.

<span id="simple"></span>

### Quick Eval API

`Eval(name, data, task, scores, threshold=...)` runs a task for each input and returns an `EvalResult`; `data` can also be a loader callable. The six lightweight scorers are `equals`, `contains`, `icontains`, `levenshtein`, `matches` and `numeric_close`. Custom score functions can return supported booleans, numeric scores or named score dictionaries. Inspect results and their pass/fail state; printed output alone is not a release gate. See [simple API](api-reference.md#eval-quickstart) and [lightweight scorer semantics](scorers.md#lightweight-eval-scorers).

<span id="custom-data"></span>

### Structured suites and recorded samples

Use `TestSuite`/`TestCase` for test definitions and `EvaluationSample`/`EvalTrace` for observations. This complete local example uses a graded numeric reference:

```python
from pathlib import Path
from agentic_evals import (
    EvaluationSample,
    EvaluatorConfig,
    EvalTrace,
    TestCase,
    TestSuite,
    default_registry,
    evaluate_suite,
)

suite = TestSuite(
    name="numeric-demo",
    version="1",
    cases=[
        TestCase(
            id="answer",
            name="Answer",
            expected_output="42",
            evaluators=[
                EvaluatorConfig(name="numeric_diff", config={"abs_tol": 0.01}),
            ],
        ),
    ],
)
samples = [EvaluationSample(case_id="answer", output="42.0", trace=EvalTrace())]
report = evaluate_suite(suite, samples, registry=default_registry())
assert report.summary.pass_rate == 1.0
Path("report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
```

Native suite files are JSON/YAML. Samples accept arrays, a `samples` envelope or JSONL. Missing samples fail their cases; duplicate/unknown case IDs are errors. See [complete custom-data converter and files](guide/custom-data.md), [data model](core-concepts.md), and [load/evaluate APIs](api-reference.md).

<span id="existing-traces"></span>

### Normalized traces and adapters

Populate `EvalTrace.spans` with `EvalSpan(tool_name=..., attributes=...)`, plus observed latency, cost and metadata. The package consumes this normalized model, not arbitrary vendor JSON. `load_samples(..., trace_adapter=...)` and live runner `trace_adapter=` let a trusted host normalize an older/external payload before validation.

See [runnable trace normalization and fixtures](guide/existing-traces.md). Preserve unknown cost/provenance as unknown; do not relabel absent observations as zero or successful execution.

<span id="expectations"></span>

### Built-in case expectations

Case fields can check exact/substr output, Draft 2020-12 JSON Schema, nested output fields, required/forbidden tools, required/exact tool arguments, tool order, turns, latency and cost. Turn limits require explicit trace metadata. Schema validation resolves embedded references without fetching remote schemas. See [all TestCase fields and implicit checks](core-concepts.md) and [how named scorers compose with them](scorers.md#case-expectations-and-named-scorers).

<span id="text-scorers"></span>

### Deterministic scorers

`default_registry()` includes twelve named text/numeric scorers: `exact_match`, `contains_all`, `contains_any`, `levenshtein_similarity`, `embedding_similarity`, `valid_json`, `json_diff`, `numeric_diff`, `regex_match`, `starts_with`, `ends_with` and `numeric_range`.

Configure them through `EvaluatorConfig(name=..., threshold=..., config=...)`. Embedding similarity requires your own `embed_fn`; the package supplies no embedding client. See [each scorer's input, parameters and scoring behavior](scorers.md#deterministic-scorers), including the interaction between `expected_contains` and implicit all-substring checks.

<span id="trajectory"></span>

### Trajectory scorers

Use `tool_call_precision` with an allowed-tool set, `tool_call_recall` with required tools, `no_redundant_tool_calls` for repeated tool/attribute combinations, and `trajectory_efficiency` with measured baseline latency/cost. They grade recorded spans rather than final text. Missing traces cannot establish tool behavior. See [configuration, no-tool cases and unavailable-cost behavior](scorers.md#trajectory-scorers).

<span id="rubrics"></span>

### Rubric templates and custom criteria

Choose `FACTUALITY`, `CLOSED_QA`, `SUMMARY_QUALITY`, `BATTLE`, `TRANSLATION`, `SECURITY`, `SQL_CORRECTNESS`, `POSSIBLE`, `PII_LEAKAGE` or `MODERATION`. `make_rubric()` builds custom criteria and a verdict scale. Register `LLMRubricEvaluator(name, template, complete_fn=...)` in your registry; the callback owns the provider call and may be sync or async.

For reference-based rubrics, put the reference in evaluator `config["reference"]`. Return `JudgeResponse` to record usage. See [all ten templates, verdict scores and a complete offline example](scorers.md#rubric-templates-and-custom-criteria). Templates are judgment prompts, not runtime security/moderation enforcement or SQL execution.

<span id="custom-scorers"></span>

### Custom evaluators and registries

Extend `default_registry()` with `CallableEvaluator`, `BusinessRuleEvaluator` or `LLMJudgeEvaluator`. Callbacks receive `EvaluationContext(case, sample, config)`; version evaluators when their logic/prompt changes. Test cases refer to registered names. `AsyncEvaluator` and async callbacks are supported by the async runner APIs.

For declarative CLI use, supply a trusted `--registry module[:factory_or_registry]`; it imports code. See [custom evaluator/registry setup](advanced.md) and the [complete local business-rule example](guide/custom-scorers.md).

<span id="packs"></span>

### Evaluation packs

```bash
agentic-evals pack list
agentic-evals pack show tool-use-correctness --suite --out suite.json
```

Four built-in packs cover tool use, JSON output contracts, factual QA and adversarial containment. `load_pack()` loads a custom suite plus `required_scorers`; `load_builtin_pack()` loads a named bundle. A pack does not implement its required judge/verifier: factual QA needs a registered completion callback, and containment needs host-configured trust. See [pack structure, dependencies and all built-ins](advanced.md#eval-packs).

<span id="judges"></span>

### Judge reliability

`RetryPolicy` bounds retry attempts, timeout and backoff. `LLMJudgeEvaluator` and rubric evaluators preserve available usage/latency and return explicit unavailable scores when attempts are exhausted or verdicts cannot be parsed. Unknown usage stays unknown. A missing verdict never passes. See [judge accounting, retries and unavailable outcomes](judge-reliability.md).

<span id="agreement"></span>

### Repeated judging and agreement

Set `samples=N` on a judge evaluator to collect repeated judgments. Score value is aggregated separately from the most common verdict and agreement rate. Reports retain sample metadata and judge usage. Configure `min_judge_agreement` in release gates when agreement is required. Agreement measures repeated consistency, not correctness. See [repeated judging and ties](judge-reliability.md#repeated-judging-and-agreement).

<span id="data-model"></span>

### Reports, costs and breakdowns

`EvaluationReport` contains case scores plus suite, metric/tag, judge and live summaries. Scores preserve evaluator identity/version, required/skipped state and explanations. Agent cost and judge cost remain separate; cost coverage/provenance distinguishes missing, estimated and measured values. Optional checks do not automatically fail a case, while required failures do; skipped and unavailable states retain distinct semantics.

See [Score/Report fields and aggregates](core-concepts.md#scores-and-reports), [detailed tutorial](guide/data-model.md), and [judge summary fields](judge-reliability.md).

<span id="release-gates"></span>

### Release gates

```python
from pathlib import Path
from agentic_evals import EvaluationReport, GateConfig, evaluate_gate

report = EvaluationReport.model_validate_json(Path("report.json").read_text())
decision = evaluate_gate(report, GateConfig(min_pass_rate=1.0))
assert decision.passed
```

GateConfig supports suite quality, failed-case counts, tag/metric slices, cost/latency, judge availability/agreement/cost and live target failures/timeouts. Named slices missing from a report fail their configured checks. Default gates require every case to pass and reject unavailable judgments. See [gate parameters](api-reference.md#release-gates) and [CI policy examples](guide/release-gates.md).

<span id="live"></span>

### Live Python and HTTP targets

`run_live_suite()` executes trusted `PythonTarget` callables or `HTTPTarget` endpoints, normalizes their payloads and records target outcomes. Configure worker count, per-call timeouts and `RetryPolicy`. Exhausted errors/timeouts become explicit case outcomes; invalid payloads remain input errors.

See [target return contract, retries and timeout limits](judge-reliability.md#live-target-retries-and-timeouts), [API examples](api-reference.md#live-targets) and [live tutorial](guide/live.md). A timeout on a blocking Python thread cannot undo already-running external side effects.

<span id="async"></span>

### Async evaluation

Use `aevaluate_suite()` for recorded samples with async evaluators, and `arun_live_suite()` for async targets/evaluators. Configure `max_concurrency` for async live runs. Await native coroutines in the caller's event loop; cancelled/timed-out targets retain their outcome evidence. See [async callbacks, ordering and cancellation](judge-reliability.md#async-evaluators-and-targets).

<span id="discovery"></span>

### CLI file discovery

```bash
agentic-evals run first_eval.py
agentic-evals run evals/
```

Directories are searched recursively for `*_eval.py`, `eval_*.py` and `*.eval.py`; an explicit file is accepted directly. Files execute as Python and must call `Eval()` to register results. Exit 1 means a failed eval, import error, no matching files or no collected evaluations. See [discovery and CI conventions](cli.md#python-eval-file-discovery).

<span id="cli"></span>

### Declarative CLI and report formats

```bash
agentic-evals evaluate suite.yaml samples.jsonl --out report.json
agentic-evals gate report.json --config gate.yaml --out gate.json
agentic-evals evaluate suite.yaml samples.jsonl --format junit --out results.xml
agentic-evals evaluate suite.yaml samples.jsonl --format markdown
```

`evaluate`/`live` exit 0 when a report is produced even when cases failed. Run `gate` for release enforcement: 0 passes, 1 fails, 2 indicates input/usage/output error. Keep native JSON for gating and consumers; JUnit/Markdown are presentation formats. See the [seven-command inventory, output flags and exit codes](cli.md).

<span id="containment"></span>

### Authenticated containment scoring

Use the `adversarial-containment` pack with a host-configured `ContainmentEvaluator(verifier=...)`. The optional `[integrity]` extra supplies Lens verification through `lens_verifier(host_trusted_keys)`. Trust keys, expected task/scope, versions and attempted-call IDs come from the host, not the samples. The default registry has no trusted verifier and fails closed.

Scores check bounded authenticated dispatch/denial/acknowledgement observations, retaining in-flight completions. A safe output or BLOCK alone is insufficient. See [trust setup, exact observation contract, positive/negative fixtures and gate commands](containment.md). Scoring neither enforces runtime behavior nor proves exhaustive capture.

<span id="aios"></span>

### AIOS evidence export

Use `to_aios_evidence()` to map native report scores and optional gate results to explicit AIOS targets, and `attach_aios_evidence()` to merge into an existing Run. The CLI exposes the same workflow:

```bash
agentic-evals aios export report.json --run run.json --targets targets.yaml --out run-with-evaluations.json
```

Run/Step mappings must resolve; unavailable and skipped scores are preserved distinctly. A failed gate becomes failed exported evidence, not an export-command error. See [target mapping, unmapped policies, identity/collision checks and draft validation](aios-evidence.md). Export remains `0.4-draft`, independently of package version.

<span id="schemas"></span>

### Native report and gate schemas

`report_schema()` and `gate_decision_schema()` return offline JSON Schema dictionaries for native report/gate contract 1.0. The two schemas ship inside the package and appear in the robust reference. Native schema validity is separate from passing a gate, AIOS alignment and evidence authenticity. See [schema validation, compatibility and migration](report-contract.md).

<span id="compatibility"></span>

### Public API and compatibility

The reviewed root exports are listed in `agentic_evals.__all__`; underscore-prefixed names are private. `cli_commands`, `formatting` and `live` are implementation modules; use the root run APIs and console CLI. Public-API and schema baselines are checked by the repository's tests. See [candidate API/deprecation policy](public-api.md), [support matrix and reproduction](support-policy.md), and [coordinated acceptance limits](coordinated-v1-readiness.md).

<span id="methodology"></span>

### Methodology playbooks

The package also ships 19 guidance cards for defining objectives/criteria, building datasets, choosing or validating scorers/rubrics, designing/analyzing experiments, instrumenting traces, live runs, flaky judges, release gates, reporting, monitoring, containment and AIOS export. These are methodology documents, distinct from executable packs and Python evaluators. See the [complete playbook index](methodology.md).

<span id="settings"></span>

## Configuration and limitations

Configuration lives in `TestCase`, `EvaluatorConfig`, `GateConfig`, `RetryPolicy` and target/pack definitions. Provider clients, completion/embedding callbacks, registry imports, authenticated trust stores and live endpoint access belong to the host. Core installation has no required sibling dependency. `[integrity]` adds Lens; `[voice]` supports the separate voice example.

Named scorers do not silently remove unrelated case expectations. Lexical similarity, rubric agreement and snapshot authentication establish different things; none independently proves task correctness or runtime enforcement. Preserve unknown cost, missing trace, skipped check and unavailable judge states. For exact fields, see [data model](core-concepts.md), [catalog semantics](scorers.md), [reliability limits](judge-reliability.md), and [support policy](support-policy.md). Historical compatibility notes apply to their stated releases.

## Troubleshooting

Confirm case IDs and artifact types match, required scorers are registered, and callbacks/targets return the documented shape. Inspect score explanations and judge/live summaries before changing thresholds. A generated failing report requires an explicit gate to produce a release-blocking exit status. Use `agentic-evals COMMAND --help` for exact CLI flags.

## Reference

- [API reference](api-reference.md), [scorer/rubric catalog](scorers.md) and [CLI reference](cli.md).
- [AI Reference (robust)](https://deepagentlabs.io/agentic-evals/docs/llms-full.md) and [capability/source index](ai-reference-index.md).
- [Source manifest and checksums](ai-docs-manifest.json).
