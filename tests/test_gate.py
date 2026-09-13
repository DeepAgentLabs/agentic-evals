from agentic_evals import (
    EvalTrace,
    EvaluationSample,
    GateConfig,
    TestCase,
    TestSuite,
    evaluate_gate,
    evaluate_suite,
)


def make_trace(*, cost: float | None = 0.002) -> EvalTrace:
    return EvalTrace(trace_id="trace-1", total_latency_ms=100.0, estimated_cost_usd=cost)


def test_missing_sample_fails_gate() -> None:
    suite = TestSuite(
        name="release",
        version="1",
        cases=[TestCase(id="missing", name="missing", expected_output="ok")],
    )
    report = evaluate_suite(suite, [])
    decision = evaluate_gate(report, GateConfig())
    assert not decision.passed
    assert len(decision.reasons) == 3


def test_gate_checks_operational_thresholds() -> None:
    suite = TestSuite(
        name="release",
        version="1",
        cases=[TestCase(id="case-1", name="answer", expected_output="ok")],
    )
    report = evaluate_suite(
        suite,
        [EvaluationSample(case_id="case-1", output="ok", trace=make_trace())],
    )
    decision = evaluate_gate(
        report,
        GateConfig(max_average_latency_ms=50, max_total_cost_usd=0.001),
    )
    assert not decision.passed
    assert len(decision.reasons) == 2


def test_gate_passes_when_thresholds_are_met() -> None:
    suite = TestSuite(
        name="release",
        version="1",
        cases=[TestCase(id="case-1", name="answer", expected_output="ok")],
    )
    report = evaluate_suite(
        suite,
        [EvaluationSample(case_id="case-1", output="ok", trace=make_trace())],
    )
    decision = evaluate_gate(report, GateConfig())
    assert decision.passed
    assert decision.reasons == []
