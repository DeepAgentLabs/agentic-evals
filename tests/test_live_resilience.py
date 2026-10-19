"""Live-target retries, timeouts and async targets (v0.9)."""

import asyncio
import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from agentic_evals import (
    GateConfig,
    HTTPTarget,
    PythonTarget,
    RetryPolicy,
    TestCase,
    TestSuite,
    arun_live_suite,
    evaluate_gate,
    run_live_suite,
)
from agentic_evals.formatting import render_report

SUITE = TestSuite(
    name="resilience",
    version="1",
    cases=[
        TestCase(id=f"case-{index}", name=f"Case {index}", input=index, expected_output="ok")
        for index in range(1, 4)
    ],
)


def _target(tmp_path: Path, body: str, name: str = "target") -> str:
    path = tmp_path / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return f"{path}:run_case"


FLAKY = """
import json, pathlib
STATE = pathlib.Path(__file__).with_suffix(".state")

def run_case(payload, *, case):
    counts = json.loads(STATE.read_text()) if STATE.exists() else {}
    counts[case.id] = counts.get(case.id, 0) + 1
    STATE.write_text(json.dumps(counts))
    if counts[case.id] < FAILURES.get(case.id, 0) + 1:
        raise ConnectionError(f"transient failure {counts[case.id]}")
    return {"output": "ok", "trace": {"trace_id": case.id}}
"""


def test_retries_recover_transient_python_target_failures(tmp_path: Path) -> None:
    target = _target(tmp_path, "FAILURES = {'case-2': 2}\n" + FLAKY)
    report = run_live_suite(
        SUITE, PythonTarget(callable_path=target), retry=RetryPolicy(max_attempts=3)
    )

    assert report.summary.passed_cases == 3
    assert [case.target_attempts for case in report.cases] == [1, 3, 1]
    assert all(case.target_status == "ok" for case in report.cases)
    assert report.summary.live is not None
    assert report.summary.live.retried_cases == 1
    assert report.summary.live.ok_cases == 3


def test_exhausted_retries_report_an_error_distinct_from_a_wrong_answer(tmp_path: Path) -> None:
    target = _target(tmp_path, "FAILURES = {'case-1': 9}\n" + FLAKY)
    report = run_live_suite(
        SUITE, PythonTarget(callable_path=target), retry=RetryPolicy(max_attempts=2)
    )

    failed = report.cases[0]
    assert not failed.passed
    assert failed.target_status == "error"
    assert failed.target_attempts == 2
    assert failed.target_error == "ConnectionError: transient failure 2"
    assert not failed.sample_available
    [score] = failed.scores
    assert score.name == "target_call"
    assert score.metadata == {
        "status": "error",
        "attempts": 2,
        "error": "ConnectionError: transient failure 2",
    }
    assert report.summary.live is not None
    assert report.summary.live.error_case_ids == ["case-1"]
    assert report.summary.live.timed_out_cases == 0


SLOW = """
import time

def run_case(payload, *, case):
    if case.id == "case-2":
        time.sleep(5)
    return {"output": "ok", "trace": {"trace_id": case.id}}
"""


def test_python_target_timeout_is_reported_as_timed_out(tmp_path: Path) -> None:
    target = PythonTarget(callable_path=_target(tmp_path, SLOW), timeout_seconds=0.2)
    started = time.perf_counter()
    report = run_live_suite(SUITE, target)
    assert time.perf_counter() - started < 3

    slow = report.cases[1]
    assert slow.target_status == "timed_out"
    assert "timed out after 0.2 s" in (slow.target_error or "")
    assert report.summary.live is not None
    assert report.summary.live.timed_out_case_ids == ["case-2"]
    assert report.summary.live.error_cases == 0

    decision = evaluate_gate(report, GateConfig(min_pass_rate=0, max_timed_out_cases=0))
    assert not decision.passed
    assert "timed out on 1 case(s)" in decision.reasons[0]
    assert decision.observed["timed_out_cases"] == 1


def test_python_targets_are_not_timed_out_by_default(tmp_path: Path) -> None:
    body = """
import time

def run_case(payload, *, case):
    time.sleep(0.05)
    return {"output": "ok", "trace": {"trace_id": case.id}}
"""
    target = PythonTarget(callable_path=_target(tmp_path, body))
    assert "timeout_seconds" not in target.model_fields_set
    assert run_live_suite(SUITE, target).summary.passed_cases == 3


ASYNC = """
import asyncio

async def run_case(payload, *, case):
    await asyncio.sleep(0.2)
    return {"output": "ok", "trace": {"trace_id": case.id}}
"""


