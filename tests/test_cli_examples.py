"""Run shipped CLI examples so documentation paths remain executable."""

import subprocess
import sys
from pathlib import Path

from agentic_evals.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_ci_positive_and_negative_controls(tmp_path: Path) -> None:
    fixtures = ROOT / "examples/ci"
    report = tmp_path / "report.json"
    for samples, code in (("samples.jsonl", 0), ("failing-samples.jsonl", 1)):
        assert (
            main(
                [
                    "evaluate",
                    str(fixtures / "suite.yaml"),
                    str(fixtures / samples),
                    "--out",
                    str(report),
                ]
            )
            == 0
        )
        assert main(["gate", str(report), "--config", str(fixtures / "gate.yaml")]) == code


def test_voice_cli_matches_python(tmp_path: Path) -> None:
    script = """
import json
import sys
from pathlib import Path
from export_cli import main as export
from evaluators import build_registry
from agentic_evals import evaluate_suite, load_suite, load_samples
from agentic_evals.cli import main
export()
suite = "cli-output/suite.json"
samples = "cli-output/samples.jsonl"
assert main(["evaluate", suite, samples, "--registry", "evaluators", "--out", "report.json"]) == 0
actual = json.loads(Path("report.json").read_text())
expected = evaluate_suite(load_suite(Path(suite)), load_samples(Path(samples)),
                          registry=build_registry()).model_dump(mode="json")
actual.pop("created_at")
expected.pop("created_at")
assert actual == expected
assert main(["gate", "report.json"]) == (0 if expected["summary"]["pass_rate"] == 1 else 1)
"""
    # Copy only the worked example's Python files; generated data stays temporary.
    for source in (ROOT / "voice-agent-evals").glob("*.py"):
        (tmp_path / source.name).write_bytes(source.read_bytes())
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_v09_reliability_examples_run() -> None:
    for script, expected in (
        ("judge_reliability.py", "Judge unavailable for 1 score(s)"),
        ("async_live_target.py", "timed out: ['hangs']"),
    ):
        result = subprocess.run(
            [sys.executable, str(ROOT / "examples" / script)],
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        assert expected in result.stdout
