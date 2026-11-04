"""Candidate API compatibility contract for the coordinated major release."""

import inspect
import json
from pathlib import Path

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
        kind = "class" if inspect.isclass(obj) else "function" if inspect.isfunction(obj) else "value"
        assert kind == entry["kind"], name
        assert getattr(obj, "__module__", None) == entry["module"], name
        if kind != "function":
            continue
        parameters = list(inspect.signature(obj).parameters.values())
        old = entry["parameters"]
        assert [p.name for p in parameters[:len(old)]] == [p["name"] for p in old], name
        for expected, actual in zip(old, parameters):
            assert actual.kind.name == expected["kind"], name
            assert (actual.default is inspect.Parameter.empty) == expected["required"], name
        assert all(p.default is not inspect.Parameter.empty or p.kind in {
            inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD
        } for p in parameters[len(old):]), name
