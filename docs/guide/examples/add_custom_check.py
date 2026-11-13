import json
from pathlib import Path
from agentic_evals import EvaluatorConfig, load_suite

suite = load_suite("suite.traces.yaml")
for case in suite.cases:
    case.evaluators.append(EvaluatorConfig(name="short_answer", threshold=1.0))
Path("suite.custom-check.json").write_text(
    suite.model_dump_json(indent=2), encoding="utf-8"
)

