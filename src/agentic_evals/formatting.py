"""CI presentations of native reports and gate decisions."""

import html
import re
from xml.etree import ElementTree as ET

from agentic_evals.gate import GateDecision
from agentic_evals.models import EvaluationReport


def _xml_text(value: str) -> str:
    # XML 1.0 forbids control characters even when escaped.
    return re.sub(r"[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]", "\ufffd", value)


def _markdown(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(r"([\\`*_{}\[\]()#+.!|~-])", r"\\\1", escaped)
    return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def render_report(report: EvaluationReport, output_format: str) -> str:
    """Render JSON, Markdown or one JUnit testcase per evaluation case."""
    if output_format == "json":
        return report.model_dump_json(indent=2) + "\n"
    if output_format == "markdown":
        summary = report.summary
        lines = [
            f"## Evaluation: {_markdown(report.suite_name)}",
            "",
            f"{summary.passed_cases}/{summary.total_cases} cases passed "
            f"({summary.pass_rate:.1%}); average score {summary.average_score:.3f}.",
            "",
            "| Case | Result | Details |",
            "| --- | --- | --- |",
        ]
        for case in report.cases:
            details = "; ".join(
                f"{s.name}: {'SKIP: ' if s.skipped else ''}{s.explanation}"
                for s in case.scores
                if s.skipped or not s.passed
            )
            lines.append(
                f"| {_markdown(case.case_id)} | {'PASS' if case.passed else 'FAIL'} "
                f"| {_markdown(details)} |"
            )
        return "\n".join(lines) + "\n"
    if output_format != "junit":
        raise ValueError(f"unknown output format: {output_format}")
    root = ET.Element(
        "testsuite",
        name=_xml_text(report.suite_name),
        tests=str(len(report.cases)),
        failures=str(sum(not case.passed for case in report.cases)),
        errors="0",
        skipped="0",
        time=f"{sum(max(0, case.latency_ms) for case in report.cases) / 1000:.6f}",
    )
    for case in report.cases:
        node = ET.SubElement(
            root,
            "testcase",
            name=_xml_text(case.case_id),
            classname=_xml_text(report.suite_name),
            time=f"{max(0, case.latency_ms) / 1000:.6f}",
        )
        if not case.passed:
            details = (
                "; ".join(
                    f"{s.name}: {s.explanation}"
                    for s in case.scores
                    if not s.passed and s.required and not s.skipped
                )
                or "Case failed."
            )
            ET.SubElement(node, "failure", message=_xml_text(details)).text = _xml_text(details)
        ET.SubElement(node, "system-out").text = _xml_text(
            "\n".join(
                f"{s.name}: {'SKIP' if s.skipped else 'PASS' if s.passed else 'FAIL'}: "
                f"{s.explanation}"
                for s in case.scores
            )
        )
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def render_gate(decision: GateDecision, output_format: str) -> str:
    """Render a gate decision; JUnit contains one release-gate testcase."""
    if output_format == "json":
        return decision.model_dump_json(indent=2) + "\n"
    if output_format == "markdown":
        lines = [f"## Release gate: {'PASS' if decision.passed else 'FAIL'}", ""]
        lines.extend(f"- {_markdown(reason)}" for reason in decision.reasons)
        return "\n".join(lines) + "\n"
    if output_format != "junit":
        raise ValueError(f"unknown output format: {output_format}")
    root = ET.Element(
        "testsuite",
        name="release-gate",
        tests="1",
        failures=str(int(not decision.passed)),
        errors="0",
        skipped="0",
    )
    node = ET.SubElement(root, "testcase", name="release-gate", classname="agentic-evals")
    if not decision.passed:
        details = _xml_text("; ".join(decision.reasons))
        ET.SubElement(node, "failure", message=details).text = details
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"
