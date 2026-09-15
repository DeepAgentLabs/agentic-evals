"""Load and run a built-in eval pack.

Run: python examples/eval_pack.py
"""

from agentic_evals import (
    EvalSpan,
    EvalTrace,
    EvaluationSample,
    default_registry,
    evaluate_suite,
    list_builtin_packs,
    load_builtin_pack,
)


def main() -> None:
    print(f"Available built-in packs: {list_builtin_packs()}\n")

    pack = load_builtin_pack("tool-use-correctness")
    print(f"Loaded pack: {pack.name!r} -- {pack.description.strip()}")

    sample = EvaluationSample(
        case_id="refund-status-lookup",
        output="Your refund is on its way.",
        trace=EvalTrace(spans=[EvalSpan(tool_name="lookup_refund")]),
    )

    report = evaluate_suite(pack.to_suite(), [sample], registry=default_registry())
    print(f"Pass rate: {report.summary.pass_rate:.0%}")


if __name__ == "__main__":
    main()
