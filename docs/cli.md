# Declarative evaluations in CI (0.8.0)

`agentic-evals run` still discovers Python `Eval()` files. The declarative
commands use the same `load_suite`, `load_samples`, `evaluate_suite`,
`run_live_suite` and `evaluate_gate` APIs as Python callers.

```bash
agentic-evals evaluate examples/ci/suite.yaml examples/ci/samples.jsonl --out report.json
agentic-evals gate report.json --config examples/ci/gate.yaml --out gate.json
agentic-evals evaluate examples/ci/suite.yaml examples/ci/samples.jsonl --format junit --out results.xml
agentic-evals evaluate examples/ci/suite.yaml examples/ci/samples.jsonl --format markdown
```

Suites are YAML/JSON `TestSuite` objects. Samples are a JSON/YAML array, an
object with a `samples` array, or JSONL (one `EvaluationSample` per nonblank
line). Each sample needs `case_id`, `output`, and `trace` (which may be `{}`).
Missing samples become failed cases; duplicate or unknown case IDs are errors.
An empty array records all cases as missing, rather than passing them.

## Exit codes and output

| Command | 0 | 1 | 2 |
| --- | --- | --- | --- |
| `evaluate`, `live` | Report produced, even if cases failed or a live target timed out | Unused | Usage, input, invalid target payload, evaluator or output error |
| `gate` | Gate passed | Gate failed (decision still written) | Usage, input or output error |
| `pack list/show` | Success | Unused | Usage, input or output error |
| `run` | All discovered evals passed | Failure, import error or no evals | Argument parsing error |

Always run `gate` to enforce a release policy. Without `--config`, every case
must pass. Gate configuration uses `GateConfig` fields; misspelled fields are
rejected. Report input must be JSON matching the native 1.0 contract. Use
`--format json` (the default) to keep the report for gating and sibling readers.
JUnit and Markdown are presentations, not native evidence inputs.

`--out FILE` writes UTF-8; omitted or `--out -` writes stdout. Parent directories
must exist. Diagnostics go to stderr, including prints from imported evaluators
or live targets. JUnit uses one testcase per case and marks failed required
checks as failures; since 0.9.0 a live case whose target timed out or errored is
an `<error>` instead. Optional failures and skipped checks appear in `system-out`;
they do not invent suite failures or change the engine's pass decision. Gate
JUnit has one testcase for the release decision. Markdown escapes report text
for tables and can be appended to `GITHUB_STEP_SUMMARY`.

## Registries and live targets

Built-in deterministic and trajectory scorers are registered by default.
`--registry module` calls that module's `build_registry()`; alternatively use
`module:factory` or `module:registry_instance`. Return an `EvaluatorRegistry`,
usually extending `default_registry()`. Modules may be in the current working
directory or installed on Python's import path. This option imports trusted
Python code, including any caller-configured judge provider.

```python
# target.py
def answer(value, *, case):
    return {"output": "42", "trace": {"trace_id": case.id}}
```

```bash
agentic-evals live examples/ci/suite.yaml --target target:answer --max-workers 4 --out report.json
agentic-evals live examples/ci/suite.yaml --target https://your-service.example/evaluate --timeout-seconds 10
```

Python targets accept `(input, *, case)` and return a sample payload containing
`output` and `trace`; the runner assigns `case_id`. File targets also accept
`path.py:function`. HTTP targets receive POST JSON `{input, case_id}` and return
the same payload. `--max-workers` defaults to 1 and must be positive; larger
values require thread-safe targets. Use only trusted suites and targets.

Since 0.9.0:

- `--timeout-seconds` applies to HTTP requests (default 30) and, when given,
  to Python targets. An `async def` target is cancelled at the timeout. A
  synchronous one keeps running in a daemon thread and its result is discarded.
- `--retries N` allows N extra attempts for a call that raises or times out;
  `--retry-backoff SECONDS` is the first wait, doubling after each retry.
- A case whose calls all fail is written to the report with `target_status`
  `timed_out` or `error` instead of exiting 2, and the command still exits 0.
  Gate on it with `max_timed_out_cases` / `max_target_error_cases`. An invalid
  target payload or an unloadable target still exits 2.

```bash
agentic-evals live examples/ci/suite.yaml --target target:answer \
  --retries 2 --retry-backoff 1 --timeout-seconds 20 --out report.json
```

See [judge reliability and live resilience](judge-reliability.md).

## Discover packs

```bash
agentic-evals pack list
agentic-evals pack show json-output-contract
agentic-evals pack show json-output-contract --suite --out suite.json
```

`show` prints the whole pack, including `required_scorers`; `--suite` exports a
plain `TestSuite`. Inspection does not require judge credentials. The factual-QA
pack requires a caller-supplied `factuality` evaluator when actually evaluated.

## Export AIOS evidence

`agentic-evals aios export` (0.10.0) turns a saved report, and optionally a
gate decision, into AI Operations Specification `0.4-draft` evaluation
evidence, or merges it into an existing Run artifact:

```bash
agentic-evals aios export examples/aios/report.json \
  --run examples/aios/run.json --targets examples/aios/targets.yaml \
  --gate examples/aios/gate-decision.json --out run-with-evaluations.json
```

A report with no target mapping, an unmapped case (unless `--allow-unmapped`)
or a target missing from `--run` exits 2. The export never decides a release:
a failed gate becomes a failed `release_gate` evaluation and the command still
exits 0. See [the AIOS evidence guide](aios-evidence.md).

## Worked CI and voice examples

Copy [evaluate.yml](../examples/ci/evaluate.yml) to `.github/workflows/` in your
repository, keeping its sample paths or replacing them with your own fixtures.
Substitute `failing-samples.jsonl` to exercise a deliberate gate failure (exit 1).
The [voice example](../voice-agent-evals/README.md#declarative-cli-080) exports
its suite and samples and uses its own custom registry with this CLI.

## Sibling compatibility

Evals 0.9.0 adds optional judge and live-target fields to report schema 1.0
(see [judge reliability](judge-reliability.md)); they validate against the
0.7.2 schemas as well. For 0.8.0: report schema 1.0 and gate wire shapes were
unchanged from Evals 0.7.2. Lens
0.8.0 approved-suite exports run unchanged; suite approval and release gates
remain separate. MCP 0.3.9 and Tower 0.6.1 can validate these native JSON
artifacts against their bundled 0.7.2 schemas. JUnit and Markdown must not be
passed to native artifact validators. Chaos remains the fault producer and
Sidecar owns supervision; Evals scores their explicitly supplied observations.
Native Evals JSON is not itself AIOS evidence; `aios export` (0.10.0) derives
it, and MCP `spec.validate_artifact` validates the merged Run.
No sibling runtime dependency floor or release is required for the CLI alone.
