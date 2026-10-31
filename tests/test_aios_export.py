"""AIOS v0.4-draft evaluation evidence export (roadmap v0.10)."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from agentic_evals import (
    AIOSEvidenceExport,
    AIOSExportError,
    BusinessRuleEvaluator,
    EvalTrace,
    EvaluationReport,
    EvaluationSample,
    EvaluatorConfig,
    EvaluatorRegistry,
    GateConfig,
    LLMJudgeEvaluator,
    Score,
    TestCase,
    TestSuite,
    attach_aios_evidence,
    evaluate_gate,
    evaluate_suite,
    to_aios_evidence,
)
from agentic_evals.aios import EXTENSION_NAME, SPEC_VERSION
from aios_checks import FIXTURES, sample_run, schema_errors, semantic_issues

ROOT = Path(__file__).resolve().parents[1]
CREATED_AT = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def _down(context):
    raise TimeoutError("judge provider timed out")


def _not_applicable(context):
    return Score.skip("tone", "No customer-facing reply in this case.")


@pytest.fixture
def report() -> EvaluationReport:
    registry = EvaluatorRegistry()
    registry.register(LLMJudgeEvaluator("quality", _down, version="judge-v2"))
    registry.register(BusinessRuleEvaluator("tone", _not_applicable, version="1"))
    suite = TestSuite(
        name="support",
        version="3",
        cases=[
            TestCase(id="answer", name="Correct answer", expected_output="Paris"),
            TestCase(id="wrong", name="Wrong answer", expected_output="42"),
            TestCase(
                id="judged",
                name="Judged reply",
                expected_output="ok",
                evaluators=[
                    EvaluatorConfig(name="quality", required=False),
                    EvaluatorConfig(name="tone"),
                ],
            ),
        ],
    )
    samples = [
        EvaluationSample(case_id=case_id, output=output, trace=EvalTrace(trace_id=case_id))
        for case_id, output in (("answer", "Paris"), ("wrong", "41"), ("judged", "ok"))
    ]
    result = evaluate_suite(suite, samples, registry=registry)
    result.created_at = CREATED_AT
    return result


TARGETS = {"answer": "step-answer", "wrong": "step-answer", "judged": "step-retrieve"}


def _by_id(items, key="id"):
    return {item[key]: item for item in items}


def test_every_score_becomes_an_evaluation_with_a_target(report) -> None:
    export = to_aios_evidence(report, run_id="run-001", targets=TARGETS)

    assert isinstance(export, AIOSEvidenceExport)
    assert export.spec_version == SPEC_VERSION
    scores = sum(len(case.scores) for case in report.cases)
    assert len(export.evidence) == scores + len(report.cases)
    assert {item["type"] for item in export.evidence} == {"evaluation"}
    sources = {rel["source"]["id"] for rel in export.relationships}
    assert sources == {item["id"] for item in export.evidence}  # P08 by construction
    assert {rel["type"] for rel in export.relationships} == {"evaluates"}


def test_attributes_carry_criterion_method_result_and_score(report) -> None:
    export = to_aios_evidence(report, run_id="run-001", targets=TARGETS)
    evidence = _by_id(export.evidence)
    first = evidence["run-001:evals:support:answer:score:1"]
    case = report.cases[0]
    score = case.scores[0]

    assert first["status"] == "passed"
    attributes = first["attributes"]
    assert attributes["criterion"] == score.metric
    assert attributes["method"] == {
        "evaluator": score.evaluator,
        "evaluator_version": score.evaluator_version,
        "evaluator_type": score.evaluator_type,
    }
    assert attributes["result"] == "passed"
    assert attributes["score"] == score.value
    assert attributes["case_id"] == "answer"
    assert attributes["suite_version"] == "3"
    assert first["extensions"][EXTENSION_NAME]["producer"] == "agentic-evals"


def test_failed_scores_and_case_verdicts_keep_their_result(report) -> None:
    evidence = _by_id(to_aios_evidence(report, run_id="run-001", targets=TARGETS).evidence)

    assert evidence["run-001:evals:support:wrong:score:1"]["attributes"]["result"] == "failed"
    verdict = evidence["run-001:evals:support:wrong:case"]
    assert verdict["status"] == "failed"
    assert verdict["attributes"]["criterion"] == "case_verdict"
    assert verdict["attributes"]["failed_required_scores"] == 1
    assert evidence["run-001:evals:support:answer:case"]["status"] == "passed"


def test_a_skipped_score_is_never_exported_as_a_pass(report) -> None:
    export = to_aios_evidence(report, run_id="run-001", targets=TARGETS)
    skipped = [item for item in export.evidence if item["status"] == "skipped"]

    assert export.skipped_scores == 1 == len(skipped)
    assert skipped[0]["attributes"]["result"] == "skipped"
    assert "score" not in skipped[0]["attributes"]
    # Nothing was judged, so there is no evaluation lifecycle event for it.
    assert skipped[0]["id"] not in {event["object_id"] for event in export.events}


def test_an_unavailable_judge_is_exported_as_a_failed_evaluation(report) -> None:
    export = to_aios_evidence(report, run_id="run-001", targets=TARGETS)
    unavailable = [item for item in export.evidence if item["status"] == "unavailable"]

    assert export.unavailable_scores == 1 == len(unavailable)
    assert "score" not in unavailable[0]["attributes"]
    assert unavailable[0]["attributes"]["metadata"]["judge_status"] == "unavailable"
    events = _by_id(export.events, "object_id")
    assert events[unavailable[0]["id"]]["event_name"] == "aiops.evaluation.failed"


def test_events_identify_method_criterion_target_and_result(report) -> None:
    export = to_aios_evidence(report, run_id="run-001", targets=TARGETS)
    event = _by_id(export.events, "object_id")["run-001:evals:support:answer:score:1"]

    assert event["event_name"] == "aiops.evaluation.completed"
    assert event["occurred_at"] == "2026-10-31T12:00:00Z"
    assert event["object_type"] == "evaluation"
    assert set(event["attributes"]) == {"criterion", "method", "result", "targets"}
    assert event["attributes"]["targets"] == ["step-answer"]


def test_no_target_mapping_fails_loudly(report) -> None:
    with pytest.raises(AIOSExportError, match="no target mapping"):
        to_aios_evidence(report, run_id="run-001")
    with pytest.raises(AIOSExportError, match="no target mapping"):
        to_aios_evidence(report, run_id="run-001", targets={})


def test_an_unmapped_case_is_reported_not_guessed(report) -> None:
    partial = {"answer": "step-answer"}
    with pytest.raises(AIOSExportError, match=r"\['wrong', 'judged'\]"):
        to_aios_evidence(report, run_id="run-001", targets=partial)

    export = to_aios_evidence(report, run_id="run-001", targets=partial, allow_unmapped=True)
    assert export.unmapped_cases == ["wrong", "judged"]
    assert export.exported_cases == 1
    assert {item["attributes"]["case_id"] for item in export.evidence} == {"answer"}


def test_cases_without_observed_output_are_reported_not_exported() -> None:
    """A missing sample or a failed live call left nothing in the Run to judge."""
    live = EvaluationReport.model_validate_json(
        (ROOT / "examples/report-contract/judged-live-report.json").read_text()
    )
    outage = next(case for case in live.cases if case.case_id == "outage")
    assert outage.target_status == "error"

    # The unobserved case needs no mapping, and mapping it does not export it.
    for targets in ({"answered": "s", "judge-down": "s"}, {"outage": "s"}):
        export = to_aios_evidence(live, run_id="r", targets=targets, allow_unmapped=True)
        assert export.unobserved_cases == ["outage"]
        exported = {item["attributes"].get("case_id") for item in export.evidence}
        assert "outage" not in exported
        assert "target_call" not in {item["attributes"]["criterion"] for item in export.evidence}

    missing = EvaluationReport.model_validate_json(
        (ROOT / "examples/report-contract/evaluation-report.json").read_text()
    )
    export = to_aios_evidence(missing, run_id="r", default_target="s")
    assert export.unobserved_cases == ["missing"]
    assert export.exported_cases == 1


def test_targets_for_unknown_cases_are_rejected(report) -> None:
    with pytest.raises(AIOSExportError, match="not in the report: \\['typo'\\]"):
        to_aios_evidence(report, run_id="run-001", targets={**TARGETS, "typo": "step-answer"})


@pytest.mark.parametrize(
    "target",
    [
        {"id": " ", "type": "step"},
        {"id": "x", "type": "trace"},
        {"id": "x", "type": "step", "extra": 1},
        [],
        42,
    ],
)
def test_malformed_targets_are_rejected(report, target) -> None:
    with pytest.raises(AIOSExportError):
        to_aios_evidence(report, run_id="run-001", default_target=target)


def test_blank_run_id_is_rejected(report) -> None:
    with pytest.raises(AIOSExportError, match="run_id"):
        to_aios_evidence(report, run_id="  ", targets=TARGETS)


def test_default_and_multiple_targets(report) -> None:
    export = to_aios_evidence(
        report,
        run_id="run-001",
        targets={"judged": ["step-retrieve", {"id": "model-001", "type": "model_interaction"}]},
        default_target={"id": "run-001", "type": "run"},
    )
    targets: dict[str, list] = {}
    for rel in export.relationships:
        targets.setdefault(rel["source"]["id"], []).append(rel["target"])
    assert targets["run-001:evals:support:answer:case"] == [{"id": "run-001", "type": "run"}]
    assert targets["run-001:evals:support:judged:case"] == [
        {"id": "step-retrieve", "type": "step"},
        {"id": "model-001", "type": "model_interaction"},
    ]


def test_external_targets_are_marked(report) -> None:
    export = to_aios_evidence(
        report,
        run_id="run-001",
        default_target={"id": "trace-9", "type": "run", "external": True},
    )
    assert all(rel["target"]["external"] is True for rel in export.relationships)


def test_gate_decision_becomes_a_readiness_evaluation_of_the_run(report) -> None:
    gate = evaluate_gate(report, GateConfig())
    export = to_aios_evidence(report, run_id="run-001", targets=TARGETS, gate=gate)
    evidence = _by_id(export.evidence)["run-001:evals:support:gate"]

    assert evidence["status"] == "failed"
    assert evidence["attributes"]["criterion"] == "release_gate"
    assert evidence["attributes"]["reasons"] == gate.reasons
    gate_rels = [rel for rel in export.relationships if rel["source"]["id"] == evidence["id"]]
    assert [rel["target"] for rel in gate_rels] == [{"id": "run-001", "type": "run"}]


def test_report_and_gate_dicts_are_accepted(report) -> None:
    gate = evaluate_gate(report, GateConfig(min_pass_rate=0))
    from_models = to_aios_evidence(report, run_id="r", default_target="s", gate=gate)
    from_dicts = to_aios_evidence(
        report.model_dump(mode="json"),
        run_id="r",
        default_target="s",
        gate=gate.model_dump(mode="json"),
    )
    assert from_models == from_dicts


def test_export_is_json_serializable(report) -> None:
    export = to_aios_evidence(report, run_id="run-001", targets=TARGETS)
    assert json.loads(export.model_dump_json()) == export.model_dump(mode="json")


def test_merged_run_is_schema_and_semantically_aligned(report) -> None:
    gate = evaluate_gate(report, GateConfig())
    export = to_aios_evidence(report, run_id="run-001", targets=TARGETS, gate=gate)
    run = sample_run()
    merged = attach_aios_evidence(run, export)

    assert schema_errors(merged) == []
    assert semantic_issues(merged) == []
    assert len(merged["evidence"]) == len(run["evidence"]) + len(export.evidence)
    assert run == sample_run()  # the input artifact is not modified


def test_attach_rejects_unresolved_targets(report) -> None:
    export = to_aios_evidence(report, run_id="run-001", default_target="step-missing")
    with pytest.raises(AIOSExportError, match="step-missing"):
        attach_aios_evidence(sample_run(), export)
    wrong_type = to_aios_evidence(
        report, run_id="run-001", default_target={"id": "step-answer", "type": "agent"}
    )
    with pytest.raises(AIOSExportError, match="not found in the run"):
        attach_aios_evidence(sample_run(), wrong_type)


def test_attach_allows_external_and_existing_evidence_targets(report) -> None:
    export = to_aios_evidence(
        report,
        run_id="run-001",
        default_target=[
            {"id": "eval-001", "type": "evaluation"},
            {"id": "lens-trace", "type": "run", "external": True},
        ],
    )
    merged = attach_aios_evidence(sample_run(), export)
    assert schema_errors(merged) == []
    assert semantic_issues(merged) == []


def test_attach_rejects_a_different_run_and_non_run_artifacts(report) -> None:
    export = to_aios_evidence(report, run_id="run-002", default_target="step-answer")
    with pytest.raises(AIOSExportError, match="run-002"):
        attach_aios_evidence(sample_run(), export)
    with pytest.raises(AIOSExportError, match="run artifact"):
        attach_aios_evidence({**sample_run(), "artifact_type": "workflow"}, export)
    with pytest.raises(AIOSExportError, match="run artifact"):
        attach_aios_evidence({**sample_run(), "spec_version": "0.5-draft"}, export)


def test_attach_detects_id_collisions_and_prefix_resolves_them(report) -> None:
    first = to_aios_evidence(report, run_id="run-001", targets=TARGETS)
    again = to_aios_evidence(report, run_id="run-001", targets=TARGETS)
    with pytest.raises(AIOSExportError, match="already present"):
        attach_aios_evidence(sample_run(), [first, again])
    with pytest.raises(AIOSExportError, match="already present"):
        attach_aios_evidence(attach_aios_evidence(sample_run(), first), first)

    retry = to_aios_evidence(report, run_id="run-001", targets=TARGETS, id_prefix="retry-2")
    merged = attach_aios_evidence(sample_run(), [first, retry])
    assert schema_errors(merged) == []
    assert semantic_issues(merged) == []


def test_attach_into_a_run_without_evidence_or_events(report) -> None:
    run = {
        "spec_version": "0.4-draft",
        "artifact_type": "run",
        "id": "run-min",
        "started_at": "2026-10-31T11:59:00Z",
        "status": "completed",
        "requests": [],
        "steps": [],
        "relationships": [],
    }
    export = to_aios_evidence(
        report, run_id="run-min", default_target={"id": "run-min", "type": "run"}
    )
    merged = attach_aios_evidence(run, export)
    assert schema_errors(merged) == []
    assert semantic_issues(merged) == []


def test_dropping_a_relationship_is_caught_as_p08(report) -> None:
    """Negative control: the checker would notice orphaned evidence."""
    merged = attach_aios_evidence(
        sample_run(), to_aios_evidence(report, run_id="run-001", targets=TARGETS)
    )
    orphan = merged["evidence"][-1]["id"]
    merged["relationships"] = [
        rel for rel in merged["relationships"] if rel["source"]["id"] != orphan
    ]
    assert ("AIOS-0.4-P08", orphan) in semantic_issues(merged)


def _spec_checkout() -> Path | None:
    configured = os.environ.get("AIOS_SPEC_PATH")
    candidate = (
        Path(configured)
        if configured
        else Path(__file__).resolve().parents[2] / "ai-operations-spec"
    )
    return candidate if (candidate / "specification/v0.4/schemas").is_dir() else None


@pytest.mark.parametrize(
    "fixture,source",
    [
        ("run.schema.json", "specification/v0.4/schemas/run.schema.json"),
        ("common.schema.json", "specification/v0.4/schemas/common.schema.json"),
        ("run.json", "specification/v0.4/examples/valid/run.json"),
    ],
)
def test_vendored_fixtures_match_the_specification(fixture, source) -> None:
    checkout = _spec_checkout()
    if checkout is None:
        pytest.skip("no ai-operations-spec checkout (set AIOS_SPEC_PATH)")
    assert json.loads((FIXTURES / fixture).read_text()) == json.loads(
        (checkout / source).read_text()
    )


def test_mcp_spec_validator_reports_alignment(report) -> None:
    """Validate in: deep-agentic-core-mcp `spec.validate_artifact`, when installed."""
    adapter = pytest.importorskip("deep_agentic_core_mcp.adapters.ai_operations_spec")
    try:
        adapter._require_available()
    except Exception as exc:  # noqa: BLE001 - adapter reports a missing spec checkout
        pytest.skip(f"MCP cannot load the specification: {exc}")
    gate = evaluate_gate(report, GateConfig())
    merged = attach_aios_evidence(
        sample_run(), to_aios_evidence(report, run_id="run-001", targets=TARGETS, gate=gate)
    )
    result = adapter.validate_artifact(merged)
    assert result["ok"], result
    assert result["conformance"]["aligned"] is True
