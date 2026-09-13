import pytest

from agentic_evals import (
    BusinessRuleEvaluator,
    EvalSpan,
    EvalTrace,
    EvaluationContext,
    EvaluationSample,
    EvaluatorConfig,
    EvaluatorRegistry,
    LLMJudgeEvaluator,
    PythonTarget,
    Score,
    TestCase,
    TestSuite,
    evaluate_suite,
    run_live_suite,
)


def make_trace(*, latency_ms: float = 100.0, cost: float | None = 0.002) -> EvalTrace:
    return EvalTrace(
        trace_id="trace-1",
        total_latency_ms=latency_ms,
        estimated_cost_usd=cost,
        spans=[EvalSpan(tool_name="add")],
    )


def test_evaluate_suite_scores_output_tools_latency_and_cost() -> None:
    suite = TestSuite(
        name="release",
        version="1",
        cases=[
            TestCase(
                id="case-1",
                name="answer",
                expected_contains=["42"],
                required_tools=["add"],
                forbidden_tools=["network"],
                max_latency_ms=200,
                max_cost_usd=0.01,
            )
        ],
    )
    report = evaluate_suite(
        suite,
        [EvaluationSample(case_id="case-1", output="The answer is 42.", trace=make_trace())],
    )
    assert report.summary.pass_rate == 1
    assert report.summary.average_score == 1
    assert report.summary.total_cost_usd == 0.002


def test_missing_sample_fails_evaluation() -> None:
    suite = TestSuite(
        name="release",
        version="1",
        cases=[TestCase(id="missing", name="missing", expected_output="ok")],
    )
    report = evaluate_suite(suite, [])
    assert report.summary.failed_cases == 1


def test_registered_llm_judge_uses_suite_threshold() -> None:
    def judge(context: EvaluationContext) -> Score:
        assert context.config.config["rubric"] == "Correct and concise"
        return Score(
            name="answer_quality",
            value=0.85,
            passed=False,
            explanation="The response is correct and concise.",
        )

    registry = EvaluatorRegistry()
    registry.register(LLMJudgeEvaluator("quality_judge", judge))
    suite = TestSuite(
        name="judge-suite",
        version="1",
        cases=[
            TestCase(
                id="case-1",
                name="Judge answer quality",
                evaluators=[
                    EvaluatorConfig(
                        name="quality_judge",
                        threshold=0.8,
                        config={"rubric": "Correct and concise"},
                    )
                ],
            )
        ],
    )
    report = evaluate_suite(
        suite,
        [EvaluationSample(case_id="case-1", output="42", trace=make_trace())],
        registry=registry,
    )

    assert report.cases[0].passed
    assert report.cases[0].scores[0].evaluator_type == "llm_judge"
    assert report.cases[0].scores[0].value == 0.85


def test_unregistered_evaluator_is_rejected() -> None:
    suite = TestSuite(
        name="custom",
        version="1",
        cases=[
            TestCase(
                id="case-1",
                name="Custom",
                evaluators=[EvaluatorConfig(name="missing")],
            )
        ],
    )

    with pytest.raises(ValueError, match="no evaluator registry"):
        evaluate_suite(
            suite,
            [EvaluationSample(case_id="case-1", output="ok", trace=make_trace())],
        )


def test_evaluate_suite_supports_json_fields_tool_args_and_turn_thresholds() -> None:
    suite = TestSuite(
        name="structured",
        version="1",
        cases=[
            TestCase(
                id="case-1",
                name="Structured output",
                output_json_schema={
                    "type": "object",
                    "required": ["answer", "meta"],
                    "properties": {
                        "answer": {"type": "string"},
                        "meta": {"type": "object", "required": ["confidence"]},
                    },
                },
                required_output_fields=["meta.confidence"],
                required_tool_arguments={"add": ["a", "b"]},
                max_turns=2,
            )
        ],
    )
    trace = make_trace()
    trace.metadata["turn_count"] = 2
    trace.spans[0].attributes["tool_args"] = {"a": 40, "b": 2}

    report = evaluate_suite(
        suite,
        [
            EvaluationSample(
                case_id="case-1",
                output='{"answer":"42","meta":{"confidence":0.9}}',
                trace=trace,
            )
        ],
    )
    assert report.cases[0].passed
    assert {score.name for score in report.cases[0].scores} >= {
        "json_schema",
        "required_field:meta.confidence",
        "tool_args:add",
        "turn_count_threshold",
    }


