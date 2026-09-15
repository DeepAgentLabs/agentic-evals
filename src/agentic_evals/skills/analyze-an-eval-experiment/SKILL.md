---
name: analyze-an-eval-experiment
description: Read two EvaluationReports (or EvalResults) past the headline pass rate -- paired differences, uncertainty, and subgroup breakdowns -- before declaring a winner.
---

# Analyze an eval experiment

## Trigger

Use this once `design-an-eval-experiment` has produced two `EvaluationReport`s
(or `EvalResult`s) to compare, before writing "v2 is better" anywhere that
influences a real decision.

## Do

1. Compare **paired** per-case results, not just the two aggregate
   `pass_rate`/`average_score` numbers — join both reports on `case_id`
   and look at which specific cases flipped. Two suites can have identical
   pass rates while disagreeing on every single case.
2. Ask how many cases would need to flip to change the conclusion. A
   3-percentage-point pass-rate difference on a 20-case suite is one case
   flipping; on a 2,000-case suite it's sixty. Treat the first as noise
   until `build-an-eval-dataset`/`size-a-test-suite` gives you enough
   cases to trust a difference that small.
3. Break results down by the tags set in `build-an-eval-dataset` — a small
   overall improvement that's actually a large improvement on one
   scenario and a regression on another is a different finding (and a
   different decision) than a uniform small gain.
4. For suites involving an `LLMRubricEvaluator`, re-run a sample of
   flipped cases and check whether the judge's verdict is stable (see
   `debug-a-flaky-llm-judge`) before counting a flip as a real difference
   between the two arms.
5. Report cost and latency deltas alongside the quality delta, even when
   the objective was framed purely around correctness — a quality win
   that comes with a large cost/latency regression changes what the
   actual decision should be.

## Avoid

- Don't report only the direction of the difference ("v2 improved pass
  rate") without the magnitude and the number of underlying cases — a
  reader can't judge whether that's a real signal without both.
- Don't discard "flaky" flipped cases from the analysis without noting it
  — silently dropping the hardest cases to explain inflates the apparent
  win.
- Don't let a large aggregate improvement hide a regression on a
  high-stakes subgroup (e.g. safety-tagged cases) — always check the
  subgroup breakdown even when the topline looks good.

## Check

- You can name the specific cases that flipped between arms, not just the
  aggregate delta.
- The result has been checked against a rough sense of whether the sample
  size actually supports the claimed difference.
- Cost/latency deltas are reported alongside the quality delta.
- Subgroup/tag breakdowns have been reviewed, not just the topline number.

## Risk

Headline pass-rate deltas are the easiest thing to over-trust precisely
because they're a single, clean-looking number. The real risk in this
stage isn't a calculation error — `evaluate_suite`'s arithmetic is
correct — it's mistaking noise for signal, or a uniform-looking gain for
one that's actually concentrated (or reversed) in the subgroup that
matters most for the decision this eval was built to inform.
