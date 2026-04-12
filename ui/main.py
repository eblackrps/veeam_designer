"""Compatibility wrapper for ``uvicorn ui.main:app`` style deployments."""

from chrome_policy_merge.web import app, run

__all__ = ["app", "run"]


if __name__ == "__main__":
    raise SystemExit(run())