def test_async_python_target_runs_concurrently(tmp_path: Path) -> None:
    target = PythonTarget(callable_path=_target(tmp_path, ASYNC))
    started = time.perf_counter()
    report = asyncio.run(arun_live_suite(SUITE, target, max_concurrency=3))
    elapsed = time.perf_counter() - started

    assert report.summary.passed_cases == 3
    assert [case.case_id for case in report.cases] == ["case-1", "case-2", "case-3"]
    assert elapsed < 0.5  # three 0.2 s calls in sequence would take 0.6 s


def test_async_python_target_is_cancelled_at_its_timeout(tmp_path: Path) -> None:
    target = PythonTarget(callable_path=_target(tmp_path, ASYNC), timeout_seconds=0.05)
    report = asyncio.run(arun_live_suite(SUITE, target, max_concurrency=3))
    assert {case.target_status for case in report.cases} == {"timed_out"}
    assert report.summary.live is not None
    assert report.summary.live.timed_out_cases == 3


def test_sync_api_runs_an_async_target(tmp_path: Path) -> None:
    target = PythonTarget(callable_path=_target(tmp_path, ASYNC))
    assert run_live_suite(SUITE, target).summary.passed_cases == 3


def test_sync_and_async_runs_produce_the_same_report(tmp_path: Path) -> None:
    target = PythonTarget(callable_path=_target(tmp_path, SLOW.replace("time.sleep(5)", "pass")))
    sync = run_live_suite(SUITE, target).model_dump(mode="json")
    concurrent = asyncio.run(arun_live_suite(SUITE, target, max_concurrency=3)).model_dump(
        mode="json"
    )
    sync.pop("created_at")
    concurrent.pop("created_at")
    assert sync == concurrent


def test_async_run_retries_and_validates_concurrency(tmp_path: Path) -> None:
    target = PythonTarget(callable_path=_target(tmp_path, "FAILURES = {'case-3': 1}\n" + FLAKY))
    report = asyncio.run(arun_live_suite(SUITE, target, retry=RetryPolicy(max_attempts=2)))
    assert [case.target_attempts for case in report.cases] == [1, 1, 2]
    with pytest.raises(ValueError, match="max_concurrency"):
        asyncio.run(arun_live_suite(SUITE, target, max_concurrency=0))


def test_invalid_payload_still_stops_the_run(tmp_path: Path) -> None:
    body = "def run_case(payload, *, case):\n    return ['not', 'a', 'sample']\n"
    with pytest.raises(ValueError, match="expected an object"):
        run_live_suite(SUITE, PythonTarget(callable_path=_target(tmp_path, body)))


class _SlowHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - http.server naming
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if body["case_id"] == "case-1":
            time.sleep(1.0)
        payload = json.dumps({"output": "ok", "trace": {"trace_id": body["case_id"]}}).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except OSError:
            return

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return


@pytest.fixture
def slow_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _SlowHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/run"
    finally:
        server.shutdown()
        server.server_close()


def test_http_timeout_is_reported_as_timed_out(slow_url: str) -> None:
    report = run_live_suite(
        SUITE,
        HTTPTarget(url=slow_url, timeout_seconds=0.2),
        retry=RetryPolicy(max_attempts=2),
    )
    slow = report.cases[0]
    assert slow.target_status == "timed_out"
    assert slow.target_attempts == 2
    assert "HTTP target timed out" in (slow.target_error or "")
    assert [case.target_status for case in report.cases[1:]] == ["ok", "ok"]

    junit = render_report(report, "junit")
    assert 'errors="1"' in junit and 'failures="0"' in junit
    assert '<error message="TIMEOUT' in junit
    markdown = render_report(report, "markdown")
    assert "| TIMEOUT |" in markdown
    assert "1 timed out" in markdown


def test_async_http_target_matches_sync(slow_url: str) -> None:
    target = HTTPTarget(url=slow_url, timeout_seconds=5)
    report = asyncio.run(arun_live_suite(SUITE, target, max_concurrency=3))
    assert report.summary.passed_cases == 3


def test_live_gate_checks_need_a_live_report(tmp_path: Path) -> None:
    from agentic_evals import EvalTrace, EvaluationSample, evaluate_suite

    report = evaluate_suite(
        SUITE,
        [EvaluationSample(case_id=case.id, output="ok", trace=EvalTrace()) for case in SUITE.cases],
    )
    assert report.summary.live is None
    decision = evaluate_gate(report, GateConfig(max_target_error_cases=0))
    assert not decision.passed
    assert "not a live run" in decision.reasons[0]
