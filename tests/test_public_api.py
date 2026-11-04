"""Candidate API compatibility contract for the coordinated major release."""

import inspect
import json
import re
from importlib.metadata import version
from pathlib import Path
from typing import get_origin

import agentic_evals as api

BASELINE = json.loads((Path(__file__).parent / "fixtures/v0.12/public-api.json").read_text())


def test_public_exports_are_unique_and_resolve() -> None:
    assert len(api.__all__) == len(set(api.__all__))
    assert set(BASELINE) <= set(api.__all__)
    for name in api.__all__:
        assert getattr(api, name) is not None


def test_public_api_retains_imports_and_call_shapes() -> None:
    for name, entry in BASELINE.items():
        obj = getattr(api, name)
        kind = (
            "alias"
            if get_origin(obj) is not None
            else "class"
            if inspect.isclass(obj)
            else "function"
            if inspect.isfunction(obj)
            else "value"
        )
        assert kind == entry["kind"], name
        assert getattr(obj, "__module__", None) == entry["module"], name
        if "parameters" in entry:
            assert_call_compatible(entry["parameters"], obj)
        for method, parameters in entry.get("methods", {}).items():
            assert_call_compatible(parameters, getattr(obj, method))


def assert_call_compatible(old, obj) -> None:
    parameters = list(inspect.signature(obj).parameters.values())
    assert [p.name for p in parameters[: len(old)]] == [p["name"] for p in old]
    for expected, actual in zip(old, parameters, strict=False):
        assert actual.kind.name == expected["kind"]
        assert (actual.default is inspect.Parameter.empty) == expected["required"]
    assert all(
        p.default is not inspect.Parameter.empty
        or p.kind in {inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD}
        for p in parameters[len(old) :]
    )


def test_call_guard_rejects_incompatible_changes() -> None:
    import pytest

    baseline = [{"name": "value", "kind": "POSITIONAL_OR_KEYWORD", "required": False}]
    for changed in [
        lambda renamed=None: None,
        lambda value: None,
        lambda *, value=None: None,
        lambda value=None, *, added: None,
    ]:
        with pytest.raises(AssertionError):
            assert_call_compatible(baseline, changed)
    assert_call_compatible(baseline, lambda value=None, *, optional=None: None)


def test_release_metadata_matches_runtime_provenance() -> None:
    root = Path(__file__).resolve().parents[1]
    metadata = (root / "pyproject.toml").read_text()
    declared = re.search(r'^version = "([^"]+)"', metadata, re.MULTILINE)
    assert declared is not None
    assert declared.group(1) == api.__version__ == version("agentic-evals")
