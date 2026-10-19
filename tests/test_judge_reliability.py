"""Judge usage, retries, unavailable outcomes and repeated judging (v0.9)."""

import asyncio
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from agentic_evals import (
    FACTUALITY,
    EvalTrace,
    EvaluationContext,
    EvaluationSample,
    EvaluatorConfig,
    EvaluatorRegistry,
    GateConfig,
    JudgeResponse,
    LLMJudgeEvaluator,
    LLMRubricEvaluator,
    RetryPolicy,
    Score,
    TestCase,
    TestSuite,
    evaluate_gate,
    evaluate_suite,
)


def _suite(*, required: bool = True, cases: int = 3) -> TestSuite:
    return TestSuite(
        name="judged",
        version="1",
        cases=[
            TestCase(
                id=f"case-{index}",
                name=f"Case {index}",
                input="What is the capital of France?",
                evaluators=[
                    EvaluatorConfig(
                        name="factuality",
                        threshold=0.6,
                        required=required,
                        config={"reference": "Paris"},
                    )
                ],
            )
            for index in range(1, cases + 1)
        ],
    )


def _samples(suite: TestSuite) -> list[EvaluationSample]:
    return [
        EvaluationSample(case_id=case.id, output="Paris", trace=EvalTrace(trace_id=case.id))
        for case in suite.cases
    ]


def _registry(evaluator: Any) -> EvaluatorRegistry:
    registry = EvaluatorRegistry()
    registry.register(evaluator)
    return registry


def _scripted(responses: list[Any]) -> Callable[[str], Any]:
    """A complete_fn that plays `responses` in order; exceptions are raised."""
    queue: Iterator[Any] = iter(responses)

    def complete(prompt: str) -> Any:
        item = next(queue)
        if isinstance(item, Exception):
            raise item
        return item

    return complete


def _priced(text: str, cost: float = 0.001) -> JudgeResponse:
    return JudgeResponse(
        text=text,
        input_tokens=100,
        output_tokens=5,
        cost_usd=cost,
        cost_source="measured",
        model="judge-model",
        provider="judge-provider",
    )


def test_rubric_records_judge_usage_and_report_sums_it() -> None:
    suite = _suite()
    costs = [0.001, 0.002, 0.004]
    evaluator = LLMRubricEvaluator(
        "factuality", FACTUALITY, _scripted([_priced("A", cost) for cost in costs])
    )
    report = evaluate_suite(suite, _samples(suite), registry=_registry(evaluator))

    scores = [case.scores[0] for case in report.cases]
    for score, cost in zip(scores, costs, strict=True):
        assert score.metadata["judge_cost_usd"] == cost
        assert score.metadata["judge_cost_source"] == "measured"
        assert score.metadata["judge_input_tokens"] == 100
        assert score.metadata["judge_model"] == "judge-model"
        assert score.metadata["judge_provider"] == "judge-provider"
        assert score.metadata["judge_status"] == "ok"
        assert score.metadata["judge_attempts"] == 1
        assert score.metadata["judge_latency_ms"] >= 0

    judge = report.summary.judge
    assert judge is not None
    assert judge.judge_scores == 3
    assert judge.priced_scores == 3
    assert judge.total_cost_usd == pytest.approx(
        sum(score.metadata["judge_cost_usd"] for score in scores)
    )
    assert judge.cost_sources == {"measured": 3}
    assert judge.input_tokens == 300
    assert judge.output_tokens == 15
    assert judge.total_latency_ms == pytest.approx(
        sum(score.metadata["judge_latency_ms"] for score in scores), abs=0.01
    )
    # Judge spend is kept apart from the cost of the system under evaluation.
    assert report.summary.total_cost_usd is None


def test_judge_cost_total_is_none_when_any_score_is_unpriced() -> None:
    suite = _suite(cases=2)
    evaluator = LLMRubricEvaluator("factuality", FACTUALITY, _scripted([_priced("A"), "A"]))
    report = evaluate_suite(suite, _samples(suite), registry=_registry(evaluator))

    assert report.summary.judge is not None
    assert report.summary.judge.priced_scores == 1
    assert report.summary.judge.total_cost_usd is None
    decision = evaluate_gate(report, GateConfig(max_judge_cost_usd=1.0))
    assert not decision.passed
    assert "1 of 2" in decision.reasons[0]


def test_cost_without_source_is_recorded_as_estimated() -> None:
    assert JudgeResponse(text="A", cost_usd=0.5).usage_metadata() == {
        "judge_cost_usd": 0.5,
        "judge_cost_source": "estimated",
    }


