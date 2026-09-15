---
name: build-an-eval-dataset
description: Source, label, and split the TestCase/Eval() rows a suite runs against, so the dataset itself doesn't become the eval's weakest link.
---

# Build an eval dataset

## Trigger

Use this once criteria are elicited (`elicit-eval-criteria`) and before
`size-a-test-suite`, when you're deciding *what rows* go into a `TestSuite`
or an `Eval()` `data=[...]` list — not yet how many.

## Do

1. Source from at least two places: real production/user inputs (via
   `load_samples`/`run_live_suite` traces if you have them) and
   deliberately constructed edge cases. Real traffic alone under-samples
   rare-but-important failure shapes; hand-built cases alone drift from
   what users actually send.
2. Label each case with the *strongest* expectation it actually supports —
   prefer `expected_output` over `expected_contains` over a rubric,
   whenever the stronger check is genuinely valid for that row. Weak
   labels on cases that could support strong ones quietly lower the
   suite's power to catch regressions.
3. Include negative cases on purpose: inputs where the correct behavior is
   to refuse, use `forbidden_tools`, or return an error — not just cases
   where success means producing an answer. `POSSIBLE` and `required_tool_arguments`
   exist because "did nothing wrong" is its own criterion.
4. Hold out a slice you don't look at while iterating on the system under
   test. A dataset that's fully visible during development stops
   measuring generalization and starts measuring memorization of the eval
   itself.
5. Tag cases (`TestCase.tags`, `Case.metadata`) by scenario/criterion so a
   failing run can be filtered to "which category regressed," not just an
   aggregate pass rate — this is what `discover-failure-modes` and
   `report-eval-results` both depend on later.

## Avoid

- Don't build the dataset from the same examples used to write the prompt
  or agent — that measures whether the system fits its own training
  examples, not whether it generalizes.
- Don't let the dataset grow by accretion with no review — a suite that
  only ever gains cases and never prunes stale/duplicate/contradictory
  ones stops being legible; revisit it the same way you'd review scorers.
- Don't skip labeling "hard" cases as hard — if you know a row is a known
  edge case the system may reasonably fail, tag it so a regression there
  is triaged differently from a regression on a core-path case.

## Check

- Every case has the strongest expectation it can honestly support, not
  just whatever was fastest to write.
- Negative/refusal cases exist, not just positive "answer this correctly"
  cases.
- A held-out slice exists and its results aren't used to steer prompt/
  agent iteration.
- Cases are tagged well enough that a failing run can be sliced by
  scenario without re-reading every case by hand.

## Risk

A dataset skewed toward easy or already-passing cases makes every system
look good and catches nothing — the eval will report high pass rates
right up until a real regression ships. The failure is silent because a
skewed dataset doesn't look broken; it just never fails.
