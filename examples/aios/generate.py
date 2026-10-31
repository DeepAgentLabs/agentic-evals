"""Run with: uv run python examples/aios/generate.py.

Scores one support conversation, gates it, and attaches the results to the
AIOS Run artifact that recorded the conversation (`run.json`). Writes:

- `report.json` and `gate-decision.json`: the native Evals artifacts
- `evidence.json`: the AIOS evaluation evidence, before merging
- `run-with-evaluations.json`: `run.json` with the evidence attached
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from agentic_evals import (
    AIOSExportError,
    EvalSpan,
    EvalTrace,
    EvaluationSample,
    GateConfig,
    TestCase,
    TestSuite,
    attach_aios_evidence,
    evaluate_gate,
    evaluate_suite,
    to_aios_evidence,
)

HERE = Path(__file__).resolve().parent
CREATED_AT = datetime(2026, 10, 31, 9, 0, 5, tzinfo=timezone.utc)


def main() -> None:
    suite = TestSuite(
        name="support-refunds",
        version="1",
        cases=[
            TestCase(
                id="grounded-answer",
                name="Answer cites the refund policy",
                expected_contains=["30 days"],
                tags=["grounding"],
            ),
            TestCase(
                id="refund-tool",
                name="Refund issued with an order ID",
                required_tools=["refund"],
                required_tool_arguments={"refund": ["order_id"]},
                tags=["tools"],
            ),
        ],
    )
    trace = EvalTrace(
        trace_id="support-run-042",
        spans=[EvalSpan(tool_name="refund", attributes={"tool_arguments": {"amount": 20}})],
    )
    report = evaluate_suite(
        suite,
        [
            EvaluationSample(
                case_id="grounded-answer",
                output="Refunds are accepted within 30 days of delivery.",
                trace=trace,
            ),
            EvaluationSample(case_id="refund-tool", output="Refund issued.", trace=trace),
        ],
    )
    report.created_at = CREATED_AT
    gate = evaluate_gate(report, GateConfig())

    run = json.loads((HERE / "run.json").read_text(encoding="utf-8"))
    targets = yaml.safe_load((HERE / "targets.yaml").read_text(encoding="utf-8"))
    export = to_aios_evidence(report, run_id=run["id"], targets=targets, gate=gate)
    merged = attach_aios_evidence(run, export)

    # A report with no target mapping fails loudly instead of orphaning evidence.
    try:
        to_aios_evidence(report, run_id=run["id"])
    except AIOSExportError:
        pass
    else:
        raise AssertionError("an unmapped export must fail")
    assert not gate.passed  # The refund call is missing its order ID.

    for name, text in (
        ("report", report.model_dump_json(indent=2)),
        ("gate-decision", gate.model_dump_json(indent=2)),
        ("evidence", export.model_dump_json(indent=2)),
        ("run-with-evaluations", json.dumps(merged, indent=2)),
    ):
        (HERE / f"{name}.json").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