def test_retry_recovers_from_transient_judge_errors() -> None:
    suite = _suite(cases=1)
    evaluator = LLMRubricEvaluator(
        "factuality",
        FACTUALITY,
        _scripted([ConnectionError("rate limited"), "not a verdict", "A"]),
        retry=RetryPolicy(max_attempts=3),
    )
    report = evaluate_suite(suite, _samples(suite), registry=_registry(evaluator))

    [score] = report.cases[0].scores
    assert score.passed
    assert score.metadata["judge_attempts"] == 3
    assert report.summary.judge is not None
    assert report.summary.judge.retried_scores == 1
    assert report.summary.judge.unavailable_scores == 0


def test_a_judge_failing_on_some_calls_names_cases_and_fails_the_default_gate() -> None:
    suite = _suite(required=False)
    evaluator = LLMRubricEvaluator(
        "factuality",
        FACTUALITY,
        _scripted(["A", TimeoutError("judge timed out"), TimeoutError("judge timed out"), "A"]),
        retry=RetryPolicy(max_attempts=2),
    )
    report = evaluate_suite(suite, _samples(suite), registry=_registry(evaluator))

    unavailable = report.cases[1].scores[0]
    assert unavailable.value == 0.0
    assert not unavailable.passed
    assert unavailable.metadata["judge_status"] == "unavailable"
    assert unavailable.metadata["judge_attempts"] == 2
    assert unavailable.metadata["judge_error"] == "TimeoutError: judge timed out"
    assert "unavailable after 2 attempt(s)" in unavailable.explanation
    assert unavailable.evaluator == "factuality"

    judge = report.summary.judge
    assert judge is not None
    assert judge.unavailable_scores == 1
    assert judge.unavailable_cases == ["case-2"]
    # The judge was optional, so every case passes, yet the default gate fails.
    assert report.summary.pass_rate == 1.0
    decision = evaluate_gate(report, GateConfig())
    assert not decision.passed
    assert "'case-2'" in decision.reasons[0]
    assert decision.observed["judge_unavailable_scores"] == 1
    assert evaluate_gate(report, GateConfig(max_judge_unavailable_scores=None)).passed


def test_unavailable_never_passes_even_with_a_zero_threshold() -> None:
    def broken(context: EvaluationContext) -> Score:
        raise RuntimeError("provider down")

    evaluator = LLMJudgeEvaluator("judge", broken)
    case = TestCase(id="c", name="c", evaluators=[EvaluatorConfig(name="judge", threshold=0.0)])
    sample = EvaluationSample(case_id="c", output="x", trace=EvalTrace())
    [score] = evaluator.evaluate(
        EvaluationContext(case=case, sample=sample, config=case.evaluators[0])
    )
    assert not score.passed
    assert score.metadata["judge_status"] == "unavailable"


def test_repeated_judging_reports_agreement_per_case() -> None:
    suite = _suite(cases=2)
    evaluator = LLMRubricEvaluator(
        "factuality",
        FACTUALITY,
        # case-1: A, A, A (stable). case-2: A, D, D (flaky).
        _scripted([_priced(text) for text in ["A", "A", "A", "A", "D", "D"]]),
        samples=3,
    )
    report = evaluate_suite(suite, _samples(suite), registry=_registry(evaluator))

    stable, flaky = (case.scores[0] for case in report.cases)
    assert stable.metadata["judge_agreement"] == 1.0
    assert stable.metadata["judge_verdicts"] == ["A", "A", "A"]
    assert stable.value == 1.0
    assert flaky.metadata["judge_agreement"] == pytest.approx(2 / 3, abs=1e-6)
    assert flaky.metadata["verdict"] == "D"
    assert flaky.value == pytest.approx(1 / 3)
    assert not flaky.passed
    assert flaky.metadata["judge_samples"] == 3
    assert flaky.metadata["judge_cost_usd"] == pytest.approx(0.003)
    assert flaky.metadata["judge_input_tokens"] == 300
    assert "agreement 67%" in flaky.explanation

    judge = report.summary.judge
    assert judge is not None
    assert judge.sampled_scores == 2
    assert judge.min_agreement == pytest.approx(2 / 3, abs=1e-6)
    assert judge.case_agreement == {"case-1": 1.0, "case-2": pytest.approx(2 / 3, abs=1e-6)}
    assert judge.total_cost_usd == pytest.approx(0.006)

    decision = evaluate_gate(report, GateConfig(min_pass_rate=0, min_judge_agreement=0.8))
    assert not decision.passed
    assert "'case-2'" in decision.reasons[0]
    assert "'case-1'" not in decision.reasons[0]