def test_evaluate_suite_supports_nullable_json_schema_types() -> None:
    suite = TestSuite(
        name="schema",
        version="1",
        cases=[
            TestCase(
                id="case-1",
                name="Nullable field",
                output_json_schema={
                    "type": "object",
                    "required": ["answer", "reasoning"],
                    "properties": {
                        "answer": {"type": "string"},
                        "reasoning": {"type": ["string", "null"]},
                    },
                },
            )
        ],
    )

    report = evaluate_suite(
        suite,
        [
            EvaluationSample(
                case_id="case-1",
                output='{"answer":"42","reasoning":null}',
                trace=make_trace(),
            )
        ],
    )

    assert report.cases[0].passed
    assert report.cases[0].scores[0].name == "json_schema"
    assert report.cases[0].scores[0].passed


def test_max_turns_requires_explicit_turn_count_metadata() -> None:
    suite = TestSuite(
        name="turns",
        version="1",
        cases=[TestCase(id="case-1", name="Turn gate", max_turns=1)],
    )

    report = evaluate_suite(
        suite,
        [EvaluationSample(case_id="case-1", output="ok", trace=make_trace())],
    )

    assert not report.cases[0].passed
    assert report.cases[0].scores[0].name == "turn_count_threshold"
    assert report.cases[0].scores[0].explanation == (
        "Trace metadata is missing a positive integer turn_count, "
        "so the max_turns check could not be evaluated."
    )


def test_business_rule_evaluator_uses_business_rule_type() -> None:
    registry = EvaluatorRegistry()
    registry.register(
        BusinessRuleEvaluator(
            "business_rule",
            lambda context: Score(
                name="vip_rule",
                value=1.0 if context.sample.output == "vip" else 0.0,
                passed=False,
                explanation="VIP response requirement.",
            ),
        )
    )
    suite = TestSuite(
        name="business",
        version="1",
        cases=[
            TestCase(
                id="case-1",
                name="VIP policy",
                evaluators=[EvaluatorConfig(name="business_rule")],
            )
        ],
    )
    report = evaluate_suite(
        suite,
        [EvaluationSample(case_id="case-1", output="vip", trace=make_trace())],
        registry=registry,
    )
    assert report.cases[0].scores[0].evaluator_type == "business_rule"


def test_json_schema_supports_null_type() -> None:
    suite = TestSuite(
        name="schema",
        version="1",
        cases=[
            TestCase(
                id="case-1",
                name="Null type",
                output_json_schema={"type": "null"},
            )
        ],
    )
    report = evaluate_suite(
        suite,
        [EvaluationSample(case_id="case-1", output="null", trace=make_trace())],
    )

    assert report.cases[0].passed
    assert report.cases[0].scores[0].explanation == (
        "Output matches the configured JSON Schema Draft 2020-12."
    )


def test_run_live_suite_executes_python_target() -> None:
    suite = TestSuite(
        name="live",
        version="1",
        cases=[
            TestCase(
                id="case-1",
                name="Answer",
                input={"response": '{"answer":"42","meta":{"confidence":0.9}}'},
                output_json_schema={"type": "object", "required": ["answer"]},
                required_tool_arguments={"add": ["a", "b"]},
                max_turns=1,
            )
        ],
    )
    report = run_live_suite(
        suite,
        PythonTarget(callable_path="tests/live_eval_target.py:run_case"),
    )
    assert report.summary.pass_rate == 1.0


def test_run_live_suite_preserves_suite_case_id_when_target_returns_one(tmp_path) -> None:
    target_file = tmp_path / "target.py"
    target_file.write_text(
        "\n".join(
            [
                "def run_case(payload, *, case):",
                "    return {",
                "        'case_id': 'wrong-case',",
                "        'output': 'ok',",
                "        'trace': {'trace_id': 'live-trace'},",
                "    }",
            ]
        ),
        encoding="utf-8",
    )
    suite = TestSuite(
        name="live",
        version="1",
        cases=[TestCase(id="case-1", name="Answer", expected_output="ok")],
    )

    report = run_live_suite(
        suite,
        PythonTarget(callable_path=f"{target_file}:run_case"),
    )

    assert report.cases[0].case_id == "case-1"
