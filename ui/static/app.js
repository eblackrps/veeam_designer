const bootstrap = JSON.parse(document.getElementById("builder-bootstrap").textContent);
const form = document.getElementById("designer-form");
const yamlEditor = document.getElementById("yaml-editor");
const sitesContainer = document.getElementById("sites-container");
const siteTemplate = document.getElementById("site-card-template");
const workloadButtons = Array.from(document.querySelectorAll(".mode-tab"));

const FORM_STORAGE_KEY = "veeam-designer-form-v401";
const EDITOR_STORAGE_KEY = "veeam-designer-yaml-v401";
const MODE_STORAGE_KEY = "veeam-designer-editor-mode-v401";

const defaultVmSites = [
  {
    name: "Primary DC",
    total_data_tb: 500,
    annual_growth_percent: 15,
    daily_change_percent: 5,
    primary_retention_days: 30,
    vm_count: 800,
    avg_vm_size_gb: 400,
    wan_bandwidth_mbps: 1000,
    backup_window_hours: 8,
    backup_type: "synthetic_full_weekly",
    repo_type: "sobr",
    has_san_access: true,
    on_host_proxy: false,
    refs_xfs: true,
    immutability_enabled: true,
    capacity_tier_enabled: true,
    direct_to_object: false,
    gfs_weekly_count: 4,
    gfs_monthly_count: 12,
    gfs_yearly_count: 3,
    block_generation_days: 10,
    concurrent_jobs: 5,
    notes: "Primary data center",
  },
  {
    name: "Regional DR",
    total_data_tb: 180,
    annual_growth_percent: 12,
    daily_change_percent: 4,
    primary_retention_days: 21,
    vm_count: 260,
    avg_vm_size_gb: 320,
    wan_bandwidth_mbps: 300,
    backup_window_hours: 10,
    backup_type: "synthetic_full_weekly",
    repo_type: "direct",
    has_san_access: false,
    on_host_proxy: true,
    refs_xfs: true,
    immutability_enabled: false,
    capacity_tier_enabled: false,
    direct_to_object: false,
    gfs_weekly_count: 2,
    gfs_monthly_count: 6,
    gfs_yearly_count: 0,
    block_generation_days: 7,
    concurrent_jobs: 3,
    notes: "Regional branch recovery target",
  },
];

const defaultState = {
  workloadType: "vm",
  editorMode: "builder",
  globals: {
    profile: "enterprise",
    hypervisor: "vmware",
    target_rpo: 24,
    compliance_framework: "none",
    compression_ratio: "",
    dedupe_ratio: "",
    throughput_mb_per_core: "",
  },
  vmSites: defaultVmSites,
  nas: {
    nas_source_tb: 120,
    nas_share_count: 80,
    nas_file_count: 1.5,
    nas_compress: 30,
    nas_daily: 5,
    nas_retention: 30,
    nas_window: 8,
    nas_growth: 10,
    nas_cft: false,
    nas_immutability: false,
    nas_object_storage: false,
  },
  physical: {
    machine_count: 150,
    avg_machine_size: 600,
    agent_daily: 5,
    agent_retention: 30,
    agent_window: 8,
    agent_network: 1000,
    agent_os: "windows",
  },
  replication: {
    rep_source_tb: 100,
    rep_vm_count: 300,
    rep_wan_mbps: 1000,
    rep_rpo_hours: 1,
    rep_rpo_seconds: 15,
    rep_cdp: false,
    rep_compression: true,
  },
};

document.addEventListener("DOMContentLoaded", () => {
  wireWorkloadButtons();
  wireEditorButtons();
  wireSiteButtons();
  wireResetButtons();
  restoreState();
  updateEditorModeNote();
  updateYamlFromBuilder();
  form.addEventListener("submit", handleSubmit);
  document.addEventListener("input", handleMutation, true);
  document.addEventListener("change", handleMutation, true);
});

function wireWorkloadButtons() {
  workloadButtons.forEach((button) => {
    button.addEventListener("click", () => {
      setWorkloadType(button.dataset.workload || "vm");
      handleMutation();
    });
  });
}

