# python-office-templates — agent guide

Generates Office documents (PPTX/XLSX) from template files that are flexibly
populated or composed using provided context. Published to PyPI as
`office-templates`.

## Repo shape

- Source: `office_templates/`
- Tests: `tests/` (plain pytest, no framework) — `uv run --all-extras pytest`
- Lint + format: `uv run --all-extras ruff check office_templates/ tests/` and
  `ruff format --check office_templates/ tests/`
- Default working branch: `develop`. Releases flow `develop` → `main`.

## Opening PRs & versioning

`main` is protected: PRs only, and checks (`lint`, `test`) must pass to merge.
The version is a static string in `pyproject.toml` and `uv.lock` (there is no
`__version__` in `office_templates/__init__.py`) and is **not** bumped
automatically on merge — it must be bumped deliberately, or no release is cut.
Publishing to PyPI is automatic once a `develop` → `main` PR merges.

**Follow the `create-merge-pr` skill** (`.agents/skills/create-merge-pr/`) for the
full PR workflow, including when and how to bump the version.
