"""The fast path in: `Eval(name, data=..., task=..., scores=[...])`.

Everything else in this package (`TestSuite`/`TestCase`/`evaluate_suite`,
packs, the release gate) stays available for teams that want declarative
suites, trace-aware scorers, or CI gating on cost/latency. This module is
the other on-ramp -- the one that gets a first eval running in under a
minute, the way `braintrust.Eval(...)` or a Promptfoo config does, with no
`TestCase`/`EvaluationSample` boilerplate required.

    from agentic_evals import Eval, exact_match

    Eval(
        "capitals",
        data=[{"input": "France", "expected": "Paris"}],
        task=lambda input: my_agent(input),
        scores=[exact_match],
    )

Running the module prints a pass/fail table and returns an `EvalResult`;
`agentic-evals run` (see `cli.py`) discovers and runs every `*_eval.py` /
`*.eval.py` file in a directory the same way, so this is also what CI calls.
"""

from __future__ import annotations

import inspect
import os
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from agentic_evals.models import Score

#: A scorer: called with whichever of `input`/`output`/`expected` it names as
#: parameters, returning a float/bool (0-1), a `Score`, or `{"score": ...}`.
ScoreFn: TypeAlias = Callable[..., Any]

#: Every `EvalResult` produced by `Eval()` in the current process, in call
#: order. `agentic_evals.cli` reads (and clears) this to aggregate exit
#: codes across the files it discovers -- not meant to be read directly.
_collected: list[EvalResult] = []


@dataclass
class Case:
    """One row of eval data: what goes in, and (optionally) what should come out."""

    input: Any
    expected: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def coerce(raw: dict[str, Any] | Case) -> Case:
        if isinstance(raw, Case):
            return raw
        if "input" not in raw:
            raise ValueError("each eval case needs an 'input' key")
        rest = {k: v for k, v in raw.items() if k not in ("input", "expected")}
        return Case(input=raw["input"], expected=raw.get("expected"), metadata=rest)


@dataclass
class CaseResult:
    case: Case
    output: Any
    scores: dict[str, float]
    error: str | None = None
    duration_ms: float = 0.0

    def passed(self, threshold: float) -> bool:
        if self.error is not None:
            return False
        if not self.scores:
            return True
        return min(self.scores.values()) >= threshold


@dataclass
class EvalResult:
    """What `Eval()` returns. `bool(result)` is True iff every case passed."""

    name: str
    threshold: float
    results: list[CaseResult]
    duration_ms: float

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 1.0
        passed = sum(1 for r in self.results if r.passed(self.threshold))
        return passed / len(self.results)

    @property
    def score_averages(self) -> dict[str, float]:
        totals: dict[str, list[float]] = {}
        for result in self.results:
            for score_name, value in result.scores.items():
                totals.setdefault(score_name, []).append(value)
        return {name: sum(values) / len(values) for name, values in totals.items()}

    def __bool__(self) -> bool:
        return all(r.passed(self.threshold) for r in self.results)

    def print_report(self, *, file: Any = None) -> None:
        _print_report(self, file=file or sys.stdout)


def _score_fn_name(fn: ScoreFn) -> str:
    name = getattr(fn, "__name__", None)
    return name if name and name != "<lambda>" else fn.__class__.__name__


def _call_score_fn(fn: ScoreFn, *, input: Any, output: Any, expected: Any) -> Any:
    """Call `fn` with whichever of input/output/expected it names as parameters.

    A scorer that declares `**kwargs` gets all three. One that names some
    subset of `input`/`output`/`expected` gets exactly those, by keyword.
    Anything else (a plain `lambda output: ...`, a positional-only builtin)
    falls back to the single positional argument every scorer needs: the
    output under test.
    """
    params: Mapping[str, inspect.Parameter]
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        params = {}
    accepts_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
    available = {"input": input, "output": output, "expected": expected}
    if accepts_kwargs:
        return fn(**available)
    kwargs = {k: v for k, v in available.items() if k in params}
    if kwargs:
        return fn(**kwargs)
    return fn(output)


def _normalize_score(raw: Any, *, default_name: str) -> dict[str, float]:
    if isinstance(raw, Score):
        return {raw.name or default_name: raw.value}
    if isinstance(raw, bool):
        return {default_name: 1.0 if raw else 0.0}
    if isinstance(raw, int | float):
        return {default_name: float(raw)}
    if isinstance(raw, dict):
        if "score" in raw:
            return {str(raw.get("name", default_name)): float(raw["score"])}
        return {str(k): float(v) for k, v in raw.items()}
    raise TypeError(
        f"scorer '{default_name}' returned {raw!r}; expected a float, bool, dict, or Score"
    )


def equals(output: Any, expected: Any) -> bool:
    """Exact match, after stripping surrounding whitespace from both sides."""
    return str(output).strip() == str(expected).strip()


