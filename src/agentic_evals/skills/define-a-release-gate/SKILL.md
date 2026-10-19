---
name: define-a-release-gate
description: Choose GateConfig thresholds and understand the cost/latency edge cases before gating a release on an EvaluationReport.
---

# Define a release gate

## Trigger

Use this when you're wiring `evaluate_gate(report, GateConfig(...))` into a
CI check or release decision and need to pick real threshold values, not
just accept the defaults.

## Do

1. Start from the strict default (`min_pass_rate=1.0`: every case must
   pass) and loosen deliberately — it's easier to justify relaxing a gate
   later than to explain why it was never strict. `min_average_score` and
   `max_failed_cases` are extra checks that are off until you set them;
   add `min_average_score` when graded scores must stay above a floor
   even on cases that pass their own thresholds.
2. Set `max_average_latency_ms`/`max_total_cost_usd` only when you have a
   real budget in mind; leaving them `None` skips that check entirely
   rather than silently passing with a made-up number.
3. Read `GateDecision.reasons` and `.observed` in CI output, not just
   `.passed` — `reasons` names exactly which threshold failed, which is
   what someone debugging a red build actually needs.
4. Treat a gate failure on cost/latency as at least as actionable as a
   pass-rate failure — regressions there are often the first sign of a
   prompt or retry-loop change before quality visibly degrades.
5. When some cases matter more than the overall rate allows for, set
   `min_tag_pass_rate` or `min_metric_pass_rate` for that slice instead
   of raising `min_pass_rate` for everything — for example a tag that
   must pass in full while the suite as a whole tolerates a few misses.
6. For LLM-judged suites, keep `max_judge_unavailable_scores=0` (the
   default) so a judge that never delivered a verdict blocks the release,
   and add `min_judge_agreement` when judges run with `samples=N`. For
   live runs, add `max_timed_out_cases`/`max_target_error_cases` so a
   target outage is gated as an outage, not hidden in the pass rate.

## Avoid

- Don't set `max_total_cost_usd` on a suite where cost is routinely
  unavailable for some cases (e.g. a live target that doesn't report
  per-span cost) — the gate will fail every run with "cost is unavailable
  or incomplete," which looks like a real regression but isn't.
- Don't set `max_judge_unavailable_scores=None` to get a red build green —
  an unavailable judgment is missing evidence, not a pass.
- Don't loosen `min_pass_rate` to make a flaky suite pass — fix the
  flaky case or evaluator instead; a gate that's routinely overridden
  stops being trusted.
- Don't gate on a suite that mixes exploratory and release-blocking cases
  in one `TestSuite` — split them, since one flaky exploratory case
  shouldn't block a release.

## Check

- For declarative CI, run `agentic-evals evaluate SUITE SAMPLES --out report.json`
  then `agentic-evals gate report.json --config gate.yaml`. Evaluation success
  only means evidence was produced; gate exits 0 (pass), 1 (policy failed), or
  2 (input/usage error). Keep JSON evidence even when using JUnit or Markdown
  presentations. Exercise a deliberately failing fixture in CI.

- `evaluate_gate`'s cost check treats an incomplete cost picture
  (`summary.total_cost_usd is None`, or any case missing `cost_usd`) as
  "unavailable," never as `$0.00` — confirm your traces actually populate
  `estimated_cost_usd` before relying on this gate for cost control.
- The gate config you shipped to CI matches the one you tested locally —
  `GateConfig` is a plain Pydantic model, so diff it explicitly rather than
  trusting two configs "look the same."

## Risk

A gate that only checks `pass_rate` can pass while cost or latency drifts
upward every release, since neither is checked unless you explicitly set
`max_average_latency_ms`/`max_total_cost_usd`. If cost or latency matters
for the product, set both thresholds, don't just default to the pass-rate
check.
