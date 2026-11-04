# Executable offline examples

Run from the repository root after `uv sync --extra dev`:

```bash
uv run python examples/quickstart.py
uv run python examples/llm_rubric_judge.py
uv run python examples/eval_pack.py
uv run python examples/async_live_target.py
uv run pytest tests/test_documented_examples.py tests/test_cli_examples.py
```

`manifest.json` lists every shipped Python example. CI fails for unregistered
scripts and runs each script in an isolated temporary example tree, preserving
checked-in artifacts. Judges are synthetic callbacks; no credentials are needed.
`capitals_eval.py` includes a deliberate wrong answer: direct execution registers
the eval; `agentic-evals run examples/` evaluates it and exits 1.

The required integrity CI job installs `integrity` and runs containment scripts,
including the registry import. The normal matrix runs all standalone examples.
CLI fixture tests cover passing and failing release gates and the voice example.
API fragments in the reference explain parameters and require the surrounding
objects; the complete runnable counterparts are linked here. Installation,
publishing and live provider commands are operator instructions, not offline
examples.

| Area | Runnable source |
| --- | --- |
| Declarative API, tools and scores | `quickstart.py`, `near_miss_similarity.py` |
| Quickstart API | `capitals_eval.py` |
| Rubrics, packs and skills | `llm_rubric_judge.py`, `eval_pack.py`; `tests/test_skills.py` validates playbook resources |
| Judge reliability and async live targets | `judge_reliability.py`, `async_live_target.py` |
| Reports and gates | `report-contract/generate.py`, `ci/` and `usecases/` |
| AIOS evidence | `aios/generate.py` |
| Authenticated containment | `containment/generate.py` (requires `integrity`) |

See [support and the sibling matrix](../docs/support-policy.md).
