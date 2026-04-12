"""Core merge and restore logic for Chrome policy files."""

from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
from collections.abc import Collection
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from ._version import __version__
from .exceptions import InvalidPolicyFileError, MergeConflictError, PolicyMergeError, RestoreError
from .models import (
    BackupManifest,
    JSONObject,
    JSONValue,
    MergeConfig,
    MergeResult,
    RestoreConfig,
    RestoreResult,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_OUTPUT_FILENAME = "merged-policy.json"
DEFAULT_BACKUP_DIRNAME = "backup"
MANIFEST_FILENAME = "manifest.json"
MANIFEST_SCHEMA_VERSION = 1
_NATURAL_SORT_PATTERN = re.compile(r"(\d+)")


def natural_sort_key(value: str | Path) -> tuple[object, ...]:
    """Return a natural sort key that orders numeric filename segments numerically."""

    text = value.name if isinstance(value, Path) else str(value)
    parts = _NATURAL_SORT_PATTERN.split(text.casefold())
    key: list[object] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part)
    return tuple(key)


def merge_policy_objects(
    existing: JSONObject,
    incoming: JSONObject,
    merge_keys: Collection[str] = (),
    *,
    strict: bool = False,
) -> JSONObject:
    """Merge two policy objects using the documented top-level merge semantics."""

    merge_key_set = set(merge_keys)
    merged = deepcopy(existing)

    for key, incoming_value in incoming.items():
        if key not in merged:
            merged[key] = deepcopy(incoming_value)
            continue

        current_value = merged[key]
        if key in merge_key_set:
            merged[key] = _deep_merge_value(
                current_value,
                incoming_value,
                strict=strict,
                path=(key,),
            )
            continue

        if strict and current_value != incoming_value:
            raise MergeConflictError(
                f"Conflicting values for policy '{key}'. Add --merge-key {key} or disable --strict."
            )

        merged[key] = deepcopy(incoming_value)

    return merged


def discover_policy_files(
    input_directory: Path,
    *,
    output_file: Path,
) -> tuple[list[Path], list[Path]]:
    """Discover candidate input files and skipped entries from a directory."""

    candidates: list[Path] = []
    skipped: list[Path] = []

    for entry in input_directory.iterdir():
        resolved_entry = entry.resolve()
        if entry.is_dir():
            skipped.append(entry)
            continue
        if resolved_entry == output_file:
            skipped.append(entry)
            continue
        if entry.suffix.casefold() != ".json":
            skipped.append(entry)
            continue
        candidates.append(entry)

    candidates.sort(key=natural_sort_key)
    skipped.sort(key=natural_sort_key)

    return candidates, skipped


def load_policy_file(path: Path) -> JSONObject:
    """Load and validate a single JSON policy file."""

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidPolicyFileError(path, f"unable to read file: {exc.strerror or exc}") from exc

    return load_policy_text(path, text)


def load_policy_text(source: str | Path, payload: str) -> JSONObject:
    """Load and validate a policy object from raw JSON text."""

    source_path = Path(source)

    try:
        raw_payload = json.loads(payload)
    except json.JSONDecodeError as exc:
        message = f"invalid JSON ({exc.msg} at line {exc.lineno}, column {exc.colno})"
        raise InvalidPolicyFileError(source_path, message) from exc

    if not isinstance(raw_payload, dict):
        raise InvalidPolicyFileError(source_path, "top-level JSON value must be an object")

    return raw_payload


