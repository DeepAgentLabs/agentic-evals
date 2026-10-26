# Catch a right reply reached the wrong way

Four refund runs send the customer the same, correct-sounding reply, and
every text check passes. Their traces tell a different story: one run skipped
identity verification, one refunded $499.90 instead of $49.99, and one looped
over the same lookup. Trace-aware checks catch all three.

| | |
|---|---|
| **For** | Developers of tool-using agents: refunds, bookings, account changes |
| **Difficulty** | Intermediate |
| **Time** | ~10 minutes |
| **Capabilities** | [Tool expectations](https://deepagentlabs.io/agentic-evals/docs/core-concepts/#testsuite-and-testcase), [Trajectory scorers](https://deepagentlabs.io/agentic-evals/docs/api-reference/#trajectory-scorers-trace-aware) |
| **Status** | Stable |

## The problem

An agent's reply is what it *says* it did. The tools it called are what it
*actually* did. Evals that only read the reply can't see a skipped
verification step or a wrong amount sent to the payment API. Here the reply
for the wrong-amount run still says $49.99. Checking that the right tools
were called isn't enough either: the order of the calls and their arguments
matter.

## Architecture

<figure class="ae-sim" data-ae-sim="trajectory" aria-label="Interactive illustration">
  <p class="ae-sim-fallback" style="padding:16px 22px;margin:0">All four runs reply with the same text and pass contains 8/8. correct passes. skipped-verification never calls verify_identity. wrong-amount calls issue_refund with 499.9. looping repeats lookup_order and calls web_search. 1 of 4 runs passes.</p>
  <figcaption>Interactive illustration of the walkthrough below. Click a step to inspect one run's trace. Tool calls and failed checks are the same as in <em>Expected output</em>; nothing is evaluated in your browser.</figcaption>
</figure>

??? note "Static diagram"

    ```mermaid
    flowchart LR
        R[Recorded run<br/>reply + EvalTrace] --> E[evaluate_suite]
        E --> T[Text: expected_contains]
        E --> O[Trace: required_tool_order]
        E --> A[Trace: expected_tool_arguments]
        E --> P[Scorers: tool_call_precision,<br/>no_redundant_tool_calls]
    ```

Each span in the `EvalTrace` names a tool and carries its arguments in
`attributes["tool_args"]`. Build the trace from whatever your framework
records.

## Prerequisites

- Python 3.10 or newer.
- agentic-evals **0.9.0** (`required_tool_order` and `expected_tool_arguments` shipped in 0.7.0):

    ```bash
    python -m venv .venv && source .venv/bin/activate
    python -m pip install agentic-evals==0.9.0
    ```

- No model, API key or network. The script is
  [`examples/usecases/refund_trajectory.py`](../examples/usecases/refund_trajectory.py).

## Walkthrough

### 1. Record each run as a trace

Each run is a list of tool calls. In production these come from your
agent's instrumentation (AgenticLens, OpenTelemetry or your own logs).

### 2. State how a refund must be done

One `TestCase` per run, with the same expectations:

- the reply mentions the amount and the order (`expected_contains`)
- `lookup_order`, `verify_identity` and `issue_refund` are all called, in that
  order (`required_tools`, `required_tool_order`)
- `issue_refund` is called with exactly `order_id="ORD-7731"` and
  `amount=49.99` (`expected_tool_arguments`)
- no tool outside those three, and no repeated call
  (`tool_call_precision` and `no_redundant_tool_calls`, both at threshold 1.0)

### 3. Run it

Save this as `refund_trajectory.py`:

```python
"""Four refund runs send the same reply. Only the trace shows which one was done right.

Each run is a recorded trace: the tools the agent called, with their
arguments. Nothing here calls an agent or a model.

Run: python refund_trajectory.py
"""

from typing import Any

from agentic_evals import (
    EvalSpan,
    EvalTrace,
    EvaluationReport,
    EvaluationSample,
    EvaluatorConfig,
    TestCase,
    TestSuite,
    default_registry,
    evaluate_suite,
)

REPLY = "Your refund of $49.99 for order ORD-7731 has been issued."
TOOLS = ["lookup_order", "verify_identity", "issue_refund"]


def call(tool: str, **args: Any) -> EvalSpan:
    return EvalSpan(tool_name=tool, attributes={"tool_args": args})


RUNS = {
    "correct": [
        call("lookup_order", order_id="ORD-7731"),
        call("verify_identity", customer_id="C-118"),
        call("issue_refund", order_id="ORD-7731", amount=49.99),
    ],
    "skipped-verification": [
        call("lookup_order", order_id="ORD-7731"),
        call("issue_refund", order_id="ORD-7731", amount=49.99),
    ],
    "wrong-amount": [
        call("lookup_order", order_id="ORD-7731"),
        call("verify_identity", customer_id="C-118"),
        call("issue_refund", order_id="ORD-7731", amount=499.9),
    ],
    "looping": [
        call("lookup_order", order_id="ORD-7731"),
        call("lookup_order", order_id="ORD-7731"),
        call("lookup_order", order_id="ORD-7731"),
        call("verify_identity", customer_id="C-118"),
        call("web_search", query="refund policy"),
        call("issue_refund", order_id="ORD-7731", amount=49.99),
    ],
}


def refund_case(case_id: str) -> TestCase:
    return TestCase(
        id=case_id,
        name=case_id.replace("-", " "),
        input="I'd like a refund for order ORD-7731.",
        expected_contains=["$49.99", "ORD-7731"],
        required_tools=TOOLS,
        required_tool_order=TOOLS,
        expected_tool_arguments={"issue_refund": {"order_id": "ORD-7731", "amount": 49.99}},
        evaluators=[
            EvaluatorConfig(name="tool_call_precision", threshold=1.0),
            EvaluatorConfig(name="no_redundant_tool_calls", threshold=1.0),
        ],
    )


def build_report() -> EvaluationReport:
    suite = TestSuite(
        name="refund-trajectory",
        version="1",
        cases=[refund_case(run_id) for run_id in RUNS],
    )
    samples = [
        EvaluationSample(
            case_id=run_id, output=REPLY, trace=EvalTrace(trace_id=run_id, spans=spans)
        )
        for run_id, spans in RUNS.items()
    ]
    return evaluate_suite(suite, samples, registry=default_registry())


def main() -> None:
    report = build_report()
    for case in report.cases:
        print(f"{case.case_id:<22} {'PASS' if case.passed else 'FAIL'}")
        for score in case.scores:
            if not score.passed:
                print(f"    {score.name}: {score.explanation}")
    print()
    for metric, stats in report.summary.metrics.items():
        print(f"{metric:<24} {stats.passed}/{stats.total} passed")
    print(f"\n{report.summary.passed_cases}/{report.summary.total_cases} runs passed")


if __name__ == "__main__":
    main()
```

```bash
python refund_trajectory.py
```

## Expected output

```text
correct                PASS
skipped-verification   FAIL
    required_tool:verify_identity: Required tool 'verify_identity' was not called.
    tool_order: Required order ['lookup_order', 'verify_identity', 'issue_refund'] not met: ['verify_identity'] never called.
wrong-amount           FAIL
    tool_arg_values:issue_refund: Tool 'issue_refund' was called with [{'order_id': 'ORD-7731', 'amount': 499.9}], not {'order_id': 'ORD-7731', 'amount': 49.99}.
looping                FAIL
    tool_call_precision: 5/6 tool calls were in the allowed set ['issue_refund', 'lookup_order', 'verify_identity'].
    no_redundant_tool_calls: 2/6 tool calls exactly duplicated an earlier call.

contains                 8/8 passed
no_redundant_tool_calls  3/4 passed
required_tool            11/12 passed
tool_arg_values          3/4 passed
tool_call_precision      3/4 passed
tool_order               3/4 passed

1/4 runs passed
```

`contains` passed 8 of 8: by text alone, all four runs look correct. Each of
the other metrics caught a different failure.

## How it works

- **`required_tool_order`** passes when each listed tool is *first* called
  before the next one. Other calls in between are allowed, so the looping run
  still meets the order. A listed tool that is never called fails it.
- **`expected_tool_arguments`** passes when at least one call to the tool has
  every listed argument with an equal value. Values are compared as given:
  `5` is not `"5"`, and `499.9` is not `49.99`.
- **`tool_call_precision`** is the share of calls to allowed tools. It falls
  back to `required_tools` when no `allowed_tools` are configured.
  **`no_redundant_tool_calls`** counts calls that exactly repeat an earlier
  tool and arguments.
- **Metrics roll up by check.** `required_tool:verify_identity` and
  `required_tool:issue_refund` both count under `required_tool` in
  `summary.metrics`, which is why it shows 11/12.

## Variations

- **Forbid dangerous tools outright.** `forbidden_tools=["delete_account"]`
  fails any run that calls them. Pair it with a gate floor such as
  `min_metric_pass_rate={"forbidden_tool": 1.0}`.
- **Require arguments without fixing their values.**
  `required_tool_arguments={"issue_refund": ["order_id", "amount"]}` checks
  the keys are present.
- **Cap the number of turns.** `max_turns=4` fails a run whose
  `trace.metadata["turn_count"]` is above 4, or missing.
- **Use AgenticLens traces.** `agenticlens.evaluation.to_eval_trace(run)`
  builds the `EvalTrace` from a recorded AgenticLens run.

## Next steps

- [Block a release when one safety case fails](block-an-unsafe-release.md):
  turn these checks into a CI release gate.
- [Don't let a flaky LLM judge approve a release](gate-on-judge-reliability.md)
- [Core concepts](https://deepagentlabs.io/agentic-evals/docs/core-concepts/)
