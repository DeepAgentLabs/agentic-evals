"""Trusted CLI registry for public synthetic fixtures only."""

from agentic_evals import ContainmentEvaluator, default_registry, lens_verifier

registry = default_registry()
registry.register(
    ContainmentEvaluator(
        verifier=lens_verifier({"example": b"synthetic-containment-example-key!"})
    ),
    replace=True,
)
