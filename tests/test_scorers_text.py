import pytest

from agentic_evals import (
    EvalTrace,
    EvaluationContext,
    EvaluationSample,
    EvaluatorConfig,
    TestCase,
    contains_all,
    contains_any,
    embedding_similarity,
    exact_match,
    json_diff,
    levenshtein_similarity,
    numeric_diff,
    valid_json,
)


def _sample(output: str) -> EvaluationSample:
    return EvaluationSample(case_id="case-1", output=output, trace=EvalTrace())


def _context(
    output: str,
    *,
    expected_output: str | None = None,
    expected_contains: list[str] | None = None,
    threshold: float = 1.0,
    config: dict | None = None,
) -> EvaluationContext:
    case = TestCase(
        id="case-1",
        name="case",
        expected_output=expected_output,
        expected_contains=expected_contains or [],
        # Filler expectation unrelated to the field(s) under test, since
        # TestCase requires at least one expectation to be set.
        max_turns=1_000_000,
    )
    return EvaluationContext(
        case=case,
        sample=_sample(output),
        config=EvaluatorConfig(name="scorer", threshold=threshold, config=config or {}),
    )


def test_exact_match_passes_on_exact_text() -> None:
    context = _context("42", expected_output="42")
    score = exact_match(context)
    assert score.value == 1.0
    assert score.passed is True


def test_exact_match_fails_on_mismatch() -> None:
    context = _context("41", expected_output="42")
    score = exact_match(context)
    assert score.value == 0.0
    assert score.passed is False


def test_exact_match_requires_expected_output() -> None:
    context = _context("42")
    with pytest.raises(ValueError, match="expected_output"):
        exact_match(context)


def test_contains_all_requires_every_substring() -> None:
    context = _context("the total is 42 dollars", expected_contains=["42", "dollars"])
    assert contains_all(context).value == 1.0

    context = _context("the total is 42", expected_contains=["42", "dollars"])
    assert contains_all(context).value == 0.0


def test_contains_any_passes_on_a_single_match() -> None:
    context = _context("the total is 42", expected_contains=["missing", "42"])
    assert contains_any(context).value == 1.0


def test_levenshtein_similarity_is_one_for_identical_strings() -> None:
    context = _context("hello world", expected_output="hello world")
    score = levenshtein_similarity(context)
    assert score.value == 1.0
    assert score.passed is True


def test_levenshtein_similarity_reflects_edit_distance() -> None:
    context = _context("hello warld", expected_output="hello world", threshold=0.5)
    score = levenshtein_similarity(context)
    assert 0.0 < score.value < 1.0
    assert score.passed is True


def test_embedding_similarity_requires_embed_fn() -> None:
    context = _context("hello", expected_output="hello")
    with pytest.raises(ValueError, match="embed_fn"):
        embedding_similarity(context)


def test_embedding_similarity_scores_identical_vectors_as_one() -> None:
    context = _context(
        "hello",
        expected_output="hello",
        config={"embed_fn": lambda text: [1.0, 0.0, 0.0]},
    )
    score = embedding_similarity(context)
    assert score.value == pytest.approx(1.0)
    assert score.metadata["raw_cosine_similarity"] == pytest.approx(1.0)


def test_embedding_similarity_scores_orthogonal_vectors_as_half() -> None:
    embed_fn = lambda text: [1.0, 0.0] if text == "a" else [0.0, 1.0]  # noqa: E731
    context = _context("a", expected_output="b", config={"embed_fn": embed_fn})
    score = embedding_similarity(context)
    assert score.value == pytest.approx(0.5)


def test_valid_json_detects_malformed_output() -> None:
    assert valid_json(_context("{}")).value == 1.0
    assert valid_json(_context("not json")).value == 0.0


def test_json_diff_passes_on_structural_match() -> None:
    context = _context('{"a": 1, "b": [1, 2]}', expected_output='{"b": [1, 2], "a": 1}')
    assert json_diff(context).value == 1.0


def test_json_diff_reports_first_mismatch() -> None:
    context = _context('{"a": 2}', expected_output='{"a": 1}')
    score = json_diff(context)
    assert score.value == 0.0
    assert "$.a" in score.explanation


def test_json_diff_fails_gracefully_on_invalid_output_json() -> None:
    context = _context("not json", expected_output='{"a": 1}')
    score = json_diff(context)
    assert score.value == 0.0
    assert score.passed is False


def test_numeric_diff_within_tolerance_passes() -> None:
    context = _context("1.0000001", expected_output="1.0")
    score = numeric_diff(context)
    assert score.passed is True
    assert score.value == pytest.approx(1.0, abs=1e-4)


def test_numeric_diff_outside_tolerance_fails() -> None:
    context = _context("2.0", expected_output="1.0")
    score = numeric_diff(context)
    assert score.passed is False
    assert 0.0 <= score.value < 1.0


def test_numeric_diff_rejects_non_numeric_output() -> None:
    context = _context("not a number", expected_output="1.0")
    score = numeric_diff(context)
    assert score.value == 0.0
    assert score.passed is False
