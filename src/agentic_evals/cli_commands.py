"""Declarative CLI commands, composed from the public evaluation APIs."""

import argparse
import contextlib
import importlib
import json
import sys
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from agentic_evals.aios import attach_aios_evidence, to_aios_evidence
from agentic_evals.evaluators import EvaluatorRegistry
from agentic_evals.formatting import render_gate, render_report
from agentic_evals.gate import GateConfig, GateDecision, evaluate_gate
from agentic_evals.models import EvaluationReport, HTTPTarget, PythonTarget
from agentic_evals.packs import EvalPack, list_builtin_packs
from agentic_evals.reliability import RetryPolicy
from agentic_evals.report_contract import report_schema
from agentic_evals.runner import evaluate_suite, load_samples, load_suite, run_live_suite
from agentic_evals.scorers import default_registry


@contextlib.contextmanager
def _local_imports() -> Iterator[None]:
    previous = sys.path[:]
    sys.path.insert(0, str(Path.cwd()))
    try:
        yield
    finally:
        sys.path[:] = previous


def _load_registry(reference: str | None) -> EvaluatorRegistry:
    if reference is None:
        return default_registry()
    module_name, separator, attribute = reference.partition(":")
    # `--registry module` uses its build_registry() factory. Explicit attributes
    # may be factories or registry instances. The caller trusts imported code.
    module = importlib.import_module(module_name)
    value = getattr(module, attribute if separator else "build_registry")
    registry = value() if callable(value) else value
    if not isinstance(registry, EvaluatorRegistry):
        raise ValueError("--registry must resolve to an EvaluatorRegistry or its factory")
    return registry


def _data(path: str) -> Any:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    return json.loads(text) if file.suffix.lower() == ".json" else yaml.safe_load(text)


def _emit(text: str, destination: str | None) -> None:
    if destination and destination != "-":
        Path(destination).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _load_report(path: str) -> EvaluationReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    Draft202012Validator(report_schema()).validate(payload)
    report = EvaluationReport.model_validate(payload)
    if report.schema_version != "1.0":
        raise ValueError(f"unsupported report schema_version: {report.schema_version}")
    return report


def _output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", help="output file (default: stdout; '-' also means stdout)")
    parser.add_argument("--format", choices=("json", "junit", "markdown"), default="json")


def add_commands(subparsers: Any) -> None:
    evaluate = subparsers.add_parser("evaluate", help="evaluate saved samples against a suite")
    evaluate.add_argument("suite", help="YAML or JSON TestSuite")
    evaluate.add_argument("samples", help="JSON, JSONL or YAML evaluation samples")
    evaluate.add_argument("--registry", help="trusted module[:factory_or_registry]")
    _output_options(evaluate)

    live = subparsers.add_parser("live", help="evaluate a trusted Python or HTTP target")
    live.add_argument("suite", help="YAML or JSON TestSuite")
    live.add_argument(
        "--target", required=True, help="module:function, path.py:function or HTTP URL"
    )
    live.add_argument("--max-workers", type=int, default=1)
    live.add_argument(
        "--timeout-seconds",
        type=float,
        help="per-call timeout (HTTP default: 30; Python targets: none unless set)",
    )
    live.add_argument(
        "--retries",
        type=int,
        default=0,
        help="extra attempts for a target call that raises or times out (default: 0)",
    )
    live.add_argument(
        "--retry-backoff",
        type=float,
        default=0.0,
        help="seconds before the first retry, doubling after each (default: 0)",
    )
    live.add_argument("--registry", help="trusted module[:factory_or_registry]")
    _output_options(live)

    gate = subparsers.add_parser("gate", help="apply release thresholds to a saved JSON report")
    gate.add_argument("report")
    gate.add_argument("--config", help="YAML or JSON GateConfig (default: every case must pass)")
    _output_options(gate)

    aios = subparsers.add_parser("aios", help="export AI Operations Specification evidence")
    aios_commands = aios.add_subparsers(dest="aios_command", required=True)
    export = aios_commands.add_parser(
        "export", help="export a saved report as AIOS v0.4-draft evaluation evidence"
    )
    export.add_argument("report", help="native JSON EvaluationReport")
    export.add_argument("--run-id", help="AIOS Run ID (default: the --run artifact's id)")
    export.add_argument("--run", help="AIOS run artifact to merge the evidence into")
    export.add_argument("--targets", help="YAML or JSON mapping of case ID to evaluates target(s)")
    export.add_argument(
        "--default-target",
        help="target for unmapped cases: a step ID, or a JSON reference or list of references",
    )
    export.add_argument(
        "--default-run",
        action="store_true",
        help="unmapped cases evaluate the whole Run",
    )
    export.add_argument("--gate", help="saved JSON GateDecision to export as release readiness")
    export.add_argument(
        "--allow-unmapped",
        action="store_true",
        help="leave out cases without a target instead of failing (they are listed on stderr)",
    )
    export.add_argument("--id-prefix", help="evidence ID prefix (default: <run>:evals:<suite>)")
    export.add_argument("--out", help="output file (default: stdout; '-' also means stdout)")

    pack = subparsers.add_parser("pack", help="discover built-in runnable packs")
    commands = pack.add_subparsers(dest="pack_command", required=True)
    commands.add_parser("list", help="list built-in pack names")
    show = commands.add_parser("show", help="print a pack as JSON")
    show.add_argument("name")
    show.add_argument("--suite", action="store_true", help="emit only its runnable TestSuite")
    show.add_argument("--out", help="output file (default: stdout)")


