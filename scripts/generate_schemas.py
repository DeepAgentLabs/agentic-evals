"""Regenerate packaged schemas: uv run python scripts/generate_schemas.py."""

import json
from pathlib import Path

from agentic_evals import EvaluationReport, GateDecision

DESTINATION = Path(__file__).resolve().parents[1] / "src/agentic_evals/schemas"


def main() -> None:
    for model, name in (
        (EvaluationReport, "evaluation-report"),
        (GateDecision, "gate-decision"),
    ):
        schema = model.model_json_schema(mode="validation")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = (
            "https://raw.githubusercontent.com/DeepAgentLabs/agentic-evals/"
            f"v0.7.2/src/agentic_evals/schemas/{name}-1.0.schema.json"
        )
        (DESTINATION / f"{name}-1.0.schema.json").write_text(
            json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