def contains(output: Any, expected: Any) -> bool:
    """`expected` (or every item of it, if a list) appears in `output`."""
    haystack = str(output)
    needles = expected if isinstance(expected, list | tuple) else [expected]
    return all(str(needle) in haystack for needle in needles)


def icontains(output: Any, expected: Any) -> bool:
    """Case-insensitive `contains`."""
    haystack = str(output).casefold()
    needles = expected if isinstance(expected, list | tuple) else [expected]
    return all(str(needle).casefold() in haystack for needle in needles)


def levenshtein(output: Any, expected: Any) -> float:
    """Similarity in [0, 1] (1.0 = identical) from the Levenshtein edit distance."""
    from agentic_evals.scorers.text import _levenshtein_distance

    left, right = str(output).strip(), str(expected).strip()
    distance = _levenshtein_distance(left, right)
    longest = max(len(left), len(right), 1)
    return 1.0 - (distance / longest)


def matches(output: Any, expected: Any) -> bool:
    """`expected` is a regex pattern searched for (not anchored) in `output`."""
    import re

    return re.search(str(expected), str(output)) is not None


def numeric_close(output: Any, expected: Any) -> bool:
    """Both parse as floats and agree within a 1% relative / 1e-9 absolute tolerance."""
    import math

    return math.isclose(float(output), float(expected), rel_tol=1e-2, abs_tol=1e-9)


def Eval(  # noqa: N802 - PascalCase is the convention this API deliberately matches
    name: str,
    *,
    data: Iterable[dict[str, Any] | Case] | Callable[[], Iterable[dict[str, Any] | Case]],
    task: Callable[[Any], Any],
    scores: Sequence[ScoreFn] = (),
    threshold: float = 1.0,
    print_results: bool = True,
) -> EvalResult:
    """Run `task` over every row in `data`, score each output, report, and return.

    - `data` is any iterable of `{"input": ..., "expected": ...}` dicts (or
      `Case` instances) -- or a zero-argument callable returning one, for
      data you'd rather build lazily.
    - `task(input) -> output` is the thing under test: an agent call, a
      prompt template + model call, anything.
    - each entry in `scores` is called with whichever of `input`, `output`,
      `expected` it declares as parameters (by name), and may return a
      float/bool (0-1), a `Score`, or `{"score": ..., "name": ...}`.
    - a case counts as passed when every one of its scores is `>= threshold`
      (default 1.0, i.e. exact). `bool(result)` reflects the whole eval.
    """
    started = time.perf_counter()
    rows = data() if callable(data) else data
    results: list[CaseResult] = []
    for raw_row in rows:
        case = Case.coerce(raw_row)
        case_started = time.perf_counter()
        try:
            output = task(case.input)
        except Exception as exc:  # noqa: BLE001 - reported per-case, not raised
            results.append(
                CaseResult(
                    case=case,
                    output=None,
                    scores={},
                    error=f"{type(exc).__name__}: {exc}",
                    duration_ms=(time.perf_counter() - case_started) * 1000,
                )
            )
            continue
        case_scores: dict[str, float] = {}
        for score_fn in scores:
            fn_name = _score_fn_name(score_fn)
            raw = _call_score_fn(score_fn, input=case.input, output=output, expected=case.expected)
            case_scores.update(_normalize_score(raw, default_name=fn_name))
        results.append(
            CaseResult(
                case=case,
                output=output,
                scores=case_scores,
                duration_ms=(time.perf_counter() - case_started) * 1000,
            )
        )
    result = EvalResult(
        name=name,
        threshold=threshold,
        results=results,
        duration_ms=(time.perf_counter() - started) * 1000,
    )
    _collected.append(result)
    if print_results:
        result.print_report()
    return result


def _supports_color(file: Any) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    isatty = getattr(file, "isatty", None)
    return bool(isatty and isatty())


def _print_report(result: EvalResult, *, file: Any) -> None:
    color = _supports_color(file)

    def paint(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if color else text

    total = len(result.results)
    passed = sum(1 for r in result.results if r.passed(result.threshold))
    header = f"agentic-evals :: {result.name}"
    print(f"\n{header}\n{'-' * len(header)}", file=file)
    for row in result.results:
        ok = row.passed(result.threshold)
        mark = paint("32", "PASS") if ok else paint("31", "FAIL")
        label = str(row.case.metadata.get("id", row.case.input))[:60]
        scores = ", ".join(f"{k}={v:.2f}" for k, v in row.scores.items())
        detail = row.error if row.error else scores
        print(f"  [{mark}] {label}  {detail}", file=file)
    print("", file=file)
    for score_name, avg in result.score_averages.items():
        print(f"  {score_name:<28} avg {avg:.3f}", file=file)
    rate_color = "32" if passed == total else "31"
    print(
        f"\n  {paint(rate_color, f'{passed}/{total} passed')}"
        f"  ({result.pass_rate:.1%})  in {result.duration_ms:.0f}ms\n",
        file=file,
    )