def _default_target(args: argparse.Namespace, run_id: str) -> Any:
    if args.default_run and args.default_target:
        raise ValueError("use either --default-target or --default-run, not both")
    if args.default_run:
        return {"id": run_id, "type": "run"}
    value = args.default_target
    if value is not None and value.lstrip().startswith(("{", "[")):
        return json.loads(value)
    return value


def _export_aios(args: argparse.Namespace) -> int:
    report = _load_report(args.report)
    run = json.loads(Path(args.run).read_text(encoding="utf-8")) if args.run else None
    run_id = args.run_id or (run.get("id") if isinstance(run, dict) else None)
    if not run_id:
        raise ValueError("pass --run-id, or --run with an AIOS run artifact")
    targets = _data(args.targets) if args.targets else None
    if targets is not None and not isinstance(targets, dict):
        raise ValueError("--targets must map case IDs to targets")
    gate = None
    if args.gate:
        gate = GateDecision.model_validate_json(Path(args.gate).read_text(encoding="utf-8"))
    export = to_aios_evidence(
        report,
        run_id=run_id,
        targets=targets,
        default_target=_default_target(args, run_id),
        gate=gate,
        allow_unmapped=args.allow_unmapped,
        id_prefix=args.id_prefix,
    )
    if export.unmapped_cases:
        print(
            f"agentic-evals: not exported (no target): {', '.join(export.unmapped_cases)}",
            file=sys.stderr,
        )
    if run is not None:
        text = json.dumps(attach_aios_evidence(run, export), indent=2)
    else:
        text = export.model_dump_json(indent=2)
    _emit(text + "\n", args.out)
    return 0


def execute(args: argparse.Namespace) -> int:
    if args.command == "aios":
        return _export_aios(args)
    if args.command == "pack":
        if args.pack_command == "list":
            print("\n".join(list_builtin_packs()))
        else:
            if args.name not in list_builtin_packs():
                raise ValueError(f"unknown built-in pack: {args.name!r}")
            resource = (
                files("agentic_evals.packs").joinpath("builtin").joinpath(f"{args.name}.yaml")
            )
            pack = EvalPack.model_validate(yaml.safe_load(resource.read_text(encoding="utf-8")))
            _emit((pack.suite if args.suite else pack).model_dump_json(indent=2) + "\n", args.out)
        return 0
    if args.command == "gate":
        report = _load_report(args.report)
        raw_config = _data(args.config) if args.config else {}
        if not isinstance(raw_config, dict):
            raise ValueError("gate config must be an object")
        unknown = raw_config.keys() - GateConfig.model_fields.keys()
        if unknown:
            raise ValueError(f"unknown gate config fields: {sorted(unknown)}")
        decision = evaluate_gate(report, GateConfig.model_validate(raw_config))
        _emit(render_gate(decision, args.format), args.out)
        return 0 if decision.passed else 1

    # A target or custom evaluator may print diagnostics: keep stdout parseable.
    with contextlib.redirect_stdout(sys.stderr), _local_imports():
        suite = load_suite(Path(args.suite))
        registry = _load_registry(args.registry)
        if args.command == "evaluate":
            report = evaluate_suite(suite, load_samples(Path(args.samples)), registry=registry)
        else:
            if args.retries < 0:
                raise ValueError("--retries must not be negative")
            timeout = (
                {} if args.timeout_seconds is None else {"timeout_seconds": args.timeout_seconds}
            )
            target = (
                HTTPTarget(url=args.target, **timeout)
                if args.target.startswith(("http://", "https://"))
                else PythonTarget(callable_path=args.target, **timeout)
            )
            retry = RetryPolicy(max_attempts=args.retries + 1, backoff_seconds=args.retry_backoff)
            report = run_live_suite(
                suite, target, registry=registry, max_workers=args.max_workers, retry=retry
            )
    _emit(render_report(report, args.format), args.out)
    # Evaluation writes evidence; the separate gate command decides release policy.
    return 0
