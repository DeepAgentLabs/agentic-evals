"""Convert our illustrative custom dataset to native suite/sample files."""
import json
from pathlib import Path
from agentic_evals import EvaluationSample, EvalTrace, TestCase, TestSuite

rows = json.loads(Path("custom-data.json").read_text(encoding="utf-8"))
suite = TestSuite(
    name="refund-answer-checks", version="1",
    cases=[TestCase(id=row["id"], name=row["id"], input=row["input"],
                    expected_output=row["expected"], tags=["answers"])
           for row in rows],
)
samples = [
    EvaluationSample(case_id=row["id"], output=row["output"],
                     trace=EvalTrace(metadata={"evidence_scope": "answer_only"}))
    for row in rows
]
Path("suite.custom.json").write_text(suite.model_dump_json(indent=2), encoding="utf-8")
Path("samples.custom.jsonl").write_text(
    "\n".join(sample.model_dump_json() for sample in samples) + "\n",
    encoding="utf-8",
)
print("Created suite.custom.json and samples.custom.jsonl")

