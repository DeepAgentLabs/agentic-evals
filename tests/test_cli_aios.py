"""`agentic-evals aios export`: report to AIOS evaluation evidence from the CLI."""

import json
import shutil
from pathlib import Path

import pytest
import yaml

from agentic_evals import EvaluationReport, attach_aios_evidence, cli, to_aios_evidence
from aios_checks import FIXTURES, schema_errors, semantic_issues

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "examples/report-contract/evaluation-report.json"
GATE = ROOT / "examples/report-contract/gate-decision.json"


@pytest.fixture
def files(tmp_path: Path) -> dict[str, Path]:
    targets = tmp_path / "targets.yaml"
    targets.write_text(
        yaml.safe_dump({"answer": "step-answer", "missing": "step-retrieve"}), encoding="utf-8"
    )
    run = tmp_path / "run.json"
    shutil.copy(FIXTURES / "run.json", run)
    return {"targets": targets, "run": run, "out": tmp_path / "out.json"}


def test_export_merges_into_the_run_and_matches_python(files) -> None:
    code = cli.main(
        [
            "aios",
            "export",
            str(REPORT),
            "--run",
            str(files["run"]),
            "--targets",
            str(files["targets"]),
            "--gate",
            str(GATE),
            "--out",
            str(files["out"]),
        ]
    )
    merged = json.loads(files["out"].read_text())

    assert code == 0
    assert schema_errors(merged) == []
    assert semantic_issues(merged) == []
    report = EvaluationReport.model_validate_json(REPORT.read_text())
    gate = json.loads(GATE.read_text())
    expected = attach_aios_evidence(
        json.loads(files["run"].read_text()),
        to_aios_evidence(
            report,
            run_id="run-001",
            targets={"answer": "step-answer", "missing": "step-retrieve"},
            gate=gate,
        ),
    )
    assert merged == expected


def test_export_without_a_run_prints_the_evidence(capsys) -> None:
    code = cli.main(["aios", "export", str(REPORT), "--run-id", "r1", "--default-run"])
    export = json.loads(capsys.readouterr().out)

    assert code == 0
    assert export["run_id"] == "r1"
    assert {rel["target"]["id"] for rel in export["relationships"]} == {"r1"}


def test_default_target_accepts_a_step_or_json_reference(capsys) -> None:
    cli.main(["aios", "export", str(REPORT), "--run-id", "r1", "--default-target", "step-a"])
    plain = json.loads(capsys.readouterr().out)
    reference = '{"id": "m1", "type": "model_interaction"}'
    cli.main(["aios", "export", str(REPORT), "--run-id", "r1", "--default-target", reference])
    parsed = json.loads(capsys.readouterr().out)

    assert {rel["target"]["type"] for rel in plain["relationships"]} == {"step"}
    assert {rel["target"]["id"] for rel in parsed["relationships"]} == {"m1"}


def test_no_mapping_is_a_usage_error(capsys) -> None:
    assert cli.main(["aios", "export", str(REPORT), "--run-id", "r1"]) == 2
    assert "no target mapping" in capsys.readouterr().err


def test_unmapped_cases_fail_unless_allowed(files, capsys, tmp_path) -> None:
    partial = tmp_path / "partial.json"
    partial.write_text('{"answer": "step-answer"}', encoding="utf-8")
    args = ["aios", "export", str(REPORT), "--run-id", "r1", "--targets", str(partial)]

    assert cli.main(args) == 2
    assert "missing" in capsys.readouterr().err
    assert cli.main([*args, "--allow-unmapped"]) == 0
    captured = capsys.readouterr()
    assert "not exported (no target): missing" in captured.err
    assert json.loads(captured.out)["unmapped_cases"] == ["missing"]


def test_unresolved_target_in_the_run_is_an_error(files, capsys) -> None:
    code = cli.main(
        ["aios", "export", str(REPORT), "--run", str(files["run"]), "--default-target", "nope"]
    )
    assert code == 2
    assert "not found in the run" in capsys.readouterr().err


@pytest.mark.parametrize(
    "extra,message",
    [
        ([], "--run-id"),
        (["--run-id", "r1", "--default-run", "--default-target", "s"], "not both"),
    ],
)
def test_argument_errors(extra, message, capsys) -> None:
    assert cli.main(["aios", "export", str(REPORT), *extra]) == 2
    assert message in capsys.readouterr().err


def test_targets_must_be_a_mapping(tmp_path, capsys) -> None:
    targets = tmp_path / "targets.yaml"
    targets.write_text("- step-answer\n", encoding="utf-8")
    code = cli.main(["aios", "export", str(REPORT), "--run-id", "r", "--targets", str(targets)])
    assert code == 2
    assert "must map case IDs" in capsys.readouterr().err


def test_invalid_reports_are_rejected(tmp_path, capsys) -> None:
    broken = tmp_path / "report.json"
    broken.write_text('{"suite_name": "x"}', encoding="utf-8")
    assert cli.main(["aios", "export", str(broken), "--run-id", "r", "--default-run"]) == 2
    assert "ValidationError" in capsys.readouterr().err
