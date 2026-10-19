"""Bounded retries shared by LLM judges and live targets.

A `RetryPolicy` says how many times a call may be attempted and how long to
wait between attempts. It never retries forever and never hides a failure:
`call_with_retry` returns the last error alongside the attempt count, so the
caller can record an explicit "unavailable" or "timed out" outcome instead of
guessing a result.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """At most `max_attempts` calls, with exponential backoff between them.

    The wait before retry `n` (1-based) is
    `backoff_seconds * backoff_multiplier ** (n - 1)`, capped at
    `max_backoff_seconds`. Only exceptions that are instances of `retry_on`
    are retried; any other exception ends the call at once and is reported as
    the outcome's error. The default is a single attempt: retries are opt-in.
    """

    max_attempts: int = 1
    backoff_seconds: float = 0.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 30.0
    retry_on: tuple[type[Exception], ...] = (Exception,)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff_seconds < 0 or self.max_backoff_seconds < 0:
            raise ValueError("backoff seconds must not be negative")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1")
        if not self.retry_on:
            raise ValueError("retry_on must name at least one exception type")

    def delay(self, retry: int) -> float:
        """Seconds to wait before retry number `retry` (1 for the second attempt)."""
        wait = self.backoff_seconds * self.backoff_multiplier ** (retry - 1)
        return float(min(wait, self.max_backoff_seconds))


@dataclass
class Attempted(Generic[T]):
    """The outcome of a retried call: a value, or the last error, never both."""

    value: T | None = None
    error: Exception | None = None
    attempts: int = 0
    elapsed_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    failures: list[Exception] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None


def describe_error(error: BaseException) -> str:
    """`Type: message`, the form reports record for a failed call."""
    message = str(error)
    return f"{type(error).__name__}: {message}" if message else type(error).__name__


def call_with_retry(
    call: Callable[[], T],
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], None] = time.sleep,
    propagate: tuple[type[Exception], ...] = (),
) -> Attempted[T]:
    """Call `call` until it returns or the policy's attempts run out.

    Exceptions of a `propagate` type are caller or contract errors, not
    failures of the call: they are raised at once instead of recorded.
    """
    outcome: Attempted[T] = Attempted()
    started = time.perf_counter()
    for attempt in range(1, policy.max_attempts + 1):
        outcome.attempts = attempt
        try:
            outcome.value = call()
            outcome.error = None
            break
        except Exception as exc:  # noqa: BLE001 - recorded on the outcome
            if isinstance(exc, propagate):
                raise
            outcome.error = exc
            outcome.errors.append(describe_error(exc))
            outcome.failures.append(exc)
            if not isinstance(exc, policy.retry_on) or attempt == policy.max_attempts:
                break
            sleep(policy.delay(attempt))
    outcome.elapsed_ms = (time.perf_counter() - started) * 1000
    return outcome


async def acall_with_retry(
    call: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    propagate: tuple[type[Exception], ...] = (),
) -> Attempted[T]:
    """Async `call_with_retry`: awaits each attempt and the backoff between them."""
    outcome: Attempted[T] = Attempted()
    started = time.perf_counter()
    for attempt in range(1, policy.max_attempts + 1):
        outcome.attempts = attempt
        try:
            outcome.value = await call()
            outcome.error = None
            break
        except Exception as exc:  # noqa: BLE001 - recorded on the outcome
            if isinstance(exc, propagate):
                raise
            outcome.error = exc
            outcome.errors.append(describe_error(exc))
            outcome.failures.append(exc)
            if not isinstance(exc, policy.retry_on) or attempt == policy.max_attempts:
                break
            await sleep(policy.delay(attempt))
    outcome.elapsed_ms = (time.perf_counter() - started) * 1000
    return outcome
