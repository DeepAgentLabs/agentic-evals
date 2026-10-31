"""Offline AIOS v0.4-draft checks for exported Run artifacts (test helper only).

Validates against the vendored schemas in `fixtures/aios-v0.4/` and applies the
semantic rules an evidence export can break. `deep-agentic-core-mcp`'s
`spec.validate_artifact` is the full validator; tests also run it when it is
importable.
"""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "aios-v0.4"


def _schema(name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return document


def run_validator() -> Draft202012Validator:
    common = _schema("common.schema.json")
    registry = Registry().with_resource(common["$id"], Resource.from_contents(common))
    return Draft202012Validator(
        _schema("run.schema.json"), registry=registry, format_checker=FormatChecker()
    )


def sample_run() -> dict[str, Any]:
    run: dict[str, Any] = json.loads((FIXTURES / "run.json").read_text(encoding="utf-8"))
    return run


def schema_errors(artifact: dict[str, Any]) -> list[str]:
    return [error.message for error in run_validator().iter_errors(artifact)]


def semantic_issues(run: dict[str, Any]) -> list[tuple[str, str]]:
    """Rule-labelled issues for P02, P03, P05, P06, P07 and P08."""
    objects = [(run["id"], "run")]
    for key, kind in (
        ("requests", "request"),
        ("steps", "step"),
        ("agents", "agent"),
        ("incidents", "incident"),
    ):
        objects += [(item["id"], kind) for item in run.get(key, [])]
    for key in ("occurrences", "evidence"):
        objects += [(item["id"], item["type"]) for item in run.get(key, [])]
    issues: list[tuple[str, str]] = []
    ids = [object_id for object_id, _ in objects]
    if len(ids) != len(set(ids)):
        issues.append(("AIOS-0.4-P02", "duplicate object id"))
    relationships = run.get("relationships", [])
    for key, items in (
        ("id", relationships),
        ("event_id", run.get("events", [])),
    ):
        values = [item[key] for item in items]
        if len(values) != len(set(values)):
            issues.append(("AIOS-0.4-P03", f"duplicate {key}"))
    types = dict(objects)
    for rel in relationships:
        if rel["source"]["id"] == rel["target"]["id"]:
            issues.append(("AIOS-0.4-P11", rel["id"]))
        for end in (rel["source"], rel["target"]):
            if not end.get("external") and types.get(end["id"]) != end["type"]:
                issues.append(("AIOS-0.4-P05", f"{rel['id']} -> {end['id']}"))
    for step in run.get("steps", []):
        count = sum(
            rel["type"] == "contains"
            and rel["source"]["id"] == run["id"]
            and rel["target"]["id"] == step["id"]
            for rel in relationships
        )
        if count != 1:
            issues.append(("AIOS-0.4-P06", step["id"]))
    for occurrence in run.get("occurrences", []):
        count = sum(
            rel["type"] == "observed-in" and rel["source"]["id"] == occurrence["id"]
            for rel in relationships
        )
        if count != 1:
            issues.append(("AIOS-0.4-P07", occurrence["id"]))
    for evidence in run.get("evidence", []):
        if evidence["type"] == "evaluation" and not any(
            rel["type"] == "evaluates" and rel["source"]["id"] == evidence["id"]
            for rel in relationships
        ):
            issues.append(("AIOS-0.4-P08", evidence["id"]))
    for event in run.get("events", []):
        if types.get(event["object_id"]) != event["object_type"]:
            issues.append(("AIOS-0.4-P10", event["event_id"]))
    return issues
