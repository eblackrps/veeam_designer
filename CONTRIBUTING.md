# Contributing

Thanks for helping improve Chrome Policy Merge.

## Development Setup

Create a virtual environment, install the project in editable mode, and add the developer tools:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pre-commit install
```

On Windows PowerShell, activate the environment with `.venv\Scripts\Activate.ps1`.

Use a standard CPython 3.10+ interpreter for development work. Some embedded vendor Python
distributions on Windows do not support editable installs or isolated build hooks reliably.

## Local Workflows

Run the web console:

```bash
chrome-policy-merge-web --reload
```

Run the CLI:

```bash
python -m chrome_policy_merge --help
```

Run the repository source tree directly:

```bash
python -m uvicorn --app-dir src chrome_policy_merge.web:app --reload
```

## Validation

Run the standard validation suite before opening a pull request:

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest
python -m build
```

## Contribution Expectations

- Keep the web UI, API, CLI, and docs aligned
- Preserve deterministic merge behavior and safe restore behavior
- Add tests with any behavior change, especially around merge semantics or filesystem safety
- Prefer clear errors and explicit behavior over silent fallbacks
- Keep Docker and local web startup instructions accurate

## Pull Requests

Include:

- a short summary of the change
- the validation commands you ran
- updated documentation when behavior or workflow changes

## Reporting Issues

Open an issue with:

- the version you are using
- whether you used the web UI, CLI, API, or Docker deployment
- the command or workflow that failed
- your Python version or container image tag
- a minimal reproduction when possible
