import pytest

from agentic_evals import (
    Case,
    Eval,
    Score,
    contains,
    equals,
    icontains,
    levenshtein,
    matches,
    numeric_close,
)


def test_eval_all_pass() -> None:
    result = Eval(
        "all-pass",
        data=[{"input": "hi", "expected": "hi"}],
        task=lambda input: input,
        scores=[equals],
        print_results=False,
    )
    assert bool(result) is True
    assert result.pass_rate == 1.0
    assert result.score_averages == {"equals": 1.0}


def test_eval_partial_failure() -> None:
    result = Eval(
        "partial",
        data=[
            {"input": "a", "expected": "a"},
            {"input": "b", "expected": "z"},
        ],
        task=lambda input: input,
        scores=[equals],
        print_results=False,
    )
    assert bool(result) is False
    assert result.pass_rate == 0.5
    assert result.score_averages == {"equals": 0.5}


def test_eval_empty_data_is_vacuously_true() -> None:
    result = Eval(
        "empty",
        data=[],
        task=lambda input: input,
        scores=[equals],
        print_results=False,
    )
    assert bool(result) is True
    assert result.pass_rate == 1.0
    assert result.score_averages == {}


def test_eval_accepts_callable_data() -> None:
    result = Eval(
        "lazy-data",
        data=lambda: [{"input": "x", "expected": "x"}],
        task=lambda input: input,
        scores=[equals],
        print_results=False,
    )
    assert bool(result) is True


def test_eval_accepts_case_instances() -> None:
    result = Eval(
        "case-instances",
        data=[Case(input="x", expected="x")],
        task=lambda input: input,
        scores=[equals],
        print_results=False,
    )
    assert bool(result) is True


def test_eval_case_requires_input_key() -> None:
    with pytest.raises(ValueError, match="input"):
        Eval(
            "bad-data",
            data=[{"expected": "x"}],
            task=lambda input: input,
            scores=[equals],
            print_results=False,
        )


def test_eval_task_exception_is_recorded_not_raised() -> None:
    def boom(input: str) -> str:
        raise RuntimeError("nope")

    result = Eval(
        "task-fails",
        data=[{"input": "x"}],
        task=boom,
        scores=[equals],
        print_results=False,
    )
    assert bool(result) is False
    assert result.results[0].error is not None
    assert "RuntimeError" in result.results[0].error


def test_eval_scorer_sees_input_and_expected_by_name() -> None:
    def custom(input: str, output: str, expected: str) -> bool:
        return input == "x" and output == "x" and expected == "y"

    result = Eval(
        "named-params",
        data=[{"input": "x", "expected": "y"}],
        task=lambda input: input,
        scores=[custom],
        print_results=False,
    )
    assert result.score_averages == {"custom": 1.0}


def test_eval_scorer_returns_score_model() -> None:
    def judge(output: str) -> Score:
        return Score(name="judge", value=0.75, passed=True, explanation="ok")

    result = Eval(
        "score-model",
        data=[{"input": "x"}],
        task=lambda input: input,
        scores=[judge],
        threshold=0.5,
        print_results=False,
    )
    assert result.score_averages == {"judge": 0.75}
    assert bool(result) is True


def test_eval_scorer_returns_named_dict() -> None:
    def judge(output: str) -> dict[str, object]:
        return {"score": 0.4, "name": "custom_name"}

    result = Eval(
        "score-dict",
        data=[{"input": "x"}],
        task=lambda input: input,
        scores=[judge],
        threshold=0.0,
        print_results=False,
    )
    assert result.score_averages == {"custom_name": 0.4}


def test_eval_threshold_controls_pass_fail() -> None:
    def judge(output: str) -> float:
        return 0.6

    strict = Eval(
        "strict",
        data=[{"input": "x"}],
        task=lambda input: input,
        scores=[judge],
        threshold=0.9,
        print_results=False,
    )
    lenient = Eval(
        "lenient",
        data=[{"input": "x"}],
        task=lambda input: input,
        scores=[judge],
        threshold=0.5,
        print_results=False,
    )
    assert bool(strict) is False
    assert bool(lenient) is True


def test_equals() -> None:
    assert equals(" hi ", "hi") is True
    assert equals("hi", "bye") is False


def test_contains_single_and_list() -> None:
    assert contains("the cat sat", "cat") is True
    assert contains("the cat sat", ["cat", "sat"]) is True
    assert contains("the cat sat", ["cat", "dog"]) is False


def test_icontains_case_insensitive() -> None:
    assert icontains("The CAT sat", "cat") is True
    assert icontains("The dog sat", "cat") is False


def test_levenshtein_identical_is_one() -> None:
    assert levenshtein("hello", "hello") == 1.0


def test_levenshtein_partial_similarity() -> None:
    score = levenshtein("hello", "hallo")
    assert 0.0 < score < 1.0


def test_matches_searches_by_regex() -> None:
    assert matches("order #42 shipped", r"#\d+") is True
    assert matches("order shipped", r"#\d+") is False


def test_numeric_close_within_tolerance() -> None:
    assert numeric_close("1.001", "1.0") is True
    assert numeric_close("2.0", "1.0") is False
