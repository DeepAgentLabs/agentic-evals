"""Published JSON Schema contracts, available without network access."""

import json
from importlib.resources import files
from typing import Any


def report_schema() -> dict[str, Any]:
    """Return a fresh Draft 2020-12 schema for native evaluation reports."""
    return _load("evaluation-report-1.0.schema.json")


def gate_decision_schema() -> dict[str, Any]:
    """Return a fresh Draft 2020-12 schema for native gate decisions."""
    return _load("gate-decision-1.0.schema.json")


def _load(name: str) -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(
        files("agentic_evals").joinpath("schemas").joinpath(name).read_text(encoding="utf-8")
    )
    return schema
