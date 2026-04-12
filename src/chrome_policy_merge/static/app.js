const bootstrap = JSON.parse(document.getElementById("bootstrap-data").textContent);

const state = {
  config: bootstrap,
  snapshots: [],
};

document.addEventListener("DOMContentLoaded", () => {
  wireTabs();
  wireChipRows();
  wireUploadDropzone();
  wireButtons();
  updateUploadFileList();
  void initialize();
});

async function initialize() {
  try {
    const config = await requestJSON("/api/config");
    state.config = config;
    updateWorkspaceRoot(config.workspace_root);
    populateDirectoryList(config.directories || []);
    setNotice(`Ready. Workspace root is ${config.workspace_root}.`, "info");
    await Promise.all([scanWorkspace(), loadSnapshots()]);
  } catch (error) {
    setNotice(getErrorMessage(error), "error");
  }
}

function wireTabs() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.target;
      if (!target) {
        return;
      }

      document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("is-active"));
      document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.remove("is-active"));
      button.classList.add("is-active");
      document.getElementById(target)?.classList.add("is-active");
    });
  });
}

function wireChipRows() {
  document.querySelectorAll(".chip-row").forEach((row) => {
    const targetId = row.dataset.target;
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target) {
      return;
    }

    row.querySelectorAll(".chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const key = chip.textContent.trim();
        const existing = parseMergeKeys(target.value);
        if (!existing.includes(key)) {
          existing.push(key);
          target.value = existing.join("\n");
        }
      });
    });
  });
}

function wireUploadDropzone() {
  const dropzone = document.getElementById("upload-dropzone");
  const fileInput = document.getElementById("upload-files");
  if (!dropzone || !fileInput) {
    return;
  }

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-active");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-active");
    });
  });

  dropzone.addEventListener("drop", (event) => {
    if (!event.dataTransfer?.files?.length) {
      return;
    }
    const transfer = new DataTransfer();
    Array.from(event.dataTransfer.files).forEach((file) => transfer.items.add(file));
    fileInput.files = transfer.files;
    updateUploadFileList();
  });

  fileInput.addEventListener("change", () => updateUploadFileList());
}

function wireButtons() {
  document.getElementById("workspace-scan")?.addEventListener("click", () => void scanWorkspace());
  document.getElementById("workspace-merge")?.addEventListener("click", () => void mergeWorkspace());
  document.getElementById("workspace-refresh-snapshots")?.addEventListener("click", () => void loadSnapshots());
  document.getElementById("workspace-restore")?.addEventListener("click", () => void restoreWorkspace());
  document.getElementById("upload-preview")?.addEventListener("click", () => void previewUpload());
  document.getElementById("upload-download")?.addEventListener("click", () => void downloadBundle());
}

function updateWorkspaceRoot(rootPath) {
  const workspaceRoot = document.getElementById("workspace-root");
  if (workspaceRoot) {
    workspaceRoot.textContent = rootPath;
  }
}

function populateDirectoryList(directories) {
  const list = document.getElementById("workspace-directories");
  if (!list) {
    return;
  }
  list.innerHTML = "";
  directories.forEach((directory) => {
    const option = document.createElement("option");
    option.value = directory;
    list.appendChild(option);
  });
}

function updateUploadFileList() {
  const fileInput = document.getElementById("upload-files");
  const list = document.getElementById("upload-file-list");
  if (!fileInput || !list) {
    return;
  }

  if (!fileInput.files?.length) {
    list.classList.add("empty-state");
    list.innerHTML = "<li>No upload files selected.</li>";
    return;
  }

  list.classList.remove("empty-state");
  list.innerHTML = "";
  Array.from(fileInput.files).forEach((file) => {
    const item = document.createElement("li");
    item.textContent = `${file.name} (${formatBytes(file.size)})`;
    list.appendChild(item);
  });
}

function getWorkspacePayload() {
  return {
    input_directory: getValue("workspace-input-directory"),
    output_file: getOptionalValue("workspace-output-file"),
    backup_dir: getOptionalValue("workspace-backup-dir"),
    merge_keys: parseMergeKeys(getValue("workspace-merge-keys")),
    strict: document.getElementById("workspace-strict")?.checked ?? false,
    dry_run: document.getElementById("workspace-dry-run")?.checked ?? false,
  };
}

