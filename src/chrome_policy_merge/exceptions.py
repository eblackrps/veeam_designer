"""Custom exceptions for Chrome Policy Merge."""

from __future__ import annotations

from pathlib import Path


class PolicyMergeError(RuntimeError):
    """Base exception for merge and restore failures."""


class InvalidPolicyFileError(PolicyMergeError):
    """Raised when an input file cannot be parsed as a valid policy object."""

    def __init__(self, path: Path, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path


class MergeConflictError(PolicyMergeError):
    """Raised when strict mode rejects an unsafe merge."""


class RestoreError(PolicyMergeError):
    """Raised when a backup snapshot cannot be restored safely."""
