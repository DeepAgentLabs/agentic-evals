# Limitations

This page lists what the current Agentic Evals release does not do, so you can
plan around it. The package's PyPI classifier is Beta. Planned
work appears in the [Roadmap](../ROADMAP.md). Topic guides list further limits
for their own features.

---

## Inputs and traces

### Normalized traces only

Evals scores the `EvalTrace` / `EvalSpan` model, not arbitrary vendor JSON. It
has no built-in importer for any tracing tool. Convert external traces with
your own `trace_adapter=` callable; see [existing traces](guide/existing-traces.md).

### Tool checks need complete tool evidence

Tool expectations and trajectory scorers grade the recorded spans. A tool call
that was never recorded looks like a tool that was never called, and a missing
trace cannot establish tool behaviour.

### `max_turns` requires explicit metadata

`max_turns` checks need a turn count in the trace metadata. Evals does not infer
conversational turns from spans.

### Unknown cost stays unknown

Evals never computes cost. It reports the cost your traces carry, and
`total_cost_usd` stays `None` unless every case in scope has a known cost. A
cost-based gate fails on an unknown cost rather than treating it as $0.

---

## Scoring

### Implicit case checks stay on

`TestCase` fields such as `expected_output` and `expected_contains` run as
implicit checks alongside named scorers. Adding `contains_any` does not turn a
case into an any-match check: every `expected_contains` entry is still
required. See [case expectations and named scorers](scorers.md#case-expectations-and-named-scorers).

### Thresholds can loosen graded scorers

Named scorers pass when their value reaches `EvaluatorConfig.threshold`
(default 1.0). A lower threshold can pass a `numeric_diff` result outside its
configured tolerance. Keep 1.0 when the tolerance itself must be strict.

### Similarity is not correctness

Levenshtein and embedding similarity measure closeness to a reference, not
whether an answer is right. Embedding similarity needs your own `embed_fn`; no
embedding client ships with the package.

---

## LLM judges

### No built-in provider clients

Evals ships no model clients. You supply the completion callback;
`LLMRubricEvaluator` and `LLMJudgeEvaluator` format the prompt, call your
function and parse the verdict. Usage and cost are recorded only when your
callback returns them in a `JudgeResponse`.

### Rubric templates are prompts, not enforcement

`SECURITY`, `MODERATION`, `PII_LEAKAGE` and `SQL_CORRECTNESS` ask a model to
judge an output. They do not enforce policy at runtime or execute SQL.

### Agreement is not accuracy

`samples=N` measures how consistently a judge repeats its verdict. A judge can
agree with itself and still be wrong. Calibrating judges against human labels
is an AgenticLens feature, not part of this package.

---

## Live targets

### Trusted targets only

`PythonTarget` imports and runs code, and `HTTPTarget` sends case inputs to the
URL you configure. Run only suites, targets and registries you trust. With more
than one worker, targets must be thread-safe.

### Timeouts do not stop synchronous work

An `async def` target is cancelled at its timeout. A synchronous target keeps
running in a daemon thread and its result is discarded, so side effects it has
already started are not undone. See
[live target retries and timeouts](judge-reliability.md#live-target-retries-and-timeouts).

### Sync APIs inside an event loop

`evaluate_suite` and `run_live_suite` run async judges and targets with
`asyncio.run`, which fails inside a running event loop. Use `aevaluate_suite`
or `arun_live_suite` there.

---

## Release gates

### A report is not a release decision

`evaluate` and `live` exit 0 whenever a report is produced, including when
cases fail. Only `evaluate_gate()` or `agentic-evals gate` turns a report into
a pass/fail decision, and gate thresholds are yours to choose: a permissive
gate can deliberately let failed cases through.

---

## Containment scoring

### Scoring is not enforcement

`ContainmentEvaluator` checks authenticated evidence after the run. It does not
stop, revoke or block anything at runtime (Sidecar owns enforcement), does not
promise cancellation of running work, and does not prove that every event was
captured.

### A trusted verifier is required

The default registry has no verifier, so every containment score fails until
you register `ContainmentEvaluator(verifier=...)`. Trust keys come from the
host, never from samples. See [authenticated containment scoring](containment.md).

---

## Reports and contracts

### JUnit and Markdown are presentation formats

Gate on the native JSON report. JUnit XML and Markdown output are for CI
displays and summaries; they are not inputs to `gate` or `aios export`.

### AIOS export is draft and structural

AIOS evidence follows the draft `0.4-draft` specification. Evals ships no AIOS
validator, and you supply the mapping from cases to Run Steps. Structural
alignment does not mean the evaluation passed or the mapping was right. See
[AIOS evidence](aios-evidence.md).

### Not in this package

Dataset versioning and splitting, judge calibration, HTML report rendering,
failure diagnosis, and deeper trace-aware evaluators (handoffs, retrieval
groundedness) live in AgenticLens, which builds on this package's
`EvaluationReport`.

---

## Platform

### Python 3.10+ required

Agentic Evals supports CPython 3.10 to 3.14. Older Python versions are not
supported. See the [support policy](support-policy.md).
