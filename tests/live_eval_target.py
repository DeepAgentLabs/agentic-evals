def run_case(payload, *, case):
    trace = {
        "trace_id": "live-trace-1",
        "metadata": {"turn_count": 1},
        "spans": [
            {
                "tool_name": "add",
                "attributes": {"tool_args": {"a": 40, "b": 2}},
            }
        ],
    }
    return {"output": payload["response"], "trace": trace}
