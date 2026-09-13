---
name: size-a-test-suite
description: Decide how many TestCases a TestSuite needs and how to split criteria across them without bundling unrelated checks into one case.
---

# Size a test suite

## Trigger

Use this when you're building a new `TestSuite` and unsure whether to add
more `TestCase`s, add more `evaluators` to an existing case, or split one
case into several.

## Do

1. One `TestCase` per input/scenario, not per criterion — if the same
   input needs three checks (contains a fact, calls the right tool, stays
   under a latency budget), that's one `TestCase` with three entries in
   `evaluators`/threshold fields, not three cases.
2. Cover the boundary the criterion actually claims to check: a
   `max_turns` case needs both a passing sample at the limit and a failing
   one just over it, not just one happy-path sample.
3. Include at least one adversarial or edge-case input per suite (empty
   input, a refusal, a malformed tool response) — `TestCase.require
   expectation`'s validator forces every case to declare *something* to
   check, so use that to your advantage: even an edge case needs a real
   expectation, not a placeholder.
4. Give every `TestCase.id` a stable, descriptive slug (`refund-large-amount`,
   not `case-7`) — `TestSuite` rejects duplicate IDs, and stable IDs are
   what `EvaluationSample.case_id` and dataset splits key off of.

## Avoid

- Don't cram every acceptance criterion for a feature into one
  mega-`TestCase` with a dozen `evaluators` entries — when it fails, a
  report should point at one clear thing, not require reading six scores
  to find the one that mattered.
- Don't size a suite by "how many cases feels thorough" — size it by
  "which distinct behaviors would a regression actually break," and stop
  once you've covered them once each plus their edges.
- Don't let a suite silently grow stale: a case with an `expected_output`
  that references a value your system no longer produces will fail forever
  and gets ignored, which is worse than not having the case.

## Check

- Every `TestCase` has at least one expectation set (`TestCase`'s own
  validator enforces this) — if you're stuck picking one, that's a signal
  the case doesn't yet test anything specific.
- Running the suite against a known-good sample set produces a 100% pass
  rate; running it against a known-bad set fails on the case(s) you'd
  expect, not a different one.

## Risk

A suite that's easy to make pass by construction (loose thresholds, only
happy-path cases) gives false confidence in a release gate — it's the
gate's job to fail sometimes, so a suite that never produces a genuine
failure during development hasn't been tested itself.
