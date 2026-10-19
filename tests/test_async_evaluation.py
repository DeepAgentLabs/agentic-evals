"""aevaluate_suite and async evaluators (v0.9)."""

import asyncio
import json
import time
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from agentic_evals import (
    FACTUALITY,
    CallableEvaluator,
    EvalTrace,
    EvaluationContext,
    EvaluationSample,
    EvaluatorConfig,
    EvaluatorRegistry,
    LLMJudgeEvaluator,
    LLMRubricEvaluator,
    RetryPolicy,
    Score,
    TestCase,
    TestSuite,
    aevaluate_suite,
    cli,
    evaluate_suite,
    report_schema,
)

SUITE = TestSuite(
    name="async",
    version="1",
    cases=[
        TestCase(
            id=f"case-{index}",
            name=f"Case {index}",
            input=index,
            expected_contains=["ok"],
            evaluators=[EvaluatorConfig(name="judge", threshold=0.5)],
        )
        for index in range(1, 5)
    ],
)
SAMPLES = [
    EvaluationSample(case_id=case.id, output="ok", trace=EvalTrace(trace_id=case.id))
    for case in SUITE.cases
]


async def slow_judge(context: EvaluationContext) -> Score:
    await asyncio.sleep(0.2)
    return Score(name="judge", value=1.0, passed=True, explanation="looks fine")


def _registry(evaluator: object) -> EvaluatorRegistry:
    registry = EvaluatorRegistry()
    registry.register(evaluator)  # type: ignore[arg-type]
    return registry


def test_async_judges_run_concurrently_and_keep_case_order() -> None:
    registry = _registry(LLMJudgeEvaluator("judge", slow_judge))
    started = time.perf_counter()
    report = asyncio.run(aevaluate_suite(SUITE, SAMPLES, registry=registry, max_concurrency=4))
    elapsed = time.perf_counter() - started

    assert [case.case_id for case in report.cases] == [case.id for case in SUITE.cases]
    assert report.summary.passed_cases == 4
    assert elapsed < 0.6  # four 0.2 s judges in sequence would take 0.8 s


def test_async_and_sync_reports_match() -> None:
    registry = _registry(CallableEvaluator("judge", slow_judge))
    sync = evaluate_suite(SUITE, SAMPLES, registry=registry).model_dump(mode="json")
    concurrent = asyncio.run(aevaluate_suite(SUITE, SAMPLES, registry=registry)).model_dump(
        mode="json"
    )
    sync.pop("created_at")
    concurrent.pop("created_at")
    assert sync == concurrent


def test_sync_evaluators_run_in_threads_under_aevaluate_suite() -> None:
    def blocking(context: EvaluationContext) -> Score:
        time.sleep(0.2)
        return Score(name="judge", value=1.0, passed=True, explanation="ok")

    registry = _registry(CallableEvaluator("judge", blocking))
    started = time.perf_counter()
    report = asyncio.run(aevaluate_suite(SUITE, SAMPLES, registry=registry, max_concurrency=4))
    assert time.perf_counter() - started < 0.6
    assert report.summary.passed_cases == 4


class EvaluateOnly:
    """A third-party evaluator with no aevaluate method."""

    name = "judge"

    def evaluate(self, context: EvaluationContext) -> list[Score]:
        return [Score(name="judge", value=1.0, passed=True, explanation="ok")]


def test_evaluators_without_aevaluate_are_supported() -> None:
    report = asyncio.run(aevaluate_suite(SUITE, SAMPLES, registry=_registry(EvaluateOnly())))
    assert report.summary.passed_cases == 4


def test_async_rubric_retries_and_samples_concurrently() -> None:
    calls = 0

    async def complete(prompt: str) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("first call fails")
        return "A"

    suite = TestSuite(
        name="rubric",
        version="1",
        cases=[
            TestCase(
                id="c",
                name="c",
                evaluators=[EvaluatorConfig(name="factuality", config={"reference": "Paris"})],
            )
        ],
    )
    evaluator = LLMRubricEvaluator(
        "factuality", FACTUALITY, complete, retry=RetryPolicy(max_attempts=2), samples=3
    )
    report = asyncio.run(
        aevaluate_suite(
            suite,
            [EvaluationSample(case_id="c", output="Paris", trace=EvalTrace())],
            registry=_registry(evaluator),
        )
    )
    [score] = report.cases[0].scores
    assert score.passed
    assert score.metadata["judge_attempts"] == 4
    assert score.metadata["judge_agreement"] == 1.0


def test_sync_api_rejects_async_judges_inside_a_running_loop() -> None:
    registry = _registry(CallableEvaluator("judge", slow_judge))

    async def misuse() -> None:
        evaluate_suite(SUITE, SAMPLES, registry=registry)

    with pytest.raises(RuntimeError, match="aevaluate_suite"):
        asyncio.run(misuse())


def test_max_concurrency_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_concurrency"):
        asyncio.run(aevaluate_suite(SUITE, SAMPLES, max_concurrency=0))


def test_cli_live_retries_and_writes_a_valid_report(tmp_path: Path) -> None:
    target = tmp_path / "flaky_target.py"
    target.write_text(
        "\n".join(
            [
                "import pathlib",
                "STATE = pathlib.Path(__file__).with_suffix('.calls')",
                "def run_case(payload, *, case):",
                "    calls = int(STATE.read_text()) + 1 if STATE.exists() else 1",
                "    STATE.write_text(str(calls))",
                "    if calls == 1:",
                "        raise ConnectionError('warming up')",
                "    return {'output': 'ok', 'trace': {'trace_id': case.id}}",
            ]
        ),
        encoding="utf-8",
    )
    suite = tmp_path / "suite.json"
    suite.write_text(
        TestSuite(
            name="cli", version="1", cases=[TestCase(id="a", name="a", expected_output="ok")]
        ).model_dump_json(),
        encoding="utf-8",
    )
    out = tmp_path / "report.json"
    args = ["live", str(suite), "--target", f"{target}:run_case", "--out", str(out)]
    assert cli.main([*args, "--retries", "1", "--retry-backoff", "0"]) == 0
    report = json.loads(out.read_text())
    Draft202012Validator(report_schema(), format_checker=FormatChecker()).validate(report)
    assert report["cases"][0]["target_attempts"] == 2
    assert report["summary"]["live"]["retried_cases"] == 1
    assert cli.main(["gate", str(out)]) == 0
    assert cli.main([*args, "--retries", "-1"]) == 2


def test_cli_live_python_timeout(tmp_path: Path) -> None:
    target = tmp_path / "slow_target.py"
    target.write_text(
        "import time\n"
        "def run_case(payload, *, case):\n"
        "    time.sleep(5)\n"
        "    return {'output': 'ok', 'trace': {}}\n",
        encoding="utf-8",
    )
    suite = tmp_path / "suite.json"
    suite.write_text(
        TestSuite(
            name="cli", version="1", cases=[TestCase(id="a", name="a", expected_output="ok")]
        ).model_dump_json(),
        encoding="utf-8",
    )
    out = tmp_path / "report.json"
    code = cli.main(
        [
            "live",
            str(suite),
            "--target",
            f"{target}:run_case",
            "--timeout-seconds",
            "0.1",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    report = json.loads(out.read_text())
    assert report["cases"][0]["target_status"] == "timed_out"
    gate = tmp_path / "gate.yaml"
    gate.write_text("min_pass_rate: 0\nmax_timed_out_cases: 0\n", encoding="utf-8")
    assert cli.main(["gate", str(out), "--config", str(gate)]) == 1
