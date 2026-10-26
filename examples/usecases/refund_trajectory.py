"""Four refund runs send the same reply. Only the trace shows which one was done right.

Each run is a recorded trace: the tools the agent called, with their
arguments. Nothing here calls an agent or a model.

Run: python refund_trajectory.py
"""

from typing import Any

from agentic_evals import (
    EvalSpan,
    EvalTrace,
    EvaluationReport,
    EvaluationSample,
    EvaluatorConfig,
    TestCase,
    TestSuite,
    default_registry,
    evaluate_suite,
)

REPLY = "Your refund of $49.99 for order ORD-7731 has been issued."
TOOLS = ["lookup_order", "verify_identity", "issue_refund"]


def call(tool: str, **args: Any) -> EvalSpan:
    return EvalSpan(tool_name=tool, attributes={"tool_args": args})


RUNS = {
    "correct": [
        call("lookup_order", order_id="ORD-7731"),
        call("verify_identity", customer_id="C-118"),
        call("issue_refund", order_id="ORD-7731", amount=49.99),
    ],
    "skipped-verification": [
        call("lookup_order", order_id="ORD-7731"),
        call("issue_refund", order_id="ORD-7731", amount=49.99),
    ],
    "wrong-amount": [
        call("lookup_order", order_id="ORD-7731"),
        call("verify_identity", customer_id="C-118"),
        call("issue_refund", order_id="ORD-7731", amount=499.9),
    ],
    "looping": [
        call("lookup_order", order_id="ORD-7731"),
        call("lookup_order", order_id="ORD-7731"),
        call("lookup_order", order_id="ORD-7731"),
        call("verify_identity", customer_id="C-118"),
        call("web_search", query="refund policy"),
        call("issue_refund", order_id="ORD-7731", amount=49.99),
    ],
}


def refund_case(case_id: str) -> TestCase:
    return TestCase(
        id=case_id,
        name=case_id.replace("-", " "),
        input="I'd like a refund for order ORD-7731.",
        expected_contains=["$49.99", "ORD-7731"],
        required_tools=TOOLS,
        required_tool_order=TOOLS,
        expected_tool_arguments={"issue_refund": {"order_id": "ORD-7731", "amount": 49.99}},
        evaluators=[
            EvaluatorConfig(name="tool_call_precision", threshold=1.0),
            EvaluatorConfig(name="no_redundant_tool_calls", threshold=1.0),
        ],
    )


def build_report() -> EvaluationReport:
    suite = TestSuite(
        name="refund-trajectory",
        version="1",
        cases=[refund_case(run_id) for run_id in RUNS],
    )
    samples = [
        EvaluationSample(
            case_id=run_id, output=REPLY, trace=EvalTrace(trace_id=run_id, spans=spans)
        )
        for run_id, spans in RUNS.items()
    ]
    return evaluate_suite(suite, samples, registry=default_registry())


def main() -> None:
    report = build_report()
    for case in report.cases:
        print(f"{case.case_id:<22} {'PASS' if case.passed else 'FAIL'}")
        for score in case.scores:
            if not score.passed:
                print(f"    {score.name}: {score.explanation}")
    print()
    for metric, stats in report.summary.metrics.items():
        print(f"{metric:<24} {stats.passed}/{stats.total} passed")
    print(f"\n{report.summary.passed_cases}/{report.summary.total_cases} runs passed")


if __name__ == "__main__":
    main()
