"""Export the worked voice dataset for the declarative CLI (no network required).

Run from this directory: python export_cli.py
"""

import json
from pathlib import Path

from run_evals import build_test_suite, run_agent_and_create_samples


def main() -> None:
    suite = build_test_suite()
    destination = Path("cli-output")
    destination.mkdir(exist_ok=True)
    (destination / "suite.json").write_text(
        suite.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    (destination / "samples.jsonl").write_text(
        "".join(sample.model_dump_json() + "\n" for sample in run_agent_and_create_samples(suite)),
        encoding="utf-8",
    )
    (destination / "gate.json").write_text(json.dumps({"min_pass_rate": 1.0}), encoding="utf-8")


if __name__ == "__main__":
    main()