def test_agreement_ties_resolve_to_the_lower_verdict() -> None:
    suite = _suite(cases=1)
    evaluator = LLMRubricEvaluator("factuality", FACTUALITY, _scripted(["A", "D"]), samples=2)
    report = evaluate_suite(suite, _samples(suite), registry=_registry(evaluator))

    [score] = report.cases[0].scores
    assert score.metadata["verdict"] == "D"
    assert score.metadata["judge_agreement"] == 0.5
    assert score.value == 0.5


def test_a_failed_sample_makes_the_whole_score_unavailable() -> None:
    suite = _suite(cases=1)
    evaluator = LLMRubricEvaluator(
        "factuality", FACTUALITY, _scripted(["A", ValueError("bad")]), samples=3
    )
    report = evaluate_suite(suite, _samples(suite), registry=_registry(evaluator))

    [score] = report.cases[0].scores
    assert score.metadata["judge_status"] == "unavailable"
    assert score.metadata["judge_completed_samples"] == 1
    assert not report.cases[0].passed


def test_min_judge_agreement_needs_sampled_scores() -> None:
    suite = _suite(cases=1)
    evaluator = LLMRubricEvaluator("factuality", FACTUALITY, _scripted(["A"]))
    report = evaluate_suite(suite, _samples(suite), registry=_registry(evaluator))
    decision = evaluate_gate(report, GateConfig(min_judge_agreement=0.5))
    assert not decision.passed
    assert "no case was judged" in decision.reasons[0]


def test_generic_judge_samples_aggregate_on_value_and_sum_recorded_usage() -> None:
    values = iter([1.0, 0.0, 1.0])

    def judge(context: EvaluationContext) -> Score:
        return Score(
            name="quality",
            value=next(values),
            passed=True,
            explanation="judged",
            metadata={"judge_cost_usd": 0.01, "judge_cost_source": "measured"},
        )

    evaluator = LLMJudgeEvaluator("quality", judge, samples=3, version="2")
    case = TestCase(id="c", name="c", evaluators=[EvaluatorConfig(name="quality", threshold=0.5)])
    sample = EvaluationSample(case_id="c", output="x", trace=EvalTrace())
    [score] = evaluator.evaluate(
        EvaluationContext(case=case, sample=sample, config=case.evaluators[0])
    )
    assert score.value == pytest.approx(2 / 3)
    assert score.passed
    assert score.metadata["judge_verdicts"] == [1.0, 0.0, 1.0]
    assert score.metadata["judge_cost_usd"] == pytest.approx(0.03)
    assert score.metadata["judge_cost_source"] == "measured"
    assert score.evaluator_version == "2"


def test_single_sample_keeps_latency_recorded_by_the_judge() -> None:
    def judge(context: EvaluationContext) -> Score:
        return Score(
            name="q", value=1.0, passed=True, explanation="ok", metadata={"judge_latency_ms": 7.0}
        )

    case = TestCase(id="c", name="c", evaluators=[EvaluatorConfig(name="q")])
    sample = EvaluationSample(case_id="c", output="x", trace=EvalTrace())
    [score] = LLMJudgeEvaluator("q", judge).evaluate(
        EvaluationContext(case=case, sample=sample, config=case.evaluators[0])
    )
    assert score.metadata["judge_latency_ms"] == 7.0


def test_samples_must_be_positive() -> None:
    with pytest.raises(ValueError, match="samples"):
        LLMRubricEvaluator("f", FACTUALITY, lambda prompt: "A", samples=0)


def test_async_complete_fn_works_from_the_sync_api() -> None:
    async def complete(prompt: str) -> JudgeResponse:
        await asyncio.sleep(0)
        return _priced("A")

    suite = _suite(cases=2)
    evaluator = LLMRubricEvaluator("factuality", FACTUALITY, complete, samples=2)
    report = evaluate_suite(suite, _samples(suite), registry=_registry(evaluator))
    assert report.summary.passed_cases == 2
    assert report.summary.judge is not None
    assert report.summary.judge.min_agreement == 1.0


def test_reports_without_judges_have_no_judge_summary() -> None:
    suite = TestSuite(
        name="plain", version="1", cases=[TestCase(id="c", name="c", expected_output="x")]
    )
    report = evaluate_suite(suite, [EvaluationSample(case_id="c", output="x", trace=EvalTrace())])
    assert report.summary.judge is None
    assert "judge_unavailable_scores" not in evaluate_gate(report, GateConfig()).observed
