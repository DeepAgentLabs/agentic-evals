import json
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import yaml
from jsonschema import Draft202012Validator
from junitparser import JUnitXml

from agentic_evals import cli, evaluate_suite, load_samples, load_suite, report_schema
from agentic_evals.formatting import render_report


@pytest.fixture
def inputs(tmp_path: Path) -> tuple[Path, Path]:
    suite = tmp_path / "suite.yaml"
    suite.write_text(
        yaml.safe_dump(
            {
                "name": "CLI <suite>",
                "version": "1",
                "cases": [
                    {"id": "a", "name": "A", "input": "ok", "expected_output": "ok"},
                    {"id": "b", "name": "B", "input": "ok", "expected_output": "ok"},
                ],
            }
        ),
        encoding="utf-8",
    )
    samples = tmp_path / "samples.jsonl"
    samples.write_text(
        '\n{"case_id":"a","output":"ok","trace":{"total_latency_ms":100}}\n'
        '{"case_id":"b","output":"bad","trace":{}}\n',
        encoding="utf-8",
    )
    return suite, samples


def test_evaluate_matches_python_and_gate_fails(inputs: tuple[Path, Path], tmp_path: Path) -> None:
    suite, samples = inputs
    out = tmp_path / "report.json"
    assert cli.main(["evaluate", str(suite), str(samples), "--out", str(out)]) == 0
    actual = json.loads(out.read_text())
    Draft202012Validator(report_schema()).validate(actual)
    expected = evaluate_suite(load_suite(suite), load_samples(samples)).model_dump(mode="json")
    assert actual.pop("created_at")
    expected.pop("created_at")
    assert actual == expected
    assert cli.main(["gate", str(out)]) == 1
    config = tmp_path / "gate.yaml"
    config.write_text("min_pass_rate: 0.5\n")
    assert cli.main(["gate", str(out), "--config", str(config)]) == 0


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_suite_and_sample_formats(inputs: tuple[Path, Path], tmp_path: Path, suffix: str) -> None:
    suite, samples = inputs
    new_suite = tmp_path / ("converted" + suffix)
    data = yaml.safe_load(suite.read_text())
    new_suite.write_text(json.dumps(data) if suffix == ".json" else yaml.safe_dump(data))
    new_samples = tmp_path / ("samples" + suffix)
    payload = {"samples": [sample.model_dump() for sample in load_samples(samples)]}
    new_samples.write_text(json.dumps(payload) if suffix == ".json" else yaml.safe_dump(payload))
    assert cli.main(["evaluate", str(new_suite), str(new_samples)]) == 0


