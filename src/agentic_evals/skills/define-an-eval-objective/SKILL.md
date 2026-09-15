---
name: define-an-eval-objective
description: Pin down the decision an eval needs to support and the evidence it needs to produce, before writing any TestCase or Eval() data.
---

# Define an eval objective

## Trigger

Use this before creating any `TestSuite`/`Eval()` for a new agent or
prompt change — when someone says "we should eval this" but hasn't said
what decision the numbers need to inform.

## Do

1. Write down the decision this eval exists to support ("ship prompt v2
   instead of v1", "block this PR", "alert on-call") before picking a
   single scorer — the decision determines the threshold, not the other
   way around.
2. Name who acts on the result and what action they take on pass vs. fail.
   If nobody can name the action, the eval isn't ready to build yet.
3. Decide up front whether this is a one-off comparison (→
   `design-an-eval-experiment`), a recurring release check (→
   `define-a-release-gate`), or ongoing production monitoring (→
   `monitor-evals-in-production`) — each wants a different shape of suite.
4. State the minimum pass rate / average score that would actually change
   the decision, before you see any numbers. Deciding this after seeing
   results is how thresholds get quietly bent to fit whatever shipped.

## Avoid

- Don't start from "let's measure everything we can" — an eval with ten
  unrelated scorers and no stated decision produces a report nobody acts on.
- Don't let the objective drift to match whatever the first run produces
  ("well, 80% is probably fine") — that's the threshold being reverse-
  engineered from the result, not set from the decision.
- Don't conflate "this eval exists" with "this eval is trustworthy" —
  objective-setting is step one; `validate-a-scorer` and
  `analyze-an-eval-experiment` are what earn the trust.

## Check

- You can state the objective as one sentence naming the decision, the
  actor, and the action on pass/fail.
- The threshold you'd act on is written down before the first `TestSuite`
  run, not chosen afterward.
- Every scorer you're about to add in `write-a-scorer` traces back to this
  objective — if a scorer doesn't move the decision, it doesn't belong in
  this suite.

## Risk

An eval built without a stated objective still produces numbers — and
numbers get trusted by default. The risk isn't "the eval fails to run,"
it's a plausible-looking pass rate steering a real decision that the eval
was never actually designed to inform.
