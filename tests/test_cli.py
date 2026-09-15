from pathlib import Path

from agentic_evals import cli

PASSING_EVAL = """
from agentic_evals import Eval, equals

Eval(
    "passing",
    data=[{"input": "x", "expected": "x"}],
    task=lambda input: input,
    scores=[equals],
)
"""

FAILING_EVAL = """
from agentic_evals import Eval, equals

Eval(
    "failing",
    data=[{"input": "x", "expected": "y"}],
    task=lambda input: input,
    scores=[equals],
)
"""

NOT_AN_EVAL = """
x = 1 + 1
"""


def test_discover_finds_conventional_filenames(tmp_path: Path) -> None:
    (tmp_path / "foo_eval.py").write_text(PASSING_EVAL)
    (tmp_path / "eval_bar.py").write_text(PASSING_EVAL)
    (tmp_path / "baz.eval.py").write_text(PASSING_EVAL)
    (tmp_path / "unrelated.py").write_text(NOT_AN_EVAL)

    found = cli.discover([str(tmp_path)])
    names = {p.name for p in found}
    assert names == {"foo_eval.py", "eval_bar.py", "baz.eval.py"}


def test_discover_accepts_a_single_file(tmp_path: Path) -> None:
    target = tmp_path / "whatever_name.py"
    target.write_text(PASSING_EVAL)

    found = cli.discover([str(target)])
    assert found == [target.resolve()]


def test_run_exits_zero_when_all_evals_pass(tmp_path: Path) -> None:
    (tmp_path / "good_eval.py").write_text(PASSING_EVAL)
    assert cli.run([str(tmp_path)]) == 0


def test_run_exits_nonzero_when_any_eval_fails(tmp_path: Path) -> None:
    (tmp_path / "good_eval.py").write_text(PASSING_EVAL)
    (tmp_path / "bad_eval.py").write_text(FAILING_EVAL)
    assert cli.run([str(tmp_path)]) == 1


def test_run_exits_nonzero_when_nothing_found(tmp_path: Path) -> None:
    assert cli.run([str(tmp_path)]) == 1


def test_run_exits_nonzero_when_files_call_no_eval(tmp_path: Path) -> None:
    (tmp_path / "quiet_eval.py").write_text(NOT_AN_EVAL)
    assert cli.run([str(tmp_path)]) == 1


def test_main_run_subcommand(tmp_path: Path) -> None:
    (tmp_path / "good_eval.py").write_text(PASSING_EVAL)
    assert cli.main(["run", str(tmp_path)]) == 0
