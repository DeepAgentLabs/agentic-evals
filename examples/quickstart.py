"""Score a sample against a suite using the built-in scorer registry.

Run: python examples/quickstart.py
"""

from agentic_evals import (
    EvalSpan,
    EvalTrace,
    EvaluationSample,
    EvaluatorConfig,
    TestCase,
    TestSuite,
    default_registry,
    evaluate_suite,
)


def main() -> None:
    suite = TestSuite(
        name="support-answers",
        version="1",
        cases=[
            TestCase(
                id="refund-status",
                name="Agent calls the right tool and stays under budget",
                required_tools=["lookup_refund"],
                forbidden_tools=["delete_order"],
                max_latency_ms=2000,
                evaluators=[
                    EvaluatorConfig(
                        name="tool_call_precision",
                        threshold=1.0,
                        config={"allowed_tools": ["lookup_refund"]},
                    )
                ],
            )
        ],
    )

    sample = EvaluationSample(
        case_id="refund-status",
        output="Your refund is on its way!",
        trace=EvalTrace(
            trace_id="trace-1",
            total_latency_ms=350,
            spans=[EvalSpan(tool_name="lookup_refund")],
        ),
    )

    report = evaluate_suite(suite, [sample], registry=default_registry())
    print(report.model_dump_json(indent=2))
    print(f"\nPass rate: {report.summary.pass_rate:.0%}")


if __name__ == "__main__":
    main()
