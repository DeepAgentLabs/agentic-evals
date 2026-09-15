"""`agentic-evals run` -- discover and run every eval file in a directory.

An eval file is any `*_eval.py`, `eval_*.py`, or `*.eval.py` module that
calls `Eval(...)` at module level (the same convention `pytest` uses for
`test_*.py`, just for evals instead of assertions). This command imports
each one, lets its own `Eval()` calls print their own report, and exits
non-zero if any of them failed a case -- so it drops into CI exactly the
way `pytest` or `braintrust eval` do:

    agentic-evals run                 # everything under the current directory
    agentic-evals run evals/          # a specific directory
    agentic-evals run evals/foo_eval.py

No config file, no project setup -- `pip install agentic-evals` and this
command finds anything the convention names.
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

from agentic_evals import simple

DEFAULT_PATTERNS = ("*_eval.py", "eval_*.py", "*.eval.py")


def discover(paths: list[str], patterns: tuple[str, ...] = DEFAULT_PATTERNS) -> list[Path]:
    """Find eval files under `paths` (files are taken as-is; directories are searched)."""
    roots = [Path(p) for p in paths] or [Path()]
    found: set[Path] = set()
    for root in roots:
        if not root.exists():
            print(f"agentic-evals: path not found: {root}", file=sys.stderr)
            continue
        if root.is_file():
            found.add(root.resolve())
            continue
        for pattern in patterns:
            found.update(p.resolve() for p in root.rglob(pattern))
    return sorted(found)


def run(paths: list[str]) -> int:
    files = discover(paths)
    if not files:
        print(
            f"agentic-evals: no eval files found (looked for {', '.join(DEFAULT_PATTERNS)})",
            file=sys.stderr,
        )
        return 1

    all_results: list[simple.EvalResult] = []
    for file in files:
        before = len(simple._collected)
        try:
            runpy.run_path(str(file), run_name="__main__")
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller, not re-raised
            print(f"agentic-evals: {file} raised {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        all_results.extend(simple._collected[before:])

    if not all_results:
        print(
            "agentic-evals: discovered eval file(s) but none called Eval(...)",
            file=sys.stderr,
        )
        return 1

    failed = [r for r in all_results if not r]
    passed = len(all_results) - len(failed)
    print(f"{passed}/{len(all_results)} evals passed across {len(files)} file(s)")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentic-evals")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="discover and run eval files")
    run_parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="files or directories to search (default: current directory)",
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        return run(args.paths)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
