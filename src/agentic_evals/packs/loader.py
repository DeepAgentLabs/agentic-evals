"""Runnable eval packs: a `TestSuite` bundled with the scorer names it needs.

Distinct from `agentic_evals.skills` (methodology playbooks) -- a pack is a
small, shareable, immediately-runnable configuration.
"""

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agentic_evals.evaluators import EvaluatorRegistry
from agentic_evals.models import TestSuite
from agentic_evals.scorers.registry import default_registry


class EvalPack(BaseModel):
    name: str
    description: str = ""
    suite: TestSuite
    required_scorers: list[str] = Field(default_factory=list)

    def to_suite(self) -> TestSuite:
        return self.suite


def _load_data(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix.lower() == ".json" else yaml.safe_load(text)


def load_pack(path: Path, *, registry: EvaluatorRegistry | None = None) -> EvalPack:
    """Load an `EvalPack` from a YAML/JSON file, failing fast if a required scorer is missing.

    `registry` defaults to `default_registry()`; pass your own (e.g. one
    with an `LLMRubricEvaluator` registered) if the pack needs a scorer
    that isn't in the default set.
    """
    pack = EvalPack.model_validate(_load_data(path))
    available = (registry or default_registry()).names()
    missing = [name for name in pack.required_scorers if name not in available]
    if missing:
        raise ValueError(
            f"eval pack {pack.name!r} requires scorer(s) not available in the registry: {missing}"
        )
    return pack
