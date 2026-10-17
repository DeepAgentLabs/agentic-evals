"""Exercise packaged resources from an installed wheel, outside the source path."""

import json
import tarfile
from pathlib import Path

from jsonschema import Draft202012Validator

import agentic_evals

ROOT = Path(__file__).resolve().parents[1]
assert Path(agentic_evals.__file__).parent != ROOT / "src/agentic_evals"
for name, accessor in (
    ("evaluation-report", agentic_evals.report_schema),
    ("gate-decision", agentic_evals.gate_decision_schema),
):
    schema = accessor()
    Draft202012Validator.check_schema(schema)
    artifact = json.loads((ROOT / "examples/report-contract" / f"{name}.json").read_text())
    Draft202012Validator(schema).validate(artifact)
    for archive in (ROOT / "dist").glob("*.tar.gz"):
        with tarfile.open(archive) as source:
            assert any(
                path.endswith(f"/src/agentic_evals/schemas/{name}-1.0.schema.json")
                for path in source.getnames()
            )
print(f"Installed contract verified: agentic-evals {agentic_evals.__version__}")
