---
name: write-a-scorer
description: Choose and implement the right kind of scorer (deterministic, embedding, LLM rubric, or trajectory) for a new eval criterion in agentic_evals.
---

# Write a scorer

## Trigger

Use this when you're adding a new grading criterion to a `TestCase` and
aren't sure whether to reach for a built-in scorer, write a custom
`CallableEvaluator`, or reach for an LLM judge.

## Do

1. Name one criterion per scorer. If you're tempted to score "correctness
   and tone" in a single evaluator, that's two evaluators.
2. Prefer `agentic_evals.scorers.text` first: `exact_match`,
   `contains_all`/`contains_any`, `valid_json`, `json_diff`, `numeric_diff`
   are deterministic, free, and never flaky — use them whenever the
   criterion has an objectively checkable answer.
3. Reach for `embedding_similarity` only when near-miss wording should
   still pass and you already have an embedding call available; it needs
   an `embed_fn` in `EvaluatorConfig.config` since this package never
   calls an embedding API itself.
4. Reach for `LLMRubricEvaluator` + a `RubricTemplate` only when the
   criterion is genuinely subjective (factual consistency, summary
   quality, pairwise preference). Supply your own `complete_fn` —
   `agentic_evals` never calls a model.
5. Reach for `agentic_evals.scorers.trajectory` (`tool_call_precision`,
   `tool_call_recall`, `no_redundant_tool_calls`, `trajectory_efficiency`)
   when the criterion is about *how* the agent got the answer, not just
   the final text.
6. If none of the above fit, write a plain `CallableEvaluator(name, fn)` —
   `fn` takes an `EvaluationContext` and returns a `Score` or `list[Score]`.

## Avoid

- Don't wrap an LLM judge around something a deterministic check already
  covers (`valid_json`, `json_diff`) — it's slower, costs money, and can
  disagree with itself between runs.
- Don't average unrelated criteria into a single `Score.value` — register
  them as separate evaluators so a report shows exactly what failed.
- Don't hardcode a specific model or embedding provider inside a scorer
  function — take `complete_fn`/`embed_fn` as a parameter, the way every
  built-in rubric/embedding scorer does.

## Check

- The scorer raises a clear `ValueError` when its required input
  (`expected_output`, `case.input`, a trace with tool calls) is missing,
  rather than silently returning a meaningless score.
- `Score.value` stays in `[0, 1]`; a hard pass/fail scorer returns exactly
  `0.0` or `1.0`, a graded one returns a genuine gradient.
- You've tested the scorer directly against at least one passing and one
  failing sample (call it with a hand-built `EvaluationContext`), not only
  through a full suite run.

## Risk

An LLM-graded rubric is only as good as its verdict parsing —
`RubricTemplate.parse_verdict` raises if the model's completion doesn't
contain one of the expected tokens. Don't swallow that exception upstream:
a silently defaulted score is worse than a visible failure.
