from agentic_evals import (
    BusinessRuleEvaluator,
    Eval,
    EvalSpan,
    EvalTrace,
    EvaluationContext,
    EvaluationReport,
    EvaluationSample,
    EvaluatorConfig,
    EvaluatorRegistry,
    Score,
    TestCase,
    TestSuite,
    evaluate_suite,
)


def _sample(case_id: str, output: str, *tools: str) -> EvaluationSample:
    trace = EvalTrace(trace_id=case_id, spans=[EvalSpan(tool_name=tool) for tool in tools])
    return EvaluationSample(case_id=case_id, output=output, trace=trace)


def _report() -> EvaluationReport:
    suite = TestSuite(
        name="support",
        version="1",
        cases=[
            TestCase(
                id="refund-ok",
                name="refund ok",
                expected_contains=["refund", "5 days"],
                required_tools=["lookup_order"],
                tags=["refunds", "happy-path"],
                metadata={"owner": "payments"},
            ),
            TestCase(
                id="refund-no-lookup",
                name="refund without lookup",
                expected_contains=["refund"],
                required_tools=["lookup_order"],
                tags=["refunds"],
            ),
            TestCase(
                id="tracking",
                name="tracking",
                expected_contains=["shipped"],
                tags=["tracking", "happy-path"],
            ),
            TestCase(id="untagged", name="untagged", expected_contains=["hello"]),
        ],
    )
    samples = [
        _sample("refund-ok", "Your refund arrives in 5 days.", "lookup_order"),
        _sample("refund-no-lookup", "Your refund is on its way."),
        _sample("tracking", "Your order has shipped."),
        _sample("untagged", "goodbye"),
    ]
    return evaluate_suite(suite, samples)


def test_implicit_checks_share_a_metric_and_keep_their_detailed_name() -> None:
    scores = _report().cases[0].scores

    assert [(score.name, score.metric) for score in scores] == [
        ("contains:refund", "contains"),
        ("contains:5 days", "contains"),
        ("required_tool:lookup_order", "required_tool"),
    ]


def test_metric_defaults_to_the_score_name() -> None:
    score = Score(name="groundedness", value=1.0, passed=True, explanation="ok")
    assert score.metric == "groundedness"


def test_summary_breaks_results_down_by_metric() -> None:
    metrics = _report().summary.metrics

    assert list(metrics) == ["contains", "required_tool"]
    assert metrics["contains"].model_dump() == {
        "total": 5,
        "passed": 4,
        "failed": 1,
        "skipped": 0,
        "pass_rate": 0.8,
        "average_score": 0.8,
    }
    assert metrics["required_tool"].pass_rate == 0.5


def test_summary_breaks_results_down_by_tag() -> None:
    tags = _report().summary.tags

    assert list(tags) == ["happy-path", "refunds", "tracking"]
    assert tags["refunds"].model_dump() == {
        "total_cases": 2,
        "passed_cases": 1,
        "failed_cases": 1,
        "pass_rate": 0.5,
        "average_score": 0.8,
    }
    assert tags["happy-path"].pass_rate == 1.0
    assert tags["tracking"].total_cases == 1


def test_case_results_carry_tags_and_metadata() -> None:
    report = _report()

    assert report.cases[0].tags == ["refunds", "happy-path"]
    assert report.cases[0].metadata == {"owner": "payments"}
    assert report.cases[3].tags == []


def test_missing_sample_still_counts_toward_its_tags() -> None:
    suite = TestSuite(
        name="support",
        version="1",
        cases=[TestCase(id="c", name="c", expected_contains=["x"], tags=["refunds"])],
    )
    report = evaluate_suite(suite, [])

    assert report.cases[0].tags == ["refunds"]
    assert report.summary.tags["refunds"].failed_cases == 1
    assert report.summary.metrics["sample_available"].failed == 1


def _order_id_rule(context: EvaluationContext) -> Score:
    order_id = context.case.metadata.get("order_id")
    if order_id is None:
        return Score.skip("cites_order_id", "Case has no order id to cite.")
    cited = order_id in context.sample.output
    return Score(
        name="cites_order_id",
        value=float(cited),
        passed=cited,
        explanation=f"Output {'cites' if cited else 'does not cite'} {order_id}.",
    )


