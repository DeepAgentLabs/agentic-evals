"""Calling live targets: loading, timeouts and retries (internal).

`run_live_suite` and `arun_live_suite` in `agentic_evals.runner` build on
these helpers. A call never raises for a target failure: it returns a
`LiveCall` saying whether the target answered, timed out or errored, after
how many attempts, so the report can show the outcome per case.
"""

import asyncio
import inspect
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

from agentic_evals import _async
from agentic_evals.models import HTTPTarget, LiveTarget, PythonTarget, TargetStatus, TestCase
from agentic_evals.reliability import (
    Attempted,
    RetryPolicy,
    acall_with_retry,
    call_with_retry,
    describe_error,
)


class InvalidPayloadError(ValueError):
    """A target answered with something that is not a sample payload.

    This is a target bug that retrying will not fix, so it stops the run
    instead of being recorded as a per-case `error`.
    """


#: Exceptions a live call raises instead of recording on the case.
PROPAGATED = (InvalidPayloadError, _async.EventLoopMisuseError)


@dataclass
class LiveCall:
    """One case's target outcome. `payload` is set only when `status == "ok"`."""

    status: TargetStatus
    attempts: int
    payload: Any = None
    error: str | None = None

    @classmethod
    def from_outcome(cls, outcome: Attempted[Any]) -> "LiveCall":
        if outcome.ok:
            return cls(status="ok", attempts=outcome.attempts, payload=outcome.value)
        error = outcome.error
        # Timed out only if every attempt did: a mix of errors is an error.
        timed_out = bool(outcome.failures) and all(
            isinstance(failure, TimeoutError) for failure in outcome.failures
        )
        return cls(
            status="timed_out" if timed_out else "error",
            attempts=outcome.attempts,
            error=describe_error(error) if error is not None else "unknown error",
        )


