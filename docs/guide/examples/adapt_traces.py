"""Adapter for the GENERIC training export, not a vendor-specific importer.

Replace source keys and extraction logic for your vendor's actual schema.
Require complete ordered tool evidence for this trace-based tutorial.
"""
import json
import math
from pathlib import Path
from agentic_evals import EvalSpan, EvalTrace, EvaluationSample

def number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return value

def nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value

def adapt(row):
    if row.get("trace_complete") is not True:
        raise ValueError("Complete tool evidence required; do not treat missing spans as no calls")
    case_id = nonempty(row["evaluation_case_id"], "evaluation_case_id")
    run_id = nonempty(row["run_id"], "run_id")
    if not isinstance(row["final_answer"], str):
        raise ValueError("final_answer must be a string")
    duration = number(row["duration_ms"], "duration_ms")
    cost = row.get("cost_usd")
    if cost is not None:
        number(cost, "cost_usd")
    cost_source = row.get("cost_source")
    if cost_source not in (None, "measured", "estimated"):
        raise ValueError("cost_source must be measured, estimated, or null")
    events = row["events"]
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    sequences = [event["sequence"] for event in events]
    if any(type(value) is not int for value in sequences):
        raise ValueError("sequence must contain integers")
    if len(sequences) != len(set(sequences)):
        raise ValueError("Duplicate event order; resolve ordering before evaluation")
    spans = []
    for event in sorted(events, key=lambda item: item["sequence"]):
        event_type = nonempty(event["type"], "event type")
        attributes = {"source_sequence": event["sequence"], "source_type": event_type}
        tool_name = None
        if event_type == "tool":
            tool_name = nonempty(event["name"], "tool name")
            args = event["args"]
            if not isinstance(args, dict):
                raise ValueError("Tool args must be a JSON object")
            attributes["tool_args"] = args
        spans.append(EvalSpan(tool_name=tool_name, attributes=attributes))
    return EvaluationSample(
        case_id=case_id, output=row["final_answer"],
        trace=EvalTrace(
            trace_id=run_id, spans=spans, total_latency_ms=duration,
            estimated_cost_usd=cost, cost_source=cost_source,
            metadata={"source": "generic-training-export", "trace_complete": True},
        ),
    )

if __name__ == "__main__":
    rows = json.loads(Path("third-party-traces.json").read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a nonempty JSON array")
    samples = [adapt(row) for row in rows]
    ids = [sample.case_id for sample in samples]
    if len(ids) != len(set(ids)):
        raise ValueError("One sample per case per evaluation run; duplicate case IDs found")
    Path("samples.traces.jsonl").write_text(
        "\n".join(sample.model_dump_json() for sample in samples) + "\n",
        encoding="utf-8",
    )
    print(f"Mapped {len(samples)} traces to samples.traces.jsonl")

