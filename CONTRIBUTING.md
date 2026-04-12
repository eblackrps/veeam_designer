# Contributing

Thanks for helping improve Veeam Designer.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

## Local Validation

Run these before opening a pull request:

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m build
```

## UI Work

- Keep the web UI grounded in actual Veeam planning workflows
- Preserve the live YAML workflow and API parity
- Update screenshots whenever the visible calculator UI changes materially
- Keep Docker instructions and runtime commands aligned with the real app

## Pull Requests

- Keep changes focused
- Add or update tests for engine, API, or UI behavior changes
- Update `README.md` and `CHANGELOG.md` when the user-facing behavior changes
- Do not leave stale version strings or release notes behind
