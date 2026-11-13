# Apply release gates

Apply the policy to the native JSON report produced by [the trace evaluation](existing-traces.md).

gate.yaml · complete file

```yaml
min_pass_rate: 0.95
min_tag_pass_rate:
  safety: 1.0
min_metric_pass_rate:
  forbidden_tool: 1.0
max_average_latency_ms: 1500
max_total_cost_usd: 0.05
```

[Download gate.yaml](examples/gate.yaml)

```
agentic-evals gate report.traces.json --config gate.yaml --out gate-decision.json
```

| Command | Meaning |
| --- | --- |
| evaluate / live | Successful exit means report produced, even when cases fail. |
| gate | Exit 0: policy passed. Exit 1: gate failed. Exit 2: invalid input or usage. |
| run | Discovers Python Eval files; all discovered cases must pass for success. |

Tag floors protect critical subsets from being hidden by aggregate pass rates. A named tag or metric missing from the report fails the configured gate. Keep unknown costs unknown.