function wireEditorButtons() {
  document.getElementById("editor-mode-builder")?.addEventListener("click", () => {
    setEditorMode("builder");
    updateYamlFromBuilder();
    saveState();
  });
  document.getElementById("editor-mode-manual")?.addEventListener("click", () => {
    setEditorMode("manual");
    saveState();
  });
  document.getElementById("sync-yaml")?.addEventListener("click", () => {
    setEditorMode("builder");
    updateYamlFromBuilder();
    saveState();
  });
}

function wireSiteButtons() {
  document.getElementById("add-site")?.addEventListener("click", () => {
    appendSiteCard(newSiteDefaults(getCurrentSiteCount() + 1));
    refreshSiteTitles();
    handleMutation();
  });

  sitesContainer?.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement) || !target.classList.contains("remove-site")) {
      return;
    }

    if (getCurrentSiteCount() <= 1) {
      return;
    }

    target.closest(".site-card")?.remove();
    refreshSiteTitles();
    handleMutation();
  });
}

function wireResetButtons() {
  document.getElementById("reset-example")?.addEventListener("click", () => {
    localStorage.removeItem(FORM_STORAGE_KEY);
    localStorage.removeItem(EDITOR_STORAGE_KEY);
    localStorage.removeItem(MODE_STORAGE_KEY);
    window.location = "/run";
  });
}

function handleSubmit() {
  if (getEditorMode() === "builder") {
    updateYamlFromBuilder();
  }
  saveState();
}

function handleMutation() {
  if (getEditorMode() === "builder") {
    updateYamlFromBuilder();
  }
  refreshSiteTitles();
  saveState();
}

function restoreState() {
  const state = loadStoredState();
  applyGlobalState(state.globals);
  applyModeState(state);
  renderVmSites(state.vmSites);
  setWorkloadType(state.workloadType);
  setEditorMode(localStorage.getItem(MODE_STORAGE_KEY) || state.editorMode || "builder");

  const storedYaml = localStorage.getItem(EDITOR_STORAGE_KEY);
  if (storedYaml && getEditorMode() === "manual") {
    yamlEditor.value = storedYaml;
  } else {
    yamlEditor.value = bootstrap.yamlContent || yamlEditor.value;
  }
}

function loadStoredState() {
  try {
    const raw = localStorage.getItem(FORM_STORAGE_KEY);
    if (!raw) {
      return structuredClone(defaultState);
    }
    const parsed = JSON.parse(raw);
    return {
      ...structuredClone(defaultState),
      ...parsed,
      globals: { ...defaultState.globals, ...(parsed.globals || {}) },
      nas: { ...defaultState.nas, ...(parsed.nas || {}) },
      physical: { ...defaultState.physical, ...(parsed.physical || {}) },
      replication: { ...defaultState.replication, ...(parsed.replication || {}) },
      vmSites: Array.isArray(parsed.vmSites) && parsed.vmSites.length ? parsed.vmSites : structuredClone(defaultState.vmSites),
    };
  } catch {
    return structuredClone(defaultState);
  }
}

function applyGlobalState(globals) {
  setField("profile", globals.profile);
  setField("hypervisor", globals.hypervisor);
  setField("target-rpo", globals.target_rpo);
  setField("compliance-framework", globals.compliance_framework);
  setField("compression-ratio", globals.compression_ratio);
  setField("dedupe-ratio", globals.dedupe_ratio);
  setField("throughput-mb-per-core", globals.throughput_mb_per_core);
}

function applyModeState(state) {
  Object.entries(state.nas).forEach(([key, value]) => setField(camelToId(key), value));
  Object.entries(state.physical).forEach(([key, value]) => setField(camelToId(key), value));
  Object.entries(state.replication).forEach(([key, value]) => setField(camelToId(key), value));
}

function renderVmSites(sites) {
  sitesContainer.innerHTML = "";
  sites.forEach((site) => appendSiteCard(site));
  refreshSiteTitles();
}

