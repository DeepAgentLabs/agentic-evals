import pytest

from agentic_evals import (
    BATTLE,
    CLOSED_QA,
    FACTUALITY,
    EvalTrace,
    EvaluationContext,
    EvaluationSample,
    EvaluatorConfig,
    LLMRubricEvaluator,
    TestCase,
)


def _context(
    *, output: str, expected_output: str | None, input_: object = None
) -> EvaluationContext:
    case = TestCase(id="case-1", name="case", expected_output=expected_output, input=input_)
    sample = EvaluationSample(case_id="case-1", output=output, trace=EvalTrace())
    return EvaluationContext(
        case=case, sample=sample, config=EvaluatorConfig(name="judge", threshold=0.8)
    )


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
    context = _context(output="Paris", expected_output="Paris is the capital of France")

    scores = evaluator.evaluate(context)

    assert len(scores) == 1
    score = scores[0]
    assert score.name == "factuality"
    assert score.value == 1.0
    assert score.passed is True
    assert score.metadata["verdict"] == "A"


def test_llm_rubric_evaluator_applies_threshold_from_config() -> None:
    evaluator = LLMRubricEvaluator("factuality", FACTUALITY, complete_fn=lambda prompt: "(C)")
    context = _context(output="Paris", expected_output="Paris is the capital of France")

    score = evaluator.evaluate(context)[0]

    assert score.value == 0.6
    assert score.passed is False  # threshold is 0.8 in _context()


def test_llm_rubric_evaluator_propagates_unparseable_completion() -> None:
    evaluator = LLMRubricEvaluator("factuality", FACTUALITY, complete_fn=lambda prompt: "unclear")
    context = _context(output="Paris", expected_output="Paris is the capital of France")

    with pytest.raises(ValueError, match="could not parse a verdict"):
        evaluator.evaluate(context)
