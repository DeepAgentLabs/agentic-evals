import pytest

from agentic_evals import (
    BUILTIN_EVALUATOR,
    BusinessRuleEvaluator,
    CallableEvaluator,
    EvalTrace,
    EvaluationContext,
    EvaluationSample,
    EvaluatorConfig,
    EvaluatorRegistry,
    LLMJudgeEvaluator,
    LLMRubricEvaluator,
    Score,
    TestCase,
    TestSuite,
    __version__,
    evaluate_suite,
    make_rubric,
)


def _suite(*cases: TestCase) -> TestSuite:
    return TestSuite(name="provenance", version="1", cases=list(cases))


def _sample(
    case_id: str, *, cost: float | None = None, source: str | None = None
) -> EvaluationSample:
    return EvaluationSample(
        case_id=case_id,
        output="ok",
        trace=EvalTrace(trace_id=f"trace-{case_id}", estimated_cost_usd=cost, cost_source=source),
    )


def test_builtin_checks_are_attributed_to_the_package_version() -> None:
    report = evaluate_suite(
        _suite(TestCase(id="a", name="a", expected_output="ok", expected_contains=["o"])),
        [_sample("a")],
    )

    scores = report.cases[0].scores
    assert {score.evaluator for score in scores} == {BUILTIN_EVALUATOR}
    assert {score.evaluator_version for score in scores} == {__version__}


def test_registered_evaluator_scores_carry_name_and_declared_version() -> None:
    registry = EvaluatorRegistry()
    registry.register(
        LLMJudgeEvaluator(
            "judge",
            lambda context: Score(name="quality", value=0.9, passed=True, explanation="good"),
            version="judge-prompt-v3",
        )
    )
    registry.register(
        BusinessRuleEvaluator(
            "rule",
            lambda context: Score(name="policy", value=1.0, passed=True, explanation="ok"),
        )
    )
    case = TestCase(
        id="a",
        name="a",
        evaluators=[EvaluatorConfig(name="judge", threshold=0.5), EvaluatorConfig(name="rule")],
    )

    scores = {
        score.name: score
        for score in evaluate_suite(_suite(case), [_sample("a")], registry=registry).cases[0].scores
    }

    assert scores["quality"].evaluator == "judge"
    assert scores["quality"].evaluator_version == "judge-prompt-v3"
    assert scores["policy"].evaluator == "rule"
    assert scores["policy"].evaluator_version is None


def test_protocol_evaluator_without_callable_base_is_still_attributed() -> None:
    class VersionedRule:
        name = "versioned"
        version = "2.1"

        def evaluate(self, context: EvaluationContext) -> list[Score]:
            return [Score(name="rule", value=1.0, passed=True, explanation="ok")]

    registry = EvaluatorRegistry()
    registry.register(VersionedRule())
    case = TestCase(id="a", name="a", evaluators=[EvaluatorConfig(name="versioned")])

    score = evaluate_suite(_suite(case), [_sample("a")], registry=registry).cases[0].scores[0]

    assert (score.evaluator, score.evaluator_version) == ("versioned", "2.1")


def test_rubric_evaluator_accepts_a_version() -> None:
    evaluator = LLMRubricEvaluator(
        "rubric", make_rubric("tone", "Is polite"), lambda prompt: "A", version="tone@1"
    )
    assert evaluator.version == "tone@1"


def test_blank_evaluator_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="version"):
        CallableEvaluator("x", lambda context: [], version="  ")


def test_missing_sample_is_flagged_rather_than_left_as_an_empty_trace_id() -> None:
    report = evaluate_suite(
        _suite(
            TestCase(id="a", name="a", expected_output="ok"),
            TestCase(id="b", name="b", expected_output="ok"),
        ),
        [_sample("a")],
    )

    by_id = {case.case_id: case for case in report.cases}
    assert by_id["a"].sample_available is True
    assert by_id["b"].sample_available is False
    assert by_id["b"].scores[0].evaluator == BUILTIN_EVALUATOR


def test_cost_provenance_and_completeness_are_summarized() -> None:
    suite = _suite(
        TestCase(id="a", name="a", expected_output="ok"),
        TestCase(id="b", name="b", expected_output="ok"),
        TestCase(id="c", name="c", expected_output="ok"),
        TestCase(id="d", name="d", expected_output="ok"),
    )
    report = evaluate_suite(
        suite,
        [
            _sample("a", cost=0.01, source="measured"),
            _sample("b", cost=0.02, source="estimated"),
            _sample("c", cost=0.03),
            _sample("d", source="measured"),
        ],
    )

    summary = report.summary
    assert summary.total_cost_usd is None
    assert summary.priced_cases == 3
    assert summary.cost_sources == {"estimated": 1, "measured": 1, "unspecified": 1}
    by_id = {case.case_id: case for case in report.cases}
    assert by_id["a"].cost_source == "measured"
    # A provenance label without a cost is dropped rather than describing nothing.
    assert by_id["d"].cost_source is None


def test_unknown_cost_source_is_rejected() -> None:
    with pytest.raises(ValueError):
        EvalTrace(estimated_cost_usd=0.1, cost_source="guessed")  # type: ignore[arg-type]


def test_registry_provenance_overrides_what_the_evaluator_wrote() -> None:
    class Impostor:
        name = "registered"
        version = "1.0"

        def evaluate(self, context: EvaluationContext) -> list[Score]:
            return [
                Score(
                    name="rule",
                    value=1.0,
                    passed=True,
                    explanation="ok",
                    evaluator="someone-else",
                    evaluator_version="9.9",
                )
            ]

    registry = EvaluatorRegistry()
    registry.register(Impostor())
    case = TestCase(id="a", name="a", evaluators=[EvaluatorConfig(name="registered")])

    score = evaluate_suite(_suite(case), [_sample("a")], registry=registry).cases[0].scores[0]

    assert (score.evaluator, score.evaluator_version) == ("registered", "1.0")
