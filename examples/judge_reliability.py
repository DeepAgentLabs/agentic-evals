"""Judge cost, retries, an unavailable judge and repeated judging, offline.

`complete_fn` stands in for a real model call. It reports usage through
`JudgeResponse`, fails transiently on its first call, never answers for one
case, and is unsure about another, so the report shows every v0.9 outcome:

- judge cost and tokens on each score and totalled in `summary.judge`
- a retried call that recovered
- an unavailable judgment that fails the default gate and names its case
- low agreement across `samples=3` that `min_judge_agreement` catches

Run: python examples/judge_reliability.py
"""

from agentic_evals import (
    FACTUALITY,
    EvalTrace,
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

QUESTIONS = {
    "france": ("What is the capital of France?", "Paris"),
    "japan": ("What is the capital of Japan?", "Tokyo"),
    "australia": ("What is the capital of Australia?", "Canberra"),
}
calls: dict[str, int] = {}


def complete_fn(prompt: str) -> JudgeResponse:
    """Replace with your provider call; return its usage when it reports one."""
    case = next(name for name, (question, _) in QUESTIONS.items() if question in prompt)
    calls[case] = calls.get(case, 0) + 1
    if case == "france" and calls[case] == 1:
        raise ConnectionError("rate limited")  # transient: the retry recovers
    if case == "japan":
        raise TimeoutError("judge provider timed out")  # never answers
    # Australia: the judge is unsure and flips between verdicts.
    verdict = "A" if case == "france" or calls[case] % 3 == 0 else "C"
    return JudgeResponse(
        text=verdict,
        input_tokens=180,
        output_tokens=1,
        cost_usd=0.0003,
        cost_source="measured",
        model="example-judge",
        provider="example",
    )


def main() -> None:
    registry = EvaluatorRegistry()
    registry.register(
        LLMRubricEvaluator(
            "factuality",
            FACTUALITY,
            complete_fn,
            version="2026-10",
            retry=RetryPolicy(max_attempts=3, backoff_seconds=0.0),
            samples=3,
        )
    )
    suite = TestSuite(
        name="judge-reliability-demo",
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
            for case, (question, answer) in QUESTIONS.items()
        ],
    )
    samples = [
        EvaluationSample(case_id=case, output=answer, trace=EvalTrace(trace_id=case))
        for case, (_, answer) in QUESTIONS.items()
    ]
    report = evaluate_suite(suite, samples, registry=registry)

    for case in report.cases:
        score = case.scores[0]
        meta = score.metadata
        print(
            f"{case.case_id:<10} {meta['judge_status']:<12} attempts={meta['judge_attempts']} "
            f"agreement={meta.get('judge_agreement', '-')} value={score.value:.2f}"
        )
    judge = report.summary.judge
    assert judge is not None
    # The unavailable judgment has no cost, so the total is honestly incomplete.
    total = "incomplete" if judge.total_cost_usd is None else f"${judge.total_cost_usd:.4f}"
    print(f"\njudge cost {total} over {judge.judge_scores} scores")
    print(f"priced {judge.priced_scores}, unavailable in {judge.unavailable_cases}")
    print(f"lowest agreement {judge.min_agreement}, per case {judge.case_agreement}")

    gate = evaluate_gate(report, GateConfig(min_pass_rate=0, min_judge_agreement=0.8))
    print(f"\ngate passed: {gate.passed}")
    for reason in gate.reasons:
        print(f"- {reason}")
    assert not gate.passed


if __name__ == "__main__":
    main()