def merge_policy_directory(config: MergeConfig) -> MergeResult:
    """Merge all eligible policy files from a directory."""

    input_directory = config.input_directory.resolve()
    output_file = (config.output_file or input_directory / DEFAULT_OUTPUT_FILENAME).resolve()
    backup_dir = (config.backup_dir or input_directory / DEFAULT_BACKUP_DIRNAME).resolve()
    merge_keys = tuple(dict.fromkeys(config.merge_keys))

    _validate_merge_paths(
        input_directory=input_directory,
        output_file=output_file,
        backup_dir=backup_dir,
    )

    candidates, skipped = discover_policy_files(
        input_directory,
        output_file=output_file,
    )

    if not candidates:
        LOGGER.info("No JSON policy files found in %s", input_directory)
        return MergeResult(
            merged_policy={},
            processed_files=(),
            skipped_entries=tuple(skipped),
            output_file=output_file,
            backup_snapshot=None,
            output_written=False,
            dry_run=config.dry_run,
        )

    merged_policy: JSONObject = {}
    for candidate in candidates:
        LOGGER.debug("Loading %s", candidate)
        policy_object = load_policy_file(candidate)
        merged_policy = merge_policy_objects(
            merged_policy,
            policy_object,
            merge_keys=merge_keys,
            strict=config.strict,
        )

    if config.dry_run:
        planned_snapshot = backup_dir / _build_snapshot_name(backup_dir)
        LOGGER.info(
            "Dry run complete: %s file(s) would be merged into %s",
            len(candidates),
            output_file,
        )
        return MergeResult(
            merged_policy=merged_policy,
            processed_files=tuple(candidates),
            skipped_entries=tuple(skipped),
            output_file=output_file,
            backup_snapshot=planned_snapshot,
            output_written=False,
            dry_run=True,
        )

    _prepare_merge_runtime_paths(output_file=output_file, backup_dir=backup_dir)
    snapshot_dir = _create_snapshot_dir(backup_dir)
    moved_files: list[tuple[Path, Path]] = []
    try:
        for source in candidates:
            destination = snapshot_dir / source.name
            shutil.move(str(source), str(destination))
            moved_files.append((source, destination))

        manifest = BackupManifest(
            schema_version=MANIFEST_SCHEMA_VERSION,
            tool_version=__version__,
            created_at=datetime.now(timezone.utc).isoformat(),
            input_directory=str(input_directory),
            output_file=str(output_file),
            merge_keys=merge_keys,
            files=tuple(path.name for path in candidates),
        )
        _write_manifest(snapshot_dir, manifest)
        _atomic_write_json(output_file, merged_policy)
    except Exception as exc:  # pragma: no cover - exercised via integration tests
        rollback_errors = _rollback_moves(moved_files)
        _remove_snapshot(snapshot_dir)
        if rollback_errors:
            detail = "; ".join(rollback_errors)
            raise PolicyMergeError(
                f"Merge failed and rollback was incomplete: {exc}. Rollback errors: {detail}"
            ) from exc
        if isinstance(exc, PolicyMergeError):
            raise
        raise PolicyMergeError(f"Merge failed while finalizing output: {exc}") from exc

    LOGGER.info(
        "Merged %s file(s) into %s and archived them in %s",
        len(candidates),
        output_file,
        snapshot_dir,
    )
    return MergeResult(
        merged_policy=merged_policy,
        processed_files=tuple(candidates),
        skipped_entries=tuple(skipped),
        output_file=output_file,
        backup_snapshot=snapshot_dir,
        output_written=True,
        dry_run=False,
    )


def restore_backup_snapshot(config: RestoreConfig) -> RestoreResult:
    """Copy a backup snapshot back into the input directory."""

    input_directory = config.input_directory.resolve()
    backup_dir = (config.backup_dir or input_directory / DEFAULT_BACKUP_DIRNAME).resolve()

    if not input_directory.is_dir():
        raise RestoreError(
            f"Input directory does not exist or is not a directory: {input_directory}"
        )
    if not backup_dir.is_dir():
        raise RestoreError(f"Backup directory does not exist or is not a directory: {backup_dir}")

    snapshot_dir = _select_snapshot_dir(backup_dir, config.snapshot_name)
    manifest = _read_manifest(snapshot_dir / MANIFEST_FILENAME)

    if not manifest.files:
        raise RestoreError(f"Snapshot {snapshot_dir.name} does not contain any policy files")

    output_file = _resolve_restore_output_file(
        input_directory=input_directory,
        configured_output_file=config.output_file,
        manifest_output_file=manifest.output_file,
    )
    restored_targets = tuple(input_directory / name for name in manifest.files)
    conflicts = [path for path in restored_targets if path.exists()]
    if conflicts:
        conflict_names = ", ".join(path.name for path in conflicts)
        raise RestoreError(
            f"Refusing to overwrite existing file(s) during restore: {conflict_names}"
        )

    for name in manifest.files:
        source = snapshot_dir / name
        if not source.is_file():
            raise RestoreError(f"Snapshot file listed in manifest is missing: {source}")

    if config.dry_run:
        LOGGER.info(
            "Dry run complete: %s file(s) would be restored from %s",
            len(manifest.files),
            snapshot_dir,
        )
        return RestoreResult(
            snapshot_dir=snapshot_dir,
            restored_files=restored_targets,
            output_file=output_file,
            output_removed=False,
            dry_run=True,
        )

    copied_targets: list[Path] = []
    try:
        for name in manifest.files:
            source = snapshot_dir / name
            target = input_directory / name
            shutil.copy2(source, target)
            copied_targets.append(target)
        output_removed = False
        if config.remove_output and output_file.exists():
            output_file.unlink()
            output_removed = True
    except Exception as exc:
        for target in reversed(copied_targets):
            target.unlink(missing_ok=True)
        if isinstance(exc, PolicyMergeError):
            raise
        raise RestoreError(f"Restore failed: {exc}") from exc

    LOGGER.info("Restored %s file(s) from %s", len(copied_targets), snapshot_dir)
    return RestoreResult(
        snapshot_dir=snapshot_dir,
        restored_files=tuple(copied_targets),
        output_file=output_file,
        output_removed=output_removed,
        dry_run=False,
    )


