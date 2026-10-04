import pytest

from agentic_evals import (
    EvalSpan,
    EvalTrace,
    EvaluationSample,
    Score,
    TestCase,
    TestSuite,
    evaluate_suite,
)


def _call(tool: str, **tool_args: object) -> EvalSpan:
    return EvalSpan(tool_name=tool, attributes={"tool_args": tool_args})


def _scores(case: TestCase, *spans: EvalSpan) -> dict[str, Score]:
    suite = TestSuite(name="tools", version="1", cases=[case])
    sample = EvaluationSample(case_id=case.id, output="done", trace=EvalTrace(spans=list(spans)))
    return {score.name: score for score in evaluate_suite(suite, [sample]).cases[0].scores}


def _values_case(**expected: dict[str, object]) -> TestCase:
    return TestCase(id="c", name="c", expected_tool_arguments=expected)


def test_expected_tool_arguments_pass_when_a_call_carries_the_values() -> None:
    case = _values_case(search={"query": "invoice 88", "limit": 5})
    score = _scores(case, _call("search", query="invoice 88", limit=5, lang="en"))[
        "tool_arg_values:search"
    ]

    assert score.passed
    assert score.metric == "tool_arg_values"


def test_expected_tool_arguments_fail_on_a_wrong_value() -> None:
    case = _values_case(search={"query": "invoice 88"})
    score = _scores(case, _call("search", query="invoice 89"))["tool_arg_values:search"]

    assert not score.passed
    assert "invoice 89" in score.explanation


def test_expected_tool_arguments_do_not_coerce_types() -> None:
    case = _values_case(search={"limit": 5})
    assert not _scores(case, _call("search", limit="5"))["tool_arg_values:search"].passed


def test_expected_tool_arguments_match_any_call_to_the_tool() -> None:
    case = _values_case(search={"query": "b"})
    spans = (_call("search", query="a"), _call("search", query="b"))

    assert _scores(case, *spans)["tool_arg_values:search"].passed


def test_expected_tool_arguments_need_one_call_with_every_value() -> None:
    case = _values_case(search={"query": "a", "limit": 5})
    spans = (_call("search", query="a", limit=1), _call("search", query="z", limit=5))

    assert not _scores(case, *spans)["tool_arg_values:search"].passed


def test_expected_tool_arguments_fail_when_the_tool_was_never_called() -> None:
    case = _values_case(search={"query": "a"})
    score = _scores(case, _call("fetch", url="x"))["tool_arg_values:search"]

    assert not score.passed
    assert "was not called" in score.explanation


def test_expected_tool_arguments_compare_nested_values() -> None:
    case = _values_case(write={"record": {"id": 7, "tags": ["a", "b"]}})

    assert _scores(case, _call("write", record={"id": 7, "tags": ["a", "b"]}))[
        "tool_arg_values:write"
    ].passed
    assert not _scores(case, _call("write", record={"id": 7, "tags": ["b", "a"]}))[
        "tool_arg_values:write"
    ].passed


def _order_case(*order: str) -> TestCase:
    return TestCase(id="c", name="c", required_tool_order=list(order))


@pytest.mark.parametrize(
    "called",
    [
        ["authenticate", "read", "write"],
        ["authenticate", "log", "read", "log", "write"],
        ["authenticate", "read", "read", "write", "authenticate"],
    ],
)
def test_required_tool_order_passes_when_first_calls_are_in_order(called: list[str]) -> None:
    case = _order_case("authenticate", "read", "write")
    assert _scores(case, *(_call(tool) for tool in called))["tool_order"].passed


def test_required_tool_order_fails_when_a_later_tool_is_called_first() -> None:
    case = _order_case("authenticate", "write")
    score = _scores(case, _call("write"), _call("authenticate"), _call("write"))["tool_order"]

    assert not score.passed
    assert "'write' was called before 'authenticate'" in score.explanation


def test_required_tool_order_fails_when_a_listed_tool_is_missing() -> None:
    case = _order_case("authenticate", "read", "write")
    score = _scores(case, _call("authenticate"), _call("write"))["tool_order"]

    assert not score.passed
    assert "['read'] never called" in score.explanation


def test_required_tool_order_fails_on_an_empty_trace() -> None:
    assert not _scores(_order_case("authenticate", "write"))["tool_order"].passed


def test_tool_expectations_alone_satisfy_the_expectation_requirement() -> None:
    assert _values_case(search={"query": "a"}).expected_tool_arguments
    assert _order_case("a", "b").required_tool_order
    with pytest.raises(ValueError, match="at least one expectation"):
        TestCase(id="c", name="c")
