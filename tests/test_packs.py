import pytest

from agentic_evals import (
    FACTUALITY,
    EvalSpan,
    EvalTrace,
    EvaluationSample,
    EvaluatorRegistry,
    LLMRubricEvaluator,
    default_registry,
    evaluate_suite,
    list_builtin_packs,
    load_builtin_pack,
)


def test_list_builtin_packs_includes_the_shipped_packs() -> None:
    names = list_builtin_packs()
    assert names == tuple(sorted(names))
    assert set(names) >= {"tool-use-correctness", "factual-qa", "json-output-contract"}


def test_load_builtin_pack_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="unknown builtin eval pack"):
        load_builtin_pack("does-not-exist")


def test_tool_use_correctness_pack_runs_end_to_end() -> None:
    pack = load_builtin_pack("tool-use-correctness")
    sample = EvaluationSample(
        case_id="refund-status-lookup",
        output="Your refund is on its way.",
        trace=EvalTrace(spans=[EvalSpan(tool_name="lookup_refund")]),
    )

    report = evaluate_suite(pack.to_suite(), [sample], registry=default_registry())

    assert report.summary.pass_rate == 1.0


def test_json_output_contract_pack_runs_end_to_end() -> None:
    pack = load_builtin_pack("json-output-contract")
    sample = EvaluationSample(
        case_id="structured-answer",
        output='{"answer": "42", "confidence": 0.9}',
        trace=EvalTrace(),
    )

    report = evaluate_suite(pack.to_suite(), [sample], registry=default_registry())

    assert report.summary.pass_rate == 1.0


def test_factual_qa_pack_requires_a_registry_with_factuality_registered() -> None:
    with pytest.raises(ValueError, match="factuality"):
        load_builtin_pack("factual-qa")  # default_registry() has no LLM-judge scorers

    registry = EvaluatorRegistry()
    registry.register(
        LLMRubricEvaluator("factuality", FACTUALITY, complete_fn=lambda prompt: "(A)")
    )
    pack = load_builtin_pack("factual-qa", registry=registry)

    sample = EvaluationSample(
        case_id="capital-of-france",
        output="Paris",
        trace=EvalTrace(),
    )
    report = evaluate_suite(pack.to_suite(), [sample], registry=registry)

    assert report.summary.pass_rate == 1.0