def _validate_merge_paths(*, input_directory: Path, output_file: Path, backup_dir: Path) -> None:
    """Validate merge paths before any processing begins."""

    if not input_directory.is_dir():
        raise PolicyMergeError(
            f"Input directory does not exist or is not a directory: {input_directory}"
        )
    if backup_dir == input_directory:
        raise PolicyMergeError("Backup directory must not be the same as the input directory")
    if output_file == backup_dir:
        raise PolicyMergeError("Output file path must not be the same as the backup directory")
    if _is_relative_to(output_file, backup_dir):
        raise PolicyMergeError("Output file must not be placed inside the backup directory")


def _prepare_merge_runtime_paths(*, output_file: Path, backup_dir: Path) -> None:
    """Create runtime directories after validation and before mutating input files."""

    output_file.parent.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)


def _deep_merge_value(
    current_value: JSONValue,
    incoming_value: JSONValue,
    *,
    strict: bool,
    path: tuple[str, ...],
) -> JSONValue:
    """Deeply merge compatible dicts and lists under an allowed merge key."""

    if isinstance(current_value, dict) and isinstance(incoming_value, dict):
        merged_mapping = deepcopy(current_value)
        for key, nested_value in incoming_value.items():
            if key in merged_mapping:
                merged_mapping[key] = _deep_merge_value(
                    merged_mapping[key],
                    nested_value,
                    strict=strict,
                    path=(*path, key),
                )
            else:
                merged_mapping[key] = deepcopy(nested_value)
        return merged_mapping

    if isinstance(current_value, list) and isinstance(incoming_value, list):
        return _merge_list_values(current_value, incoming_value)

    if strict and _container_type_conflict(current_value, incoming_value):
        dotted_path = ".".join(path)
        raise MergeConflictError(
            f"Incompatible values while deep merging '{dotted_path}': "
            f"{type(current_value).__name__} vs {type(incoming_value).__name__}."
        )

    return deepcopy(incoming_value)


def _container_type_conflict(current_value: JSONValue, incoming_value: JSONValue) -> bool:
    """Return True when a deep merge encounters incompatible container types."""

    return isinstance(current_value, (dict, list)) or isinstance(incoming_value, (dict, list))


def _merge_list_values(
    current_value: list[JSONValue],
    incoming_value: list[JSONValue],
) -> list[JSONValue]:
    """Merge lists using ordered union semantics."""

    merged_list: list[JSONValue] = []
    seen: set[str] = set()
    for item in [*current_value, *incoming_value]:
        marker = _canonical_json(item)
        if marker in seen:
            continue
        seen.add(marker)
        merged_list.append(deepcopy(item))
    return merged_list


