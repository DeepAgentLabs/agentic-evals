"""Live-target behavior: concurrency and Python/HTTP parity on one suite."""

import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from agentic_evals import HTTPTarget, PythonTarget, TestCase, TestSuite, run_live_suite
from agentic_evals.cli import main as cli_main

SUITE = TestSuite(
    name="parity",
    version="1",
    cases=[
        TestCase(
            id=f"case-{index}",
            name=f"Case {index}",
            input={"response": "ok" if index % 2 else "bad"},
            expected_output="ok",
            required_tools=["lookup"],
            max_latency_ms=100,
            max_cost_usd=0.01,
        )
        for index in range(1, 5)
    ],
)


def _result(payload: dict[str, Any], case_id: str) -> dict[str, Any]:
    return {
        "output": payload["response"],
        "trace": {
            "trace_id": f"trace-{case_id}",
            "total_latency_ms": 20.0,
            "estimated_cost_usd": 0.001,
            "cost_source": "measured",
            "spans": [{"tool_name": "lookup"}],
        },
    }


def run_case(payload: dict[str, Any], *, case: TestCase) -> dict[str, Any]:
    return _result(payload, case.id)


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server naming
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        payload = json.dumps(_result(body["input"], body["case_id"])).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


@pytest.fixture
def http_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/run"
    finally:
        server.shutdown()
        server.server_close()


def _comparable(report: Any) -> list[tuple[Any, ...]]:
    return [
        (
            case.case_id,
            case.passed,
            case.trace_id,
            case.cost_usd,
            case.cost_source,
            [(score.name, score.value, score.passed) for score in case.scores],
        )
        for case in report.cases
    ]


def test_python_and_http_targets_score_the_same_suite_identically(http_url: str) -> None:
    python_report = run_live_suite(SUITE, PythonTarget(callable_path=f"{Path(__file__)}:run_case"))
    http_report = run_live_suite(SUITE, HTTPTarget(url=http_url))

    assert _comparable(python_report) == _comparable(http_report)
    assert python_report.summary.model_dump() == http_report.summary.model_dump()
    assert python_report.summary.pass_rate == 0.5
    assert python_report.summary.cost_sources == {"measured": 4}


def test_concurrent_http_run_matches_sequential_run(http_url: str) -> None:
    sequential = run_live_suite(SUITE, HTTPTarget(url=http_url))
    concurrent = run_live_suite(SUITE, HTTPTarget(url=http_url), max_workers=4)

    assert _comparable(sequential) == _comparable(concurrent)


def test_cli_http_matches_python_api(http_url: str, tmp_path: Path) -> None:
    suite_path, report_path = tmp_path / "suite.json", tmp_path / "report.json"
    suite_path.write_text(SUITE.model_dump_json(), encoding="utf-8")
    assert (
        cli_main(
            [
                "live",
                str(suite_path),
                "--target",
                http_url,
                "--max-workers",
                "3",
                "--timeout-seconds",
                "5",
                "--out",
                str(report_path),
            ]
        )
        == 0
    )
    actual = json.loads(report_path.read_text())
    expected = run_live_suite(SUITE, HTTPTarget(url=http_url)).model_dump(mode="json")
    actual.pop("created_at")
    expected.pop("created_at")
    assert actual == expected
    assert cli_main(["gate", str(report_path)]) == 1


def test_concurrent_python_run_overlaps_calls_and_keeps_case_order(tmp_path: Path) -> None:
    target = tmp_path / "slow_target.py"
    target.write_text(
        "\n".join(
            [
                "import time",
                "def run_case(payload, *, case):",
                "    time.sleep(0.2)",
                "    return {'output': payload['response'], 'trace': {'trace_id': case.id}}",
            ]
        ),
        encoding="utf-8",
    )

    started = time.perf_counter()
    report = run_live_suite(SUITE, PythonTarget(callable_path=f"{target}:run_case"), max_workers=4)
    elapsed = time.perf_counter() - started

    assert [case.case_id for case in report.cases] == [case.id for case in SUITE.cases]
    assert [case.trace_id for case in report.cases] == [case.id for case in SUITE.cases]
    assert elapsed < 0.6  # four 0.2 s calls run sequentially would take 0.8 s


def test_max_workers_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_workers"):
        run_live_suite(
            SUITE, PythonTarget(callable_path=f"{Path(__file__)}:run_case"), max_workers=0
        )


def test_http_target_failure_names_the_case() -> None:
    with pytest.raises(ValueError, match="case-1"):
        run_live_suite(SUITE, HTTPTarget(url="http://127.0.0.1:9/unreachable", timeout_seconds=1))


def test_sequential_run_stops_calling_the_target_after_an_invalid_payload(
    tmp_path: Path,
) -> None:
    calls = tmp_path / "calls.log"
    target = tmp_path / "bad_target.py"
    target.write_text(
        "\n".join(
            [
                f"LOG = {str(calls)!r}",
                "def run_case(payload, *, case):",
                "    with open(LOG, 'a', encoding='utf-8') as fh:",
                "        fh.write(case.id + '\\n')",
                "    return {'output': 'missing trace'}",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        run_live_suite(SUITE, PythonTarget(callable_path=f"{target}:run_case"))

    assert calls.read_text(encoding="utf-8").splitlines() == ["case-1"]
