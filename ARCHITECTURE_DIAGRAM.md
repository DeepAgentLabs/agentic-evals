# Agentic Evals Architecture & Flow Diagrams

## 1. High-Level System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                    AGENTIC EVALS SYSTEM                                │
├────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  INPUT LAYER                PROCESSING LAYER           OUTPUT LAYER    │
│  ────────────────           ─────────────────           ────────────    │
│                                                                          │
│  ┌──────────────┐           ┌──────────────────┐    ┌────────────────┐ │
│  │  TestSuite   │           │ EvaluatorRegistry│    │ EvaluationReport │
│  │  (expected)  ├──────────→│  (run all        │───→│ (per-case       │
│  └──────────────┘           │   scorers)       │    │  scores)        │
│                             └──────────────────┘    └────────────────┘ │
│  ┌──────────────┐                 ↑                        ↓           │
│  │  Evaluation  │                 │                        │           │
│  │  Sample      ├─────────────────┘                        │           │
│  │  (observed)  │                                          ↓           │
│  └──────────────┘           SCORERS:              ┌────────────────┐   │
│                             - Text                │ GateConfig     │   │
│                             - Trajectory          │ (thresholds)   │   │
│  ┌──────────────┐           - LLM-Judge          └────────────────┘   │
│  │  EvalTrace   │           - Custom                      ↓           │
│  │  (spans,                                      ┌────────────────┐   │
│  │   latency,               Built-ins:           │ Gate Decision  │   │
│  │   cost)      │           18+ ready-made       │ (deploy or     │   │
│  └──────────────┘                                │  block)        │   │
│                                                  └────────────────┘   │
│                                                                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Data Flow: Agent Evaluation Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: DEFINE EXPECTATIONS                                            │
└─────────────────────────────────────────────────────────────────────────┘

    Write TestCase:
    ├─ id: "order-status-001"
    ├─ input: "Where is order 1042?"
    ├─ expected_contains: ["shipped", "2026-09-15"]
    ├─ required_tools: ["order_lookup"]
    ├─ required_tool_arguments: {"order_lookup": ["order_id"]}
    ├─ max_latency_ms: 1000
    ├─ max_cost_usd: 0.02
    └─ evaluators: [tool_call_precision, tool_call_recall]

            ↓

┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: RUN AGENT & CAPTURE TRACE                                      │
└─────────────────────────────────────────────────────────────────────────┘

    Agent receives: "Where is order 1042?"
    
    Agent execution:
    ├─ Transcribe audio (if voice)
    ├─ Detect intent
    ├─ Extract entity (order_id: 1042)
    ├─ Call order_lookup(order_id=1042)
    │  └─ Tool result: {status: "shipped", eta: "2026-09-15"}
    ├─ Generate response: "Order 1042 shipped on 2026-09-15."
    └─ Record execution time: 420ms, cost: $0.012

            ↓

    Create EvaluationSample:
    ├─ case_id: "order-status-001"
    ├─ output: "Order 1042 shipped on 2026-09-15."
    └─ trace: EvalTrace
        ├─ trace_id: "trace-001"
        ├─ total_latency_ms: 420
        ├─ estimated_cost_usd: 0.012
        └─ spans: [
            EvalSpan(
              tool_name="order_lookup",
              attributes={
                "tool_args": {"order_id": 1042},
                "tool_result": {status: "shipped", ...}
              }
            )
          ]

            ↓

┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: EVALUATE (Run All Scorers)                                     │
└─────────────────────────────────────────────────────────────────────────┘

    EvaluatorRegistry.evaluate(context):
    
    FOR each EvaluatorConfig in TestCase:
    
    ┌─ Scorer 1: tool_call_precision
    │  ├─ Check: Only "order_lookup" was called
    │  ├─ Result: ✅ PASS (value=1.0)
    │  └─ Score(name="tool_call_precision", value=1.0, passed=True)
    │
    ├─ Scorer 2: tool_call_recall
    │  ├─ Check: "order_lookup" was called (required tool)
    │  ├─ Result: ✅ PASS (value=1.0)
    │  └─ Score(name="tool_call_recall", value=1.0, passed=True)
    │
    ├─ Scorer 3: contains (built-in)
    │  ├─ Check: output contains "shipped" AND "2026-09-15"
    │  ├─ Result: ✅ PASS (value=1.0)
    │  └─ Score(name="contains", value=1.0, passed=True)
    │
    ├─ Scorer 4: latency_threshold (built-in)
    │  ├─ Check: 420ms <= 1000ms
    │  ├─ Result: ✅ PASS (value=1.0)
    │  └─ Score(name="latency_threshold", value=1.0, passed=True)
    │
    └─ Scorer 5: max_cost (built-in)
       ├─ Check: $0.012 <= $0.02
       ├─ Result: ✅ PASS (value=1.0)
       └─ Score(name="max_cost", value=1.0, passed=True)

            ↓

    CaseEvaluation:
    ├─ case_id: "order-status-001"
    ├─ passed: true
    ├─ scores: [5 Score objects above]
    ├─ latency_ms: 420
    └─ cost_usd: 0.012

            ↓

┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: REPORT & GATE DECISION                                         │
└─────────────────────────────────────────────────────────────────────────┘

    EvaluationReport:
    ├─ suite_name: "order-support"
    ├─ summary:
    │  ├─ total_cases: 1
    │  ├─ passed_cases: 1
    │  ├─ pass_rate: 1.0 (100%)
    │  ├─ average_score: 1.0
    │  ├─ average_latency_ms: 420
    │  └─ total_cost_usd: 0.012
    └─ cases: [CaseEvaluation from above]

            ↓

    GateConfig:
    ├─ min_pass_rate: 1.0
    ├─ max_average_latency_ms: 1000
    └─ max_total_cost_usd: 0.02

            ↓

    evaluate_gate() → GateDecision:
    ├─ passed: true
    └─ reasons: ["All thresholds met"]

            ↓

    ✅ DEPLOYMENT APPROVED (CI continues)
```

---

## 3. Scorer Ecosystem

```
┌──────────────────────────────────────────────────────────────┐
│ EVALUATORREGISTRY (Hub for all scorers)                      │
└──────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ↓                   ↓                   ↓
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ TEXT SCORERS    │  │TRAJECTORY       │  │ LLM JUDGES      │
│ (Deterministic) │  │SCORERS          │  │ (LLM-based)     │
├─────────────────┤  ├─────────────────┤  ├─────────────────┤
│ exact_match     │  │ tool_call_      │  │ FACTUALITY      │
│ contains        │  │ precision       │  │ CLOSED_QA       │
│ contains_all    │  │ tool_call_      │  │ SUMMARY_QUALITY │
│ levenshtein_    │  │ recall          │  │ BATTLE (A/B)    │
│ similarity      │  │ no_redundant_   │  │ MODERATION      │
│ embedding_      │  │ tool_calls      │  │ TRANSLATION     │
│ similarity      │  │ trajectory_     │  │ SECURITY        │
│ valid_json      │  │ efficiency      │  │ SQL_CORRECTNESS │
│ json_diff       │  │                 │  │ POSSIBLE        │
│ numeric_diff    │  │ OPERATIONAL:    │  │ PII_LEAKAGE     │
│ regex_match     │  │ latency_        │  └─────────────────┘
│ starts_with     │  │ threshold       │
│ ends_with       │  │ max_cost        │  ┌─────────────────┐
│ numeric_range   │  │ max_turns       │  │ CUSTOM EVALUATORS
│                 │  │ required_tools  │  │ (Your logic)
└─────────────────┘  │ forbidden_tools │  ├─────────────────┤
                     │ required_output_│  │ groundedness
Call signature:      │ fields          │  │ intent_accuracy
def scorer(          │ output_json_    │  │ transcript_
  output,            │ schema          │  │ accuracy
  expected           │                 │  │ custom_rule_X
)                    └─────────────────┘  └─────────────────┘
                     
