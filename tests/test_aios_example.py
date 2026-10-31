"""The checked-in AIOS export example stays reproducible and aligned."""

import json
import runpy
from pathlib import Path

from aios_checks import schema_errors, semantic_issues

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/aios"
OUTPUTS = ("report", "gate-decision", "evidence", "run-with-evaluations")


def test_example_regenerates_identically() -> None:
    before = {name: (EXAMPLE / f"{name}.json").read_text() for name in OUTPUTS}
    runpy.run_path(str(EXAMPLE / "generate.py"), run_name="__main__")
    assert {name: (EXAMPLE / f"{name}.json").read_text() for name in OUTPUTS} == before


def test_example_run_is_aligned_and_keeps_the_failing_verdicts() -> None:
    merged = json.loads((EXAMPLE / "run-with-evaluations.json").read_text())
    assert schema_errors(merged) == []
    assert semantic_issues(merged) == []
    gate = [item for item in merged["evidence"] if item["id"].endswith(":gate")]
    assert [item["status"] for item in gate] == ["failed"]
    assert {item["status"] for item in merged["evidence"]} == {"passed", "failed"}