function appendSiteCard(siteData) {
  const fragment = siteTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".site-card");
  Object.entries(siteData).forEach(([field, value]) => {
    const input = card.querySelector(`[data-field="${field}"]`);
    if (!input) {
      return;
    }
    if (input.type === "checkbox") {
      input.checked = Boolean(value);
    } else {
      input.value = value ?? "";
    }
  });
  sitesContainer.appendChild(fragment);
}

function refreshSiteTitles() {
  getSiteCards().forEach((card, index) => {
    const title = card.querySelector("[data-site-title]");
    if (title) {
      const siteName = getCardValue(card, "name") || `Site ${index + 1}`;
      title.textContent = siteName;
    }
  });

  const disableRemove = getCurrentSiteCount() <= 1;
  document.querySelectorAll(".remove-site").forEach((button) => {
    button.disabled = disableRemove;
  });
}

function getSiteCards() {
  return Array.from(document.querySelectorAll(".site-card"));
}

function getCurrentSiteCount() {
  return getSiteCards().length;
}

function getCurrentWorkload() {
  return document.querySelector(".mode-tab.is-active")?.dataset.workload || "vm";
}

function setWorkloadType(workload) {
  workloadButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.workload === workload);
  });
  document.querySelectorAll(".mode-panel").forEach((panel) => {
    panel.classList.toggle("is-active", panel.id === `mode-${workload}`);
  });
}

function getEditorMode() {
  return document.getElementById("editor-mode-builder")?.classList.contains("is-active") ? "builder" : "manual";
}

function setEditorMode(mode) {
  document.getElementById("editor-mode-builder")?.classList.toggle("is-active", mode === "builder");
  document.getElementById("editor-mode-manual")?.classList.toggle("is-active", mode === "manual");
  yamlEditor.readOnly = mode === "builder";
  updateEditorModeNote();
  localStorage.setItem(MODE_STORAGE_KEY, mode);
}

function updateEditorModeNote() {
  const note = document.getElementById("editor-mode-note");
  if (!note) {
    return;
  }
  note.textContent = getEditorMode() === "builder"
    ? "Builder Sync keeps the YAML editor generated from the calculator fields."
    : "Manual YAML leaves the editor writable. Use Rebuild YAML to replace it with the calculator state.";
}

function saveState() {
  const state = {
    workloadType: getCurrentWorkload(),
    editorMode: getEditorMode(),
    globals: {
      profile: getFieldValue("profile"),
      hypervisor: getFieldValue("hypervisor"),
      target_rpo: getFieldValue("target-rpo"),
      compliance_framework: getFieldValue("compliance-framework"),
      compression_ratio: getFieldValue("compression-ratio"),
      dedupe_ratio: getFieldValue("dedupe-ratio"),
      throughput_mb_per_core: getFieldValue("throughput-mb-per-core"),
    },
    vmSites: collectVmSites(),
    nas: collectNamedFields(defaultState.nas),
    physical: collectNamedFields(defaultState.physical),
    replication: collectNamedFields(defaultState.replication),
  };

  localStorage.setItem(FORM_STORAGE_KEY, JSON.stringify(state));
  localStorage.setItem(EDITOR_STORAGE_KEY, yamlEditor.value);
}

function collectNamedFields(shape) {
  const output = {};
  Object.keys(shape).forEach((key) => {
    output[key] = getFieldValue(camelToId(key));
  });
  return output;
}