Returns:             Call signature:      Call signature:
float | bool         def scorer(           def judge(
Score dict           context)              context)
```

---

## 4. Two API Paths

```
                    START: "I need to evaluate my agent"
                              ↓
                    ┌─────────────────────┐
                    │ Quick or Detailed?  │
                    └─────────────────────┘
                         ↙         ↖
              (Quick, Prototyping) (Production, Tools, SLAs)
                   ↙                          ↖
    
    ┌────────────────────────┐    ┌──────────────────────────┐
    │   SIMPLE API           │    │  ADVANCED API            │
    │   (Eval function)      │    │  (TestSuite +            │
    │                        │    │   evaluate_suite)        │
    ├────────────────────────┤    ├──────────────────────────┤
    │                        │    │                          │
    │ Eval(                  │    │ TestSuite(               │
    │   "capitals",          │    │   name="order-support",  │
    │   data=[...],          │    │   cases=[                │
    │   task=agent,          │    │     TestCase(            │
    │   scores=[equals]      │    │       id="001",          │
    │ )                      │    │       expected_contains, │
    │                        │    │       required_tools,    │
    │ → EvalResult           │    │       max_latency_ms,    │
    │   ├─ pass_rate         │    │       evaluators=[...]   │
    │   ├─ results[]         │    │     )                    │
    │   └─ __bool__()        │    │   ]                      │
    │                        │    │ )                        │
    │                        │    │                          │
    │ Use cases:             │    │ evaluate_suite(          │
    │ - Text matching        │    │   suite, samples         │
    │ - Quick prototypes     │    │ )                        │
    │ - Simple scorers       │    │                          │
    │ - One-off evals        │    │ → EvaluationReport       │
    │                        │    │   ├─ summary             │
    │ Auto-discovered by:    │    │   └─ cases[]             │
    │ agentic-evals run *.py │    │                          │
    │                        │    │ evaluate_gate(           │
    │                        │    │   report, config         │
    │                        │    │ )                        │
    │                        │    │                          │
    │                        │    │ → GateDecision           │
    │                        │    │   ├─ passed              │
    │                        │    │   └─ reasons[]           │
    │                        │    │                          │
    │                        │    │ Use cases:               │
    │                        │    │ - Agent tool validation  │
    │                        │    │ - Operational SLAs       │
    │                        │    │ - CI/CD gating           │
    │                        │    │ - Production evaluation  │
    │                        │    │ - Custom scoring logic   │
    │                        │    │                          │
    └────────────────────────┘    └──────────────────────────┘
```

---

## 5. Trace Instrumentation Pattern

```
YOUR AGENT                  AGENTIC EVALS
─────────────               ──────────────

run_agent(input)
    │
    ├─ Extract intent
    │
    ├─ Call tool_1
    │  └─ Record: tool_name, args, result
    │
    ├─ Call tool_2
    │  └─ Record: tool_name, args, result
    │
    ├─ Generate response
    │
    └─ Record: response, latency, cost
         │
         └──────────────────────→ Build EvalTrace
                                 ├─ spans: [
                                 │   EvalSpan(tool_name="tool_1", ...),
                                 │   EvalSpan(tool_name="tool_2", ...)
                                 │ ]
                                 ├─ total_latency_ms: 420
                                 ├─ estimated_cost_usd: 0.012
                                 └─ metadata: {
                                     "intent": "...",
                                     "transcript": "...",
                                     "recovered": false
                                   }
                                 
                                 Create EvaluationSample:
                                 {
                                   case_id: "test-001",
                                   output: response,
                                   trace: EvalTrace
                                 }
                                 
                                 Pass to evaluate_suite()
```

---

## 6. Voice Agent Example: Complete Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│ VOICE AGENT EVALUATION PIPELINE (Real-World Example)          │
└────────────────────────────────────────────────────────────────┘

USER INPUT (audio)
    ↓ "Where is my order 1234?"
    ↓
VOICE_AGENTS.py (Simulated STT)
    ├─ transcribe() → "Where is my order 1234?"
    ├─ detect_intent() → "order_status"
    ├─ extract_entity() → order_id = "1234"
    └─ Record all in trace.metadata
    ↓
VOICE_AGENTS.py (Tool Selection)
    ├─ Select tool: get_order
    ├─ Call get_order(order_id="1234")
    │  └─ Result: {status: "shipped", eta: "September 28"}
    └─ Record in EvalSpan
    ↓
VOICE_AGENTS.py (Response)
    └─ Generate: "Order 1234 shipped on September 28"
    ↓
SCENARIO_RUNNER.py (Capture)
    ├─ Create EvalTrace with all spans
    ├─ Record latency, cost
    └─ Create EvaluationSample
    ↓
RUN_EVALS.py (Evaluate)
    ├─ Load TestSuite (10 test cases)
    ├─ Run evaluate_suite()
    └─ Collect scores
    ↓
EVALUATORS.py (Custom Scorers)
    ├─ transcript_accuracy: "Where..." == "Where..." ✅
    ├─ intent_accuracy: "order_status" == "order_status" ✅
    ├─ required_tool: "get_order" was called ✅
    ├─ tool_arguments: order_id provided ✅
    ├─ contains: "1234" AND "shipped" ✅
    ├─ groundedness: Claims grounded in tool output ✅
    ├─ latency_threshold: 420ms < 5000ms ✅
    └─ reliability: Handled gracefully ✅
    ↓
EvaluationReport
    ├─ summary: 10/10 passed (100%)
    └─ metrics breakdown
    ↓
SERVER.py (Dashboard)
    ├─ Expose evaluation API
    └─ Serve interactive UI
    ↓
BROWSER
    └─ View results, inject faults, re-run
        ├─ Normal Order Status → 100% pass
        ├─ Wrong Tool Selected → precision fails ❌
        ├─ Wrong Arguments → argument check fails ❌
        ├─ Hallucinated Response → groundedness fails ❌
        ├─ Missing Order ID → recovery fails ❌
        └─ Unknown Intent → reliability fails ❌
```

