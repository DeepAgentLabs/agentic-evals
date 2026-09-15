---
name: run-a-live-suite
description: Point run_live_suite at a real PythonTarget or HTTPTarget safely, instead of only ever scoring pre-recorded EvaluationSamples.
---

# Run a live suite

## Trigger

Use this when you're moving a `TestSuite` from `evaluate_suite` (scoring
samples you already have) to `run_live_suite` (calling a real running
system for each case) — a Python callable via `PythonTarget` or an HTTP
endpoint via `HTTPTarget`.

## Do

1. Confirm the suite and target are both trusted before running — a
   `PythonTarget` executes `callable_path` as local code and an
   `HTTPTarget` will call whatever `url` the target names. Only run
   suite/target combinations you'd be comfortable running unattended.
2. Set `timeout_seconds` deliberately rather than accepting the default —
   a hung call to a live target blocks the whole suite run, and a timeout
   that's too short turns a slow-but-correct response into a false failure.
3. Start against a staging/sandboxed instance of the target, not
   production, especially for the first run of a new suite — a case with
   a destructive side effect (a `required_tools` check that actually
   triggers a real action) will really trigger it.
4. Check what `run_live_suite` does with a target-side exception (network
   error, non-2xx response, Python exception) versus a scoring failure —
   they should not be conflated in the report; a target outage isn't the
   same finding as the system giving a wrong answer.
5. Re-run flaky-looking live cases before concluding the system regressed
   — a live target reintroduces real network/latency variance that a
   pre-recorded `EvaluationSample` doesn't have.

## Avoid

- Don't point an `HTTPTarget` at a URL from an untrusted or unreviewed
  suite file — the suite author controls what gets called, with your
  credentials/network access.
- Don't reuse a `GateConfig` tuned against pre-recorded samples unchanged
  for a live run — live latency and cost are usually higher and noisier,
  so `max_average_latency_ms`/`max_total_cost_usd` thresholds calibrated
  offline will over-fire against a live target.
- Don't run a live suite against a shared production dependency (a real
  payments API, a real ticketing system) without confirming side effects
  are safe to repeat — CI re-runs a suite far more often than a human would.

## Check

- The suite file and the target's `callable_path`/`url` both came from a
  reviewed source, not an arbitrary input.
- `timeout_seconds` reflects the target's real p99 latency, not a guess.
- Target-side failures (timeout, non-2xx, exception) are visibly distinct
  in the report from scoring failures.

## Risk

`PythonTarget` and `HTTPTarget` are deliberately powerful — they are the
only two ways this package reaches outside its own process. Treating a
live-target suite file with the same trust as a plain data file is the
most direct way this package's design intentionally warns against:
"only point them at trusted suite files and trusted target definitions."
