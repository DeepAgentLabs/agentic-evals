"""A standalone, framework-agnostic evaluation and scoring engine.

Score whatever trace-shaped data you give it (see `EvalTrace`/`EvalSpan`) —
this package has no dependency on any specific tracing/observability tool.
Extracted from AgenticLens's evaluation module (github.com/DeepAgentLabs/agenticlens).
"""

from agentic_evals.evaluators import (
    BusinessRuleEvaluator,
    CallableEvaluator,
    EvaluationContext,
    Evaluator,
    EvaluatorRegistry,
    LLMJudgeEvaluator,
)
from agentic_evals.gate import GateConfig, GateDecision, evaluate_gate
from agentic_evals.models import (
    CaseEvaluation,
    EvalSpan,
    EvalTrace,
    EvaluationReport,
    EvaluationSample,
    EvaluationSummary,
    EvaluatorConfig,
    HTTPTarget,
    LiveTarget,
    PythonTarget,
    Score,
    TestCase,
    TestSuite,
)
from agentic_evals.runner import (
    evaluate_suite,
    load_samples,
    load_suite,
    run_live_suite,
)

__version__ = "0.1.0"

__all__ = [
    "BusinessRuleEvaluator",
    "CallableEvaluator",
    "CaseEvaluation",
    "EvalSpan",
    "EvalTrace",
    "EvaluationContext",
    "EvaluationReport",
    "EvaluationSample",
    "EvaluationSummary",
    "Evaluator",
    "EvaluatorConfig",
    "EvaluatorRegistry",
    "GateConfig",
    "GateDecision",
    "HTTPTarget",
    "LLMJudgeEvaluator",
    "LiveTarget",
    "PythonTarget",
    "Score",
    "TestCase",
    "TestSuite",
    "__version__",
    "evaluate_gate",
    "evaluate_suite",
    "load_samples",
    "load_suite",
    "run_live_suite",
]