function collectVmSites() {
  return getSiteCards().map((card, index) => ({
    name: getCardValue(card, "name") || `Site ${index + 1}`,
    total_data_tb: getCardNumber(card, "total_data_tb", 0),
    annual_growth_percent: getCardNumber(card, "annual_growth_percent", 0),
    daily_change_percent: getCardNumber(card, "daily_change_percent", 0),
    primary_retention_days: getCardNumber(card, "primary_retention_days", 30),
    vm_count: getCardNumber(card, "vm_count", 0),
    avg_vm_size_gb: getCardNumber(card, "avg_vm_size_gb", 0),
    wan_bandwidth_mbps: getCardNumber(card, "wan_bandwidth_mbps", 0),
    backup_window_hours: getCardNumber(card, "backup_window_hours", 8),
    backup_type: getCardValue(card, "backup_type"),
    repo_type: getCardValue(card, "repo_type"),
    has_san_access: getCardChecked(card, "has_san_access"),
    on_host_proxy: getCardChecked(card, "on_host_proxy"),
    refs_xfs: getCardChecked(card, "refs_xfs"),
    immutability_enabled: getCardChecked(card, "immutability_enabled"),
    capacity_tier_enabled: getCardChecked(card, "capacity_tier_enabled"),
    direct_to_object: getCardChecked(card, "direct_to_object"),
    gfs_weekly_count: getCardNumber(card, "gfs_weekly_count", 0),
    gfs_monthly_count: getCardNumber(card, "gfs_monthly_count", 0),
    gfs_yearly_count: getCardNumber(card, "gfs_yearly_count", 0),
    block_generation_days: getCardNumber(card, "block_generation_days", 10),
    concurrent_jobs: getCardNumber(card, "concurrent_jobs", 5),
    notes: getCardValue(card, "notes"),
  }));
}

function updateYamlFromBuilder() {
  yamlEditor.value = buildYamlFromBuilder();
}

function buildYamlFromBuilder() {
  const workload = getCurrentWorkload();
  const profile = getFieldValue("profile") || "enterprise";
  const compression = optionalNumberLine("compression_ratio", getFieldValue("compression-ratio"));
  const dedupe = optionalNumberLine("dedupe_ratio", getFieldValue("dedupe-ratio"));
  const throughput = optionalNumberLine("throughput_mb_per_core", getFieldValue("throughput-mb-per-core"));

  if (workload === "nas") {
    return [
      `profile: ${profile}`,
      "workload_type: nas",
      `source_tb: ${numberValue("nas-source-tb", 0)}`,
      `share_count: ${numberValue("nas-share-count", 0)}`,
      `file_count_millions: ${numberValue("nas-file-count", 0)}`,
      `compress_pct: ${numberValue("nas-compress", 30)}`,
      `daily_change_pct: ${numberValue("nas-daily", 5)}`,
      `retention_days: ${numberValue("nas-retention", 30)}`,
      `backup_window_hours: ${numberValue("nas-window", 8)}`,
      `growth_rate_pct: ${numberValue("nas-growth", 10)}`,
      `storage_native_cft: ${booleanValue("nas-cft")}`,
      `immutability_enabled: ${booleanValue("nas-immutability")}`,
      `object_storage: ${booleanValue("nas-object-storage")}`,
    ].join("\n");
  }

  if (workload === "physical") {
    return [
      `profile: ${profile}`,
      "workload_type: physical",
      `machine_count: ${numberValue("machine-count", 0)}`,
      `avg_size_gb: ${numberValue("avg-machine-size", 0)}`,
      `daily_change_pct: ${numberValue("agent-daily", 5)}`,
      `backup_window_hours: ${numberValue("agent-window", 8)}`,
      `retention_days: ${numberValue("agent-retention", 30)}`,
      `os_type: ${getFieldValue("agent-os") || "windows"}`,
      `network_bandwidth_mbps: ${numberValue("agent-network", 1000)}`,
    ].join("\n");
  }

  if (workload === "replication") {
    return [
      `profile: ${profile}`,
      "workload_type: replication",
      `source_tb: ${numberValue("rep-source-tb", 0)}`,
      `vm_count: ${numberValue("rep-vm-count", 0)}`,
      `wan_mbps: ${numberValue("rep-wan-mbps", 0)}`,
      `rpo_hours: ${numberValue("rep-rpo-hours", 1)}`,
      `cdp_enabled: ${booleanValue("rep-cdp")}`,
      `rpo_seconds: ${numberValue("rep-rpo-seconds", 15)}`,
      `compression: ${booleanValue("rep-compression")}`,
    ].join("\n");
  }

  const targetRpo = numberValue("target-rpo", 24);
  const complianceFramework = getFieldValue("compliance-framework") || "none";
  const hypervisor = getFieldValue("hypervisor") || "vmware";
  const siteBlocks = collectVmSites().map((site) => buildVmSiteYaml(site, targetRpo, hypervisor, compression, dedupe, throughput));

  return [
    `profile: ${profile}`,
    "workload_type: vm",
    `compliance_framework: ${complianceFramework}`,
    "sites:",
    siteBlocks.join("\n"),
  ].join("\n");
}