def test_junit_and_markdown(inputs: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    suite, samples = inputs
    assert cli.main(["evaluate", str(suite), str(samples), "--format", "junit"]) == 0
    output = capsys.readouterr().out
    root = ET.fromstring(output)
    junit = JUnitXml.fromstring(output.encode("utf-8"))
    assert junit.tests == 2
    assert junit.failures == 1
    assert root.attrib["tests"] == "2"
    assert root.attrib["failures"] == "1"
    assert root.find("testcase").attrib["time"] == "0.100000"  # type: ignore[union-attr]
    assert len(root.findall("testcase/failure")) == 1
    report = evaluate_suite(load_suite(suite), load_samples(samples))
    report.cases[0].scores[0].explanation = "bad\x00\ud800xml"
    assert ET.fromstring(render_report(report, "junit")) is not None
    report.cases[1].scores[0].explanation = "<script> | [link](bad)\nnext"
    text = render_report(report, "markdown")
    assert "&lt;script&gt;" in text
    assert "\\|" in text
    assert "<br>next" in text


@pytest.mark.parametrize("content", ["null", "{}", '{"samples":null}', "[{}]", "{bad"])
def test_invalid_samples_are_input_errors(
    inputs: tuple[Path, Path], tmp_path: Path, content: str, capsys: pytest.CaptureFixture[str]
) -> None:
    sample = tmp_path / "invalid.json"
    sample.write_text(content)
    assert cli.main(["evaluate", str(inputs[0]), str(sample)]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "agentic-evals:" in output.err


def test_bad_jsonl_names_line(
    inputs: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    suite, samples = inputs
    samples.write_text("\n{bad\n")
    assert cli.main(["evaluate", str(suite), str(samples)]) == 2
    assert "line 2" in capsys.readouterr().err


def test_gate_invalid_config_and_report(inputs: tuple[Path, Path], tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    config = tmp_path / "gate.json"
    assert cli.main(["evaluate", *map(str, inputs), "--out", str(report)]) == 0
    for value in ({"min_pass_rat": 0.9}, {"min_pass_rate": 2}, None, []):
        config.write_text(json.dumps(value))
        assert cli.main(["gate", str(report), "--config", str(config)]) == 2
    payload = json.loads(report.read_text())
    payload["schema_version"] = "2.0"
    report.write_text(json.dumps(payload))
    assert cli.main(["gate", str(report)]) == 2
    report.write_text("{}")
    assert cli.main(["gate", str(report)]) == 2


@pytest.mark.parametrize("fmt", ["junit", "markdown", "json"])
def test_gate_formats(inputs: tuple[Path, Path], tmp_path: Path, fmt: str) -> None:
    report, output = tmp_path / "report.json", tmp_path / "decision"
    assert cli.main(["evaluate", *map(str, inputs), "--out", str(report)]) == 0
    assert cli.main(["gate", str(report), "--format", fmt, "--out", str(output)]) == 1
    text = output.read_text()
    if fmt == "junit":
        assert ET.fromstring(text).find("testcase/failure") is not None
    elif fmt == "json":
        assert json.loads(text)["passed"] is False
    else:
        assert "Release gate: FAIL" in text


def test_pack_discovery_and_export(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["pack", "list"]) == 0
    names = capsys.readouterr().out.splitlines()
    assert "factual-qa" in names
    for name in names:
        assert cli.main(["pack", "show", name]) == 0
        assert json.loads(capsys.readouterr().out)["name"]
        out = tmp_path / "suite.json"
        assert cli.main(["pack", "show", name, "--suite", "--out", str(out)]) == 0
        assert load_suite(out).cases
    assert cli.main(["pack", "show", "../factual-qa"]) == 2


def test_live_and_registry_from_cwd(
    inputs: tuple[Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "cli_test_plugin.py").write_text(
        "from agentic_evals import default_registry\n"
        "registry = default_registry()\n"
        'def build_registry():\n    print("registry diagnostic")\n    return registry\n'
        'def target(value, *, case):\n    print("target diagnostic")\n'
        '    return {"output":value,"trace":{}}\n'
    )
    monkeypatch.chdir(tmp_path)
    for reference in ("cli_test_plugin", "cli_test_plugin:registry"):
        assert (
            cli.main(
                [
                    "live",
                    str(inputs[0]),
                    "--target",
                    "cli_test_plugin:target",
                    "--registry",
                    reference,
                    "--max-workers",
                    "2",
                ]
            )
            == 0
        )
        captured = capsys.readouterr()
        report = json.loads(captured.out)
        assert report["summary"]["pass_rate"] == 1
        assert [c["case_id"] for c in report["cases"]] == ["a", "b"]
        assert "target diagnostic" in captured.err
    assert (
        cli.main(
            ["live", str(inputs[0]), "--target", "cli_test_plugin:target", "--max-workers", "0"]
        )
        == 2
    )
    assert cli.main(["evaluate", *map(str, inputs), "--registry", "cli_test_plugin:target"]) == 2


def test_real_process_exit_codes(inputs: tuple[Path, Path], tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    command = [sys.executable, "-m", "agentic_evals.cli"]
    evaluated = subprocess.run(
        command + ["evaluate", *map(str, inputs), "--out", str(out)], capture_output=True, text=True
    )
    assert evaluated.returncode == 0, evaluated.stderr
    assert subprocess.run(command + ["gate", str(out)], capture_output=True).returncode == 1
    assert subprocess.run(command + ["gate"], capture_output=True).returncode == 2
    assert (
        subprocess.run(
            command + ["gate", str(tmp_path / "missing")], capture_output=True
        ).returncode
        == 2
    )
