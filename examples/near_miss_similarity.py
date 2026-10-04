"""Grades a near-match with a similarity scorer instead of a strict
exact-match check. The reference text goes in
`EvaluatorConfig.config["reference"]` -- the same pattern
`LLMRubricEvaluator` uses. Setting `case.expected_output` works too:
`evaluate_suite` leaves out its exact-match check when a similarity
scorer is grading against that field.

Run: python examples/near_miss_similarity.py
"""

from agentic_evals import (
    EvalTrace,
    EvaluationSample,
    EvaluatorConfig,
    TestCase,
    TestSuite,
    default_registry,
    evaluate_suite,
)


def main() -> None:
    reference = "Your refund is on its way."
    suite = TestSuite(
        name="near-miss-demo",
        version="1",
        cases=[
            TestCase(
                id="paraphrase",
                name="Answer is close to the reference, not identical",
                # The reference text for the graded scorer lives in the
                # evaluator's own config.
                evaluators=[
                    EvaluatorConfig(
                        name="levenshtein_similarity",
                        threshold=0.85,
                        config={"reference": reference},
                    )
                ],
            )
        ],
    )

    # A near-miss: same meaning, different punctuation.
    sample = EvaluationSample(
        case_id="paraphrase", output="Your refund is on its way!", trace=EvalTrace()
    )

    report = evaluate_suite(suite, [sample], registry=default_registry())
    case = report.cases[0]
    score = case.scores[0]

    print(f"levenshtein_similarity: passed={score.passed}  value={score.value:.3f}")
    print(f"case.passed = {case.passed}")


if __name__ == "__main__":
    main()
