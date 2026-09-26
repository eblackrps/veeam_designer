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
python -m mypy .
node --check ui/static/app.js
python -m pytest -q
python -m build
python tools/build_pages.py --output _site
```

## Calculation Freeze

The sizing engine is frozen at the verified `5.0.0a8` calculation baseline. CI validates the
protected engine files against `calculation-freeze.manifest`.

Do not change the frozen calculation files for cleanup, refactoring, wording, or convenience.
Advance the baseline only when one of these conditions is met:

- a calculation defect is reproduced and corrected with exact known-answer regression coverage
- verified Veeam behavior or requirements changed and the model must be updated
- an explicitly approved calculation feature requires new math and corresponding validation

Presentation-only work should stay outside the frozen files. Any approved baseline change must be
reviewed as a calculation change, not bundled into unrelated UI or documentation work.

## UI Work

- Keep the web UI grounded in actual Veeam planning workflows
- Preserve the live YAML workflow and API parity
- Keep the FastAPI, Docker, and GitHub Pages UI paths aligned
- Keep documentation and runtime commands aligned with the real app

## Pull Requests

- Keep changes focused
- Add or update tests for engine, API, or UI behavior changes
- Update `README.md` and `CHANGELOG.md` when the user-facing behavior changes
- Keep the GitHub Pages build working when web UI, templates, or packaged resources change
- Do not leave stale version strings or release notes behind
