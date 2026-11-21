# Evaluation methodology playbooks

The distribution includes 19 guidance cards under `agentic_evals/skills/`. They are methodology documentation, distinct from runnable evaluation packs, registered scorers and Python APIs. A card's advice does not install a scorer, execute a target, verify evidence or establish statistical confidence.

| Playbook | Purpose |
| --- | --- |
| [analyze-an-eval-experiment](../src/agentic_evals/skills/analyze-an-eval-experiment/SKILL.md) | Read two EvaluationReports (or EvalResults) past the headline pass rate -- paired differences, uncertainty, and subgroup breakdowns -- before declaring a winner. |
| [build-an-eval-dataset](../src/agentic_evals/skills/build-an-eval-dataset/SKILL.md) | Source, label, and split the TestCase/Eval() rows a suite runs against, so the dataset itself doesn't become the eval's weakest link. |
| [choose-a-rubric-template](../src/agentic_evals/skills/choose-a-rubric-template/SKILL.md) | Pick the right built-in RubricTemplate (FACTUALITY, SECURITY, SQL_CORRECTNESS, POSSIBLE, PII_LEAKAGE, TRANSLATION, BATTLE, CLOSED_QA, SUMMARY_QUALITY, MODERATION) instead of hand-writing a new one. |
| [debug-a-flaky-llm-judge](../src/agentic_evals/skills/debug-a-flaky-llm-judge/SKILL.md) | Diagnose an LLMRubricEvaluator or LLMJudgeEvaluator whose verdict changes between runs on the same input, before concluding the eval itself is unreliable. |
| [define-a-release-gate](../src/agentic_evals/skills/define-a-release-gate/SKILL.md) | Choose GateConfig thresholds and understand the cost/latency edge cases before gating a release on an EvaluationReport. |
| [define-an-eval-objective](../src/agentic_evals/skills/define-an-eval-objective/SKILL.md) | Pin down the decision an eval needs to support and the evidence it needs to produce, before writing any TestCase or Eval() data. |
| [design-an-eval-experiment](../src/agentic_evals/skills/design-an-eval-experiment/SKILL.md) | Set up a fair A/B comparison between two prompts/agents/models with agentic_evals, so the diff you measure is the one you intended to measure. |
| [discover-failure-modes](../src/agentic_evals/skills/discover-failure-modes/SKILL.md) | Turn a low pass rate in an EvaluationReport into named, actionable failure categories instead of a flat list of failing case IDs. |
| [elicit-eval-criteria](../src/agentic_evals/skills/elicit-eval-criteria/SKILL.md) | Turn a vague quality bar ("the answers should be good") into concrete, checkable TestCase expectations before writing scorers. |
| [evaluate-containment](../src/agentic_evals/skills/evaluate-containment/SKILL.md) | Score authenticated bounded containment evidence separately from task success. |
| [export-aios-evidence](../src/agentic_evals/skills/export-aios-evidence/SKILL.md) | Attach evaluation results to an AI Operations Specification Run as evaluation evidence, with every judgment tied to the Run object it judged. |
| [instrument-a-trace](../src/agentic_evals/skills/instrument-a-trace/SKILL.md) | Build EvalTrace/EvalSpan correctly from your own agent's data, including how to normalize legacy or differently-shaped trace payloads with a trace_adapter. |
| [monitor-evals-in-production](../src/agentic_evals/skills/monitor-evals-in-production/SKILL.md) | Turn a one-off TestSuite/pack into a recurring check against a live target, with alerting thresholds that account for production noise a pre-release run never sees. |
| [red-team-an-agent-suite](../src/agentic_evals/skills/red-team-an-agent-suite/SKILL.md) | Build adversarial TestCases (forbidden tools, injected instructions, unanswerable requests) that probe for unsafe or unintended agent behavior, not just wrong answers. |
| [report-eval-results](../src/agentic_evals/skills/report-eval-results/SKILL.md) | Turn an EvaluationReport/GateDecision into a summary a stakeholder can act on, without losing the caveats that made the analysis trustworthy. |
| [run-a-live-suite](../src/agentic_evals/skills/run-a-live-suite/SKILL.md) | Point run_live_suite at a real PythonTarget or HTTPTarget safely, instead of only ever scoring pre-recorded EvaluationSamples. |
| [size-a-test-suite](../src/agentic_evals/skills/size-a-test-suite/SKILL.md) | Decide how many TestCases a TestSuite needs and how to split criteria across them without bundling unrelated checks into one case. |
| [validate-a-scorer](../src/agentic_evals/skills/validate-a-scorer/SKILL.md) | Check that a new scorer or LLMRubricEvaluator actually agrees with expert judgment before trusting it to gate a release or block a PR. |
| [write-a-scorer](../src/agentic_evals/skills/write-a-scorer/SKILL.md) | Choose and implement the right kind of scorer (deterministic, embedding, LLM rubric, or trajectory) for a new eval criterion in agentic_evals. |

Cards use Trigger/Do/Avoid/Check/Risk sections to guide objective definition, dataset and criterion design, trace instrumentation, scorer/rubric selection and validation, live runs, judge debugging, release policy, reporting, production monitoring, containment and AIOS export. The robust reference includes their full maintained text. Use the actual package APIs and evidence contracts described in the [Developer Guide](developer-guide.md#capability-index) and [scorer catalog](scorers.md) to carry out a workflow.