function getRestorePayload() {
  return {
    input_directory: getValue("workspace-input-directory"),
    backup_dir: getOptionalValue("workspace-backup-dir"),
    snapshot_name: getOptionalValue("workspace-snapshot-select"),
    output_file: getOptionalValue("workspace-output-file"),
    remove_output: document.getElementById("workspace-remove-output")?.checked ?? false,
    dry_run: document.getElementById("workspace-restore-dry-run")?.checked ?? false,
  };
}

async function scanWorkspace() {
  try {
    const params = new URLSearchParams({
      input_directory: getValue("workspace-input-directory"),
      output_file: getValue("workspace-output-file"),
    });
    const result = await requestJSON(`/api/workspace/scan?${params.toString()}`);
    renderSimpleList("workspace-candidates", result.candidate_files, "No eligible JSON policy files were found.");
    renderSimpleList("workspace-skipped", result.skipped_entries, "Nothing is currently being skipped.");
  } catch (error) {
    setNotice(getErrorMessage(error), "error");
  }
}

async function loadSnapshots() {
  try {
    const params = new URLSearchParams({ input_directory: getValue("workspace-input-directory") });
    const backupDir = getOptionalValue("workspace-backup-dir");
    if (backupDir) {
      params.set("backup_dir", backupDir);
    }

    const result = await requestJSON(`/api/workspace/snapshots?${params.toString()}`);
    state.snapshots = result.snapshots || [];
    populateSnapshotSelect();
    renderSnapshotList();
  } catch (error) {
    setNotice(getErrorMessage(error), "error");
  }
}

function populateSnapshotSelect() {
  const select = document.getElementById("workspace-snapshot-select");
  if (!select) {
    return;
  }

  select.innerHTML = "";
  if (!state.snapshots.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No snapshots available";
    select.appendChild(option);
    return;
  }

  state.snapshots.forEach((snapshot) => {
    const option = document.createElement("option");
    option.value = snapshot.name;
    option.textContent = snapshot.name;
    select.appendChild(option);
  });
}

function renderSnapshotList() {
  const snapshotList = document.getElementById("workspace-snapshot-list");
  if (!snapshotList) {
    return;
  }

  if (!state.snapshots.length) {
    snapshotList.classList.add("empty-state");
    snapshotList.innerHTML = "<li>No snapshots available yet.</li>";
    return;
  }

  snapshotList.classList.remove("empty-state");
  snapshotList.innerHTML = state.snapshots
    .map((snapshot) => {
      const count = snapshot.files?.length ?? 0;
      const createdAt = snapshot.created_at ? ` • ${snapshot.created_at}` : "";
      return `<li><strong>${escapeHtml(snapshot.name)}</strong><span class="snapshot-meta">${count} file(s)${escapeHtml(createdAt)}</span></li>`;
    })
    .join("");
}

async function mergeWorkspace() {
  try {
    setNotice("Running workspace merge...", "info");
    const result = await requestJSON("/api/workspace/merge", {
      method: "POST",
      body: JSON.stringify(getWorkspacePayload()),
    });
    renderResult(result);
    await Promise.all([loadSnapshots(), scanWorkspace()]);
    setNotice(
      result.dry_run ? "Dry-run merge completed successfully." : `Merge completed. Output written to ${result.output_file}.`,
      "success",
    );
  } catch (error) {
    setNotice(getErrorMessage(error), "error");
  }
}

async function restoreWorkspace() {
  try {
    setNotice("Running restore...", "info");
    const result = await requestJSON("/api/workspace/restore", {
      method: "POST",
      body: JSON.stringify(getRestorePayload()),
    });
    renderResult(result);
    await Promise.all([loadSnapshots(), scanWorkspace()]);
    setNotice(
      result.dry_run ? "Dry-run restore completed successfully." : `Restore completed from ${result.snapshot_dir}.`,
      "success",
    );
  } catch (error) {
    setNotice(getErrorMessage(error), "error");
  }
}

async function previewUpload() {
  try {
    setNotice("Previewing uploaded files...", "info");
    const result = await requestJSON("/api/upload/preview", {
      method: "POST",
      body: buildUploadFormData(),
      isForm: true,
    });
    renderResult(result);
    setNotice("Upload preview completed successfully.", "success");
  } catch (error) {
    setNotice(getErrorMessage(error), "error");
  }
}

