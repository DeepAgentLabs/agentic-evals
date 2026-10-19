"""Bridges between synchronous and asynchronous callables (internal)."""

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


async def _await(awaitable: Awaitable[T]) -> T:
    return await awaitable


def resolve(value: Any) -> Any:
    """Return `value`, running it to completion first if it is awaitable.

    Lets the synchronous APIs accept `async def` judges and targets. Inside a
    running event loop that is impossible without blocking it, so the caller
    is pointed at the async API instead.
    """
    if not inspect.isawaitable(value):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_await(value))
    if inspect.iscoroutine(value):
        value.close()
    raise RuntimeError(
        "an async evaluator or target was called from a running event loop; "
        "use aevaluate_suite() or arun_live_suite() instead"
    )


async def call(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Await an `async def` function, or run a synchronous one in a worker thread."""
    if inspect.iscoroutinefunction(function):
        return await function(*args, **kwargs)
    result = await asyncio.to_thread(function, *args, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result
