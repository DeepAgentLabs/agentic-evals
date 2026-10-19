"""RetryPolicy bounds and the sync/async retry loops."""

import asyncio

import pytest

from agentic_evals import RetryPolicy
from agentic_evals.reliability import acall_with_retry, call_with_retry, describe_error


class Flaky:
    def __init__(self, failures: int, error: Exception | None = None) -> None:
        self.failures = failures
        self.calls = 0
        self.error = error or ConnectionError("boom")

    def __call__(self) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return "ok"


def test_default_policy_makes_one_attempt() -> None:
    flaky = Flaky(failures=1)
    outcome = call_with_retry(flaky, RetryPolicy())
    assert not outcome.ok
    assert outcome.attempts == 1
    assert flaky.calls == 1
    assert outcome.errors == ["ConnectionError: boom"]


def test_retries_until_success_and_waits_with_backoff() -> None:
    waits: list[float] = []
    flaky = Flaky(failures=2)
    policy = RetryPolicy(max_attempts=4, backoff_seconds=0.5, backoff_multiplier=2)
    outcome = call_with_retry(flaky, policy, sleep=waits.append)
    assert outcome.ok and outcome.value == "ok"
    assert outcome.attempts == 3
    assert waits == [0.5, 1.0]
    assert len(outcome.errors) == 2


def test_attempts_are_bounded_and_last_error_is_kept() -> None:
    waits: list[float] = []
    outcome = call_with_retry(Flaky(failures=10), RetryPolicy(max_attempts=3), sleep=waits.append)
    assert not outcome.ok
    assert outcome.attempts == 3
    assert isinstance(outcome.error, ConnectionError)
    assert waits == [0.0, 0.0]


def test_backoff_is_capped() -> None:
    policy = RetryPolicy(max_attempts=10, backoff_seconds=1, max_backoff_seconds=3)
    assert [policy.delay(n) for n in range(1, 5)] == [1.0, 2.0, 3.0, 3.0]


def test_non_retryable_errors_stop_at_once() -> None:
    flaky = Flaky(failures=5, error=KeyError("missing"))
    outcome = call_with_retry(flaky, RetryPolicy(max_attempts=3, retry_on=(ConnectionError,)))
    assert outcome.attempts == 1
    assert isinstance(outcome.error, KeyError)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"backoff_seconds": -1},
        {"max_backoff_seconds": -1},
        {"backoff_multiplier": 0.5},
        {"retry_on": ()},
    ],
)
def test_invalid_policies_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        RetryPolicy(**kwargs)  # type: ignore[arg-type]


def test_async_retry_matches_sync_behavior() -> None:
    flaky = Flaky(failures=1)
    waits: list[float] = []

    async def call() -> str:
        return flaky()

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    policy = RetryPolicy(max_attempts=2, backoff_seconds=0.25)
    outcome = asyncio.run(acall_with_retry(call, policy, sleep=sleep))
    assert outcome.ok and outcome.value == "ok"
    assert outcome.attempts == 2
    assert waits == [0.25]


def test_describe_error_handles_empty_messages() -> None:
    assert describe_error(TimeoutError()) == "TimeoutError"
    assert describe_error(ValueError("bad")) == "ValueError: bad"
