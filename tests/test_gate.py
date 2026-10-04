from agentic_evals import (
    EvalTrace,
    EvaluationReport,
    EvaluationSample,
    EvaluatorConfig,
    GateConfig,
    TestCase,
    TestSuite,
    default_registry,
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
    assert len(decision.reasons) == 1

    strict = evaluate_gate(report, GateConfig(min_average_score=1.0, max_failed_cases=0))
    assert len(strict.reasons) == 3


def _near_match_report(outputs: list[str]) -> EvaluationReport:
    reference = "The combined total is 42."
    suite = TestSuite(
        name="release",
        version="1",
        cases=[
            TestCase(
                id=f"case-{index}",
                name="near match",
                evaluators=[
                    EvaluatorConfig(
                        name="levenshtein_similarity",
                        threshold=0.9,
                        config={"reference": reference},
                    )
                ],
            )
            for index in range(len(outputs))
        ],
    )
    samples = [
        EvaluationSample(case_id=f"case-{index}", output=output, trace=make_trace())
        for index, output in enumerate(outputs)
    ]
    return evaluate_suite(suite, samples, registry=default_registry())


def test_default_gate_passes_when_every_case_clears_its_own_threshold() -> None:
    report = _near_match_report(["The combined total is 42"])
    assert report.summary.pass_rate == 1.0
    assert report.summary.average_score < 1.0

    assert evaluate_gate(report, GateConfig()).passed
    assert not evaluate_gate(report, GateConfig(min_average_score=1.0)).passed


def test_min_pass_rate_alone_decides_how_many_failures_are_tolerated() -> None:
    report = _near_match_report(["The combined total is 42."] * 19 + ["unrelated"])
    assert report.summary.failed_cases == 1

    assert not evaluate_gate(report, GateConfig()).passed
    assert evaluate_gate(report, GateConfig(min_pass_rate=0.95)).passed
    assert not evaluate_gate(report, GateConfig(min_pass_rate=0.95, max_failed_cases=0)).passed


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
