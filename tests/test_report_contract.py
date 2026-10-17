"""Wire compatibility, schema drift and invalid-artifact regression coverage."""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from agentic_evals import (
    EvaluationReport,
    GateConfig,
    GateDecision,
    evaluate_gate,
    gate_decision_schema,
    report_schema,
)

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "tests/fixtures/v0.7.1"
CONTRACTS = [
    ("evaluation-report", EvaluationReport, report_schema),
    ("gate-decision", GateDecision, gate_decision_schema),
]


@pytest.mark.parametrize("name,model,accessor", CONTRACTS)
def test_packaged_schema_matches_model(name, model, accessor) -> None:
    schema = accessor()
    Draft202012Validator.check_schema(schema)
    assert schema.pop("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert schema.pop("$id").endswith(f"/{name}-1.0.schema.json")
    assert schema == model.model_json_schema(mode="validation")


@pytest.mark.parametrize("name,model,accessor", CONTRACTS)
def test_071_artifacts_and_examples_validate(name, model, accessor) -> None:
    validator = Draft202012Validator(accessor(), format_checker=FormatChecker())
    for directory in (LEGACY, ROOT / "examples/report-contract"):
        artifact = json.loads((directory / f"{name}.json").read_text())
        validator.validate(artifact)
        validator.validate(model.model_validate(artifact).model_dump(mode="json"))
        # Readers must tolerate future additive fields at every object level.
        artifact["future_optional_field"] = {"anything": True}
        validator.validate(artifact)


def assert_additive(old: Any, new: Any) -> None:
    """Freeze existing wire shapes; permit new optional properties/definitions."""
    if isinstance(old, dict):
        assert isinstance(new, dict)
        for key, value in old.items():
            if key in {"title", "description"}:
                continue
            assert key in new, f"Removed schema keyword: {key}"
            if key in {"properties", "$defs"}:
                for name, definition in value.items():
                    assert name in new[key], f"Removed field/definition: {name}"
                    assert_additive(definition, new[key][name])
            elif key == "required":
                assert set(value) == set(new[key]), "Required fields changed"
            else:
                assert_additive(value, new[key])
        # A previously optional object must not acquire required fields.
        if "required" not in old:
            assert not new.get("required"), "Added required fields"
        # New validation restrictions on existing nodes are breaking too.
        assert set(new) - set(old) <= {"title", "description", "$schema", "$id"}
    else:
        assert old == new


@pytest.mark.parametrize("name,model,accessor", CONTRACTS)
def test_contract_is_additive_to_071(name, model, accessor) -> None:
    baseline = json.loads((LEGACY / f"{name}.schema.json").read_text())
    assert_additive(baseline, accessor())


@pytest.mark.parametrize("change", ["remove", "type", "required", "constraint"])
def test_compatibility_guard_detects_breaking_changes(change: str) -> None:
    old = {"type": "object", "properties": {"passed": {"type": "boolean"}}}
    new = deepcopy(old)
    if change == "remove":
        del new["properties"]["passed"]
    elif change == "type":
        new["properties"]["passed"]["type"] = "string"
    elif change == "required":
        new["required"] = ["passed"]
    else:
        new["additionalProperties"] = False
    with pytest.raises(AssertionError):
        assert_additive(old, new)


def test_compatibility_guard_allows_optional_fields() -> None:
    old = {"type": "object", "properties": {"passed": {"type": "boolean"}}}
    new = deepcopy(old)
    new["properties"]["optional"] = {"type": "string"}
    assert_additive(old, new)


@pytest.mark.parametrize("name,model,accessor", CONTRACTS)
def test_accessors_return_independent_copies(name, model, accessor) -> None:
    first = accessor()
    first["properties"].clear()
    assert accessor()["properties"]


@pytest.mark.parametrize(
    "path,value",
    [
        (("summary", "pass_rate"), 1.1),
        (("cases", 0, "scores", 0, "value"), -0.1),
        (("cases", 0, "cost_source"), "invented"),
        (("created_at",), "not-a-date"),
        (("summary", "total_cases"), "three"),
    ],
)
def test_report_rejects_invalid_values(path, value) -> None:
    artifact = json.loads((LEGACY / "evaluation-report.json").read_text())
    node = artifact
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ValidationError):
        Draft202012Validator(report_schema(), format_checker=FormatChecker()).validate(artifact)


def test_gate_rejects_invalid_values() -> None:
    validator = Draft202012Validator(gate_decision_schema())
    with pytest.raises(ValidationError):
        validator.validate({"passed": "yes", "reasons": [], "observed": {}})
    with pytest.raises(ValidationError):
        validator.validate({"passed": False, "reasons": []})


def test_live_models_produce_valid_contracts() -> None:
    report = EvaluationReport.model_validate_json((LEGACY / "evaluation-report.json").read_text())
    gate = evaluate_gate(report, GateConfig(min_metric_pass_rate={"missing": 1.0}))
    assert gate.passed is False
    assert gate.observed["metric_pass_rate:missing"] is None
    Draft202012Validator(gate_decision_schema()).validate(gate.model_dump(mode="json"))