def _canonical_json(value: JSONValue) -> str:
    """Serialize a JSON value canonically for deterministic equality checks."""

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _atomic_write_json(path: Path, payload: JSONObject) -> None:
    """Write JSON atomically so partial output files are never published."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
            newline="\n",
            prefix=f".{path.stem}-",
            suffix=".tmp",
        ) as temp_file:
            temp_file_path = Path(temp_file.name)
            json.dump(payload, temp_file, ensure_ascii=False, indent=2, sort_keys=True)
            temp_file.write("\n")
        temp_file_path.replace(path)
    except Exception:
        if temp_file_path is not None:
            temp_file_path.unlink(missing_ok=True)
        raise


def _create_snapshot_dir(backup_dir: Path) -> Path:
    """Create a unique snapshot directory inside the backup root."""

    backup_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = backup_dir / _build_snapshot_name(backup_dir)
    snapshot_dir.mkdir()
    return snapshot_dir


def _build_snapshot_name(backup_dir: Path) -> str:
    """Generate a unique snapshot directory name."""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"snapshot-{timestamp}"
    candidate = base_name
    counter = 1
    while (backup_dir / candidate).exists():
        candidate = f"{base_name}-{counter}"
        counter += 1
    return candidate


def _write_manifest(snapshot_dir: Path, manifest: BackupManifest) -> None:
    """Persist a backup manifest to disk."""

    _atomic_write_json(snapshot_dir / MANIFEST_FILENAME, manifest.to_json_object())


def _read_manifest(path: Path) -> BackupManifest:
    """Load and validate a backup manifest file."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RestoreError(f"Backup manifest is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RestoreError(f"Backup manifest is invalid JSON: {path}") from exc
    except OSError as exc:
        raise RestoreError(f"Unable to read backup manifest {path}: {exc}") from exc

    try:
        return BackupManifest.from_json_object(payload)
    except ValueError as exc:
        raise RestoreError(f"Backup manifest is invalid: {exc}") from exc


def _rollback_moves(moved_files: list[tuple[Path, Path]]) -> list[str]:
    """Move archived files back to their original locations after a failure."""

    rollback_errors: list[str] = []
    for original_path, archived_path in reversed(moved_files):
        if not archived_path.exists():
            continue
        try:
            shutil.move(str(archived_path), str(original_path))
        except Exception as exc:  # pragma: no cover - only hit on filesystem failures
            rollback_errors.append(f"{archived_path.name}: {exc}")
    return rollback_errors


def _remove_snapshot(snapshot_dir: Path) -> None:
    """Remove a snapshot directory if it exists."""

    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir, ignore_errors=True)


def _select_snapshot_dir(backup_dir: Path, snapshot_name: str | None) -> Path:
    """Select a named snapshot or the newest available snapshot."""

    resolved_backup_dir = backup_dir.resolve()

    if snapshot_name is not None:
        _validate_snapshot_name(snapshot_name)
        snapshot_dir = (backup_dir / snapshot_name).resolve()
        if not _is_relative_to(snapshot_dir, resolved_backup_dir):
            raise RestoreError(
                "Snapshot names must refer to a directory directly inside the backup directory"
            )
        if not snapshot_dir.is_dir():
            raise RestoreError(f"Snapshot does not exist: {snapshot_name}")
        return snapshot_dir

    snapshots = sorted(
        (
            path.resolve()
            for path in backup_dir.iterdir()
            if path.is_dir() and _is_relative_to(path.resolve(), resolved_backup_dir)
        ),
        key=natural_sort_key,
    )
    if not snapshots:
        raise RestoreError(f"No backup snapshots found in {backup_dir}")
    return snapshots[-1]


def _resolve_restore_output_file(
    *,
    input_directory: Path,
    configured_output_file: Path | None,
    manifest_output_file: str,
) -> Path:
    """Resolve the output file affected by a restore operation safely."""

    if configured_output_file is not None:
        return configured_output_file.resolve()

    manifest_path = Path(manifest_output_file)
    resolved_manifest_path = (
        manifest_path.resolve()
        if manifest_path.is_absolute()
        else (input_directory / manifest_path).resolve()
    )
    if resolved_manifest_path.parent == input_directory:
        return resolved_manifest_path
    return (input_directory / DEFAULT_OUTPUT_FILENAME).resolve()


def _validate_snapshot_name(snapshot_name: str) -> None:
    """Reject snapshot selectors that do not refer to a direct child of the backup directory."""

    candidate = Path(snapshot_name)
    if candidate.is_absolute() or len(candidate.parts) != 1 or snapshot_name in {".", ".."}:
        raise RestoreError(
            "Snapshot names must refer to a directory directly inside the backup directory"
        )


def _is_relative_to(path: Path, other: Path) -> bool:
    """Return True when ``path`` is contained within ``other``."""

    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True
