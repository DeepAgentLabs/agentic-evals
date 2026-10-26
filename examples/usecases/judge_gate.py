"""Gate support answers on an LLM judge, and on whether the judge itself held up.

`complete_fn` stands in for your model call. The flaky judge is rate limited
once, never answers for one case and flips its verdict on another; the steady
judge answers every call the same way. Nothing here calls a model.

Run: python judge_gate.py            (flaky judge, gate fails, exit 1)
     python judge_gate.py --steady   (steady judge, gate passes, exit 0)
"""

import sys
from collections.abc import Callable

from agentic_evals import (
    FACTUALITY,
    EvalTrace,
    EvaluationReport,
    EvaluationSample,
    EvaluatorConfig,
    EvaluatorRegistry,
    GateConfig,
    JudgeResponse,
    LLMRubricEvaluator,
    RetryPolicy,
    TestCase,
    TestSuite,
    evaluate_gate,
    evaluate_suite,
)

ANSWERS = {
    "refund-window": ("How long do I have to return an item?", "You have 30 days from delivery."),
    "shipping-cost": ("Is shipping free?", "Shipping is free on orders over $50."),
    "warranty": ("Does the blender have a warranty?", "Yes, a two-year limited warranty."),
}
GATE = GateConfig(min_pass_rate=0.9, min_judge_agreement=0.8, max_judge_cost_usd=0.05)


def make_judge(flaky: bool) -> Callable[[str], JudgeResponse]:
    calls: dict[str, int] = {}

    def complete_fn(prompt: str) -> JudgeResponse:
        """Replace with your provider call; return its usage when it reports one."""
        case = next(c for c, (question, _) in ANSWERS.items() if question in prompt)
        calls[case] = calls.get(case, 0) + 1
        verdict = "A"
        if flaky and case == "refund-window" and calls[case] == 1:
            raise ConnectionError("429 rate limited")  # transient: the retry recovers
        if flaky and case == "shipping-cost":
            raise TimeoutError("judge provider timed out")  # never answers
        if flaky and case == "warranty" and calls[case] % 3:
            verdict = "C"  # unsure: two of three samples disagree with the third
        return JudgeResponse(
            text=verdict,
            input_tokens=210,
            output_tokens=1,
            cost_usd=0.0004,
            cost_source="measured",
            model="your-judge-model",
        )

    return complete_fn


def build_report(flaky: bool) -> EvaluationReport:
    registry = EvaluatorRegistry()
    registry.register(
        LLMRubricEvaluator(
            "factuality",
            FACTUALITY,
            make_judge(flaky),
            version="support-v1",
            retry=RetryPolicy(max_attempts=3, backoff_seconds=0.0),
            samples=3,
        )
    )
    suite = TestSuite(
        name="support-answers-judged",
        version="1",
        cases=[
            TestCase(
                id=case,
                name=question,
                input=question,
                evaluators=[
                    EvaluatorConfig(name="factuality", threshold=0.6, config={"reference": answer})
                ],
            )
            for case, (question, answer) in ANSWERS.items()
        ],
    )
    samples = [
        EvaluationSample(case_id=case, output=answer, trace=EvalTrace(trace_id=case))
        for case, (_, answer) in ANSWERS.items()
    ]
    return evaluate_suite(suite, samples, registry=registry)


def main(argv: list[str]) -> int:
    flaky = "--steady" not in argv
    report = build_report(flaky)
    print(f"== {'flaky' if flaky else 'steady'} judge ==")
    for case in report.cases:
        meta = case.scores[0].metadata
        print(
            f"{case.case_id:<14} {meta['judge_status']:<12} attempts={meta['judge_attempts']} "
            f"agreement={meta.get('judge_agreement', '-')} {'PASS' if case.passed else 'FAIL'}"
        )
    judge = report.summary.judge
    assert judge is not None
    cost = "incomplete" if judge.total_cost_usd is None else f"${judge.total_cost_usd:.4f}"
    print(f"judge cost {cost}; unavailable in {judge.unavailable_cases}")
    print(f"lowest agreement {judge.min_agreement}")

    gate = evaluate_gate(report, GATE)
    print(f"\ngate passed: {gate.passed}")
    for reason in gate.reasons:
        print(f"- {reason}")
    return 0 if gate.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