def load_python_callable(callable_path: str) -> Any:
    """Load a trusted Python live target from module:function or path.py:function."""
    module_name, _, attr_path = callable_path.rpartition(":")
    if not module_name or not attr_path:
        raise ValueError("python target callable_path must be in module:function format")
    try:
        target: Any = import_module(module_name)
    except ModuleNotFoundError as exc:
        file_path = Path(module_name)
        if not file_path.exists():
            raise
        spec = spec_from_file_location(file_path.stem, file_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Unable to load Python target from {file_path}") from exc
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        target = module
    for part in attr_path.split("."):
        target = getattr(target, part)
    return target


def _is_timeout(error: BaseException) -> bool:
    return isinstance(error, TimeoutError) or (
        isinstance(error, urllib.error.URLError) and isinstance(error.reason, TimeoutError)
    )


def http_payload(target: HTTPTarget, case: TestCase) -> Any:
    request = urllib.request.Request(
        target.url,
        data=json.dumps({"input": case.input, "case_id": case.id}).encode("utf-8"),
        headers={"Content-Type": "application/json", **target.headers},
        method=target.method.upper(),
    )
    try:
        with urllib.request.urlopen(request, timeout=target.timeout_seconds) as response:
            body = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        if _is_timeout(exc):
            raise TimeoutError(
                f"HTTP target timed out after {target.timeout_seconds:g} s for case {case.id!r}"
            ) from exc
        raise ValueError(f"HTTP target request failed for case {case.id!r}: {exc}") from exc
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError as exc:
        raise InvalidPayloadError(
            f"HTTP target returned a body that is not JSON for case {case.id!r}: {exc}"
        ) from exc


def python_timeout(target: PythonTarget) -> float | None:
    """A Python target's timeout, or `None` when it was left at the default."""
    return target.timeout_seconds if "timeout_seconds" in target.model_fields_set else None


def _timeout_error(case: TestCase, timeout: float) -> TimeoutError:
    return TimeoutError(f"Python target timed out after {timeout:g} s for case {case.id!r}")


def _in_daemon_thread(function: Callable[[], Any], timeout: float | None) -> Any:
    """Run `function` in a daemon thread and wait at most `timeout` seconds.

    A daemon thread, unlike an executor worker, does not keep the process
    alive when a timed-out call never returns.
    """
    result: dict[str, Any] = {}

    def run() -> None:
        try:
            result["value"] = function()
        except BaseException as exc:  # noqa: BLE001 - re-raised in the caller
            result["error"] = exc

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise TimeoutError
    if "error" in result:
        raise result["error"]
    return result["value"]


async def _in_daemon_thread_async(function: Callable[[], Any]) -> Any:
    loop = asyncio.get_running_loop()
    future: asyncio.Future[Any] = loop.create_future()

    def settle(value: Any = None, error: BaseException | None = None) -> None:
        if future.done():
            return
        if error is not None:
            future.set_exception(error)
        else:
            future.set_result(value)

    def run() -> None:
        try:
            value = function()
        except BaseException as exc:  # noqa: BLE001 - delivered to the awaiting task
            loop.call_soon_threadsafe(settle, None, exc)
        else:
            loop.call_soon_threadsafe(settle, value)

    threading.Thread(target=run, daemon=True).start()
    return await future


def sync_caller(target: LiveTarget) -> Callable[[TestCase], Any]:
    """A blocking `case -> payload` function for `target` that enforces its timeout."""
    if isinstance(target, PythonTarget):
        function = load_python_callable(target.callable_path)
        timeout = python_timeout(target)

        def call_python(case: TestCase) -> Any:
            def invoke() -> Any:
                result = function(case.input, case=case)
                if inspect.isawaitable(result):
                    # An async target in a sync run gets its own loop in this
                    # worker thread, and is cancelled there at the timeout.
                    return asyncio.run(_wait_for(result, timeout))
                return result

            if timeout is None:
                return _async.resolve(function(case.input, case=case))
            try:
                return _in_daemon_thread(invoke, timeout)
            except TimeoutError as exc:
                if exc.args:
                    raise
                raise _timeout_error(case, timeout) from None

        return call_python
    if isinstance(target, HTTPTarget):
        http_target = target
        return lambda case: http_payload(http_target, case)
    raise ValueError(f"Unsupported live target kind: {target.kind}")


async def _wait_for(awaitable: Any, timeout: float | None) -> Any:
    if timeout is None:
        return await awaitable
    try:
        return await asyncio.wait_for(awaitable, timeout)
    except asyncio.TimeoutError:  # a distinct class before Python 3.11
        raise TimeoutError from None


def async_caller(target: LiveTarget) -> Callable[[TestCase], Any]:
    """An awaitable `case -> payload` function; `async def` targets are cancelled at timeout."""
    if isinstance(target, PythonTarget):
        function = load_python_callable(target.callable_path)
        timeout = python_timeout(target)

        async def call_python(case: TestCase) -> Any:
            try:
                if inspect.iscoroutinefunction(function):
                    return await _wait_for(function(case.input, case=case), timeout)
                result = await _wait_for(
                    _in_daemon_thread_async(lambda: function(case.input, case=case)), timeout
                )
                if inspect.isawaitable(result):
                    result = await _wait_for(result, timeout)
                return result
            except TimeoutError as exc:
                if exc.args or timeout is None:
                    raise
                raise _timeout_error(case, timeout) from None

        return call_python
    if isinstance(target, HTTPTarget):
        http_target = target

        async def call_http(case: TestCase) -> Any:
            return await _in_daemon_thread_async(lambda: http_payload(http_target, case))

        return call_http
    raise ValueError(f"Unsupported live target kind: {target.kind}")


def call_target(call: Callable[[TestCase], Any], case: TestCase, retry: RetryPolicy) -> LiveCall:
    return LiveCall.from_outcome(call_with_retry(lambda: call(case), retry, propagate=PROPAGATED))


async def acall_target(
    call: Callable[[TestCase], Any], case: TestCase, retry: RetryPolicy
) -> LiveCall:
    async def attempt() -> Any:
        return await call(case)

    return LiveCall.from_outcome(await acall_with_retry(attempt, retry, propagate=PROPAGATED))
