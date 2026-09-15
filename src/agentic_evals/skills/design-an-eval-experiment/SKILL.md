---
name: design-an-eval-experiment
description: Set up a fair A/B comparison between two prompts/agents/models with agentic_evals, so the diff you measure is the one you intended to measure.
---

# Design an eval experiment

## Trigger

Use this when the objective (`define-an-eval-objective`) is a comparison —
"is prompt v2 better than v1," "does this new tool improve results" —
before running either variant through a `TestSuite`/`Eval()`.

## Do

1. Run both variants against the exact same dataset (`build-an-eval-dataset`)
   and the exact same `TestSuite`/scorer configuration — same
   `EvaluatorConfig.threshold`, same rubric `complete_fn` model if an
   `LLMRubricEvaluator` is involved. A different judge model between arms
   invalidates the comparison before it starts.
2. Decide the primary metric before running either arm — pass rate,
   `average_score`, a specific scorer's average, cost, or latency. If two
   metrics disagree (v2 has a higher pass rate but higher cost), that's a
   real tradeoff to report, not something to resolve by picking whichever
   metric favors the arm you expected to win.
3. For pairwise judging (`BATTLE`), counterbalance which variant is
   presented as "candidate A" — a fixed ordering can bias a judge toward
   whichever position it saw first, independent of quality.
4. Keep the dataset **held out** from whatever process produced the
   variant being tested — if v2's prompt was iterated against the same
   cases now used to score it, the comparison measures overfitting, not
   improvement.
5. Record the full configuration (suite version, scorer versions, judge
   model, dataset snapshot) alongside the result — an experiment result
   with no recorded configuration can't be reproduced or trusted later.

## Avoid

- Don't compare `EvaluationReport`s that ran against different dataset
  versions, even if both are nominally "the same suite" — check
  `TestSuite.version` and the underlying data actually match.
- Don't treat a single run of each arm as sufficient when either arm
  involves an LLM judge or a nondeterministic live target — see
  `analyze-an-eval-experiment` for how to size the number of repeats.
- Don't cherry-pick which scorer's average to report after seeing which
  one favors the outcome you wanted — the primary metric is chosen in
  step 2, before the results exist.

## Check

- Both arms ran against the identical dataset and suite configuration,
  confirmed by diffing the actual files/config, not by assumption.
- The primary metric was written down before either arm's results were
  seen.
- Any judge involved graded both arms with the same model and the same
  prompt template/version.

## Risk

An experiment that differs in more than one variable — a new prompt *and*
a newer judge model, a new agent *and* a slightly different dataset slice
— can't attribute a result to the change you actually care about. A
confident-looking "v2 wins" number is worse than no number at all if the
win is actually explained by something else that quietly changed at the
same time.
