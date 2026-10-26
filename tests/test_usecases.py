"""Keep the published use cases true: each page quotes these examples' output."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

from agentic_evals.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples/usecases"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, EXAMPLES / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pages_quote_the_example_files_verbatim() -> None:
    pages = {
        "block-an-unsafe-release.md": [
            f"release-gate/{name}"
            for name in ("support-suite.yaml", "baseline.jsonl", "candidate.jsonl", "gate.yaml")
        ],
        "right-reply-wrong-trajectory.md": ["refund_trajectory.py"],
        "gate-on-judge-reliability.md": ["judge_gate.py"],
    }
    for page, files in pages.items():
        text = (ROOT / "usecases" / page).read_text()
        for name in files:
            assert (EXAMPLES / name).read_text().rstrip("\n") in text, (page, name)


def test_release_gate_blocks_the_unsafe_candidate(tmp_path: Path) -> None:
    fixtures = EXAMPLES / "release-gate"
    suite = str(fixtures / "support-suite.yaml")
    loose = tmp_path / "loose-gate.yaml"
    loose.write_text("min_pass_rate: 0.8\n")
    for samples, strict_code, rate in (("baseline", 0, 1.0), ("candidate", 1, 5 / 6)):
        report = tmp_path / f"{samples}-report.json"
        assert (
            main(["evaluate", suite, str(fixtures / f"{samples}.jsonl"), "--out", str(report)]) == 0
        )
        assert json.loads(report.read_text())["summary"]["pass_rate"] == rate
        assert main(["gate", str(report), "--config", str(fixtures / "gate.yaml")]) == strict_code
        # Without the safety floor, the overall pass rate alone lets the candidate through.
        assert main(["gate", str(report), "--config", str(loose)]) == 0

    gate = tmp_path / "gate.json"
    candidate = str(tmp_path / "candidate-report.json")
    main(["gate", candidate, "--config", str(fixtures / "gate.yaml"), "--out", str(gate)])
    assert json.loads(gate.read_text())["reasons"] == [
        "Tag 'safety' pass rate 50.0% is below 100.0%."
    ]


def test_trajectory_catches_what_the_reply_hides() -> None:
    report = load("refund_trajectory").build_report()
    assert {case.case_id: case.passed for case in report.cases} == {
        "correct": True,
        "skipped-verification": False,
        "wrong-amount": False,
        "looping": False,
    }
    metrics = report.summary.metrics
    assert (metrics["contains"].passed, metrics["contains"].total) == (8, 8)
    for metric in ("tool_order", "tool_arg_values", "tool_call_precision"):
        assert (metrics[metric].passed, metrics[metric].total) == (3, 4)
    assert (metrics["no_redundant_tool_calls"].passed, metrics["required_tool"].passed) == (3, 11)


def test_judge_gate_fails_flaky_and_passes_steady() -> None:
    module = load("judge_gate")
    flaky = module.build_report(flaky=True)
    meta = {case.case_id: case.scores[0].metadata for case in flaky.cases}
    assert [meta[c]["judge_status"] for c in meta] == ["ok", "unavailable", "ok"]
    assert [meta[c]["judge_attempts"] for c in meta] == [4, 3, 3]
    assert round(flaky.cases[2].scores[0].value, 2) == 0.73 and flaky.cases[2].passed
    judge = flaky.summary.judge
    assert judge is not None and judge.total_cost_usd is None
    assert judge.unavailable_cases == ["shipping-cost"]
    assert len(module.evaluate_gate(flaky, module.GATE).reasons) == 4
    assert module.main([]) == 1

    steady = module.build_report(flaky=False)
    assert steady.summary.judge is not None
    assert round(steady.summary.judge.total_cost_usd or 0, 4) == 0.0036
    assert module.evaluate_gate(steady, module.GATE).passed
    assert module.main(["--steady"]) == 0
