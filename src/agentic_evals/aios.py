"""Export evaluation results as AI Operations Specification v0.4-draft evidence.

The native `EvaluationReport` stays this package's own report format. This
module derives AIOS `evaluation` evidence objects from it so the results can
travel with a Run artifact produced elsewhere (for example by
`agentic_chaos.export.to_aios_run` or an AgenticLens trace export):

- every score becomes one `evaluation` evidence object. Its `attributes` carry
  the criterion (`Score.metric`), the method (evaluator, version and type),
  the result and the score value
- every case also gets one case-verdict evaluation for `CaseEvaluation.passed`
- a case with no observed output (no sample supplied, or a live target that
  timed out or errored) is not exported: there is nothing in the Run it could
  have judged, and its `sample_available`/`target_call` score describes the
  evaluation harness. It is listed in `unobserved_cases` instead
- an optional `GateDecision` becomes one release-readiness evaluation of the Run
- each evaluation `evaluates` the Run objects the caller maps its case to, and
  emits `aiops.evaluation.completed`, or `aiops.evaluation.failed` when the
  judge could not deliver a verdict

The export states only what the report records. A skipped score is exported
with result `skipped` and no score value, never as a pass. A judgment the judge
could not deliver is `unavailable`. A case with no target mapping is reported
and never attached to a guessed target. A report exported with no mapping at
all raises `AIOSExportError` instead of producing orphaned evidence, which would
break rule `AIOS-0.4-P08` (every Evaluation has an `evaluates` target).

Evals does not validate AIOS artifacts. Validate the merged Run with
`deep-agentic-core-mcp`'s `spec.validate_artifact`, which applies the schemas
and semantic rules published by `ai-operations-spec`.
"""

from __future__ import annotations

import copy
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_core import to_jsonable_python

from agentic_evals._version import __version__
from agentic_evals.gate import GateDecision
from agentic_evals.models import CaseEvaluation, EvaluationReport, Score

SPEC_VERSION = "0.4-draft"
EXTENSION_NAME = "io.deepagentlabs.agentic-evals"

# The AIOS v0.4 reference vocabulary (`common.schema.json#/$defs/reference`).
REFERENCE_TYPES = frozenset(
    {
        "workflow",
        "run",
        "request",
        "step",
        "agent",
        "model_interaction",
        "prompt",
        "context",
        "tool_invocation",
        "rag_retrieval",
        "memory_operation",
        "evaluation",
        "safety_signal",
        "reliability_event",
        "incident",
    }
)

# Which Run artifact array holds each object type `attach_aios_evidence` resolves.
_GROUP_TYPES = {"requests": "request", "steps": "step", "agents": "agent", "incidents": "incident"}

Result = Literal["passed", "failed", "skipped", "unavailable"]
TargetSpec = str | Mapping[str, Any]


class AIOSExportError(ValueError):
    """Raised when a report cannot be exported without guessing or orphaning evidence."""


class AIOSEvidenceExport(BaseModel):
    """AIOS evidence derived from one report, ready to merge into a Run artifact.

    `evidence`, `relationships` and `events` are AIOS v0.4-draft objects.
    `unmapped_cases` lists the cases that had no target (only possible with
    `allow_unmapped=True`); none of their scores were exported.
    `unobserved_cases` lists the cases with no observed output (no sample, or
    a live target that timed out or errored), which are never exported. The counts
    say how many exported evaluations were skipped or unavailable, so a
    reader never mistakes them for passes.
    """

    spec_version: str = SPEC_VERSION
    run_id: str
    suite_name: str
    suite_version: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    unmapped_cases: list[str] = Field(default_factory=list)
    unobserved_cases: list[str] = Field(default_factory=list)
    exported_cases: int = 0
    skipped_scores: int = 0
    unavailable_scores: int = 0