---

## 7. Release Gate Decision Tree

```
          Evaluation Report Ready?
                  ↓
         ┌─────────────────────┐
         │ GateConfig Defined  │
         └─────────────────────┘
                  ↓
         ┌─────────────────────────────┐
         │ Apply Threshold Checks      │
         └─────────────────────────────┘
              ↙  ↓  ↓  ↓  ↓  ↓
             /   │  │  │  │  \
   min_pass_rate │  │  │  max_failed_cases
                 │  │  │  
        min_avg_score  max_average_latency_ms
                       │
                  max_total_cost_usd
                       ↓
         ┌──────────────────────────────┐
         │ Any Threshold Violated?      │
         └──────────────────────────────┘
            ↙ YES                 NO ↘
           /                         \
    ❌ GATE FAILS              ✅ GATE PASSES
    Collect all violations     Deploy approved
    Return reasons[] array     Return reasons=[]
           ↓                          ↓
    CI blocks deployment       CI continues
    (exit 1)                   (exit 0)
```

---

## 8. Custom Evaluator Anatomy

```
┌────────────────────────────────────────────────────────────────┐
│ WRITING A CUSTOM EVALUATOR                                     │
└────────────────────────────────────────────────────────────────┘

def my_groundedness_check(context: EvaluationContext) -> Score:
    """
    Input: EvaluationContext
      ├─ context.case         TestCase (what we expected)
      ├─ context.sample       EvaluationSample (what agent did)
      │  ├─ output: str       Agent's response
      │  └─ trace: EvalTrace  Full execution trace
      │     ├─ spans[]        Tool calls
      │     │  ├─ tool_name
      │     │  └─ attributes
      │     ├─ total_latency_ms
      │     ├─ estimated_cost_usd
      │     └─ metadata       Custom data
      └─ context.config       EvaluatorConfig (scorer params)
    
    Logic:
    1. Extract tool results from trace.spans
    2. Extract claims from agent output
    3. Check if each claim is grounded
    
    Output: Score
      ├─ name: str            "groundedness"
      ├─ value: float          0.0 to 1.0
      ├─ passed: bool          True/False
      ├─ explanation: str      Why it passed/failed
      └─ evaluator_type: str   "business_rule"
    
    Register:
    registry = default_registry()
    registry.register(
        BusinessRuleEvaluator("groundedness", my_groundedness_check)
    )
    
    Use:
    TestCase(..., evaluators=[
        EvaluatorConfig(name="groundedness", threshold=0.9)
    ])
```

---

## Summary

This architecture enables:

1. **Separation of Concerns**
   - TestCases define expectations (declarative)
   - Agents implement logic (imperative)
   - Evaluators judge independently (pluggable)

2. **Composability**
   - Mix built-in + custom scorers
   - Adapt any trace format to EvalTrace
   - Chain evaluations into CI gates

3. **Transparency**
   - Every score has an explanation
   - Every gate decision shows reasons
   - Full audit trail of what passed/failed

4. **Production Readiness**
   - Latency/cost tracking
   - Release gates for CI/CD
   - Fail-safe defaults (never hides missing data)
