# AI Reference capability index

This index opens the generated [AI Reference (robust)](https://deepagentlabs.io/agentic-evals/docs/llms-full.md). In that raw Markdown file, **Full reference** identifies an included topic section; **Source** links to the maintained document. Use the [Developer Guide (simple)](developer-guide.md#capability-index) for short workflows.

## Capability index

| Capability | Included scope | Detailed reference |
| --- | --- | --- |
| Quick Eval API | Evaluate local datasets with lightweight score functions and inspect EvalResult. | <a href="#api-reference">Full reference</a> · [Source](api-reference.md) |
| Structured suites and recorded samples | Define expectations and evaluate JSON, YAML or JSONL samples by case ID. | <a href="#custom-data-workflow">Full reference</a> · [Source](guide/custom-data.md) |
| Normalized traces and adapters | Normalize tool spans, latency, cost and provenance from caller-owned trace data. | <a href="#existing-trace-workflow">Full reference</a> · [Source](guide/existing-traces.md) |
| Built-in case expectations | Check output/schema/fields, tool arguments/order, turns, latency and cost. | <a href="#core-concepts-and-data-model">Full reference</a> · [Source](core-concepts.md) |
| Deterministic scorers | Use all twelve named text, numeric, structural and embedding-assisted scorers. | <a href="#complete-scorer-and-rubric-catalog">Full reference</a> · [Source](scorers.md) |
| Trajectory scorers | Score tool precision/recall, duplicate calls and baseline-relative efficiency. | <a href="#complete-scorer-and-rubric-catalog">Full reference</a> · [Source](scorers.md) |
| Rubric templates and custom criteria | Choose ten model-graded templates or build a verdict scale with make_rubric. | <a href="#complete-scorer-and-rubric-catalog">Full reference</a> · [Source](scorers.md) |
| Custom evaluators and registries | Register callable, business-rule, judge or async evaluators with provenance. | <a href="#custom-evaluators-and-packs">Full reference</a> · [Source](advanced.md) |
| Evaluation packs | Load built-in or custom bundles with required scorer validation. | <a href="#custom-evaluators-and-packs">Full reference</a> · [Source](advanced.md) |
| Judge reliability | Bound retries, preserve usage, and report unavailable judgments explicitly. | <a href="#judge-reliability-and-live-target-resilience">Full reference</a> · [Source](judge-reliability.md) |
| Repeated judging and agreement | Measure repeated verdict agreement separately from score averages. | <a href="#judge-reliability-and-live-target-resilience">Full reference</a> · [Source](judge-reliability.md) |
| Reports, costs and breakdowns | Inspect per-case scores, judge/live summaries and metric/tag aggregates. | <a href="#core-concepts-and-data-model">Full reference</a> · [Source](core-concepts.md) |
| Release gates | Gate quality, tag/metric slices, cost, latency, unavailable judges and target outcomes. | <a href="#api-reference">Full reference</a> · [Source](api-reference.md) |
| Live Python and HTTP targets | Run trusted targets with concurrency, timeout and retry controls. | <a href="#judge-reliability-and-live-target-resilience">Full reference</a> · [Source](judge-reliability.md) |
| Async evaluation | Await async evaluators/targets with bounded concurrency and cancellation. | <a href="#judge-reliability-and-live-target-resilience">Full reference</a> · [Source](judge-reliability.md) |
| CLI file discovery | Discover and execute Python Eval files for a CI pass/fail result. | <a href="#cli-reference-and-ci">Full reference</a> · [Source](cli.md) |
| Declarative CLI and report formats | Evaluate/live/gate from files and export JSON, JUnit or Markdown. | <a href="#cli-reference-and-ci">Full reference</a> · [Source](cli.md) |
| Authenticated containment scoring | Score trusted, scoped dispatch/denial observations using a host-configured verifier. | <a href="#authenticated-containment-scoring">Full reference</a> · [Source](containment.md) |
| AIOS evidence export | Map native report/gate judgments to draft AIOS targets and attach them to Runs. | <a href="#aios-evaluation-evidence">Full reference</a> · [Source](aios-evidence.md) |
| Native report and gate schemas | Validate native JSON with two offline schema accessors and independent contract versions. | <a href="#native-report-and-gate-contract">Full reference</a> · [Source](report-contract.md) |
| Public API and compatibility | Distinguish reviewed exports from implementation helpers and track support/migration policy. | <a href="#public-api-candidate">Full reference</a> · [Source](public-api.md) |
| Methodology playbooks | Use all 19 bundled evaluation guidance cards. | <a href="#evaluation-methodology-playbooks">Full reference</a> · [Source](methodology.md) |
| Configuration and limitations | Choose explicit registries, callbacks, trust, thresholds and host-owned execution boundaries. | <a href="#support-and-compatibility-policy">Full reference</a> · [Source](support-policy.md) |

## How to use the robust reference

1. Choose a capability and read its detailed prerequisites, input contract, scoring behavior and limitations. The scorer catalog inventories all default registry names, all six lightweight score helpers, and all ten rubric templates.
2. Consult **Source declarations: src/agentic_evals/...** for statically extracted signatures, model fields and exports from every package module. Extraction does not execute imports. Internal helpers and implementation modules remain internal; inclusion does not promote their APIs. See the reviewed public API policy.
3. Consult **Data contract: src/agentic_evals/schemas/...** for native report/gate schema 1.0. Schemas, package releases and AIOS `0.4-draft` exports have independent versions. JUnit/Markdown are presentations, not native evidence inputs.
4. Use the full task tutorials for runnable custom-data, trace adaptation, registry, live/async and judge workflows. Supplied callbacks/registry modules/targets are trusted host code, not vendor importers or built-in provider clients.
5. Treat release-labelled compatibility/acceptance sections as records for their stated versions. Current declarations and package metadata describe this checkout; synthetic examples and schema validity do not establish production success, safety or exhaustive capture.
6. Verify `ai-docs-manifest.json` before ingestion. It records every selected source and normalized hash plus the generated reference checksum. Missing evidence, skipped checks, unavailable judges and failed gates must remain distinct.

## Maintaining coverage

`docs/ai-docs.json` selects detailed topic/task guides, all package Python modules and both packaged native schemas. Update both indexes and the scorer/CLI inventories when adding user-facing capabilities. Regenerate from this repository root using the shared sibling documentation checkout (Python 3.11 or newer):

```bash
python3 ../deepagentlabs.github.io/scripts/build_ai_docs.py --sources .. --project agentic-evals
python3 ../deepagentlabs.github.io/scripts/build_ai_docs.py --sources .. --project agentic-evals --check
```

The shared site build publishes the robust pack verbatim as a raw Markdown download. The manifest also records downloadable tutorial files.
