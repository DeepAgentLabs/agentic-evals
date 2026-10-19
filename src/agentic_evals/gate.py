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

    Judge and live-target checks read `summary.judge` and `summary.live`.
    `max_judge_unavailable_scores` defaults to 0: a judgment the judge could
    not deliver fails the gate even when its score was optional, and the
    reason names the affected cases. Set it to `None` to tolerate them.
    `max_judge_cost_usd` fails when any judge score lacks a cost, and
    `min_judge_agreement` fails when any case judged with `samples=N` has
    lower agreement than the floor, or no case was sampled at all.
    `max_timed_out_cases` and `max_target_error_cases` bound live-target
    failures separately from wrong answers; both are unchecked by default,
    though such cases already count as failed for `min_pass_rate`.
    """

    min_pass_rate: float = Field(default=1.0, ge=0, le=1)
    min_average_score: float | None = Field(default=None, ge=0, le=1)
    max_failed_cases: int | None = Field(default=None, ge=0)
    min_tag_pass_rate: dict[str, PassRate] = Field(default_factory=dict)
    min_metric_pass_rate: dict[str, PassRate] = Field(default_factory=dict)
    max_average_latency_ms: float | None = Field(default=None, gt=0)
    max_total_cost_usd: float | None = Field(default=None, ge=0)
    max_judge_unavailable_scores: int | None = Field(default=0, ge=0)
    max_judge_cost_usd: float | None = Field(default=None, ge=0)
    min_judge_agreement: float | None = Field(default=None, ge=0, le=1)
    max_timed_out_cases: int | None = Field(default=None, ge=0)
    max_target_error_cases: int | None = Field(default=None, ge=0)


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
    _check_judges(report, config, reasons, observed)
    _check_live(report, config, reasons, observed)
    return GateDecision(passed=not reasons, reasons=reasons, observed=observed)


def _cases(case_ids: list[str], limit: int = 5) -> str:
    shown = ", ".join(repr(case_id) for case_id in case_ids[:limit])
    return shown + (f" and {len(case_ids) - limit} more" if len(case_ids) > limit else "")


def _check_judges(
    report: EvaluationReport,
    config: GateConfig,
    reasons: list[str],
    observed: dict[str, float | int | None],
) -> None:
    judge = report.summary.judge
    if judge is not None:
        observed["judge_unavailable_scores"] = judge.unavailable_scores
        limit = config.max_judge_unavailable_scores
        if limit is not None and judge.unavailable_scores > limit:
            reasons.append(
                f"Judge unavailable for {judge.unavailable_scores} score(s), more than "
                f"{limit}, in cases {_cases(judge.unavailable_cases)}."
            )
    if config.max_judge_cost_usd is not None:
        total = judge.total_cost_usd if judge is not None else None
        observed["judge_total_cost_usd"] = total
        if judge is None or judge.judge_scores == 0:
            reasons.append("Judge cost is unavailable: the report has no judge scores.")
        elif total is None:
            reasons.append(
                f"Judge cost is incomplete: {judge.priced_scores} of {judge.judge_scores} "
                "judge scores recorded a cost."
            )
        elif total > config.max_judge_cost_usd:
            reasons.append(f"Judge cost ${total:.6f} exceeds ${config.max_judge_cost_usd:.6f}.")
    if config.min_judge_agreement is not None:
        floor = config.min_judge_agreement
        lowest = judge.min_agreement if judge is not None else None
        observed["min_judge_agreement"] = lowest
        if judge is None or lowest is None:
            reasons.append("Judge agreement is unavailable: no case was judged with samples > 1.")
        elif lowest < floor:
            flaky = [case_id for case_id, value in judge.case_agreement.items() if value < floor]
            reasons.append(
                f"Judge agreement {lowest:.0%} is below {floor:.0%} in cases {_cases(flaky)}."
            )


def _check_live(
    report: EvaluationReport,
    config: GateConfig,
    reasons: list[str],
    observed: dict[str, float | int | None],
) -> None:
    live = report.summary.live
    if live is None:
        if config.max_timed_out_cases is not None or config.max_target_error_cases is not None:
            reasons.append("Live-target outcomes are unavailable: the report is not a live run.")
        return
    observed["timed_out_cases"] = live.timed_out_cases
    observed["target_error_cases"] = live.error_cases
    for limit, count, ids, label in (
        (config.max_timed_out_cases, live.timed_out_cases, live.timed_out_case_ids, "timed out"),
        (config.max_target_error_cases, live.error_cases, live.error_case_ids, "errored"),
    ):
        if limit is not None and count > limit:
            reasons.append(
                f"Live target {label} on {count} case(s), more than {limit}: {_cases(ids)}."
            )
