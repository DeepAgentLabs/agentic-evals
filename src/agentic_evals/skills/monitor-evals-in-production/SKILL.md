---
name: monitor-evals-in-production
description: Turn a one-off TestSuite/pack into a recurring check against a live target, with alerting thresholds that account for production noise a pre-release run never sees.
---

# Monitor evals in production

## Trigger

Use this once a suite has passed `define-a-release-gate` and shipped, and
the objective shifts from "is this safe to ship" to "is this still
behaving in production" — recurring `run_live_suite` runs or scoring
sampled live traffic, not a single pre-release check.

## Do

1. Run the same suite (or an explicitly versioned subset) on a schedule
   against the live target via `run_live_suite`, rather than hand-copying
   the pre-release suite into a separate "prod" one that silently drifts
   out of sync — see `run-a-live-suite` for the trust/timeout mechanics
   of pointing a target at a real system.
2. Reuse or adapt a built-in `EvalPack` (`load_builtin_pack`) for common
   production checks like `tool-use-correctness` — packs pin the suite
   and required scorers together, so a monitoring job doesn't quietly
   diverge from the config that was actually validated pre-release.
3. Widen `GateConfig` thresholds deliberately for production monitoring
   versus pre-release gating — live traffic has real variance
   (`run-a-live-suite`) that a curated pre-release dataset doesn't, so the
   same strict threshold that's right for a release gate will alert
   constantly against production noise.
4. Alert on trend, not just a single run's `GateDecision.passed` — a
   pass rate that's noisy but stable around 95% looks different from one
   that's steadily declining toward 95%; only the second is a real signal
   worth paging someone over.
5. Sample rather than score every live request when volume is high, but
   make the sampling itself explicit and stable (e.g. a fixed percentage
   or hash-based selection) so month-over-month comparisons aren't
   comparing different implicit populations.

## Avoid

- Don't monitor with a suite that's never been validated
  (`validate-a-scorer`) against human judgment — production monitoring
  amplifies a bad scorer's mistakes across every future run instead of
  just one release decision.
- Don't reuse pre-release cost/latency thresholds unchanged — production
  traffic mix (input length, tool-call volume) usually differs from a
  curated pre-release dataset.
- Don't let a monitoring suite silently diverge from the suite that
  actually gated the release — if they're meant to be the same checks,
  load them from the same pack/file, not two hand-maintained copies.

## Check

- The monitoring suite's version is traceable to the pack/file that was
  validated before release, not a separately hand-maintained copy.
- Alert thresholds are set from observed production variance, not copied
  unchanged from the pre-release gate.
- There's a clear escalation path (who gets paged, what they do) for a
  monitoring alert — a monitor with no consumer is just a log nobody reads.

## Risk

Production monitoring is the last line of defense against a regression
`define-a-release-gate` didn't catch (a case shape the pre-release dataset
never covered, a dependency that changed after ship). A monitor tuned to
never alert is indistinguishable from no monitor at all until the
regression it should have caught actually happens.
