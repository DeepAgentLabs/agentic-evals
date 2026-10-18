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
| `evaluate`, `live` | Report produced, even if cases failed | Unused | Usage, input, target, evaluator or output error |
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
checks as failures. Optional failures and skipped checks appear in `system-out`;
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
the same payload. `--timeout-seconds` applies only to HTTP requests; Python
targets are not interrupted. `--max-workers` defaults to 1 and must be positive;
larger values require thread-safe targets. Use only trusted suites and targets.
The CLI adds no retry behavior; target errors exit 2 without a partial report.

## Discover packs

```bash
agentic-evals pack list
agentic-evals pack show json-output-contract
agentic-evals pack show json-output-contract --suite --out suite.json
```

`show` prints the whole pack, including `required_scorers`; `--suite` exports a
plain `TestSuite`. Inspection does not require judge credentials. The factual-QA
pack requires a caller-supplied `factuality` evaluator when actually evaluated.

## Worked CI and voice examples

Copy [evaluate.yml](../examples/ci/evaluate.yml) to `.github/workflows/` in your
repository, keeping its sample paths or replacing them with your own fixtures.
Substitute `failing-samples.jsonl` to exercise a deliberate gate failure (exit 1).
The [voice example](../voice-agent-evals/README.md#declarative-cli-080) exports
its suite and samples and uses its own custom registry with this CLI.

## Sibling compatibility

Report schema 1.0 and gate wire shapes are unchanged from Evals 0.7.2. Lens
0.8.0 approved-suite exports run unchanged; suite approval and release gates
remain separate. MCP 0.3.9 and Tower 0.6.1 can validate these native JSON
artifacts against their bundled 0.7.2 schemas. JUnit and Markdown must not be
passed to native artifact validators. Chaos remains the fault producer and
Sidecar owns supervision; Evals scores their explicitly supplied observations.
Native Evals JSON is not an AIOS evaluation-evidence export (planned for 0.10).
No sibling runtime dependency floor or release is required for the CLI alone.
