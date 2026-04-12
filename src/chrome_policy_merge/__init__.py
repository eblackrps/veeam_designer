"""Public package interface for Chrome Policy Merge."""

from ._version import __version__
from .exceptions import InvalidPolicyFileError, MergeConflictError, PolicyMergeError, RestoreError
from .merge import (
    DEFAULT_BACKUP_DIRNAME,
    DEFAULT_OUTPUT_FILENAME,
    MANIFEST_FILENAME,
    discover_policy_files,
    load_policy_file,
    merge_policy_directory,
    merge_policy_objects,
    natural_sort_key,
    restore_backup_snapshot,
)
from .models import (
    BackupManifest,
    JSONObject,
    JSONValue,
    MergeConfig,
    MergeResult,
    RestoreConfig,
    RestoreResult,
)

__all__ = [
    "DEFAULT_BACKUP_DIRNAME",
    "DEFAULT_OUTPUT_FILENAME",
    "MANIFEST_FILENAME",
    "BackupManifest",
    "InvalidPolicyFileError",
    "JSONObject",
    "JSONValue",
    "MergeConfig",
    "MergeConflictError",
    "MergeResult",
    "PolicyMergeError",
    "RestoreConfig",
    "RestoreError",
    "RestoreResult",
    "__version__",
    "discover_policy_files",
    "load_policy_file",
    "merge_policy_directory",
    "merge_policy_objects",
    "natural_sort_key",
    "restore_backup_snapshot",
]
