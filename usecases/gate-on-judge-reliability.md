# Don't let a flaky LLM judge approve a release

An LLM judge grades three support answers. On the flaky run, one judgment
never arrives, another case gets three different-minded verdicts, and the
judge's cost is only partly known. Each problem fails the release gate on its
own, with a reason that names the case. On the steady run the same gate
passes. The judge is a stand-in function, so nothing calls a model.

| | |
|---|---|
| **For** | Teams that grade agent answers with an LLM judge |
| **Difficulty** | Intermediate |
| **Time** | ~10 minutes |
| **Capabilities** | [Judge reliability](https://deepagentlabs.io/agentic-evals/docs/judge-reliability/), [Rubric scorers](https://deepagentlabs.io/agentic-evals/docs/api-reference/#rubric-scorers-llm-graded), [Release gates](https://deepagentlabs.io/agentic-evals/docs/api-reference/#release-gates) |
| **Status** | Stable |

## The problem

A judge is a model call, and model calls fail. Some are rate limited, some
time out, some return a different verdict each time for the same answer. If
a failed judgment counts as a pass, or simply drops out of the average, an
answer nobody graded can reach production. A single sample hides an
undecided judge, and judge spend goes unnoticed when it is mixed in with the
agent's own cost.

## Architecture

<figure class="ae-sim" data-ae-sim="judge" aria-label="Interactive illustration">
  <p class="ae-sim-fallback" style="padding:16px 22px;margin:0">refund-window is rate limited once, then judged A three times (4 attempts). shipping-cost times out three times and is unavailable. warranty is judged C, C, A: agreement 67%, score 0.73, still passing. The gate fails with four reasons. With a steady judge, all nine verdicts agree, cost is $0.0036 and the gate passes.</p>
  <figcaption>Interactive illustration of the walkthrough below. Click a step, or swap in a steady judge at step 5. Verdicts, attempts and gate reasons are the same as in <em>Expected output</em>; nothing is judged in your browser.</figcaption>
</figure>

??? note "Static diagram"

    ```mermaid
    flowchart LR
        A[Answer + reference] --> J[LLMRubricEvaluator<br/>FACTUALITY, samples=3]
        J -->|retry up to 3 attempts| M[your complete_fn]
        J --> S[Score<br/>judge_status, attempts,<br/>agreement, cost]
        S --> R[summary.judge]
        R --> G[evaluate_gate<br/>agreement, unavailable, cost]
    ```

`LLMRubricEvaluator` builds the rubric prompt and parses the verdict letter.
You supply `complete_fn`, the call to your model. Return a `JudgeResponse` to
report its tokens and cost.

## Prerequisites

- Python 3.10 or newer.
- agentic-evals **0.9.0** (retries, `samples=N`, judge cost and the judge
  gate checks are new in 0.9.0):

    ```bash
    python -m venv .venv && source .venv/bin/activate
    python -m pip install agentic-evals==0.9.0
    ```

- No model, API key or network. The script is
  [`examples/usecases/judge_gate.py`](../examples/usecases/judge_gate.py).

## Walkthrough

### 1. Wrap your model call

`complete_fn(prompt) -> str | JudgeResponse` is the only provider code you
write. In this script `make_judge(flaky=True)` stands in for an unreliable
provider:

- `refund-window`: the first call raises a rate-limit error
- `shipping-cost`: every call times out
- `warranty`: two of three calls answer `C`, the third `A`

`make_judge(flaky=False)` answers `A` every time.

### 2. Judge each answer three times, with retries

```python
LLMRubricEvaluator(
    "factuality",
    FACTUALITY,
    make_judge(flaky),
    version="support-v1",
    retry=RetryPolicy(max_attempts=3, backoff_seconds=0.0),
    samples=3,
)
```

Each case uses `threshold=0.6` and passes its reference answer in
`EvaluatorConfig.config["reference"]`.

### 3. Gate on the judge as well as the answers

```python
GATE = GateConfig(min_pass_rate=0.9, min_judge_agreement=0.8, max_judge_cost_usd=0.05)
```

`max_judge_unavailable_scores` is not set because it already defaults to 0.

### 4. Run it with both judges

Save this as `judge_gate.py`:

```python
"""Gate support answers on an LLM judge, and on whether the judge itself held up.

`complete_fn` stands in for your model call. The flaky judge is rate limited
once, never answers for one case and flips its verdict on another; the steady
judge answers every call the same way. Nothing here calls a model.

Run: python judge_gate.py            (flaky judge, gate fails, exit 1)
     python judge_gate.py --steady   (steady judge, gate passes, exit 0)
"""

import sys
from collections.abc import Callable

from agentic_evals import (
    FACTUALITY,
    EvalTrace,
    EvaluationReport,
    EvaluationSample,
    EvaluatorConfig,
    EvaluatorRegistry,
    GateConfig,
    JudgeResponse,
    LLMRubricEvaluator,
    RetryPolicy,
    TestCase,
    TestSuite,
    evaluate_gate,
    evaluate_suite,
)

ANSWERS = {
    "refund-window": ("How long do I have to return an item?", "You have 30 days from delivery."),
    "shipping-cost": ("Is shipping free?", "Shipping is free on orders over $50."),
    "warranty": ("Does the blender have a warranty?", "Yes, a two-year limited warranty."),
}
GATE = GateConfig(min_pass_rate=0.9, min_judge_agreement=0.8, max_judge_cost_usd=0.05)


def make_judge(flaky: bool) -> Callable[[str], JudgeResponse]:
    calls: dict[str, int] = {}

    def complete_fn(prompt: str) -> JudgeResponse:
        """Replace with your provider call; return its usage when it reports one."""
        case = next(c for c, (question, _) in ANSWERS.items() if question in prompt)
        calls[case] = calls.get(case, 0) + 1
        verdict = "A"
        if flaky and case == "refund-window" and calls[case] == 1:
            raise ConnectionError("429 rate limited")  # transient: the retry recovers
        if flaky and case == "shipping-cost":
            raise TimeoutError("judge provider timed out")  # never answers
        if flaky and case == "warranty" and calls[case] % 3:
            verdict = "C"  # unsure: two of three samples disagree with the third
        return JudgeResponse(
            text=verdict,
            input_tokens=210,
            output_tokens=1,
            cost_usd=0.0004,
            cost_source="measured",
            model="your-judge-model",
        )

    return complete_fn


def build_report(flaky: bool) -> EvaluationReport:
    registry = EvaluatorRegistry()
    registry.register(
        LLMRubricEvaluator(
            "factuality",
            FACTUALITY,
            make_judge(flaky),
            version="support-v1",
            retry=RetryPolicy(max_attempts=3, backoff_seconds=0.0),
            samples=3,
        )
    )
    suite = TestSuite(
        name="support-answers-judged",
        version="1",
        cases=[
            TestCase(
                id=case,
                name=question,
                input=question,
                evaluators=[
                    EvaluatorConfig(name="factuality", threshold=0.6, config={"reference": answer})
                ],
            )
            for case, (question, answer) in ANSWERS.items()
        ],
    )
    samples = [
        EvaluationSample(case_id=case, output=answer, trace=EvalTrace(trace_id=case))
        for case, (_, answer) in ANSWERS.items()
    ]
    return evaluate_suite(suite, samples, registry=registry)


def main(argv: list[str]) -> int:
    flaky = "--steady" not in argv
    report = build_report(flaky)
    print(f"== {'flaky' if flaky else 'steady'} judge ==")
    for case in report.cases:
        meta = case.scores[0].metadata
        print(
            f"{case.case_id:<14} {meta['judge_status']:<12} attempts={meta['judge_attempts']} "
            f"agreement={meta.get('judge_agreement', '-')} {'PASS' if case.passed else 'FAIL'}"
        )
    judge = report.summary.judge
    assert judge is not None
    cost = "incomplete" if judge.total_cost_usd is None else f"${judge.total_cost_usd:.4f}"
    print(f"judge cost {cost}; unavailable in {judge.unavailable_cases}")
    print(f"lowest agreement {judge.min_agreement}")

    gate = evaluate_gate(report, GATE)
    print(f"\ngate passed: {gate.passed}")
    for reason in gate.reasons:
        print(f"- {reason}")
    return 0 if gate.passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

```bash
python judge_gate.py; echo "exit $?"
python judge_gate.py --steady; echo "exit $?"
```

## Expected output

Flaky judge:

```text
== flaky judge ==
refund-window  ok           attempts=4 agreement=1.0 PASS
shipping-cost  unavailable  attempts=3 agreement=- FAIL
warranty       ok           attempts=3 agreement=0.666667 PASS
judge cost incomplete; unavailable in ['shipping-cost']
lowest agreement 0.666667

gate passed: False
- Pass rate 66.7% is below 90.0%.
- Judge unavailable for 1 score(s), more than 0, in cases 'shipping-cost'.
- Judge cost is incomplete: 2 of 3 judge scores recorded a cost.
- Judge agreement 67% is below 80% in cases 'warranty'.
exit 1
```

Steady judge:

```text
== steady judge ==
refund-window  ok           attempts=3 agreement=1.0 PASS
shipping-cost  ok           attempts=3 agreement=1.0 PASS
warranty       ok           attempts=3 agreement=1.0 PASS
judge cost $0.0036; unavailable in []
lowest agreement 1.0

gate passed: True
exit 0
```

`warranty` *passed* on the flaky run. Its mean score of 0.73 clears the 0.6
threshold. Only the agreement check shows that the judge couldn't decide.

## How it works

- **Retries are counted.** `judge_attempts` counts every call:
  `refund-window` made 4, three samples plus one retry. Each judge score also
  records `judge_status`, `judge_latency_ms` and any usage reported.
- **Unavailable is a result, not a crash.** When a call still fails after
  its last attempt, the case gets a score with `judge_status: unavailable`.
  Its value is 0 and it never passes. The suite keeps running, and
  `max_judge_unavailable_scores` (default 0) fails the gate and names the case.
- **Agreement measures the judge.** With `samples=3`, `judge_agreement` is
  the share of verdicts matching the most common one: two of three is 0.67.
  `min_judge_agreement` fails the gate when any sampled case falls below it.
- **Unknown cost is never $0.** `summary.judge.total_cost_usd` stays `None`
  until every judge score reports a cost, and `max_judge_cost_usd` fails on an
  incomplete total. Judge cost is kept apart from the agent's own cost.

## Variations

- **Use a real provider.** Replace `complete_fn` with your model call and
  return `JudgeResponse(text=..., cost_usd=..., input_tokens=...,
  output_tokens=..., model=...)`.
- **Use your own criterion.** `make_rubric("tone", "The reply is courteous
  and does not blame the reader.")` builds a template from a sentence.
- **Pin the judge version.** Change `version=` whenever the prompt or model
  changes. Every score records `evaluator_version`, so two reports are only
  compared when the same judge graded them.
- **Await an async judge.** `aevaluate_suite` awaits `async def` evaluators.

## Next steps

- [Block a release when one safety case fails](block-an-unsafe-release.md):
  combine deterministic floors with judged checks in one gate.
- [Judge reliability and live resilience](https://deepagentlabs.io/agentic-evals/docs/judge-reliability/)
