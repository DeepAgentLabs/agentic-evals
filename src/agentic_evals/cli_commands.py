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

from agentic_evals.evaluators import EvaluatorRegistry
from agentic_evals.formatting import render_gate, render_report
from agentic_evals.gate import GateConfig, evaluate_gate
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

    pack = subparsers.add_parser("pack", help="discover built-in runnable packs")
    commands = pack.add_subparsers(dest="pack_command", required=True)
    commands.add_parser("list", help="list built-in pack names")
    show = commands.add_parser("show", help="print a pack as JSON")
    show.add_argument("name")
    show.add_argument("--suite", action="store_true", help="emit only its runnable TestSuite")
    show.add_argument("--out", help="output file (default: stdout)")


def execute(args: argparse.Namespace) -> int:
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
        payload = json.loads(Path(args.report).read_text(encoding="utf-8"))
        Draft202012Validator(report_schema()).validate(payload)
        report = EvaluationReport.model_validate(payload)
        if report.schema_version != "1.0":
            raise ValueError(f"unsupported report schema_version: {report.schema_version}")
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