def to_aios_evidence(
    report: EvaluationReport | Mapping[str, Any],
    *,
    run_id: str,
    targets: Mapping[str, TargetSpec | Sequence[TargetSpec]] | None = None,
    default_target: TargetSpec | Sequence[TargetSpec] | None = None,
    gate: GateDecision | Mapping[str, Any] | None = None,
    allow_unmapped: bool = False,
    id_prefix: str | None = None,
    occurred_at: datetime | None = None,
) -> AIOSEvidenceExport:
    """Return the report's scores as AIOS `evaluation` evidence for Run `run_id`.

    `targets` maps a case ID to what that case judged: a Step ID string, an
    AIOS reference such as `{"id": "model-1", "type": "model_interaction"}`
    (`"external": True` for an object outside the Run), or a list of them.
    `default_target` applies to cases `targets` does not name; pass
    `{"id": run_id, "type": "run"}` when every case judged the whole Run.

    Raises `AIOSExportError` when neither mapping is given, when `targets`
    names a case the report does not contain, or when a case has no target,
    unless `allow_unmapped=True`, which leaves such cases out and lists them in
    `unmapped_cases`. Cases with no observed output need no mapping; they are
    listed in `unobserved_cases` and not exported.

    `gate`, when given, adds one release-readiness evaluation of the Run.
    Evidence IDs start with `id_prefix` (default `"<run_id>:evals:<suite>"`);
    pass a distinct prefix to attach two exports of the same suite to one Run.
    Events use `occurred_at`, defaulting to the report's `created_at`.
    """
    if not isinstance(report, EvaluationReport):
        report = EvaluationReport.model_validate(report)
    if gate is not None and not isinstance(gate, GateDecision):
        gate = GateDecision.model_validate(gate)
    if not isinstance(run_id, str) or not run_id.strip():
        raise AIOSExportError("run_id must be a non-blank string naming the AIOS Run")
    targets = dict(targets or {})
    if not targets and default_target is None:
        raise AIOSExportError(
            "no target mapping: pass targets={case_id: step_id, ...} or a default_target; "
            "an evaluation without an `evaluates` target would break AIOS-0.4-P08"
        )
    case_ids = {case.case_id for case in report.cases}
    unknown = sorted(set(targets) - case_ids)
    if unknown:
        raise AIOSExportError(f"targets name cases that are not in the report: {unknown}")

    default_refs = [] if default_target is None else _references(default_target, "default_target")
    case_refs: dict[str, list[dict[str, Any]]] = {}
    unmapped: list[str] = []
    unobserved = [case.case_id for case in report.cases if not case.sample_available]
    for case in report.cases:
        if not case.sample_available:
            continue
        spec = targets.get(case.case_id)
        refs = default_refs if spec is None else _references(spec, f"targets[{case.case_id!r}]")
        if refs:
            case_refs[case.case_id] = refs
        else:
            unmapped.append(case.case_id)
    if unmapped and not allow_unmapped:
        raise AIOSExportError(
            f"cases without an evaluates target: {unmapped}; map them in targets, "
            "set default_target, or pass allow_unmapped=True to leave them out"
        )

    prefix = id_prefix or f"{run_id}:evals:{report.suite_name}"
    when = _timestamp(occurred_at or report.created_at)
    export = AIOSEvidenceExport(
        run_id=run_id,
        suite_name=report.suite_name,
        suite_version=report.suite_version,
        unmapped_cases=unmapped,
        unobserved_cases=unobserved,
    )
    for case in report.cases:
        if case.case_id not in case_refs:
            continue
        refs = case_refs[case.case_id]
        export.exported_cases += 1
        for index, score in enumerate(case.scores, start=1):
            result = _score_result(score)
            export.skipped_scores += result == "skipped"
            export.unavailable_scores += result == "unavailable"
            _add(
                export,
                f"{prefix}:{case.case_id}:score:{index}",
                f"{score.name} on {case.case_name}",
                result,
                _score_attributes(report, case, score, result),
                refs,
                when,
            )
        _add(
            export,
            f"{prefix}:{case.case_id}:case",
            f"case verdict for {case.case_name}",
            "passed" if case.passed else "failed",
            _case_attributes(report, case),
            refs,
            when,
        )
    if gate is not None:
        _add(
            export,
            f"{prefix}:gate",
            f"release gate for {report.suite_name}",
            "passed" if gate.passed else "failed",
            _gate_attributes(report, gate),
            [{"id": run_id, "type": "run"}],
            when,
        )
    return export


