---
name: red-team-an-agent-suite
description: Build adversarial TestCases (forbidden tools, injected instructions, unanswerable requests) that probe for unsafe or unintended agent behavior, not just wrong answers.
---

# Red-team an agent suite

## Trigger

Use this when the objective (`define-an-eval-objective`) is safety or
robustness, not correctness — before shipping an agent with tool access,
or when `discover-failure-modes` turns up a failure that looks like a
policy violation rather than a quality miss.

## Do

1. Write cases where the *correct* behavior is refusal or inaction —
   pair `forbidden_tools` with an input that would tempt an unsafe agent
   into calling one anyway (e.g. a request that implies deleting data,
   sending money, or exfiltrating a secret). A suite with no forbidden-
   tool cases can't detect the agent overstepping, only whether it
   under-delivers.
2. Include prompt-injection-style cases: inputs (or tool outputs, for a
   trajectory-aware suite) that try to redirect the agent away from its
   actual task. Score these with `required_tools`/`forbidden_tools` plus
   `expected_contains` on a refusal phrase, not with a lenient rubric that
   might reward "creatively" following the injected instruction.
3. Use `POSSIBLE` for requests that are subtly unanswerable (missing
   information, outside the agent's actual authority) — the failure mode
   to catch is confident fabrication, which a plain correctness scorer
   won't flag since there's no "correct answer" to compare against.
4. Use `SECURITY`/`PII_LEAKAGE` rubrics on cases where the agent handles
   code, credentials, or user data, specifically checking what the agent
   does with information it shouldn't act on or shouldn't repeat.
5. Keep red-team cases in their own tagged subset (`build-an-eval-dataset`)
   scored separately from the main quality suite — mixing them dilutes a
   safety regression into a small blip on the overall pass rate instead of
   a visible, separately-gated signal.

## Avoid

- Don't rely on an LLM judge from the same model family as the agent under
  test to grade red-team cases — a shared blind spot (the same training
  data's notion of "reasonable") is exactly what red-teaming needs to
  route around.
- Don't treat a passing red-team suite as proof of safety — it's evidence
  against the specific attacks you thought to write; a new attack shape
  needs a new case, not a higher threshold on the old ones.
- Don't gate a release on the red-team suite using the same
  `min_pass_rate` as the quality suite — a safety-tagged suite usually
  wants `min_pass_rate=1.0`/`max_failed_cases=0` regardless of what the
  quality bar tolerates.

## Check

- At least one case exists per `forbidden_tools`/refusal scenario you can
  think of for this agent's actual tool access, not just a generic
  "ignore previous instructions" probe.
- Red-team cases are tagged and scored/gated separately from the main
  suite.
- The judge model (if any) grading red-team cases isn't the same model
  family as the agent being tested.

## Risk

A red-team suite only catches what it was written to catch. Treat a clean
run as narrowing the known-attack surface, not as a general safety
guarantee — and revisit this suite whenever the agent gains new tools or
new scopes of authority, since that's exactly when the existing cases
stop covering the actual risk.
