---
name: choose-a-rubric-template
description: Pick the right built-in RubricTemplate (FACTUALITY, SECURITY, SQL_CORRECTNESS, POSSIBLE, PII_LEAKAGE, TRANSLATION, BATTLE, CLOSED_QA, SUMMARY_QUALITY, MODERATION) instead of hand-writing a new one.
---

# Choose a rubric template

## Trigger

Use this when you're about to register an `LLMRubricEvaluator` and are
deciding which `agentic_evals.scorers.rubric` template fits the criterion —
or whether none of them do and you actually need a custom one.

## Do

1. Match the template to what's actually being judged, not the domain:
   - Comparing an answer to a known-good reference → `FACTUALITY`.
   - Grading a closed-ended answer against source context, no separate
     reference needed → `CLOSED_QA`.
   - Grading a summary against its source text → `SUMMARY_QUALITY`.
   - Ranking two candidate outputs against each other → `BATTLE` (put the
     second candidate in `EvaluatorConfig.config["reference"]`).
   - Checking translated text preserves meaning → `TRANSLATION`.
   - Reviewing code or command output for vulnerabilities → `SECURITY`.
   - Checking a generated SQL query is semantically right, not just
     textually similar to a reference query → `SQL_CORRECTNESS`.
   - Checking a response neither fabricates an answer to an unanswerable
     request nor over-refuses an answerable one → `POSSIBLE`.
   - Checking a response doesn't leak PII/sensitive data not already in
     context → `PII_LEAKAGE`.
   - Checking for hateful/violent/sexual/unsafe content → `MODERATION`.
2. If two templates seem to both apply (e.g. `SECURITY` and `MODERATION` on
   the same output), register both as separate evaluators rather than
   picking one — they grade different things and a report should show both.
3. If nothing fits, write a new `RubricTemplate` next to the existing ones
   in `rubric.py` rather than stuffing an unrelated criterion into an
   existing template's prompt — see `write-a-scorer` for the general rule
   on one-criterion-per-scorer.

## Avoid

- Don't use `FACTUALITY` when there's no reference answer to compare
  against — its prompt explicitly frames the grade around a reference; use
  `CLOSED_QA` (context-only) or `POSSIBLE` (answerability) instead.
- Don't use `SQL_CORRECTNESS` as a text-similarity check — it's meant to
  judge semantic equivalence of query *results*, so a reference query with
  the same effect but different column order/formatting should still score
  well; if you actually want textual similarity, use `levenshtein_similarity`.
- Don't reuse `POSSIBLE` as a generic correctness check — it specifically
  grades the fabricate-vs-refuse tradeoff, not whether an answerable
  request was answered *well* (that's `FACTUALITY`/`CLOSED_QA`).

## Check

- The template's `{input}`/`{expected}`/`{output}` placeholders line up
  with what you're actually passing to `.render()` — `SQL_CORRECTNESS` and
  `BATTLE` both read `{expected}` as a second artifact (a reference query,
  a second candidate), not as "the correct answer."
- You've run `parse_verdict` against a couple of realistic completions from
  your actual `complete_fn` model, not just the letter in isolation —
  models sometimes wrap the verdict in extra prose that still parses fine,
  but worth confirming once per new template/model pairing.

## Risk

Every rubric template here trades determinism for judgment: the same
input can grade differently between two model calls, especially near
threshold. Don't set a `threshold` where a one-notch verdict swing (e.g.
`SECURITY`'s B vs C, both 0.7 vs 0.3) flips pass/fail on borderline cases
without deliberately deciding that's the risk tolerance you want.
