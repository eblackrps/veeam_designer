"""Shared data models and JSON type aliases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
JSONObject: TypeAlias = dict[str, JSONValue]


@dataclass(frozen=True, slots=True)
class MergeConfig:
    """Configuration for merging a directory of policy files."""

    input_directory: Path
    output_file: Path | None = None
    backup_dir: Path | None = None
    merge_keys: tuple[str, ...] = ()
    dry_run: bool = False
    strict: bool = False


@dataclass(frozen=True, slots=True)
class MergeResult:
    """Result details for a merge operation."""

    merged_policy: JSONObject
    processed_files: tuple[Path, ...]
    skipped_entries: tuple[Path, ...]
    output_file: Path
    backup_snapshot: Path | None
    output_written: bool
    dry_run: bool


@dataclass(frozen=True, slots=True)
class RestoreConfig:
    """Configuration for restoring a backup snapshot."""

    input_directory: Path
    backup_dir: Path | None = None
    snapshot_name: str | None = None
    output_file: Path | None = None
    remove_output: bool = False
    dry_run: bool = False


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """Result details for a restore operation."""

    snapshot_dir: Path
    restored_files: tuple[Path, ...]
    output_file: Path
    output_removed: bool
    dry_run: bool


@dataclass(frozen=True, slots=True)
class BackupManifest:
    """Metadata written alongside each backup snapshot."""

    schema_version: int
    tool_version: str
    created_at: str
    input_directory: str
    output_file: str
    merge_keys: tuple[str, ...]
    files: tuple[str, ...]

    def to_json_object(self) -> JSONObject:
        """Serialize the manifest to a JSON-compatible mapping."""

        return {
            "schema_version": self.schema_version,
            "tool_version": self.tool_version,
            "created_at": self.created_at,
            "input_directory": self.input_directory,
            "output_file": self.output_file,
            "merge_keys": list(self.merge_keys),
            "files": list(self.files),
        }

    @classmethod
    def from_json_object(cls, payload: object) -> BackupManifest:
        """Validate and deserialize a manifest payload."""

        if not isinstance(payload, dict):
            raise ValueError("backup manifest must be a JSON object")

        schema_version = payload.get("schema_version")
        tool_version = payload.get("tool_version")
        created_at = payload.get("created_at")
        input_directory = payload.get("input_directory")
        output_file = payload.get("output_file")
        merge_keys = payload.get("merge_keys")
        files = payload.get("files")

        if not isinstance(schema_version, int):
            raise ValueError("backup manifest is missing an integer schema_version")
        if not isinstance(tool_version, str):
            raise ValueError("backup manifest is missing tool_version")
        if not isinstance(created_at, str):
            raise ValueError("backup manifest is missing created_at")
        if not isinstance(input_directory, str):
            raise ValueError("backup manifest is missing input_directory")
        if not isinstance(output_file, str):
            raise ValueError("backup manifest is missing output_file")
        if not isinstance(merge_keys, list) or not all(
            isinstance(item, str) for item in merge_keys
        ):
            raise ValueError("backup manifest merge_keys must be a list of strings")
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            raise ValueError("backup manifest files must be a list of strings")
        if any(Path(name).name != name or Path(name).is_absolute() for name in files):
            raise ValueError("backup manifest files must contain simple file names")

        return cls(
            schema_version=schema_version,
            tool_version=tool_version,
            created_at=created_at,
            input_directory=input_directory,
            output_file=output_file,
            merge_keys=tuple(merge_keys),
            files=tuple(files),
        )
