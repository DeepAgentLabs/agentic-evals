from pathlib import Path

from agentic_evals.evaluators import EvaluatorRegistry
from agentic_evals.packs.loader import EvalPack, load_pack

_BUILTIN_DIR = Path(__file__).parent / "builtin"


def list_builtin_packs() -> tuple[str, ...]:
    return tuple(sorted(path.stem for path in _BUILTIN_DIR.glob("*.yaml")))


def load_builtin_pack(name: str, *, registry: EvaluatorRegistry | None = None) -> EvalPack:
    path = _BUILTIN_DIR / f"{name}.yaml"
    if not path.is_file():
        raise ValueError(f"unknown builtin eval pack {name!r}; available: {list_builtin_packs()}")
    return load_pack(path, registry=registry)