def attach_aios_evidence(
    run: Mapping[str, Any], export: AIOSEvidenceExport | Sequence[AIOSEvidenceExport]
) -> dict[str, Any]:
    """Return a copy of AIOS Run artifact `run` with the exported evidence merged in.

    The input is not modified. Raises `AIOSExportError` when `run` is not a
    v0.4-draft Run, when its `id` differs from the export's `run_id`, when a
    non-external `evaluates` target is not an object of the declared type in
    the Run, or when an evidence, relationship or event ID is repeated within
    an export or already taken.
    """
    exports = [export] if isinstance(export, AIOSEvidenceExport) else list(export)
    if run.get("artifact_type") != "run" or run.get("spec_version") != SPEC_VERSION:
        raise AIOSExportError(f"expected an AIOS {SPEC_VERSION} run artifact")
    merged = copy.deepcopy(dict(run))
    objects = _run_objects(merged)
    relationship_ids = {item.get("id") for item in merged.get("relationships", [])}
    event_ids = {item.get("event_id") for item in merged.get("events", [])}
    for item in exports:
        if item.run_id != merged.get("id"):
            raise AIOSExportError(
                f"export targets run {item.run_id!r} but the artifact is run {merged.get('id')!r}"
            )
        repeated = sorted(
            _repeated(evidence["id"] for evidence in item.evidence)
            | _repeated(rel["id"] for rel in item.relationships)
            | _repeated(event["event_id"] for event in item.events)
        )
        if repeated:
            raise AIOSExportError(f"IDs repeated within the export: {repeated}")
        new_objects = {evidence["id"]: "evaluation" for evidence in item.evidence}
        taken = sorted(set(new_objects) & set(objects))
        taken += sorted(
            {rel["id"] for rel in item.relationships} & relationship_ids
            | {event["event_id"] for event in item.events} & event_ids
        )
        if taken:
            raise AIOSExportError(f"IDs already present in the run: {taken}; set id_prefix")
        objects.update(new_objects)
        unresolved = [
            f"{rel['target']['id']} ({rel['target']['type']})"
            for rel in item.relationships
            if rel["target"].get("external") is not True
            and objects.get(rel["target"]["id"]) != rel["target"]["type"]
        ]
        if unresolved:
            raise AIOSExportError(
                f"evaluates targets not found in the run: {sorted(set(unresolved))}; "
                "fix the mapping or mark outside objects external"
            )
        merged.setdefault("evidence", []).extend(copy.deepcopy(item.evidence))
        merged.setdefault("relationships", []).extend(copy.deepcopy(item.relationships))
        merged.setdefault("events", []).extend(copy.deepcopy(item.events))
        relationship_ids.update(rel["id"] for rel in item.relationships)
        event_ids.update(event["event_id"] for event in item.events)
    return merged


def _references(spec: Any, where: str) -> list[dict[str, Any]]:
    if isinstance(spec, (str, Mapping)):
        items = [spec]
    elif isinstance(spec, Sequence):
        items = list(spec)
    else:
        raise AIOSExportError(f"{where} must be a target or a list of targets")
    refs = [_reference(item, where) for item in items]
    if not refs:
        raise AIOSExportError(f"{where} must name at least one target")
    return refs


def _reference(item: Any, where: str) -> dict[str, Any]:
    if isinstance(item, str):
        item = {"id": item, "type": "step"}
    if not isinstance(item, Mapping):
        raise AIOSExportError(f"{where}: a target is a step ID string or an AIOS reference")
    unknown = set(item) - {"id", "type", "external"}
    target_id, target_type = item.get("id"), item.get("type")
    if unknown or not isinstance(target_id, str) or not target_id.strip():
        raise AIOSExportError(f"{where}: a reference needs a non-blank id, type and no other keys")
    if target_type not in REFERENCE_TYPES:
        raise AIOSExportError(f"{where}: {target_type!r} is not an AIOS v0.4 reference type")
    external = item.get("external", False)
    if not isinstance(external, bool):
        raise AIOSExportError(f"{where}: external must be true or false, got {external!r}")
    ref: dict[str, Any] = {"id": target_id, "type": target_type}
    if external:
        ref["external"] = True
    return ref


def _score_result(score: Score) -> Result:
    if score.skipped:
        return "skipped"
    if score.metadata.get("judge_status") == "unavailable":
        return "unavailable"
    return "passed" if score.passed else "failed"


