---
name: report-eval-results
description: Turn an EvaluationReport/GateDecision into a summary a stakeholder can act on, without losing the caveats that made the analysis trustworthy.
---

# Report eval results

## Trigger

Use this after `analyze-an-eval-experiment` or a routine `TestSuite` run,
when the result needs to reach someone who wasn't in the room for the
analysis — a PR description, a release note, a Slack update.

## Do

1. Lead with the decision, not the metric: "safe to ship" / "blocked on
   X" / "no significant change," then the numbers that support it. A
   reader acting on the report needs the conclusion first and the
   evidence second.
2. Carry over every caveat `analyze-an-eval-experiment` surfaced —
   sample size, subgroup breakdowns, cost/latency tradeoffs, any judge
   instability. A report that states "v2 improved pass rate 3%" without
   noting that's one case out of twenty misleads exactly as much as a
   wrong number would.
3. Include the `GateDecision.reasons` verbatim when a gate failed — it
   already names the specific threshold that failed and the observed
   value; don't compress it down to "the eval failed."
4. Link to (or attach) the failing case IDs and their `Score.explanation`,
   not just the count — the person reading the report is often the one
   who has to go fix it, and re-deriving "which cases and why" from
   scratch wastes the report's whole purpose.
5. State what didn't change too, when relevant — "no regression on the
   red-team suite" is worth reporting explicitly, not only regressions.

## Avoid

- Don't round a nuanced finding into a single adjective ("looks good") if
  the underlying analysis had real caveats — that erases exactly the
  information `analyze-an-eval-experiment` worked to surface.
- Don't bury a gate failure or safety-suite regression at the bottom of a
  long report under unrelated passing metrics.
- Don't report a number without saying which suite/dataset/version
  produced it — a report that can't be traced back to a specific
  `TestSuite.version` and dataset snapshot can't be checked later.

## Check

- The report states a clear conclusion in its first line or two.
- Every caveat from the underlying analysis (sample size, subgroup
  splits, judge stability) survives into the report, not just the topline
  number.
- A reader who only skims the report still sees any gate failure or
  safety regression, not just the passing headline metric.

## Risk

A report that reads more confidently than the underlying analysis
supports is how a shaky 3-case improvement becomes "v2 is better" in
institutional memory — and gets cited to justify the next decision long
after the caveats are forgotten.
