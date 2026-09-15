"""Built-in scorers: reusable `(EvaluationContext) -> Score` functions.

Organized by what a scorer looks at:

- `text`: deterministic, no LLM (exact match, similarity, JSON/numeric diff).
- `rubric`: LLM-graded rubrics, provider-neutral -- the caller supplies the
  model call (`complete_fn`); this package only supplies the prompt and the
  verdict parser.
- `trajectory`: scorers that read `EvalTrace`/`EvalSpan` directly (tool-call
  precision/recall, redundant calls, latency/cost efficiency) -- the part
  a text-only scorer library has no equivalent for.

`default_registry()` returns an `EvaluatorRegistry` pre-populated with every
scorer in `text` and `trajectory` under a stable name. Rubric scorers need a
`complete_fn` to do anything, so register an `LLMRubricEvaluator` instance
for those explicitly.
"""

from agentic_evals.scorers.registry import builtin_scorer_names, default_registry
from agentic_evals.scorers.rubric import (
    BATTLE,
    CLOSED_QA,
    FACTUALITY,
    MODERATION,
    PII_LEAKAGE,
    POSSIBLE,
    SECURITY,
    SQL_CORRECTNESS,
    SUMMARY_QUALITY,
    TRANSLATION,
    LLMRubricEvaluator,
    RubricTemplate,
)
from agentic_evals.scorers.text import (
    contains_all,
    contains_any,
    embedding_similarity,
    ends_with,
    exact_match,
    json_diff,
    levenshtein_similarity,
    numeric_diff,
    numeric_range,
    regex_match,
    starts_with,
    valid_json,
)
from agentic_evals.scorers.trajectory import (
    no_redundant_tool_calls,
    tool_call_precision,
    tool_call_recall,
    trajectory_efficiency,
)

__all__ = [
    "BATTLE",
    "CLOSED_QA",
    "FACTUALITY",
    "MODERATION",
    "PII_LEAKAGE",
    "POSSIBLE",
    "SECURITY",
    "SQL_CORRECTNESS",
    "SUMMARY_QUALITY",
    "TRANSLATION",
    "LLMRubricEvaluator",
    "RubricTemplate",
    "builtin_scorer_names",
    "contains_all",
    "contains_any",
    "default_registry",
    "embedding_similarity",
    "ends_with",
    "exact_match",
    "json_diff",
    "levenshtein_similarity",
    "no_redundant_tool_calls",
    "numeric_diff",
    "numeric_range",
    "regex_match",
    "starts_with",
    "tool_call_precision",
    "tool_call_recall",
    "trajectory_efficiency",
    "valid_json",
]
