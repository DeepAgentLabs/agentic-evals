---
name: discover-failure-modes
description: Turn a low pass rate in an EvaluationReport into named, actionable failure categories instead of a flat list of failing case IDs.
---

# Discover failure modes

## Trigger

Use this when a `TestSuite` run comes back with a pass rate below target
and the next step is figuring out *why*, not just *how many* — before
filing a single vague bug ("agent sometimes gets things wrong").

## Do

1. Group failing `CaseEvaluation`s by which scorer failed them
   (`Score.name`, `passed=False`), not just by case — a suite where ten
   cases fail `tool_call_precision` and two fail `numeric_diff` has two
   distinct problems, not twelve.
2. Cross-reference failures against the tags set in `build-an-eval-dataset`
   — a failure mode concentrated in one scenario tag points at a specific
   fix; one spread evenly across all tags points at something systemic
   (a prompt regression, a shared tool wrapper).
3. Read `Score.explanation` on every failure in a candidate cluster before
   naming it a single failure mode — two cases that both "failed
   `exact_match`" can fail for unrelated reasons (a formatting difference
   vs. a genuinely wrong answer).
4. For agentic/tool-use failures, use the trajectory scorers'
   (`tool_call_precision`, `tool_call_recall`, `no_redundant_tool_calls`)
   explanations to distinguish "wrong tool called," "right tool, wrong
   arguments," and "right tool, but also unnecessary extra calls" — these
   point at different parts of the system to fix.
5. Once a cluster is named, add a `TestCase` (or several) that isolates it
   as a minimal reproduction — a failure mode without a minimal
   reproducing case tends to silently stop being tracked once the
   original noisy failing cases are fixed by something else.

## Avoid

- Don't report "N cases failed" as the finding — that's the input to this
  skill, not the output. The output is named clusters with a
  representative example each.
- Don't assume every case failing the same scorer shares the same root
  cause — verify by reading explanations, not by scorer name alone.
- Don't skip straight to fixing the first failure you understand — a
  quick fix for the most obvious cluster can mask a rarer, more severe one
  underneath it in the same run.

## Check

- Every named failure mode has a representative case and a one-sentence
  description of the mechanism, not just a count.
- Failure modes are cross-checked against tags/subgroups, not just
  scorer names.
- At least one minimal reproducing `TestCase` exists per confirmed
  failure mode, so it can be tracked as fixed or regressed later.

## Risk

Treating a pass-rate drop as one undifferentiated problem leads to a fix
that addresses whichever failure was easiest to spot, while a smaller,
more severe cluster (e.g. a `forbidden_tools` violation buried among many
formatting mismatches) goes unnoticed inside the same failing set.
