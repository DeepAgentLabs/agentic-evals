import pytest

from agentic_evals import (
    EvalSpan,
    EvalTrace,
    EvaluationContext,
    EvaluationSample,
    EvaluatorConfig,
    TestCase,
    no_redundant_tool_calls,
    tool_call_precision,
    tool_call_recall,
    trajectory_efficiency,
)


def _context(
    *,
    spans: list[EvalSpan],
    required_tools: list[str] | None = None,
    threshold: float = 1.0,
    config: dict | None = None,
    latency_ms: float = 100.0,
    cost: float | None = 0.01,
) -> EvaluationContext:
    case = TestCase(
        id="case-1", name="case", expected_contains=["ok"], required_tools=required_tools or []
    )
    trace = EvalTrace(total_latency_ms=latency_ms, estimated_cost_usd=cost, spans=spans)
    sample = EvaluationSample(case_id="case-1", output="ok", trace=trace)
    return EvaluationContext(
        case=case,
        sample=sample,
        config=EvaluatorConfig(name="scorer", threshold=threshold, config=config or {}),
    )


def test_tool_call_precision_falls_back_to_required_tools() -> None:
    context = _context(
        spans=[EvalSpan(tool_name="lookup"), EvalSpan(tool_name="unexpected")],
        required_tools=["lookup"],
        threshold=0.4,
    )
    score = tool_call_precision(context)
    assert score.value == 0.5
    assert score.passed is True


def test_tool_call_precision_uses_explicit_allowed_tools() -> None:
    context = _context(
        spans=[EvalSpan(tool_name="lookup"), EvalSpan(tool_name="format")],
        config={"allowed_tools": ["lookup", "format"]},
    )
    assert tool_call_precision(context).value == 1.0


def test_tool_call_precision_requires_a_tool_call() -> None:
    context = _context(spans=[], required_tools=["lookup"])
    with pytest.raises(ValueError, match="at least one tool call"):
        tool_call_precision(context)


def test_tool_call_recall_counts_required_tools_called() -> None:
    context = _context(
        spans=[EvalSpan(tool_name="lookup")],
        required_tools=["lookup", "format"],
        threshold=0.4,
    )
    score = tool_call_recall(context)
    assert score.value == 0.5
    assert score.passed is True


def test_tool_call_recall_requires_required_tools_configured() -> None:
    context = _context(spans=[EvalSpan(tool_name="lookup")], required_tools=[])
    with pytest.raises(ValueError, match="required_tools"):
        tool_call_recall(context)


def test_no_redundant_tool_calls_penalizes_exact_duplicates() -> None:
    context = _context(
        spans=[
            EvalSpan(tool_name="lookup", attributes={"id": "1"}),
            EvalSpan(tool_name="lookup", attributes={"id": "1"}),
            EvalSpan(tool_name="lookup", attributes={"id": "2"}),
        ],
        threshold=0.5,
    )
    score = no_redundant_tool_calls(context)
    assert score.value == pytest.approx(2 / 3)
    assert score.passed is True


def test_no_redundant_tool_calls_perfect_when_all_unique() -> None:
    context = _context(spans=[EvalSpan(tool_name="lookup"), EvalSpan(tool_name="format")])
    assert no_redundant_tool_calls(context).value == 1.0


def test_trajectory_efficiency_requires_a_baseline() -> None:
    context = _context(spans=[])
    with pytest.raises(ValueError, match="baseline_latency_ms.*or.*baseline_cost_usd"):
        trajectory_efficiency(context)


def test_trajectory_efficiency_scores_at_or_under_baseline_as_one() -> None:
    context = _context(spans=[], latency_ms=100.0, config={"baseline_latency_ms": 100.0})
    score = trajectory_efficiency(context)
    assert score.value == 1.0


def test_trajectory_efficiency_penalizes_overrun() -> None:
    context = _context(
        spans=[], latency_ms=200.0, config={"baseline_latency_ms": 100.0}, threshold=0.9
    )
    score = trajectory_efficiency(context)
    assert score.value == pytest.approx(0.5)
    assert score.passed is False


def test_trajectory_efficiency_skips_cost_when_unavailable() -> None:
    context = _context(
        spans=[],
        latency_ms=100.0,
        cost=None,
        config={"baseline_latency_ms": 100.0, "baseline_cost_usd": 0.01},
    )
    score = trajectory_efficiency(context)
    assert score.value == 1.0  # only the latency ratio contributed
