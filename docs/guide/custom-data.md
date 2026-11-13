# Evaluate custom datasets

## Evaluate custom recorded outputs

Download both files into the working folder. The converter creates the suite and native samples. It does not call a model.

custom-data.json · complete file

```json
[
  {
    "id": "refund-1042",
    "input": "What is the status of refund 1042?",
    "expected": "Refund 1042 is processing.",
    "output": "Refund 1042 is processing."
  },
  {
    "id": "refund-1043",
    "input": "Check refund 1043. Do not issue a new refund.",
    "expected": "Refund 1043 is processing.",
    "output": "Refund 1043 is processing."
  }
]
```

[Download custom-data.json](examples/custom-data.json)

build_custom.py · complete file

```python
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
```

[Download build_custom.py](examples/build_custom.py)

```
python build_custom.py
agentic-evals evaluate suite.custom.json samples.custom.jsonl --out report.custom.json
agentic-evals gate report.custom.json
```

**Expected:** both answer checks pass. This answer-only dataset does not prove tool correctness or measured latency.
