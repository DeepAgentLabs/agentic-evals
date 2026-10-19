from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class EvalSpan(BaseModel):
    """The minimal per-span shape the evaluation engine actually inspects.

    Deliberately not AgenticLens's `Span` — a much richer model with agent
    names, model/provider, retries, timestamps, and more. This package
    never needs any of that, so it doesn't ask for it. Anyone with any
    trace-shaped data can produce an `EvalTrace` without depending on a
    specific tracing tool's schema.
    """

    tool_name: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


CostSource = Literal["measured", "estimated"]
TargetStatus = Literal["ok", "error", "timed_out"]


class EvalTrace(BaseModel):
    """The minimal per-run shape the evaluation engine actually inspects.

    `cost_source` records where `estimated_cost_usd` came from: `measured`
    (billed or provider-reported) or `estimated` (computed from token counts
    and a price table). Leave it `None` when the producer does not know;
    reports then count the cost as having unknown provenance rather than
    guessing.
    """

    trace_id: str = ""
    spans: list[EvalSpan] = Field(default_factory=list)
    total_latency_ms: float = 0.0
    estimated_cost_usd: float | None = None
    cost_source: CostSource | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluatorConfig(BaseModel):
    name: str = Field(min_length=1)
    threshold: float = Field(default=1.0, ge=0, le=1)
    required: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class TestCase(BaseModel):
    id: str
    name: str
    input: Any = None
    expected_output: str | None = None
    expected_contains: list[str] = Field(default_factory=list)
    output_json_schema: dict[str, Any] | None = None
    required_output_fields: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    required_tool_arguments: dict[str, list[str]] = Field(default_factory=dict)
    expected_tool_arguments: dict[str, dict[str, Any]] = Field(default_factory=dict)
    required_tool_order: list[str] = Field(default_factory=list)
    max_latency_ms: float | None = Field(default=None, gt=0)
    max_cost_usd: float | None = Field(default=None, ge=0)
    max_turns: int | None = Field(default=None, gt=0)
    evaluators: list[EvaluatorConfig] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_expectation(self) -> "TestCase":
        if not any(
            (
                self.expected_output is not None,
                self.expected_contains,
                self.output_json_schema is not None,
                self.required_output_fields,
                self.required_tools,
                self.forbidden_tools,
                self.required_tool_arguments,
                self.expected_tool_arguments,
                self.required_tool_order,
                self.max_latency_ms is not None,
                self.max_cost_usd is not None,
                self.max_turns is not None,
                self.evaluators,
            )
        ):
            raise ValueError("test case must define at least one expectation")
        return self


class TestSuite(BaseModel):
    name: str
    version: str
    description: str = ""
    cases: list[TestCase]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_case_ids(self) -> "TestSuite":
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("test case IDs must be unique")
        if not ids:
            raise ValueError("test suite must contain at least one case")
        return self


class EvaluationSample(BaseModel):
    case_id: str
    output: str
    trace: EvalTrace