function buildVmSiteYaml(site, targetRpo, hypervisor, compression, dedupe, throughput) {
  const lines = [
    `  - name: ${yamlString(site.name)}`,
    "    veeam_input:",
    `      total_data_tb: ${site.total_data_tb}`,
    `      annual_growth_percent: ${site.annual_growth_percent}`,
    `      daily_change_percent: ${site.daily_change_percent}`,
    `      backup_type: ${site.backup_type}`,
    `      primary_retention_days: ${site.primary_retention_days}`,
    `      gfs_weekly_count: ${site.gfs_weekly_count}`,
    `      gfs_monthly_count: ${site.gfs_monthly_count}`,
    `      gfs_yearly_count: ${site.gfs_yearly_count}`,
    `      backup_window_hours: ${site.backup_window_hours}`,
    `      target_rpo_hours: ${targetRpo}`,
    `      vm_count: ${site.vm_count}`,
    `      avg_vm_size_gb: ${site.avg_vm_size_gb}`,
    `      wan_bandwidth_mbps: ${site.wan_bandwidth_mbps}`,
    `      repo_type: ${site.repo_type}`,
    `      hypervisor: ${hypervisor}`,
    `      has_san_access: ${site.has_san_access}`,
    `      on_host_proxy: ${site.on_host_proxy}`,
    `      refs_xfs: ${site.refs_xfs}`,
    `      immutability_enabled: ${site.immutability_enabled}`,
    `      capacity_tier_enabled: ${site.capacity_tier_enabled}`,
    `      direct_to_object: ${site.direct_to_object}`,
    `      block_generation_days: ${site.block_generation_days}`,
    `      concurrent_jobs: ${site.concurrent_jobs}`,
  ];

  if (compression) {
    lines.push(`      ${compression}`);
  }
  if (dedupe) {
    lines.push(`      ${dedupe}`);
  }
  if (throughput) {
    lines.push(`      ${throughput}`);
  }
  if (site.notes?.trim()) {
    lines.push(`      notes: ${yamlString(site.notes.trim())}`);
  }

  return lines.join("\n");
}

function newSiteDefaults(index) {
  return {
    ...structuredClone(defaultVmSites[0]),
    name: `Site ${index}`,
    total_data_tb: 100,
    vm_count: 200,
    avg_vm_size_gb: 250,
    wan_bandwidth_mbps: 500,
    immutability_enabled: false,
    capacity_tier_enabled: false,
    notes: "",
  };
}

function numberValue(id, fallback) {
  const parsed = parseFloat(getFieldValue(id));
  return Number.isFinite(parsed) ? parsed : fallback;
}

function optionalNumberLine(name, rawValue) {
  const value = `${rawValue ?? ""}`.trim();
  return value === "" ? "" : `${name}: ${value}`;
}

function booleanValue(id) {
  return document.getElementById(id)?.checked ? "true" : "false";
}

function getFieldValue(id) {
  const element = document.getElementById(id);
  if (!element) {
    return "";
  }
  if (element.type === "checkbox") {
    return element.checked;
  }
  return element.value;
}

function setField(id, value) {
  const element = document.getElementById(id);
  if (!element) {
    return;
  }
  if (element.type === "checkbox") {
    element.checked = Boolean(value);
  } else {
    element.value = value ?? "";
  }
}

function getCardValue(card, field) {
  return card.querySelector(`[data-field="${field}"]`)?.value ?? "";
}

function getCardChecked(card, field) {
  return Boolean(card.querySelector(`[data-field="${field}"]`)?.checked);
}

function getCardNumber(card, field, fallback) {
  const parsed = parseFloat(getCardValue(card, field));
  return Number.isFinite(parsed) ? parsed : fallback;
}

function yamlString(value) {
  return JSON.stringify(String(value));
}

function camelToId(key) {
  return key.replaceAll("_", "-");
}
