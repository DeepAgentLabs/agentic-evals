# Contributing

Thanks for helping make `agentic-evals` better.

## Local setup

```bash
git clone https://github.com/DeepAgentLabs/agentic-evals.git
cd agentic-evals
uv sync --extra dev
```

Or without `uv`:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Development workflow

1. Create a focused branch from `main`.
2. Add or update tests with every behavior change.
3. Add or update an `examples/` script when a public API's usage pattern
   changes.
4. If you're adding a scorer, see `src/agentic_evals/skills/write-a-scorer/`
   for guidance on which category it belongs in and what its `Score.value`
   should mean.
5. If the work is release-ready, update `pyproject.toml`,
   `src/agentic_evals/__init__.py`, and `CHANGELOG.md` as part of the release.
6. Run:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

7. Keep PRs focused — one concern per pull request.
8. Write clear commit messages describing *why*, not just *what*.

## Good contributions

- New scorers (`agentic_evals.scorers.text`/`rubric`/`trajectory`) with
  tests covering at least one passing and one failing case
- New eval packs (`agentic_evals/packs/builtin/`) for common, reusable
  scenarios
- New methodology skills (`agentic_evals/skills/`) following the existing
  Trigger/Do/Avoid/Check/Risk card format
- Bug fixes with regression tests
- Documentation and usage examples

## Adding a scorer

A new scorer should:

1. Be a plain `(EvaluationContext) -> Score` function, or a
   `CallableEvaluator` subclass if it needs constructor state (see
   `LLMRubricEvaluator` for an example).
2. Raise a clear `ValueError` when required input is missing, rather than
   returning a meaningless default score.
3. Never call a model or embedding API directly — take `complete_fn`/
   `embed_fn` as a parameter, the way `LLMJudgeEvaluator`,
   `LLMRubricEvaluator`, and `embedding_similarity` all do.
4. Be registered in `agentic_evals.scorers.registry` under a stable name
   if it's deterministic/trajectory-based (rubric scorers stay opt-in
   since they need a `complete_fn`).
5. Ship with tests in the matching `tests/test_scorers_*.py` file.

## Adding an eval pack

A pack (`agentic_evals/packs/builtin/*.yaml`) should be a small, concrete,
runnable example — not a template with placeholder values. Every
`required_scorers` entry must resolve in `default_registry()`, unless the
pack's description says it needs a caller-supplied registry (e.g. one
with an `LLMRubricEvaluator` registered).

## Releases

Releases are automated via GitHub Actions when a version tag is pushed.

### Release checklist

1. Update the version string in all three locations:
   - `pyproject.toml` → `version = "X.Y.Z"`
   - `src/agentic_evals/__init__.py` → `__version__ = "X.Y.Z"`
   - `CHANGELOG.md` → add a `## X.Y.Z - YYYY-MM-DD` section
2. Commit: `git commit -am "release: vX.Y.Z"`
3. Tag: `git tag vX.Y.Z`
4. Push: `git push origin main --tags`

The `release-pypi.yml` workflow triggers on the tag push and publishes to
PyPI via Trusted Publishing (OIDC) — no stored API token needed.

## Security

See [SECURITY.md](SECURITY.md) for how to report a vulnerability.

## Design principles

- Provider-neutral — this package never calls a model, embedding API, or
  any other network service itself; every LLM/embedding-backed scorer
  takes the caller's own function.
- Zero dependency on AgenticLens or any other DeepAgentLabs project —
  `EvalTrace`/`EvalSpan` is deliberately minimal and independent.
- One criterion per scorer — don't bundle unrelated checks into a single
  `Score`.
- Never fabricate a value it can't back up — an unavailable cost is
  `None`, never `0.0`.
