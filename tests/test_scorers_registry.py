from agentic_evals import (
    EvalSpan,
    EvalTrace,
    EvaluationSample,
    EvaluatorConfig,
    TestCase,
    TestSuite,
    builtin_scorer_names,
    default_registry,
    evaluate_suite,
)


def test_builtin_scorer_names_are_sorted_and_nonempty() -> None:
    names = builtin_scorer_names()
    assert names == tuple(sorted(names))
    assert "levenshtein_similarity" in names
    assert "tool_call_precision" in names


def test_default_registry_resolves_every_builtin_name() -> None:
    registry = default_registry()
    for name in builtin_scorer_names():
        assert registry.get(name).name == name


def test_default_registry_scores_a_suite_end_to_end() -> None:
    suite = TestSuite(
        name="registry-smoke-test",
        version="1",
        cases=[
            TestCase(
                id="case-1",
                name="answer similarity",
                expected_output="hello world",
                evaluators=[EvaluatorConfig(name="levenshtein_similarity", threshold=0.9)],
            )
        ],
    )
    sample = EvaluationSample(
        case_id="case-1",
        output="hello world",
        trace=EvalTrace(spans=[EvalSpan(tool_name="respond")]),
    )

    report = evaluate_suite(suite, [sample], registry=default_registry())

    assert report.summary.pass_rate == 1.0
    assert report.cases[0].scores[-1].name == "levenshtein_similarity"
    assert report.cases[0].scores[-1].value == 1.0
