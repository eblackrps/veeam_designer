"""FastAPI web UI and API for Chrome Policy Merge."""

from __future__ import annotations

import argparse
import io
import json
import os
import zipfile
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from ._version import __version__
from .exceptions import InvalidPolicyFileError, PolicyMergeError
from .merge import (
    DEFAULT_BACKUP_DIRNAME,
    DEFAULT_OUTPUT_FILENAME,
    MANIFEST_FILENAME,
    discover_policy_files,
    load_policy_text,
    merge_policy_directory,
    merge_policy_objects,
    natural_sort_key,
    restore_backup_snapshot,
)
from .models import (
    BackupManifest,
    JSONObject,
    MergeConfig,
    MergeResult,
    RestoreConfig,
    RestoreResult,
)

MODULE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = MODULE_DIR / "templates"
STATIC_DIR = MODULE_DIR / "static"
DEFAULT_WORKSPACE_ROOTNAME = "workspace"
MAX_UPLOAD_FILE_COUNT = 64
MAX_UPLOAD_BYTES = 16 * 1024 * 1024
MERGE_KEY_SUGGESTIONS = (
    "ExtensionSettings",
    "URLAllowlist",
    "URLBlocklist",
    "ManagedBookmarks",
    "AutoSelectCertificateForUrls",
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app = FastAPI(
    title="Chrome Policy Merge",
    version=__version__,
    docs_url="/api/docs",
    redoc_url=None,
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class WorkspaceMergeRequest(BaseModel):
    """Request body for workspace merge operations."""

    input_directory: str = Field(default=".", min_length=1, max_length=240)
    output_file: str | None = Field(default=None, max_length=240)
    backup_dir: str | None = Field(default=None, max_length=240)
    merge_keys: list[str] = Field(default_factory=list)
    strict: bool = False
    dry_run: bool = False


class WorkspaceRestoreRequest(BaseModel):
    """Request body for workspace restore operations."""

    input_directory: str = Field(default=".", min_length=1, max_length=240)
    backup_dir: str | None = Field(default=None, max_length=240)
    snapshot_name: str | None = Field(default=None, max_length=240)
    output_file: str | None = Field(default=None, max_length=240)
    remove_output: bool = False
    dry_run: bool = False


@app.exception_handler(PolicyMergeError)
async def policy_error_handler(_: Request, exc: PolicyMergeError) -> JSONResponse:
    """Render merge and restore errors as API-safe JSON responses."""

    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Render the web dashboard."""

    workspace_root = _workspace_root()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "version": __version__,
            "workspace_root": str(workspace_root),
            "default_output_file": DEFAULT_OUTPUT_FILENAME,
            "default_backup_dir": DEFAULT_BACKUP_DIRNAME,
            "merge_key_suggestions": MERGE_KEY_SUGGESTIONS,
        },
    )


@app.get("/api/health")
async def api_health() -> dict[str, str]:
    """Return a health payload suitable for liveness checks."""

    return {
        "status": "ok",
        "version": __version__,
        "workspace_root": str(_workspace_root()),
    }


@app.get("/api/config")
async def api_config() -> dict[str, Any]:
    """Return UI bootstrap data."""

    workspace_root = _workspace_root()
    return {
        "version": __version__,
        "workspace_root": str(workspace_root),
        "directories": _list_workspace_directories(workspace_root),
        "merge_key_suggestions": list(MERGE_KEY_SUGGESTIONS),
        "default_output_file": DEFAULT_OUTPUT_FILENAME,
        "default_backup_dir": DEFAULT_BACKUP_DIRNAME,
    }


@app.get("/api/workspace/scan")
async def api_workspace_scan(
    input_directory: Annotated[str, Query(min_length=1, max_length=240)] = ".",
    output_file: Annotated[str | None, Query(max_length=240)] = None,
) -> dict[str, Any]:
    """Inspect a workspace directory and report eligible policy files."""

    workspace_root = _workspace_root()
    input_dir = _resolve_workspace_path(
        input_directory,
        field_name="input_directory",
        workspace_root=workspace_root,
    )
    assert input_dir is not None
    if not input_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Directory does not exist: {input_directory}")

    resolved_output = (
        _resolve_workspace_path(
            output_file,
            field_name="output_file",
            workspace_root=workspace_root,
            base_dir=input_dir,
        )
        if output_file
        else (input_dir / DEFAULT_OUTPUT_FILENAME).resolve()
    )
    assert resolved_output is not None

    candidates, skipped = discover_policy_files(input_dir, output_file=resolved_output)
    return {
        "input_directory": _to_relative_string(input_dir, workspace_root),
        "output_file": _to_relative_string(resolved_output, workspace_root),
        "candidate_files": [path.name for path in candidates],
        "skipped_entries": [path.name for path in skipped],
    }


@app.get("/api/workspace/snapshots")
async def api_workspace_snapshots(
    input_directory: Annotated[str, Query(min_length=1, max_length=240)] = ".",
    backup_dir: Annotated[str | None, Query(max_length=240)] = None,
) -> dict[str, Any]:
    """List available snapshots for a workspace directory."""

    workspace_root = _workspace_root()
    input_dir = _resolve_workspace_path(
        input_directory,
        field_name="input_directory",
        workspace_root=workspace_root,
    )
    assert input_dir is not None
    if not input_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Directory does not exist: {input_directory}")

    resolved_backup_dir = (
        _resolve_workspace_path(
            backup_dir,
            field_name="backup_dir",
            workspace_root=workspace_root,
            base_dir=input_dir,
        )
        if backup_dir
        else (input_dir / DEFAULT_BACKUP_DIRNAME).resolve()
    )
    assert resolved_backup_dir is not None

    snapshots: list[dict[str, Any]] = []
    if resolved_backup_dir.is_dir():
        for snapshot_dir in sorted(
            [path for path in resolved_backup_dir.iterdir() if path.is_dir()],
            key=natural_sort_key,
            reverse=True,
        ):
            manifest = _read_manifest_if_available(snapshot_dir / MANIFEST_FILENAME)
            snapshots.append(
                {
                    "name": snapshot_dir.name,
                    "path": _to_relative_string(snapshot_dir, workspace_root),
                    "created_at": manifest.created_at if manifest else None,
                    "files": list(manifest.files) if manifest else [],
                    "merge_keys": list(manifest.merge_keys) if manifest else [],
                    "tool_version": manifest.tool_version if manifest else None,
                }
            )

    return {
        "input_directory": _to_relative_string(input_dir, workspace_root),
        "backup_dir": _to_relative_string(resolved_backup_dir, workspace_root),
        "snapshots": snapshots,
    }


@app.post("/api/workspace/merge")
async def api_workspace_merge(payload: WorkspaceMergeRequest) -> dict[str, Any]:
    """Execute a merge against the configured workspace root."""

    workspace_root = _workspace_root()
    merge_keys = _normalize_merge_keys(payload.merge_keys)
    input_dir = _resolve_workspace_path(
        payload.input_directory,
        field_name="input_directory",
        workspace_root=workspace_root,
    )
    assert input_dir is not None
    output_file = _resolve_workspace_path(
        payload.output_file,
        field_name="output_file",
        workspace_root=workspace_root,
        base_dir=input_dir,
    )
    backup_dir = _resolve_workspace_path(
        payload.backup_dir,
        field_name="backup_dir",
        workspace_root=workspace_root,
        base_dir=input_dir,
    )

    result = merge_policy_directory(
        MergeConfig(
            input_directory=input_dir,
            output_file=output_file,
            backup_dir=backup_dir,
            merge_keys=merge_keys,
            strict=payload.strict,
            dry_run=payload.dry_run,
        )
    )
    response = _serialize_merge_result(result, workspace_root=workspace_root)
    response["merge_keys"] = list(merge_keys)
    if response["manifest"] is None and result.processed_files:
        response["manifest"] = _build_workspace_manifest(result, merge_keys).to_json_object()
    return response


@app.post("/api/workspace/restore")
async def api_workspace_restore(payload: WorkspaceRestoreRequest) -> dict[str, Any]:
    """Restore a backup snapshot inside the configured workspace root."""

    workspace_root = _workspace_root()
    input_dir = _resolve_workspace_path(
        payload.input_directory,
        field_name="input_directory",
        workspace_root=workspace_root,
    )
    assert input_dir is not None
    output_file = _resolve_workspace_path(
        payload.output_file,
        field_name="output_file",
        workspace_root=workspace_root,
        base_dir=input_dir,
    )
    backup_dir = _resolve_workspace_path(
        payload.backup_dir,
        field_name="backup_dir",
        workspace_root=workspace_root,
        base_dir=input_dir,
    )

    result = restore_backup_snapshot(
        RestoreConfig(
            input_directory=input_dir,
            backup_dir=backup_dir,
            snapshot_name=payload.snapshot_name,
            output_file=output_file,
            remove_output=payload.remove_output,
            dry_run=payload.dry_run,
        )
    )
    return _serialize_restore_result(result, workspace_root=workspace_root)


@app.post("/api/upload/preview")
async def api_upload_preview(
    files: Annotated[list[UploadFile], File(description="Policy JSON files")],
    merge_keys: Annotated[str, Form()] = "",
    strict: Annotated[bool, Form()] = False,
) -> dict[str, Any]:
    """Preview an uploaded merge in memory and return the merged JSON."""

    processed_uploads, skipped_entries = await _collect_uploads(files)
    merge_key_tuple = _parse_merge_key_text(merge_keys)
    merged_policy, processed_names = _merge_uploaded_documents(
        processed_uploads,
        merge_keys=merge_key_tuple,
        strict=strict,
    )
    manifest = _build_upload_manifest(processed_names, merge_key_tuple)
    return {
        "mode": "upload-preview",
        "processed_files": list(processed_names),
        "skipped_entries": skipped_entries,
        "strict": strict,
        "merge_keys": list(merge_key_tuple),
        "merged_policy": merged_policy,
        "manifest": manifest.to_json_object(),
        "stats": {
            "file_count": len(processed_names),
            "skipped_count": len(skipped_entries),
            "top_level_key_count": len(merged_policy),
        },
    }


@app.post("/api/upload/bundle")
async def api_upload_bundle(
    files: Annotated[list[UploadFile], File(description="Policy JSON files")],
    merge_keys: Annotated[str, Form()] = "",
    strict: Annotated[bool, Form()] = False,
) -> StreamingResponse:
    """Build a downloadable archive from uploaded policy files."""

    processed_uploads, skipped_entries = await _collect_uploads(files)
    merge_key_tuple = _parse_merge_key_text(merge_keys)
    merged_policy, processed_names = _merge_uploaded_documents(
        processed_uploads,
        merge_keys=merge_key_tuple,
        strict=strict,
    )
    manifest = _build_upload_manifest(processed_names, merge_key_tuple)
    snapshot_name = "snapshot-browser-upload"

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, mode="w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(
            DEFAULT_OUTPUT_FILENAME,
            _format_json_document(merged_policy).encode("utf-8"),
        )
        bundle.writestr(
            f"backup/{snapshot_name}/{MANIFEST_FILENAME}",
            _format_json_document(manifest.to_json_object()).encode("utf-8"),
        )
        if skipped_entries:
            skipped_payload = {"skipped_entries": skipped_entries}
            bundle.writestr(
                f"backup/{snapshot_name}/skipped.json",
                _format_json_document(skipped_payload).encode("utf-8"),
            )
        for name, raw_bytes in processed_uploads:
            bundle.writestr(f"backup/{snapshot_name}/{name}", raw_bytes)

    archive_bytes.seek(0)
    headers = {
        "Content-Disposition": 'attachment; filename="chrome-policy-merge-bundle.zip"',
    }
    return StreamingResponse(
        archive_bytes,
        media_type="application/zip",
        headers=headers,
    )


def run(argv: Sequence[str] | None = None) -> int:
    """Run the web application with Uvicorn."""

    parser = argparse.ArgumentParser(
        prog="chrome-policy-merge-web",
        description="Launch the Chrome Policy Merge web interface.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Defaults to 127.0.0.1.")
    parser.add_argument("--port", type=int, default=8000, help="Bind port. Defaults to 8000.")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    uvicorn.run("chrome_policy_merge.web:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _workspace_root() -> Path:
    """Return the configured workspace root, creating it if needed."""

    configured = os.environ.get("CHROME_POLICY_MERGE_WORKSPACE_ROOT")
    workspace_root = (
        Path(configured).expanduser() if configured else Path.cwd() / DEFAULT_WORKSPACE_ROOTNAME
    )
    resolved = workspace_root.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _resolve_workspace_path(
    raw_path: str | None,
    *,
    field_name: str,
    workspace_root: Path,
    base_dir: Path | None = None,
) -> Path | None:
    """Resolve a user path safely inside the workspace root."""

    if raw_path is None or not raw_path.strip():
        return None

    candidate = Path(raw_path.strip())
    if candidate.is_absolute():
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be a relative path inside the workspace root.",
        )

    anchor = base_dir if base_dir is not None else workspace_root
    resolved = (anchor / candidate).resolve()
    if not _is_relative_to(resolved, workspace_root):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must stay inside the workspace root.",
        )
    return resolved


def _to_relative_string(path: Path, workspace_root: Path) -> str:
    """Return a workspace-relative display path."""

    relative = path.relative_to(workspace_root)
    return "." if not relative.parts else relative.as_posix()


def _list_workspace_directories(workspace_root: Path, *, max_depth: int = 3) -> list[str]:
    """Return a bounded list of directories for the UI directory picker."""

    results = ["."]

    def walk(directory: Path, depth: int) -> None:
        if depth > max_depth:
            return
        directories = [entry for entry in directory.iterdir() if entry.is_dir()]
        for child in sorted(directories, key=natural_sort_key):
            if child.name.startswith(".") or child.name == "__pycache__":
                continue
            results.append(_to_relative_string(child, workspace_root))
            walk(child, depth + 1)

    walk(workspace_root, 1)
    return results[:200]


def _normalize_merge_keys(values: Iterable[str]) -> tuple[str, ...]:
    """Normalize merge keys by trimming whitespace and de-duplicating in order."""

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return tuple(normalized)


def _parse_merge_key_text(value: str) -> tuple[str, ...]:
    """Parse a comma- or newline-delimited merge-key list."""

    candidates = [part for chunk in value.splitlines() for part in chunk.split(",")]
    return _normalize_merge_keys(candidates)


async def _collect_uploads(
    files: Sequence[UploadFile],
) -> tuple[list[tuple[str, bytes]], list[str]]:
    """Read uploaded files into memory with size and suffix validation."""

    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one JSON policy file.")
    if len(files) > MAX_UPLOAD_FILE_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Upload at most {MAX_UPLOAD_FILE_COUNT} files per request.",
        )

    total_bytes = 0
    processed: list[tuple[str, bytes]] = []
    skipped: list[str] = []

    for upload in files:
        file_name = Path(upload.filename or "upload.json").name
        raw_bytes = await upload.read()
        await upload.close()
        total_bytes += len(raw_bytes)
        if total_bytes > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Uploads must stay below {MAX_UPLOAD_BYTES // (1024 * 1024)} MB total.",
            )

        if Path(file_name).suffix.casefold() != ".json":
            skipped.append(file_name)
            continue
        processed.append((file_name, raw_bytes))

    if not processed:
        raise HTTPException(status_code=400, detail="No JSON files were uploaded.")

    processed.sort(key=lambda item: natural_sort_key(item[0]))
    skipped.sort(key=natural_sort_key)
    return processed, skipped


def _merge_uploaded_documents(
    uploads: Sequence[tuple[str, bytes]],
    *,
    merge_keys: tuple[str, ...],
    strict: bool,
) -> tuple[JSONObject, tuple[str, ...]]:
    """Merge uploaded JSON policy documents in natural filename order."""

    merged_policy: JSONObject = {}
    processed_names: list[str] = []

    for name, raw_bytes in uploads:
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidPolicyFileError(Path(name), "file must be UTF-8 encoded JSON") from exc
        policy_object = load_policy_text(name, text)
        merged_policy = merge_policy_objects(
            merged_policy,
            policy_object,
            merge_keys=merge_keys,
            strict=strict,
        )
        processed_names.append(name)

    return merged_policy, tuple(processed_names)


def _build_upload_manifest(
    processed_names: Sequence[str],
    merge_keys: tuple[str, ...],
) -> BackupManifest:
    """Build a synthetic manifest for uploaded browser sessions."""

    return BackupManifest(
        schema_version=1,
        tool_version=__version__,
        created_at=datetime.now(timezone.utc).isoformat(),
        input_directory="browser-upload",
        output_file=DEFAULT_OUTPUT_FILENAME,
        merge_keys=merge_keys,
        files=tuple(processed_names),
    )


def _build_workspace_manifest(result: MergeResult, merge_keys: tuple[str, ...]) -> BackupManifest:
    """Build manifest metadata for dry-run workspace responses."""

    return BackupManifest(
        schema_version=1,
        tool_version=__version__,
        created_at=datetime.now(timezone.utc).isoformat(),
        input_directory=str(result.processed_files[0].parent if result.processed_files else ""),
        output_file=str(result.output_file),
        merge_keys=merge_keys,
        files=tuple(path.name for path in result.processed_files),
    )


def _serialize_merge_result(result: MergeResult, *, workspace_root: Path) -> dict[str, Any]:
    """Convert a merge result to a JSON-safe API payload."""

    manifest = (
        _read_manifest_if_available(result.backup_snapshot / MANIFEST_FILENAME)
        if result.backup_snapshot is not None
        else None
    )
    backup_snapshot = (
        _to_relative_string(result.backup_snapshot, workspace_root)
        if result.backup_snapshot is not None
        else None
    )
    return {
        "mode": "workspace-merge",
        "dry_run": result.dry_run,
        "output_written": result.output_written,
        "output_file": _to_relative_string(result.output_file, workspace_root),
        "backup_snapshot": backup_snapshot,
        "processed_files": [path.name for path in result.processed_files],
        "skipped_entries": [path.name for path in result.skipped_entries],
        "merge_keys": list(manifest.merge_keys) if manifest else [],
        "manifest": manifest.to_json_object() if manifest else None,
        "merged_policy": result.merged_policy,
        "stats": {
            "file_count": len(result.processed_files),
            "skipped_count": len(result.skipped_entries),
            "top_level_key_count": len(result.merged_policy),
        },
    }


def _serialize_restore_result(result: RestoreResult, *, workspace_root: Path) -> dict[str, Any]:
    """Convert a restore result to a JSON-safe API payload."""

    return {
        "mode": "workspace-restore",
        "dry_run": result.dry_run,
        "snapshot_dir": _to_relative_string(result.snapshot_dir, workspace_root),
        "restored_files": [path.name for path in result.restored_files],
        "output_file": _to_relative_string(result.output_file, workspace_root),
        "output_removed": result.output_removed,
    }


def _read_manifest_if_available(path: Path) -> BackupManifest | None:
    """Load a manifest if present and valid."""

    if not path.is_file():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return BackupManifest.from_json_object(payload)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _format_json_document(payload: object) -> str:
    """Render a JSON payload with stable formatting."""

    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _is_relative_to(path: Path, other: Path) -> bool:
    """Return True when ``path`` is contained within ``other``."""

    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(run())
