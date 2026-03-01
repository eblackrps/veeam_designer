# Contributing

## Getting Started

1. Fork the repository and clone your fork.
2. Create a branch for your change:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Make your changes and commit with a clear message.
4. Push your branch and open a Pull Request against `main`.

## Development Setup

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -e ".[dev,web]"
```

## Code Style

- Python 3.10+ syntax
- Max line length: 120 characters
- Run `flake8 veeam_designer/ ui/` before committing

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Update `CHANGELOG.md` under `[Unreleased]`
- Update `README.md` if you add or change user-facing behaviour
- Reference any related issues in the PR description

## Reporting Issues

Open an issue at https://github.com/eblackrps/veeam_designer/issues.

Include:
- Python version
- Steps to reproduce
- Expected vs. actual behaviour
- Relevant output or error messages
