---
name: elicit-eval-criteria
description: Turn a vague quality bar ("the answers should be good") into concrete, checkable TestCase expectations before writing scorers.
---

# Elicit eval criteria

## Trigger

Use this after `define-an-eval-objective`, when the objective is clear but
the actual pass/fail criteria are still fuzzy — "the agent should behave
well," "answers should be accurate," "it shouldn't do anything weird."

## Do

1. Ask for concrete examples, not descriptions: get 3-5 real (or
   realistic) input/output pairs the stakeholder would call "clearly
   good" and 3-5 they'd call "clearly bad." Vague adjectives ("helpful",
   "safe") turn into checkable criteria only once you see what triggers
   the label.
2. Sort each criterion into one of `agentic_evals`'s existing checks
   before inventing a new mechanism: an exact/structural match
   (`expected_output`, `output_json_schema`), a required/forbidden action
   (`required_tools`, `forbidden_tools`), a resource bound (`max_latency_ms`,
   `max_cost_usd`, `max_turns`), or a genuinely subjective judgment (→
   `choose-a-rubric-template`).
3. Split compound criteria immediately — "accurate and well-formatted" is
   two `TestCase.evaluators` entries, not one. This mirrors
   `write-a-scorer`'s one-criterion-per-scorer rule, but the split has to
   happen at elicitation time or it gets baked into a single fuzzy ask.
4. For every criterion, ask what happens when the system does something
   it wasn't asked about (an extra tool call, an unrequested caveat) —
   silence on this is why `forbidden_tools` and `required_tool_arguments`
   exist; don't leave it implicit.
5. Capture disagreement, not just consensus. If two stakeholders would
   grade the same example differently, that criterion needs either a
   sharper definition or acknowledgment that it's inherently a judgment
   call (→ an LLM rubric with human spot-checks, not a hard gate).

## Avoid

- Don't accept "it should be correct" as a finished criterion — correct
  according to what: `expected_output` (exact), `expected_contains` (partial),
  `output_json_schema` (structural), or a rubric (`FACTUALITY`/`CLOSED_QA`)?
  Each implies a different scorer and a different failure mode.
- Don't let one stakeholder's five examples stand in for the full range of
  real inputs — cross-check against `build-an-eval-dataset`'s sourcing
  guidance before treating the criteria as complete.
- Don't skip straight to writing the scorer before the criterion has at
  least one worked example on each side of the line — a criterion you
  can't demonstrate on a concrete pair isn't elicited yet.

## Check

- Every criterion maps to a specific `TestCase` field or evaluator name
  you could name right now, not a future TODO.
- You have at least one concrete pass example and one concrete fail
  example per criterion, in the stakeholder's own words or data.
- Criteria that turned out to be compound have been split before being
  handed to `write-a-scorer`.

## Risk

A criterion elicited only as an adjective gets encoded as whatever the
first person who writes the scorer assumes it means — often not what the
stakeholder pictured. The mismatch surfaces later as "the eval says this
passed but it's obviously wrong," which erodes trust in the whole suite,
not just the one criterion.
