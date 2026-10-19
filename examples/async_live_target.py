"""An `async def` live target with retries and per-case timeouts, offline.

`answer` is the agent under test. One case hangs, so its explicit
`timeout_seconds` cancels it and the report marks it `timed_out`; another
fails once and succeeds on retry. The run awaits up to three cases at once.

Run: python examples/async_live_target.py
"""

import asyncio
from pathlib import Path
from typing import Any

from agentic_evals import (
    GateConfig,
    PythonTarget,
    RetryPolicy,
    TestCase,
    TestSuite,
    arun_live_suite,
    evaluate_gate,
)

attempts: dict[str, int] = {}


async def answer(payload: Any, *, case: TestCase) -> dict[str, Any]:
    attempts[case.id] = attempts.get(case.id, 0) + 1
    if case.id == "hangs":
        await asyncio.sleep(60)
    if case.id == "flaky" and attempts[case.id] == 1:
        raise ConnectionError("upstream reset the connection")
    await asyncio.sleep(0.05)
    return {"output": str(payload).upper(), "trace": {"trace_id": f"trace-{case.id}"}}


async def main() -> None:
    suite = TestSuite(
        name="async-live-demo",
        version="1",
        cases=[
            TestCase(id=name, name=name, input=name, expected_output=name.upper())
            for name in ("steady", "flaky", "hangs")
        ],
    )
    report = await arun_live_suite(
        suite,
        PythonTarget(callable_path=f"{Path(__file__).resolve()}:answer", timeout_seconds=0.5),
        retry=RetryPolicy(max_attempts=2, backoff_seconds=0.1),
        max_concurrency=3,
    )
    for case in report.cases:
        print(
            f"{case.case_id:<7} passed={case.passed!s:<5} status={case.target_status} "
            f"attempts={case.target_attempts} {case.target_error or ''}"
        )
    live = report.summary.live
    assert live is not None
    print(f"\n{live.ok_cases} answered, {live.retried_cases} retried")
    print(f"timed out: {live.timed_out_case_ids}")

    gate = evaluate_gate(report, GateConfig(min_pass_rate=0.5, max_timed_out_cases=0))
    print(f"gate passed: {gate.passed}: {gate.reasons}")
    assert not gate.passed


if __name__ == "__main__":
    asyncio.run(main())
