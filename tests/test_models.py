import pytest
from pydantic import ValidationError

from agentic_evals import EvalTrace, TestCase, TestSuite


def test_test_case_requires_at_least_one_expectation() -> None:
    with pytest.raises(ValidationError, match="at least one expectation"):
        TestCase(id="case-1", name="empty")


def test_test_suite_requires_unique_case_ids() -> None:
    with pytest.raises(ValidationError, match="unique"):
        TestSuite(
            name="suite",
            version="1",
            cases=[
                TestCase(id="case-1", name="a", expected_output="ok"),
                TestCase(id="case-1", name="b", expected_output="ok"),
            ],
        )


def test_test_suite_requires_at_least_one_case() -> None:
    with pytest.raises(ValidationError):
        TestSuite(name="suite", version="1", cases=[])


def test_eval_trace_defaults_are_empty_and_unpriced() -> None:
    trace = EvalTrace()

    assert trace.trace_id == ""
    assert trace.spans == []
    assert trace.total_latency_ms == 0.0
    assert trace.estimated_cost_usd is None
