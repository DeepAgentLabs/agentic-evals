"""Run with: uv run python examples/report-contract/generate.py."""

from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from agentic_evals import (
    EvalTrace,
    EvaluationSample,
    GateConfig,
    TestCase,
    TestSuite,
    evaluate_gate,
    evaluate_suite,
    gate_decision_schema,
    report_schema,
)


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
    report.created_at = datetime(2026, 10, 17, tzinfo=timezone.utc)
    gate = evaluate_gate(report, GateConfig())
    destination = Path(__file__).resolve().parent
    for name, artifact, schema in (
        ("evaluation-report", report, report_schema()),
        ("gate-decision", gate, gate_decision_schema()),
    ):
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(
            artifact.model_dump(mode="json")
        )
        (destination / f"{name}.json").write_text(
            artifact.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    assert not gate.passed  # Missing evidence deliberately blocks release.


if __name__ == "__main__":
    main()
