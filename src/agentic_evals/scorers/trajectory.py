"""Scorers that grade the agent's trajectory (`EvalTrace`/`EvalSpan`) directly.

A plain text-scoring library has no equivalent for these -- they need the
trace, not just the output string.
"""

import json

from agentic_evals.evaluators import EvaluationContext
from agentic_evals.models import Score


def tool_call_precision(context: EvaluationContext) -> Score:
    """Fraction of called tools that were in the allowed set.

    Configure via `EvaluatorConfig.config = {"allowed_tools": [...]}`; falls
    back to `case.required_tools` if not given.
    """
    called = [span.tool_name for span in context.sample.trace.spans if span.tool_name]
    allowed = context.config.config.get("allowed_tools") or context.case.required_tools
    if not called:
        raise ValueError("tool_call_precision requires at least one tool call in the trace")
    if not allowed:
        raise ValueError(
            "tool_call_precision requires 'allowed_tools' in EvaluatorConfig.config "
            "or a non-empty case.required_tools"
        )
    correct = sum(1 for tool in called if tool in allowed)
    precision = correct / len(called)
    passed = precision >= context.config.threshold
    return Score(
        name="tool_call_precision",
        value=precision,
        passed=passed,
        explanation=(
            f"{correct}/{len(called)} tool calls were in the allowed set {sorted(set(allowed))}."
        ),
    )


def tool_call_recall(context: EvaluationContext) -> Score:
    """Fraction of `case.required_tools` that were actually called."""
    called = {span.tool_name for span in context.sample.trace.spans if span.tool_name}
    required = context.case.required_tools
    if not required:
        raise ValueError("tool_call_recall requires case.required_tools to be non-empty")
    found = [tool for tool in required if tool in called]
    recall = len(found) / len(required)
    passed = recall >= context.config.threshold
    return Score(
        name="tool_call_recall",
        value=recall,
        passed=passed,
        explanation=f"{len(found)}/{len(required)} required tools were called.",
    )


def no_redundant_tool_calls(context: EvaluationContext) -> Score:
    """Fraction of tool calls that were NOT exact duplicates of an earlier call."""
    spans = [span for span in context.sample.trace.spans if span.tool_name]
    if not spans:
        raise ValueError("no_redundant_tool_calls requires at least one tool call in the trace")
    seen: set[tuple[str, str]] = set()
    redundant = 0
    for span in spans:
        key = (span.tool_name or "", json.dumps(span.attributes, sort_keys=True, default=str))
        if key in seen:
            redundant += 1
        seen.add(key)
    ratio_unique = 1.0 - (redundant / len(spans))
    passed = ratio_unique >= context.config.threshold
    return Score(
        name="no_redundant_tool_calls",
        value=ratio_unique,
        passed=passed,
        explanation=f"{redundant}/{len(spans)} tool calls exactly duplicated an earlier call.",
    )


def trajectory_efficiency(context: EvaluationContext) -> Score:
    """Score latency/cost against a caller-supplied baseline.

    Configure via `EvaluatorConfig.config = {"baseline_latency_ms": ...,
    "baseline_cost_usd": ...}`. Either baseline may be omitted; cost is
    skipped (not failed) when the trace's cost is unavailable.
    """
    config = context.config.config
    baseline_latency = config.get("baseline_latency_ms")
    baseline_cost = config.get("baseline_cost_usd")
    if baseline_latency is None and baseline_cost is None:
        raise ValueError(
            "trajectory_efficiency requires at least one of 'baseline_latency_ms' "
            "or 'baseline_cost_usd' in EvaluatorConfig.config"
        )
    trace = context.sample.trace
    ratios: list[float] = []
    details: list[str] = []
    if baseline_latency is not None and baseline_latency > 0:
        ratio = min(1.0, baseline_latency / max(trace.total_latency_ms, 1e-9))
        ratios.append(ratio)
        details.append(
            f"latency {trace.total_latency_ms:.1f} ms vs baseline {baseline_latency:.1f} ms"
        )
    if baseline_cost is not None and baseline_cost > 0 and trace.estimated_cost_usd is not None:
        ratio = min(1.0, baseline_cost / max(trace.estimated_cost_usd, 1e-9))
        ratios.append(ratio)
        details.append(f"cost ${trace.estimated_cost_usd:.6f} vs baseline ${baseline_cost:.6f}")
    if not ratios:
        raise ValueError(
            "trajectory_efficiency could not compute a score: cost is unavailable "
            "and no latency baseline matched"
        )
    value = sum(ratios) / len(ratios)
    passed = value >= context.config.threshold
    return Score(
        name="trajectory_efficiency",
        value=value,
        passed=passed,
        explanation="; ".join(details) + f" -> efficiency score {value:.3f}.",
    )
