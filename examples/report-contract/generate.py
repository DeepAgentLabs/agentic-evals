"""Run with: uv run python examples/report-contract/generate.py."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from agentic_evals import (
    EvalTrace,
    EvaluationContext,
    EvaluationReport,
    EvaluationSample,
    EvaluatorConfig,
    EvaluatorRegistry,
    GateConfig,
    LLMJudgeEvaluator,
    PythonTarget,
    RetryPolicy,
    Score,
    TestCase,
    TestSuite,
    evaluate_gate,
    evaluate_suite,
    gate_decision_schema,
    report_schema,
    run_live_suite,
)

CREATED_AT = datetime(2026, 10, 17, tzinfo=timezone.utc)


def answer(payload: Any, *, case: TestCase) -> dict[str, Any]:
    """The live target for the v0.9 example: one case's backend is down."""
    if case.id == "outage":
        raise ConnectionError("backend unavailable")
    return {"output": "Paris", "trace": {"trace_id": f"live-{case.id}"}}


def _judge(context: EvaluationContext) -> Score:
    if context.case.id == "judge-down":
        raise TimeoutError("judge provider timed out")
    return Score(
        name="quality",
        value=1.0,
        passed=True,
        explanation="The answer names the capital.",
        metadata={
            "verdict": "A",
            "judge_cost_usd": 0.0004,
            "judge_cost_source": "measured",
            "judge_input_tokens": 120,
            "judge_output_tokens": 2,
            "judge_latency_ms": 85.0,
            "judge_model": "example-judge",
        },
    )


def judged_live_report() -> EvaluationReport:
    """A live run with retries, a judge outage and a target outage (Evals 0.9)."""
    judged = [EvaluatorConfig(name="quality", threshold=0.5, required=False)]
    suite = TestSuite(
        name="judged-live-contract",
        version="1",
        cases=[
            TestCase(
                id="answered", name="Judged answer", expected_output="Paris", evaluators=judged
            ),
            TestCase(
                id="judge-down", name="Judge outage", expected_output="Paris", evaluators=judged
            ),
            TestCase(id="outage", name="Target outage", expected_output="Paris"),
        ],
    )
    registry = EvaluatorRegistry()
    registry.register(LLMJudgeEvaluator("quality", _judge, version="1", retry=RetryPolicy(2)))
    report = run_live_suite(
        suite,
        PythonTarget(callable_path=f"{Path(__file__).resolve()}:answer"),
        registry=registry,
        retry=RetryPolicy(max_attempts=2),
    )
    # Measured wall-clock values vary per run; pin them so the example is stable.
    for case in report.cases:
        for score in case.scores:
            if score.metadata.get("judge_status") == "unavailable":
                score.metadata["judge_latency_ms"] = 0.0
    assert report.summary.judge is not None
    report.summary.judge.total_latency_ms = 85.0
    report.created_at = CREATED_AT
    return report


def main() -> None:
    suite = TestSuite(
        name="release-contract",
        version="1",
        cases=[
            TestCase(id="answer", name="Correct answer", expected_output="42", tags=["smoke"]),
            TestCase(id="missing", name="Missing evidence", expected_output="ok"),
        ],
    )
    report = evaluate_suite(
        suite,
        [EvaluationSample(case_id="answer", output="42", trace=EvalTrace(trace_id="example"))],
    )
    report.created_at = CREATED_AT
    gate = evaluate_gate(report, GateConfig())
    live = judged_live_report()
    live_gate = evaluate_gate(live, GateConfig(min_pass_rate=0.5))
    destination = Path(__file__).resolve().parent
    for name, artifact, schema in (
        ("evaluation-report", report, report_schema()),
        ("gate-decision", gate, gate_decision_schema()),
        ("judged-live-report", live, report_schema()),
        ("judged-live-gate-decision", live_gate, gate_decision_schema()),
    ):
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(
            artifact.model_dump(mode="json")
        )
        (destination / f"{name}.json").write_text(
            artifact.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    assert not gate.passed  # Missing evidence deliberately blocks release.
    assert not live_gate.passed  # So does a judge that could not deliver a verdict.


if __name__ == "__main__":
    main()