def _skip_report() -> EvaluationReport:
    registry = EvaluatorRegistry()
    registry.register(BusinessRuleEvaluator("cites_order_id", _order_id_rule))
    evaluators = [EvaluatorConfig(name="cites_order_id")]
    suite = TestSuite(
        name="support",
        version="1",
        cases=[
            TestCase(
                id="with-order",
                name="with order",
                evaluators=evaluators,
                metadata={"order_id": "ORD-1"},
            ),
            TestCase(id="no-order", name="no order", evaluators=evaluators),
        ],
    )
    samples = [_sample("with-order", "ORD-1 has shipped."), _sample("no-order", "Hello!")]
    return evaluate_suite(suite, samples, registry=registry)


def test_skipped_score_does_not_fail_the_case() -> None:
    report = _skip_report()
    skipped = report.cases[1].scores[0]

    assert skipped.skipped is True
    assert skipped.explanation == "Case has no order id to cite."
    assert skipped.evaluator_type == "business_rule"
    assert report.cases[1].passed
    assert report.summary.pass_rate == 1.0


def test_skipped_scores_are_left_out_of_averages_and_counted_apart() -> None:
    report = _skip_report()
    metric = report.summary.metrics["cites_order_id"]

    assert report.summary.average_score == 1.0
    assert (metric.total, metric.passed, metric.skipped) == (1, 1, 1)
    assert metric.pass_rate == 1.0


def test_metric_with_only_skipped_scores_has_no_pass_rate() -> None:
    registry = EvaluatorRegistry()
    registry.register(BusinessRuleEvaluator("cites_order_id", _order_id_rule))
    suite = TestSuite(
        name="support",
        version="1",
        cases=[
            TestCase(
                id="no-order",
                name="no order",
                evaluators=[EvaluatorConfig(name="cites_order_id")],
                tags=["greeting"],
            )
        ],
    )
    report = evaluate_suite(suite, [_sample("no-order", "Hello!")], registry=registry)
    metric = report.summary.metrics["cites_order_id"]

    assert (metric.total, metric.skipped) == (0, 1)
    assert metric.pass_rate is None
    assert metric.average_score is None
    assert report.summary.tags["greeting"].average_score is None
    assert report.summary.average_score == 0.0


def test_eval_ignores_a_skipped_score() -> None:
    def maybe(output: str) -> Score:
        return Score.skip("maybe", "Not applicable.")

    result = Eval("skips", data=[{"input": "x"}], task=str, scores=[maybe], print_results=False)

    assert result.results[0].scores == {}
    assert bool(result)


def test_report_round_trips_through_json() -> None:
    report = _report()
    restored = EvaluationReport.model_validate_json(report.model_dump_json())

    assert restored.summary.tags == report.summary.tags
    assert restored.summary.metrics == report.summary.metrics
    assert restored.cases[0].scores[0].metric == "contains"


def test_reports_without_the_new_fields_still_load() -> None:
    legacy = _report().model_dump(mode="json")
    del legacy["summary"]["metrics"], legacy["summary"]["tags"]
    for case in legacy["cases"]:
        del case["tags"], case["metadata"]
        for score in case["scores"]:
            del score["metric"], score["skipped"]

    restored = EvaluationReport.model_validate(legacy)

    assert restored.summary.metrics == {}
    assert restored.cases[0].scores[0].metric == "contains:refund"
    assert restored.cases[0].scores[0].skipped is False


def test_suite_without_tags_has_an_empty_tag_breakdown() -> None:
    suite = TestSuite(
        name="s", version="1", cases=[TestCase(id="c", name="c", expected_contains=["x"])]
    )
    report = evaluate_suite(suite, [_sample("c", "x")])

    assert report.summary.tags == {}
    assert list(report.summary.metrics) == ["contains"]


def test_suite_where_no_evaluator_returns_a_score_reports_zero_average() -> None:
    registry = EvaluatorRegistry()
    registry.register(BusinessRuleEvaluator("silent", lambda context: []))
    suite = TestSuite(
        name="s",
        version="1",
        cases=[TestCase(id="c", name="c", evaluators=[EvaluatorConfig(name="silent")])],
    )
    report = evaluate_suite(suite, [_sample("c", "x")], registry=registry)

    assert report.summary.average_score == 0.0
    assert report.summary.metrics == {}
    assert report.cases[0].passed
