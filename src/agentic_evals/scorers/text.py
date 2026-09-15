"""Deterministic, provider-neutral text scorers -- no LLM or network calls."""

import json
import math
from typing import Any

from agentic_evals.evaluators import EvaluationContext
from agentic_evals.models import Score


def _require_expected_output(context: EvaluationContext, scorer_name: str) -> str:
    expected = context.case.expected_output
    if expected is None:
        raise ValueError(f"{scorer_name} requires the test case to set expected_output")
    return expected


def _require_reference_text(context: EvaluationContext, scorer_name: str) -> str:
    """Reference text for a graded (non-exact) comparison.

    Prefers `EvaluatorConfig.config["reference"]` over `case.expected_output`
    so a near-miss scorer can be used *without* also triggering
    `evaluate_suite`'s hardcoded strict exact-match check, which fires
    whenever `expected_output` is set. Falls back to `expected_output` for
    the common case where a case has only this one criterion.
    """
    reference = context.config.config.get("reference") or context.case.expected_output
    if reference is None:
        raise ValueError(
            f"{scorer_name} requires either 'reference' in EvaluatorConfig.config "
            "or the test case to set expected_output"
        )
    return str(reference)


def exact_match(context: EvaluationContext) -> Score:
    expected = _require_expected_output(context, "exact_match")
    passed = context.sample.output.strip() == expected.strip()
    return Score(
        name="exact_match",
        value=float(passed),
        passed=passed,
        explanation="Output exactly matches the reference."
        if passed
        else "Output does not exactly match the reference.",
    )


def contains_all(context: EvaluationContext) -> Score:
    expected = context.case.expected_contains
    if not expected:
        raise ValueError("contains_all requires the test case to set expected_contains")
    output = context.sample.output.casefold()
    missing = [item for item in expected if item.casefold() not in output]
    passed = not missing
    return Score(
        name="contains_all",
        value=float(passed),
        passed=passed,
        explanation="Output contains every required substring."
        if passed
        else f"Output is missing required substrings: {missing}.",
    )


def contains_any(context: EvaluationContext) -> Score:
    expected = context.case.expected_contains
    if not expected:
        raise ValueError("contains_any requires the test case to set expected_contains")
    output = context.sample.output.casefold()
    found = [item for item in expected if item.casefold() in output]
    passed = bool(found)
    return Score(
        name="contains_any",
        value=float(passed),
        passed=passed,
        explanation=f"Output contains {found}."
        if passed
        else f"Output contains none of {expected}.",
    )


def _levenshtein_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i] + [0] * len(b)
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            current[j] = min(
                previous[j] + 1,  # deletion
                current[j - 1] + 1,  # insertion
                previous[j - 1] + cost,  # substitution
            )
        previous = current
    return previous[-1]


def levenshtein_similarity(context: EvaluationContext) -> Score:
    reference = _require_reference_text(context, "levenshtein_similarity").strip()
    output = context.sample.output.strip()
    distance = _levenshtein_distance(output, reference)
    longest = max(len(output), len(reference), 1)
    similarity = 1.0 - (distance / longest)
    passed = similarity >= context.config.threshold
    return Score(
        name="levenshtein_similarity",
        value=similarity,
        passed=passed,
        explanation=(
            f"Levenshtein similarity {similarity:.3f} "
            f"(edit distance {distance} over {longest} chars)."
        ),
    )


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("embedding vectors must be the same length")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embedding_similarity(context: EvaluationContext) -> Score:
    """Cosine similarity between the output and reference embeddings.

    This package never calls an embedding API itself -- pass an
    `embed_fn: Callable[[str], list[float]]` in `EvaluatorConfig.config`
    (the same provider-neutral pattern `LLMJudgeEvaluator` uses for model
    calls). Cosine similarity is rescaled from [-1, 1] to [0, 1] to fit
    `Score.value`'s range; the raw value is kept in `Score.metadata`.
    """
    expected = _require_reference_text(context, "embedding_similarity")
    embed_fn = context.config.config.get("embed_fn")
    if embed_fn is None or not callable(embed_fn):
        raise ValueError(
            "embedding_similarity requires an 'embed_fn' callable (text -> vector) "
            "in EvaluatorConfig.config; this package makes no embedding calls itself"
        )
    output_vector = embed_fn(context.sample.output)
    reference_vector = embed_fn(expected)
    raw_similarity = _cosine_similarity(output_vector, reference_vector)
    scaled = (raw_similarity + 1.0) / 2.0
    passed = scaled >= context.config.threshold
    return Score(
        name="embedding_similarity",
        value=scaled,
        passed=passed,
        explanation=f"Cosine similarity {raw_similarity:.3f} (scaled to {scaled:.3f}).",
        metadata={"raw_cosine_similarity": raw_similarity},
    )


