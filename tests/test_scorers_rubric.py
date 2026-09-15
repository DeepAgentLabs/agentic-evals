import pytest

from agentic_evals import (
    BATTLE,
    CLOSED_QA,
    FACTUALITY,
    PII_LEAKAGE,
    POSSIBLE,
    SECURITY,
    SQL_CORRECTNESS,
    TRANSLATION,
    EvalTrace,
    EvaluationContext,
    EvaluationSample,
    EvaluatorConfig,
    LLMRubricEvaluator,
    TestCase,
)


def _context(
    *, output: str, reference: str | None = None, input_: object = None, threshold: float = 0.8
) -> EvaluationContext:
    # Filler expectation unrelated to the rubric under test: TestCase
    # requires at least one, and expected_output is deliberately not used
    # here (see LLMRubricEvaluator's docstring on why).
    case = TestCase(id="case-1", name="case", input=input_, max_turns=1_000_000)
    sample = EvaluationSample(case_id="case-1", output=output, trace=EvalTrace())
    config = EvaluatorConfig(
        name="judge", threshold=threshold, config={"reference": reference} if reference else {}
    )
    return EvaluationContext(case=case, sample=sample, config=config)


def test_rubric_template_renders_all_fields() -> None:
    prompt = FACTUALITY.render(
        output="Paris",
        expected="Paris is the capital of France",
        input="What is the capital of France?",
    )
    assert "Paris" in prompt
    assert "capital of France" in prompt


def test_rubric_template_render_falls_back_when_fields_missing() -> None:
    prompt = FACTUALITY.render(output="Paris", expected=None, input=None)
    assert "no reference answer provided" in prompt
    assert "no input provided" in prompt


def test_parse_verdict_extracts_known_letter() -> None:
    letter, value = FACTUALITY.parse_verdict("After comparing both answers, I choose (A).")
    assert letter == "A"
    assert value == 1.0


def test_parse_verdict_prefers_earliest_match() -> None:
    letter, _ = CLOSED_QA.parse_verdict("Not B, actually the answer is A.")
    assert letter == "B"


def test_parse_verdict_raises_on_unrecognized_output() -> None:
    with pytest.raises(ValueError, match="could not parse a verdict"):
        FACTUALITY.parse_verdict("I'm not sure.")


def test_battle_template_distinguishes_win_and_tie_tokens() -> None:
    letter, value = BATTLE.parse_verdict("My verdict: WIN_A")
    assert letter == "WIN_A"
    assert value == 1.0

    letter, value = BATTLE.parse_verdict("This is a TIE.")
    assert letter == "TIE"
    assert value == 0.5


def test_llm_rubric_evaluator_scores_using_complete_fn() -> None:
    evaluator = LLMRubricEvaluator("factuality", FACTUALITY, complete_fn=lambda prompt: "(A)")
    context = _context(output="Paris", reference="Paris is the capital of France")

    scores = evaluator.evaluate(context)

    assert len(scores) == 1
    score = scores[0]
    assert score.name == "factuality"
    assert score.value == 1.0
    assert score.passed is True
    assert score.metadata["verdict"] == "A"


def test_llm_rubric_evaluator_applies_threshold_from_config() -> None:
    evaluator = LLMRubricEvaluator("factuality", FACTUALITY, complete_fn=lambda prompt: "(C)")
    context = _context(output="Paris", reference="Paris is the capital of France")

    score = evaluator.evaluate(context)[0]

    assert score.value == 0.6
    assert score.passed is False  # threshold is 0.8 in _context()


def test_llm_rubric_evaluator_propagates_unparseable_completion() -> None:
    evaluator = LLMRubricEvaluator("factuality", FACTUALITY, complete_fn=lambda prompt: "unclear")
    context = _context(output="Paris", reference="Paris is the capital of France")

    with pytest.raises(ValueError, match="could not parse a verdict"):
        evaluator.evaluate(context)


def test_translation_template_parses_verdict() -> None:
    letter, value = TRANSLATION.parse_verdict("(A) accurate and fluent")
    assert letter == "A"
    assert value == 1.0


def test_security_template_parses_verdict() -> None:
    letter, value = SECURITY.parse_verdict("Verdict: (D) exploitable")
    assert letter == "D"
    assert value == 0.0


def test_sql_correctness_template_renders_expected_as_reference_query() -> None:
    prompt = SQL_CORRECTNESS.render(
        output="SELECT * FROM t",
        expected="SELECT id FROM t",
        input="get all rows",
    )
    assert "SELECT * FROM t" in prompt
    assert "SELECT id FROM t" in prompt


def test_possible_template_parses_verdict() -> None:
    letter, value = POSSIBLE.parse_verdict("(C) fabricates an answer")
    assert letter == "C"
    assert value == 0.0


def test_pii_leakage_template_parses_verdict() -> None:
    letter, value = PII_LEAKAGE.parse_verdict("(A) no PII disclosed")
    assert letter == "A"
    assert value == 1.0


def test_llm_rubric_evaluator_works_with_new_templates() -> None:
    evaluator = LLMRubricEvaluator("security", SECURITY, complete_fn=lambda prompt: "(A)")
    context = _context(output="def f(): return 1")

    score = evaluator.evaluate(context)[0]

    assert score.name == "security"
    assert score.value == 1.0
    assert score.passed is True