def _method(evaluator: str, version: str | None, evaluator_type: str) -> dict[str, Any]:
    return {"evaluator": evaluator, "evaluator_version": version, "evaluator_type": evaluator_type}


def _context(report: EvaluationReport, case: CaseEvaluation) -> dict[str, Any]:
    return {
        "suite_name": report.suite_name,
        "suite_version": report.suite_version,
        "case_id": case.case_id,
        "case_name": case.case_name,
        "trace_id": case.trace_id,
    }


def _score_attributes(
    report: EvaluationReport, case: CaseEvaluation, score: Score, result: Result
) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "criterion": score.metric,
        "method": _method(
            score.evaluator or score.name, score.evaluator_version, score.evaluator_type
        ),
        "result": result,
    }
    # A skipped or unavailable judgment has no score to report; 0.0 would read as a verdict.
    if result in ("passed", "failed"):
        attributes["score"] = score.value
    attributes.update(
        score_name=score.name,
        required=score.required,
        explanation=score.explanation,
        **_context(report, case),
    )
    if score.metadata:
        attributes["metadata"] = to_jsonable_python(score.metadata)
    return attributes


def _case_attributes(report: EvaluationReport, case: CaseEvaluation) -> dict[str, Any]:
    required = [score for score in case.scores if score.required and not score.skipped]
    attributes: dict[str, Any] = {
        "criterion": "case_verdict",
        "method": _method("agentic-evals.case", __version__, "aggregate"),
        "result": "passed" if case.passed else "failed",
        "required_scores": len(required),
        "failed_required_scores": sum(not score.passed for score in required),
        "sample_available": case.sample_available,
        **_context(report, case),
    }
    for field in ("target_status", "target_attempts", "target_error"):
        if getattr(case, field) is not None:
            attributes[field] = getattr(case, field)
    return attributes


def _gate_attributes(report: EvaluationReport, gate: GateDecision) -> dict[str, Any]:
    return {
        "criterion": "release_gate",
        "method": _method("agentic-evals.gate", __version__, "gate"),
        "result": "passed" if gate.passed else "failed",
        "reasons": list(gate.reasons),
        "observed": dict(gate.observed),
        "suite_name": report.suite_name,
        "suite_version": report.suite_version,
    }


def _add(
    export: AIOSEvidenceExport,
    evidence_id: str,
    name: str,
    result: Result,
    attributes: dict[str, Any],
    refs: list[dict[str, Any]],
    when: str,
) -> None:
    export.evidence.append(
        {
            "id": evidence_id,
            "type": "evaluation",
            "name": name,
            "status": result,
            "attributes": attributes,
            "extensions": {
                EXTENSION_NAME: {
                    "producer": "agentic-evals",
                    "producer_version": __version__,
                    "report_schema_version": "1.0",
                }
            },
        }
    )
    for index, ref in enumerate(refs, start=1):
        export.relationships.append(
            {
                "id": f"{evidence_id}:evaluates:{index}",
                "type": "evaluates",
                "source": {"id": evidence_id, "type": "evaluation"},
                "target": dict(ref),
            }
        )
    if result == "skipped":
        return  # Nothing was judged, so no evaluation lifecycle event occurred.
    # Evaluation events must identify method, criterion, target and result (AIOS v0.3).
    export.events.append(
        {
            "event_id": f"{evidence_id}:event",
            "event_name": (
                "aiops.evaluation.failed"
                if result == "unavailable"
                else "aiops.evaluation.completed"
            ),
            "occurred_at": when,
            "object_id": evidence_id,
            "object_type": "evaluation",
            "attributes": {
                "criterion": attributes["criterion"],
                "method": attributes["method"],
                "result": result,
                "targets": [ref["id"] for ref in refs],
            },
        }
    )


def _repeated(ids: Any) -> set[str]:
    return {value for value, count in Counter(ids).items() if count > 1}


def _run_objects(run: Mapping[str, Any]) -> dict[str, str]:
    objects: dict[str, str] = {str(run.get("id")): "run"}
    for key, object_type in _GROUP_TYPES.items():
        objects.update((item["id"], object_type) for item in run.get(key, []))
    for key in ("occurrences", "evidence"):
        objects.update((item["id"], item["type"]) for item in run.get(key, []))
    return objects


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