class Score(BaseModel):
    """A single named judgment.

    `metric` is the stable key reports group by. It defaults to `name`;
    checks whose name carries a per-case detail (`contains:42`,
    `required_tool:lookup`) share one metric (`contains`, `required_tool`).

    A `skipped` score records that a check did not apply to a case. It
    never fails the case and is left out of averages and pass rates --
    build one with `Score.skip(...)`.

    `evaluator` and `evaluator_version` identify what produced the score.
    `evaluate_suite` stamps them: built-in checks are attributed to
    `BUILTIN_EVALUATOR` at this package's version, and registered
    evaluators to their registry name and their `version` attribute, if
    any. A `None` version means the evaluator did not declare one.
    """

    name: str
    metric: str = ""
    value: float = Field(ge=0, le=1)
    passed: bool
    required: bool = True
    skipped: bool = False
    explanation: str
    evaluator_type: str = "deterministic"
    evaluator: str = ""
    evaluator_version: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def default_metric_to_name(self) -> "Score":
        if not self.metric:
            self.metric = self.name
        return self

    @classmethod
    def skip(
        cls,
        name: str,
        explanation: str,
        *,
        metric: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "Score":
        """A score for a check that did not apply; `explanation` says why."""
        return cls(
            name=name,
            metric=metric,
            value=0.0,
            passed=False,
            required=False,
            skipped=True,
            explanation=explanation,
            metadata=metadata or {},
        )


class CaseEvaluation(BaseModel):
    """One case's result.

    `sample_available` is `False` when no sample was supplied for the case;
    its empty `trace_id` then means "no trace exists", not "trace ID lost".

    `target_status` is set only by live runs: `ok` when the target answered,
    `timed_out` when every attempt exceeded the case timeout, and `error`
    when the target raised or failed otherwise. A timed-out or errored case
    never passes, and is distinguishable from a case that answered wrongly.
    `target_attempts` counts the calls made, including retries, and
    `target_error` records the last failure.
    """

    case_id: str
    case_name: str
    passed: bool
    scores: list[Score]
    output: str
    trace_id: str
    latency_ms: float
    cost_usd: float | None = None
    cost_source: CostSource | None = None
    sample_available: bool = True
    target_status: TargetStatus | None = None
    target_attempts: int | None = Field(default=None, ge=1)
    target_error: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetricSummary(BaseModel):
    """How one metric did across the suite. Skipped scores are counted apart."""

    total: int
    passed: int
    failed: int
    skipped: int = 0
    pass_rate: float | None = Field(default=None, ge=0, le=1)
    average_score: float | None = Field(default=None, ge=0, le=1)


class TagSummary(BaseModel):
    """How the cases carrying one tag did."""

    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float = Field(ge=0, le=1)
    average_score: float | None = Field(default=None, ge=0, le=1)


class JudgeSummary(BaseModel):
    """What the suite's LLM judges cost, and how dependable they were.

    Counts cover evaluated (non-skipped) scores from `llm_judge` and
    `llm_rubric` evaluators. `unavailable_scores` are judgments the judge
    could not deliver after its retries; they never count as passes and
    `unavailable_cases` names the cases they belong to.

    `total_cost_usd` is the sum of `judge_cost_usd` over every judge score,
    and is `None` unless all of them recorded a cost (`priced_scores`
    says how many did). Judge cost is kept apart from the cost of the system
    under evaluation in `EvaluationSummary.total_cost_usd`.

    `sampled_scores` were judged more than once (`samples=N`).
    `case_agreement` holds, per case, the lowest agreement among its sampled
    judge scores: the share of samples that returned the most common verdict.
    """

    judge_scores: int = Field(default=0, ge=0)
    unavailable_scores: int = Field(default=0, ge=0)
    unavailable_cases: list[str] = Field(default_factory=list)
    retried_scores: int = Field(default=0, ge=0)
    priced_scores: int = Field(default=0, ge=0)
    total_cost_usd: float | None = Field(default=None, ge=0)
    cost_sources: dict[str, int] = Field(default_factory=dict)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_latency_ms: float = Field(default=0.0, ge=0)
    sampled_scores: int = Field(default=0, ge=0)
    min_agreement: float | None = Field(default=None, ge=0, le=1)
    average_agreement: float | None = Field(default=None, ge=0, le=1)
    case_agreement: dict[str, float] = Field(default_factory=dict)


class LiveSummary(BaseModel):
    """How a live target behaved across the suite (live runs only)."""

    total_cases: int = Field(ge=0)
    ok_cases: int = Field(ge=0)
    retried_cases: int = Field(default=0, ge=0)
    timed_out_cases: int = Field(default=0, ge=0)
    error_cases: int = Field(default=0, ge=0)
    timed_out_case_ids: list[str] = Field(default_factory=list)
    error_case_ids: list[str] = Field(default_factory=list)


class EvaluationSummary(BaseModel):
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float = Field(ge=0, le=1)
    average_score: float = Field(ge=0, le=1)
    total_cost_usd: float | None = None
    priced_cases: int = Field(default=0, ge=0)
    cost_sources: dict[str, int] = Field(default_factory=dict)
    average_latency_ms: float
    metrics: dict[str, MetricSummary] = Field(default_factory=dict)
    tags: dict[str, TagSummary] = Field(default_factory=dict)
    judge: JudgeSummary | None = None
    live: LiveSummary | None = None


class EvaluationReport(BaseModel):
    schema_version: str = "1.0"
    suite_name: str
    suite_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: EvaluationSummary
    cases: list[CaseEvaluation]


class LiveTarget(BaseModel):
    """Where `run_live_suite` sends each case.

    `timeout_seconds` bounds one call. HTTP targets always apply it (default
    30 s). Python targets apply it only when it is set explicitly: an
    `async def` target is cancelled at the timeout, while a synchronous one
    keeps running in its worker thread, but its result is discarded and the
    case is reported as `timed_out`.
    """

    kind: str = Field(pattern="^(python|http)$")
    timeout_seconds: float = Field(default=30.0, gt=0)


class PythonTarget(LiveTarget):
    kind: str = "python"
    callable_path: str


class HTTPTarget(LiveTarget):
    kind: str = "http"
    url: str
    method: str = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
