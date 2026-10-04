from typing import Annotated

from pydantic import BaseModel, Field

from agentic_evals.models import EvaluationReport

PassRate = Annotated[float, Field(ge=0, le=1)]


class GateConfig(BaseModel):
    """Release thresholds. The default is strict: every case must pass.

    `min_average_score` and `max_failed_cases` are extra checks, skipped
    when left `None` -- so `min_pass_rate` alone decides how many failures
    are tolerated, and a graded score below 1.0 on a passing case does not
    fail the gate unless an average-score floor is set explicitly.

    `min_tag_pass_rate` and `min_metric_pass_rate` set a floor for one
    slice of the report, keyed by tag or by `Score.metric`. They apply on
    top of `min_pass_rate`, so a single tag or metric can be held to a
    stricter bar than the suite as a whole. A tag or metric named here but
    absent from the report fails the gate rather than passing unchecked.
    """

    min_pass_rate: float = Field(default=1.0, ge=0, le=1)
    min_average_score: float | None = Field(default=None, ge=0, le=1)
    max_failed_cases: int | None = Field(default=None, ge=0)
    min_tag_pass_rate: dict[str, PassRate] = Field(default_factory=dict)
    min_metric_pass_rate: dict[str, PassRate] = Field(default_factory=dict)
    max_average_latency_ms: float | None = Field(default=None, gt=0)
    max_total_cost_usd: float | None = Field(default=None, ge=0)


class GateDecision(BaseModel):
    passed: bool
    reasons: list[str]
    observed: dict[str, float | int | None]


def evaluate_gate(report: EvaluationReport, config: GateConfig) -> GateDecision:
    summary = report.summary
    reasons: list[str] = []
    if summary.pass_rate < config.min_pass_rate:
        reasons.append(f"Pass rate {summary.pass_rate:.1%} is below {config.min_pass_rate:.1%}.")
    if config.min_average_score is not None and summary.average_score < config.min_average_score:
        reasons.append(
            f"Average score {summary.average_score:.3f} is below {config.min_average_score:.3f}."
        )
    if config.max_failed_cases is not None and summary.failed_cases > config.max_failed_cases:
        reasons.append(f"Failed cases {summary.failed_cases} exceed {config.max_failed_cases}.")
    if (
        config.max_average_latency_ms is not None
        and summary.average_latency_ms > config.max_average_latency_ms
    ):
        reasons.append(
            f"Average latency {summary.average_latency_ms:.1f} ms exceeds "
            f"{config.max_average_latency_ms:.1f} ms."
        )
    if config.max_total_cost_usd is not None:
        if (
            summary.total_cost_usd is None
            or len(report.cases) != summary.total_cases
            or any(case.cost_usd is None for case in report.cases)
        ):
            reasons.append("Total cost is unavailable or incomplete.")
        elif summary.total_cost_usd > config.max_total_cost_usd:
            reasons.append(
                f"Total cost ${summary.total_cost_usd:.6f} exceeds "
                f"${config.max_total_cost_usd:.6f}."
            )
    observed: dict[str, float | int | None] = {
        "pass_rate": summary.pass_rate,
        "average_score": summary.average_score,
        "failed_cases": summary.failed_cases,
        "average_latency_ms": summary.average_latency_ms,
        "total_cost_usd": summary.total_cost_usd,
    }
    for tag, minimum in config.min_tag_pass_rate.items():
        tagged = summary.tags.get(tag)
        observed[f"tag_pass_rate:{tag}"] = tagged.pass_rate if tagged else None
        if tagged is None:
            reasons.append(f"Tag {tag!r} has no cases in the report.")
        elif tagged.pass_rate < minimum:
            reasons.append(f"Tag {tag!r} pass rate {tagged.pass_rate:.1%} is below {minimum:.1%}.")
    for metric, minimum in config.min_metric_pass_rate.items():
        measured = summary.metrics.get(metric)
        rate = measured.pass_rate if measured else None
        observed[f"metric_pass_rate:{metric}"] = rate
        if rate is None:
            reasons.append(f"Metric {metric!r} has no evaluated scores in the report.")
        elif rate < minimum:
            reasons.append(f"Metric {metric!r} pass rate {rate:.1%} is below {minimum:.1%}.")
    return GateDecision(passed=not reasons, reasons=reasons, observed=observed)
