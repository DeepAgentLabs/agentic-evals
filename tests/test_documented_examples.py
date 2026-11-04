"""Every shipped example is registered and exercised offline in CI."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "examples/manifest.json").read_text())


def test_example_manifest_is_complete() -> None:
    assert set(MANIFEST) == {str(p.relative_to(ROOT)) for p in (ROOT / "examples").rglob("*.py")}


@pytest.mark.parametrize("relative,entry", MANIFEST.items())
def test_documented_example(relative, entry, tmp_path: Path) -> None:
    if entry["extra"] == "integrity" and importlib.util.find_spec("agenticlens") is None:
        pytest.skip("Executed in the required integrity CI job")
    # Generators write next to their script: isolate the complete example tree.
    shutil.copytree(ROOT / "examples", tmp_path / "examples")
    path = tmp_path / relative
    if entry["mode"] == "import":
        command = [sys.executable, "-c", "import registry"]
        cwd = path.parent
    else:
        command = [sys.executable, str(path)]
        cwd = tmp_path
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=60)
    assert result.returncode == entry["exit_code"], result.stdout + result.stderr
