---
name: debug-a-flaky-llm-judge
description: Diagnose an LLMRubricEvaluator or LLMJudgeEvaluator whose verdict changes between runs on the same input, before concluding the eval itself is unreliable.
---

# Debug a flaky LLM judge

## Trigger

Use this when a case graded by `LLMRubricEvaluator`/`LLMJudgeEvaluator`
passes on one run and fails on another with no change to the code under
test, and you need to find out whether the flakiness is in the judge, the
prompt, or the system being evaluated.

## Do

1. Re-run the exact same `(output, reference, input)` triple through
   `complete_fn` directly, several times, outside the eval — if the raw
   completion itself changes, the flakiness is in the judge model/prompt,
   not in `agentic_evals`.
2. Check the completions for near-boundary verdicts first (e.g.
   `FACTUALITY`'s B vs C, `SECURITY`'s B vs C) — a judge that's genuinely
   unsure tends to flip between adjacent letters, not jump from A to D;
   that pattern points at prompt ambiguity, not a broken template.
3. Lower `complete_fn`'s sampling temperature (or fix its seed, if the
   provider supports one) before touching anything in `agentic_evals` —
   this is a property of the caller-supplied model call, which this
   package deliberately never controls.
4. If the completion is stable but `parse_verdict` still raises
   intermittently, log the raw completion in `Score.metadata` (already
   populated as `raw_completion`) and check whether the model is
   occasionally wrapping the verdict in a format the regex misses (e.g.
   `**A**` vs `(A)`) — fix by tightening the prompt's "respond with only
   the letter" instruction, not by loosening the parser's token matching.
5. If the underlying system under test is itself nondeterministic (a live
   agent target with real tool calls), separate that from judge flakiness
   by re-scoring the *same recorded output* twice — same input to
   `LLMRubricEvaluator`, two judge calls — before blaming the agent.

## Avoid

- Don't raise the rubric's `threshold` to paper over flakiness near a
  boundary — that changes what counts as passing for every case, not just
  the flaky one.
- Don't retry a failed judge call silently inside a custom wrapper around
  `complete_fn` and keep only the passing result — that's p-hacking the
  eval; if you need retry-and-vote, implement it explicitly (e.g. majority
  of 3 calls) so the report shows what actually happened.
- Don't conclude "the eval is broken" from one flaky case — check whether
  it's isolated to one template/model pairing or every rubric-graded case
  in the suite before treating it as a package-level bug.

## Check

- You've confirmed the flakiness reproduces with `complete_fn` called
  directly (bypassing `TestSuite`/`evaluate_suite` entirely) — if it
  doesn't reproduce there, the bug is in how the suite builds the prompt
  or context, not in the model.
- `RubricTemplate.parse_verdict`'s `ValueError` (unparseable completion)
  and a genuine verdict flip (parseable, but a different letter) are being
  treated as two different failure modes in your triage, not lumped
  together as "the judge is flaky."

## Risk

An LLM judge that flips its verdict near a boundary is telling you the
distinction at that boundary is genuinely hard to grade from a prompt —
not necessarily that anything is broken. If a criterion keeps landing
exactly on the line between two verdicts, consider whether it needs a
deterministic scorer (`agentic_evals.scorers.text`) instead of a rubric,
per `write-a-scorer`'s guidance on preferring deterministic checks when
the criterion has an objectively checkable answer.
