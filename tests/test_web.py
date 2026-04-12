"""Tests for the FastAPI web UI and API."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from chrome_policy_merge.web import app


def test_index_renders_web_console(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHROME_POLICY_MERGE_WORKSPACE_ROOT", str(tmp_path))

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "Chrome Policy Merge Web Console" in response.text
    assert "Workspace Mode" in response.text


def test_upload_preview_merges_uploaded_files() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/upload/preview",
        data={"merge_keys": "ExtensionSettings\nURLAllowlist", "strict": "false"},
        files=[
            (
                "files",
                (
                    "10-base.json",
                    json.dumps({"HomepageLocation": "https://portal.example.com"}).encode("utf-8"),
                    "application/json",
                ),
            ),
            (
                "files",
                (
                    "20-extra.json",
                    json.dumps({"URLAllowlist": ["https://portal.example.com"]}).encode("utf-8"),
                    "application/json",
                ),
            ),
            ("files", ("notes.txt", b"ignore me", "text/plain")),
        ],
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["processed_files"] == ["10-base.json", "20-extra.json"]
    assert payload["skipped_entries"] == ["notes.txt"]
    assert payload["merged_policy"] == {
        "HomepageLocation": "https://portal.example.com",
        "URLAllowlist": ["https://portal.example.com"],
    }
    assert payload["manifest"]["tool_version"] == "4.0.1"


def test_upload_bundle_contains_manifest_and_output() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/upload/bundle",
        data={"merge_keys": "ExtensionSettings"},
        files=[
            (
                "files",
                (
                    "10-base.json",
                    json.dumps({"HomepageLocation": "https://portal.example.com"}).encode("utf-8"),
                    "application/json",
                ),
            ),
        ],
    )

    assert response.status_code == 200

    with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
        names = set(bundle.namelist())
        assert "merged-policy.json" in names
        assert "backup/snapshot-browser-upload/manifest.json" in names
        manifest = json.loads(bundle.read("backup/snapshot-browser-upload/manifest.json"))
        merged_output = json.loads(bundle.read("merged-policy.json"))

    assert manifest["tool_version"] == "4.0.1"
    assert merged_output == {"HomepageLocation": "https://portal.example.com"}


def test_upload_preview_rejects_invalid_json() -> None:
    client = TestClient(app)

    response = client.post(
        "/api/upload/preview",
        data={"merge_keys": "ExtensionSettings"},
        files=[("files", ("10-invalid.json", b"{not-json}", "application/json"))],
    )

    assert response.status_code == 422
    assert "invalid JSON" in response.json()["detail"]


def test_workspace_merge_and_restore_round_trip(monkeypatch, tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    input_dir = workspace_root / "policies"
    input_dir.mkdir(parents=True)
    (input_dir / "10-policy.json").write_text(
        json.dumps({"HomepageLocation": "https://portal.example.com"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CHROME_POLICY_MERGE_WORKSPACE_ROOT", str(workspace_root))

    client = TestClient(app)
    merge_response = client.post(
        "/api/workspace/merge",
        json={
            "input_directory": "policies",
            "output_file": "merged-policy.json",
            "backup_dir": "backup",
            "merge_keys": [],
            "strict": False,
            "dry_run": False,
        },
    )

    merge_payload = merge_response.json()
    assert merge_response.status_code == 200
    assert merge_payload["output_file"] == "policies/merged-policy.json"
    assert merge_payload["backup_snapshot"] is not None
    assert merge_payload["manifest"]["tool_version"] == "4.0.1"

    snapshots_response = client.get(
        "/api/workspace/snapshots",
        params={"input_directory": "policies", "backup_dir": "backup"},
    )
    snapshots_payload = snapshots_response.json()
    assert snapshots_response.status_code == 200
    assert len(snapshots_payload["snapshots"]) == 1

    snapshot_name = snapshots_payload["snapshots"][0]["name"]
    restore_response = client.post(
        "/api/workspace/restore",
        json={
            "input_directory": "policies",
            "backup_dir": "backup",
            "snapshot_name": snapshot_name,
            "output_file": "merged-policy.json",
            "remove_output": True,
            "dry_run": False,
        },
    )

    restore_payload = restore_response.json()
    assert restore_response.status_code == 200
    assert restore_payload["restored_files"] == ["10-policy.json"]
    assert restore_payload["output_removed"] is True
    assert (input_dir / "10-policy.json").exists()
    assert not (input_dir / "merged-policy.json").exists()


def test_workspace_path_escape_is_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHROME_POLICY_MERGE_WORKSPACE_ROOT", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/workspace/merge",
        json={"input_directory": "..", "output_file": "merged-policy.json", "backup_dir": "backup"},
    )

    assert response.status_code == 400
    assert "workspace root" in response.json()["detail"]