async function downloadBundle() {
  try {
    setNotice("Building downloadable bundle...", "info");
    const response = await fetch("/api/upload/bundle", {
      method: "POST",
      body: buildUploadFormData(),
    });
    if (!response.ok) {
      throw new Error(await readErrorDetail(response));
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "chrome-policy-merge-bundle.zip";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setNotice("Bundle ready. Your browser download should begin immediately.", "success");
  } catch (error) {
    setNotice(getErrorMessage(error), "error");
  }
}

function buildUploadFormData() {
  const fileInput = document.getElementById("upload-files");
  if (!fileInput?.files?.length) {
    throw new Error("Select at least one JSON policy file first.");
  }

  const formData = new FormData();
  Array.from(fileInput.files).forEach((file) => formData.append("files", file, file.name));
  formData.append("merge_keys", getValue("upload-merge-keys"));
  formData.append("strict", document.getElementById("upload-strict")?.checked ? "true" : "false");
  return formData;
}

function renderSimpleList(elementId, items, emptyMessage) {
  const list = document.getElementById(elementId);
  if (!list) {
    return;
  }

  if (!items?.length) {
    list.classList.add("empty-state");
    list.innerHTML = `<li>${escapeHtml(emptyMessage)}</li>`;
    return;
  }

  list.classList.remove("empty-state");
  list.innerHTML = items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
}

function renderResult(result) {
  const processedCount = result.processed_files?.length ?? result.restored_files?.length ?? 0;
  const keyCount = result.merged_policy ? Object.keys(result.merged_policy).length : 0;
  const skippedCount = result.skipped_entries?.length ?? 0;

  document.getElementById("result-mode-pill").textContent = humanizeMode(result.mode);
  document.getElementById("metric-strip").innerHTML = `
    <div class="metric-card"><span class="metric-label">Processed files</span><strong class="metric-value">${processedCount}</strong></div>
    <div class="metric-card"><span class="metric-label">Top-level keys</span><strong class="metric-value">${keyCount}</strong></div>
    <div class="metric-card"><span class="metric-label">Skipped entries</span><strong class="metric-value">${skippedCount}</strong></div>
  `;

  const summarySections = [];
  if (result.output_file) summarySections.push(summaryCard("Output", [result.output_file]));
  if (result.backup_snapshot) summarySections.push(summaryCard("Backup snapshot", [result.backup_snapshot]));
  if (result.snapshot_dir) summarySections.push(summaryCard("Restore source", [result.snapshot_dir]));
  if (result.processed_files?.length) summarySections.push(summaryCard("Processed files", result.processed_files));
  if (result.restored_files?.length) summarySections.push(summaryCard("Restored files", result.restored_files));
  if (result.skipped_entries?.length) summarySections.push(summaryCard("Skipped entries", result.skipped_entries));
  if (result.merge_keys?.length) summarySections.push(summaryCard("Merge keys", result.merge_keys));
  if (!summarySections.length) {
    summarySections.push(summaryCard("Result", ["The operation completed, but there was no file movement to report."]));
  }

  const summary = document.getElementById("result-summary-content");
  summary.classList.remove("empty-state");
  summary.innerHTML = summarySections.join("");
  document.getElementById("result-json-output").textContent = result.merged_policy
    ? JSON.stringify(result.merged_policy, null, 2)
    : "No merged JSON returned for this operation.";
  document.getElementById("result-manifest-output").textContent = result.manifest
    ? JSON.stringify(result.manifest, null, 2)
    : "No manifest returned for this operation.";
}

function summaryCard(title, items) {
  return `<div class="summary-card"><h4>${escapeHtml(title)}</h4><ul>${items.map((item) => `<li>${escapeHtml(String(item))}</li>`).join("")}</ul></div>`;
}

function setNotice(message, type) {
  const notice = document.getElementById("notice");
  if (!notice) {
    return;
  }
  notice.textContent = message;
  notice.className = `notice notice-${type}`;
}

async function requestJSON(url, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!options.isForm) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("Accept", "application/json");

  const response = await fetch(url, {
    method: options.method || "GET",
    headers,
    body: options.body,
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response));
  }
  return response.json();
}

async function readErrorDetail(response) {
  try {
    const payload = await response.json();
    return payload.detail || JSON.stringify(payload);
  } catch {
    return response.statusText || "Request failed.";
  }
}

function humanizeMode(mode) {
  return mode ? mode.replaceAll("-", " ").replace(/\b\w/g, (match) => match.toUpperCase()) : "Waiting";
}

function parseMergeKeys(value) {
  return value
    .split(/\n|,/)
    .map((part) => part.trim())
    .filter(Boolean)
    .filter((part, index, parts) => parts.indexOf(part) === index);
}

function getValue(elementId) {
  return document.getElementById(elementId)?.value?.trim() ?? "";
}

function getOptionalValue(elementId) {
  const value = getValue(elementId);
  return value || null;
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getErrorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}
