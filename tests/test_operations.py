"""Integration tests for directory merge and restore operations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chrome_policy_merge import (
    InvalidPolicyFileError,
    MergeConfig,
    PolicyMergeError,
    RestoreConfig,
    RestoreError,
    merge_policy_directory,
    restore_backup_snapshot,
)


def test_invalid_json_fails_without_writing_output(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    (input_dir / "10-valid.json").write_text(
        '{"HomepageLocation": "https://example.com"}\n',
        encoding="utf-8",
    )
    (input_dir / "20-invalid.json").write_text("{invalid}\n", encoding="utf-8")

    with pytest.raises(InvalidPolicyFileError):
        merge_policy_directory(MergeConfig(input_directory=input_dir))

    assert (input_dir / "10-valid.json").exists()
    assert (input_dir / "20-invalid.json").exists()
    assert not (input_dir / "merged-policy.json").exists()
    assert not (input_dir / "backup").exists()


def test_non_object_json_is_rejected(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    (input_dir / "10-array.json").write_text('["not", "an", "object"]\n', encoding="utf-8")

    with pytest.raises(InvalidPolicyFileError):
        merge_policy_directory(MergeConfig(input_directory=input_dir))

    assert (input_dir / "10-array.json").exists()
    assert not (input_dir / "merged-policy.json").exists()


def test_empty_directory_is_a_noop(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()

    result = merge_policy_directory(MergeConfig(input_directory=input_dir))

    assert result.processed_files == ()
    assert result.merged_policy == {}
    assert result.output_written is False
    assert not (input_dir / "merged-policy.json").exists()
    assert not (input_dir / "backup").exists()


def test_non_json_files_and_existing_output_are_ignored(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    (input_dir / "notes.txt").write_text("ignore me\n", encoding="utf-8")
    (input_dir / "merged-policy.json").write_text('{"stale": true}\n', encoding="utf-8")
    _write_json(input_dir / "10-policy.json", {"HomepageLocation": "https://portal.example.com"})

    result = merge_policy_directory(MergeConfig(input_directory=input_dir))

    assert result.processed_files == (input_dir / "10-policy.json",)
    assert (input_dir / "notes.txt").exists()
    assert json.loads((input_dir / "merged-policy.json").read_text(encoding="utf-8")) == {
        "HomepageLocation": "https://portal.example.com"
    }


def test_custom_output_file_inside_input_directory_is_ignored_as_input(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    custom_output = input_dir / "final-policy.json"
    custom_output.write_text('{"stale": true}\n', encoding="utf-8")
    _write_json(input_dir / "10-policy.json", {"HomepageLocation": "https://portal.example.com"})

    result = merge_policy_directory(
        MergeConfig(input_directory=input_dir, output_file=custom_output)
    )

    assert result.processed_files == (input_dir / "10-policy.json",)
    assert json.loads(custom_output.read_text(encoding="utf-8")) == {
        "HomepageLocation": "https://portal.example.com"
    }


def test_merge_creates_output_and_backup_snapshot(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    _write_json(
        input_dir / "10-base.json",
        {
            "ExtensionSettings": {
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": {
                    "installation_mode": "allowed",
                    "runtime_blocked_hosts": ["https://blocked.example.com"],
                }
            },
            "HomepageLocation": "https://intranet.example.com",
        },
    )
    _write_json(
        input_dir / "20-override.json",
        {
            "ExtensionSettings": {
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": {
                    "runtime_blocked_hosts": ["https://private.example.com"],
                    "toolbar_pin": "force_pinned",
                }
            },
            "HomepageLocation": "https://portal.example.com",
        },
    )

    result = merge_policy_directory(
        MergeConfig(input_directory=input_dir, merge_keys=("ExtensionSettings",))
    )

    assert result.output_written is True
    assert result.backup_snapshot is not None
    merged_output = json.loads((input_dir / "merged-policy.json").read_text(encoding="utf-8"))
    assert merged_output == {
        "ExtensionSettings": {
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": {
                "installation_mode": "allowed",
                "runtime_blocked_hosts": [
                    "https://blocked.example.com",
                    "https://private.example.com",
                ],
                "toolbar_pin": "force_pinned",
            }
        },
        "HomepageLocation": "https://portal.example.com",
    }
    assert not (input_dir / "10-base.json").exists()
    assert not (input_dir / "20-override.json").exists()
    assert (result.backup_snapshot / "10-base.json").exists()
    assert (result.backup_snapshot / "20-override.json").exists()
    assert (result.backup_snapshot / "manifest.json").exists()


def test_manifest_records_merge_metadata(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    _write_json(input_dir / "10-policy.json", {"HomepageLocation": "https://portal.example.com"})

    result = merge_policy_directory(
        MergeConfig(input_directory=input_dir, merge_keys=("ExtensionSettings",))
    )

    assert result.backup_snapshot is not None
    manifest = json.loads((result.backup_snapshot / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["tool_version"] == "4.0.0"
    assert manifest["merge_keys"] == ["ExtensionSettings"]
    assert manifest["files"] == ["10-policy.json"]


def test_dry_run_does_not_write_or_move_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    _write_json(input_dir / "10-policy.json", {"HomepageLocation": "https://portal.example.com"})

    result = merge_policy_directory(MergeConfig(input_directory=input_dir, dry_run=True))

    assert result.dry_run is True
    assert result.output_written is False
    assert result.backup_snapshot is not None
    assert (input_dir / "10-policy.json").exists()
    assert not (input_dir / "merged-policy.json").exists()
    assert not (input_dir / "backup").exists()


def test_rerun_is_safe_when_only_output_and_backup_remain(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    _write_json(input_dir / "10-policy.json", {"HomepageLocation": "https://portal.example.com"})

    first_result = merge_policy_directory(MergeConfig(input_directory=input_dir))
    second_result = merge_policy_directory(MergeConfig(input_directory=input_dir))

    assert first_result.output_written is True
    assert second_result.output_written is False
    assert second_result.processed_files == ()
    assert len(list((input_dir / "backup").iterdir())) == 1


def test_merge_rejects_output_inside_backup_directory(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    _write_json(input_dir / "10-policy.json", {"HomepageLocation": "https://portal.example.com"})

    with pytest.raises(PolicyMergeError):
        merge_policy_directory(
            MergeConfig(
                input_directory=input_dir,
                backup_dir=input_dir / "backup",
                output_file=input_dir / "backup" / "merged-policy.json",
            )
        )


def test_strict_mode_rejects_conflicting_non_merge_keys(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    _write_json(input_dir / "10-policy.json", {"HomepageLocation": "https://one.example.com"})
    _write_json(input_dir / "20-policy.json", {"HomepageLocation": "https://two.example.com"})

    with pytest.raises(PolicyMergeError):
        merge_policy_directory(MergeConfig(input_directory=input_dir, strict=True))


def test_restore_copies_files_back_and_can_remove_output(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    _write_json(input_dir / "10-policy.json", {"HomepageLocation": "https://portal.example.com"})
    merge_result = merge_policy_directory(MergeConfig(input_directory=input_dir))

    restore_result = restore_backup_snapshot(
        RestoreConfig(input_directory=input_dir, remove_output=True)
    )

    assert merge_result.backup_snapshot == restore_result.snapshot_dir
    assert (input_dir / "10-policy.json").exists()
    assert not (input_dir / "merged-policy.json").exists()
    assert restore_result.output_removed is True
    assert (restore_result.snapshot_dir / "10-policy.json").exists()


def test_restore_refuses_to_overwrite_existing_policy_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    _write_json(input_dir / "10-policy.json", {"HomepageLocation": "https://portal.example.com"})
    merge_policy_directory(MergeConfig(input_directory=input_dir))
    _write_json(input_dir / "10-policy.json", {"HomepageLocation": "https://existing.example.com"})

    with pytest.raises(RestoreError):
        restore_backup_snapshot(RestoreConfig(input_directory=input_dir))


def test_restore_does_not_remove_external_output_by_default(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    _write_json(input_dir / "10-policy.json", {"HomepageLocation": "https://portal.example.com"})
    merge_result = merge_policy_directory(MergeConfig(input_directory=input_dir))
    assert merge_result.backup_snapshot is not None

    external_output = tmp_path / "external-output.json"
    _write_json(external_output, {"should": "stay"})
    manifest_path = merge_result.backup_snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["output_file"] = str(external_output)
    _write_json(manifest_path, manifest)

    restore_result = restore_backup_snapshot(
        RestoreConfig(input_directory=input_dir, remove_output=True)
    )

    assert restore_result.output_file == input_dir / "merged-policy.json"
    assert restore_result.output_removed is True
    assert external_output.exists()


def test_restore_rejects_snapshot_path_traversal(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    backup_dir = input_dir / "backup"
    backup_dir.mkdir()
    escaped_snapshot = tmp_path / "escaped"
    escaped_snapshot.mkdir()
    _write_json(
        escaped_snapshot / "manifest.json",
        {
            "schema_version": 1,
            "tool_version": "4.0.0",
            "created_at": "2026-04-11T00:00:00Z",
            "input_directory": str(input_dir),
            "output_file": "merged-policy.json",
            "merge_keys": [],
            "files": ["10-policy.json"],
        },
    )
    _write_json(escaped_snapshot / "10-policy.json", {})

    with pytest.raises(RestoreError):
        restore_backup_snapshot(
            RestoreConfig(
                input_directory=input_dir,
                backup_dir=backup_dir,
                snapshot_name="..\\escaped",
            )
        )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
