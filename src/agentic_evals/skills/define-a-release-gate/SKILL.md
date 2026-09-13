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

1. Start from the strictest sensible defaults (`min_pass_rate=1.0`,
   `min_average_score=1.0`, `max_failed_cases=0`) and loosen deliberately —
   it's easier to justify relaxing a gate later than to explain why it was
   never strict.
2. Set `max_average_latency_ms`/`max_total_cost_usd` only when you have a
   real budget in mind; leaving them `None` skips that check entirely
   rather than silently passing with a made-up number.
3. Read `GateDecision.reasons` and `.observed` in CI output, not just
   `.passed` — `reasons` names exactly which threshold failed, which is
   what someone debugging a red build actually needs.
4. Treat a gate failure on cost/latency as at least as actionable as a
   pass-rate failure — regressions there are often the first sign of a
   prompt or retry-loop change before quality visibly degrades.

## Avoid

- Don't set `max_total_cost_usd` on a suite where cost is routinely
  unavailable for some cases (e.g. a live target that doesn't report
  per-span cost) — the gate will fail every run with "cost is unavailable
  or incomplete," which looks like a real regression but isn't.
- Don't loosen `min_pass_rate` to make a flaky suite pass — fix the
  flaky case or evaluator instead; a gate that's routinely overridden
  stops being trusted.
- Don't gate on a suite that mixes exploratory and release-blocking cases
  in one `TestSuite` — split them, since one flaky exploratory case
  shouldn't block a release.

## Check

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