def valid_json(context: EvaluationContext) -> Score:
    try:
        json.loads(context.sample.output)
    except ValueError as exc:
        return Score(
            name="valid_json",
            value=0.0,
            passed=False,
            explanation=f"Output is not valid JSON: {exc}.",
        )
    return Score(name="valid_json", value=1.0, passed=True, explanation="Output is valid JSON.")


def _first_json_difference(expected: Any, actual: Any, path: str = "$") -> str | None:
    numeric = (int, float)
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in actual:
                return f"{path}.{key}: missing from output"
            if key not in expected:
                return f"{path}.{key}: unexpected in output"
            difference = _first_json_difference(expected[key], actual[key], f"{path}.{key}")
            if difference:
                return difference
        return None
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            return f"{path}: length mismatch ({len(expected)} expected, {len(actual)} in output)"
        for index, (item_expected, item_actual) in enumerate(zip(expected, actual, strict=True)):
            difference = _first_json_difference(item_expected, item_actual, f"{path}[{index}]")
            if difference:
                return difference
        return None
    if isinstance(expected, numeric) and isinstance(actual, numeric):
        if expected != actual:
            return f"{path}: value mismatch ({expected!r} expected, {actual!r} in output)"
        return None
    if type(expected) is not type(actual) or expected != actual:
        return f"{path}: value mismatch ({expected!r} expected, {actual!r} in output)"
    return None


def json_diff(context: EvaluationContext) -> Score:
    """Structural diff of the output against `expected_output`, both parsed as JSON."""
    expected_raw = _require_reference_text(context, "json_diff")
    try:
        actual_value = json.loads(context.sample.output)
    except ValueError as exc:
        return Score(
            name="json_diff",
            value=0.0,
            passed=False,
            explanation=f"Output is not valid JSON: {exc}.",
        )
    try:
        expected_value = json.loads(expected_raw)
    except ValueError as exc:
        raise ValueError(f"json_diff's expected_output is not valid JSON: {exc}") from exc
    difference = _first_json_difference(expected_value, actual_value)
    passed = difference is None
    return Score(
        name="json_diff",
        value=float(passed),
        passed=passed,
        explanation="Output matches the expected JSON structure."
        if passed
        else f"First difference: {difference}.",
    )


def numeric_diff(context: EvaluationContext) -> Score:
    """Tolerance-based numeric comparison; configure via `rel_tol`/`abs_tol` in config."""
    expected_raw = _require_reference_text(context, "numeric_diff")
    try:
        actual_value = float(context.sample.output.strip())
    except ValueError as exc:
        return Score(
            name="numeric_diff",
            value=0.0,
            passed=False,
            explanation=f"Output is not numeric: {exc}.",
        )
    try:
        expected_value = float(expected_raw.strip())
    except ValueError as exc:
        raise ValueError(f"numeric_diff's expected_output is not numeric: {exc}") from exc
    rel_tol = context.config.config.get("rel_tol", 1e-6)
    abs_tol = context.config.config.get("abs_tol", 1e-9)
    passed = math.isclose(actual_value, expected_value, rel_tol=rel_tol, abs_tol=abs_tol)
    difference = abs(actual_value - expected_value)
    denominator = max(abs(expected_value), 1e-9)
    similarity = max(0.0, 1.0 - min(1.0, difference / denominator))
    return Score(
        name="numeric_diff",
        value=similarity,
        passed=passed,
        explanation=(
            f"Output {actual_value} vs expected {expected_value} "
            f"(absolute difference {difference:.6g})."
        ),
    )
