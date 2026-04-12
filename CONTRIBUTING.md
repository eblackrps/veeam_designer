# Contributing

Thanks for helping improve Chrome Policy Merge.

## Development Setup

On Windows:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pre-commit install
```

On Linux or macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pre-commit install
```

Use a standard CPython 3.10+ interpreter for development work. Some embedded vendor Python
distributions on Windows do not support editable installs or isolated build hooks reliably.

## Workflow

1. Create a branch for your work.
2. Keep changes focused and release-quality.
3. Update tests and documentation together with behavior changes.
4. Run the validation commands before opening a pull request.

## Validation

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
python -m build
```

## Code Standards

- Keep the CLI, docs, and tests aligned.
- Preserve deterministic merge behavior.
- Prefer clear error messages over silent fallbacks.
- Add type hints and docstrings for user-facing modules and public functions.
- Avoid adding runtime dependencies unless they materially improve the tool.

## Pull Requests

Include:

- a short summary of the change
- the validation commands you ran
- updated documentation when behavior changes

## Reporting Issues

Open an issue in the repository issue tracker with:

- the command you ran
- your Python version
- the relevant policy files or a minimal reproduction
- the expected result and the actual result
