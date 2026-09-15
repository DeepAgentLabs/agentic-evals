"""Grade an answer for factual consistency using the FACTUALITY rubric.

This package never calls a model itself -- `complete_fn` below stands in
for a real call to whatever provider you use.

Run: python examples/llm_rubric_judge.py
"""

from agentic_evals import (
    FACTUALITY,
    EvalTrace,
    EvaluationSample,
    EvaluatorConfig,
    EvaluatorRegistry,
    LLMRubricEvaluator,
    TestCase,
    TestSuite,
    evaluate_suite,
)


def complete_fn(prompt: str) -> str:
    """Replace this with a real call to your model provider."""
    print("--- prompt sent to the model ---")
    print(prompt)
    print("--- end prompt ---\n")
    return "(A) The submitted answer is fully consistent with the reference."


def main() -> None:
    registry = EvaluatorRegistry()
    registry.register(LLMRubricEvaluator("factuality", FACTUALITY, complete_fn))

    suite = TestSuite(
        name="factual-qa-demo",
        version="1",
        cases=[
            TestCase(
                id="capital-of-france",
                name="Answer states the correct capital",
                input="What is the capital of France?",
                evaluators=[
                    EvaluatorConfig(
                        name="factuality",
                        threshold=0.8,
                        config={"reference": "Paris is the capital of France."},
                    )
                ],
            )
        ],
    )
    sample = EvaluationSample(case_id="capital-of-france", output="Paris.", trace=EvalTrace())

    report = evaluate_suite(suite, [sample], registry=registry)
    score = report.cases[0].scores[0]
    print(f"verdict={score.metadata['verdict']}  value={score.value}  passed={score.passed}")


if __name__ == "__main__":
    main()
