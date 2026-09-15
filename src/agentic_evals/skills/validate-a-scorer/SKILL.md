---
name: validate-a-scorer
description: Check that a new scorer or LLMRubricEvaluator actually agrees with expert judgment before trusting it to gate a release or block a PR.
---

# Validate a scorer

## Trigger

Use this after `write-a-scorer` produces a working evaluator and before it
feeds a `GateConfig` or CI check — especially for an `LLMRubricEvaluator`
or any custom `CallableEvaluator` whose pass/fail isn't a deterministic
fact you can verify by inspection.

## Do

1. Collect a small reference set (20-50 rows is plenty to start) that a
   human — ideally the person who set the objective in
   `define-an-eval-objective` — has labeled independently, without seeing
   the scorer's verdicts.
2. Run the scorer over the same rows and compute agreement (exact match on
   pass/fail, or correlation for graded scores) against the human labels.
   Report disagreement cases individually, not just an aggregate agreement
   rate — that's where the scorer's actual failure mode lives.
3. Look specifically for a scorer that's "right for the wrong reason" —
   e.g. `contains_any` passing because a forbidden phrase happens to
   overlap with a required one, or a rubric passing because the judge
   model is lenient on verbose answers regardless of content. Read the
   `Score.explanation`/`metadata` on the disagreement cases, not just the
   value.
4. For an `LLMRubricEvaluator`, re-run the same cases through `complete_fn`
   a second time and check the verdict is stable before blaming a
   disagreement on the rubric itself — see `debug-a-flaky-llm-judge` if
   it isn't.
5. Re-validate whenever the scorer, its rubric prompt, or its underlying
   judge model changes — agreement measured against one prompt version
   doesn't carry over to the next.

## Avoid

- Don't treat "the scorer runs without errors" as validation — a scorer
  that always returns 1.0 also runs without errors.
- Don't validate against cases the scorer's author also picked — use a
  reference set built independently (see `build-an-eval-dataset`'s point
  on holding out data) or the validation just confirms the author's own
  assumptions.
- Don't average agreement across very different criteria bundled into one
  evaluator — if the evaluator isn't single-criterion, split it first
  (`write-a-scorer`) so agreement is measurable per criterion.

## Check

- You have a documented agreement rate (or correlation) against
  independent human labels, not just a spot-check of a few examples.
- Every disagreement case has been read, not just counted — and you can
  say whether the scorer or the human label was actually right on each one.
- The validated version (prompt text, `complete_fn` model, threshold) is
  the same one that's about to be deployed — validation on a since-edited
  rubric doesn't count.

## Risk

An unvalidated scorer that looks reasonable on a handful of manual checks
can still systematically favor a particular style, length, or model
family — and once it's wired into a `GateConfig`, that bias becomes a
release policy nobody chose on purpose. The cost of skipping validation
isn't a bad eval; it's a confidently wrong one.
