from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "compression_ratio_default": 1.6,
    "dedupe_ratio_default": 1.0,
    "throughput_mb_per_core": 15.0,
    "read_write_overhead": 1.3,
    "tasks_per_core": 2,
    "repo_overhead_factor": 1.25,
    "gfs_overhead_factor": 1.1,
    "years_to_plan_for": 3,
    "warn_repo_tb": 300.0,
    "max_vms_per_job": 50,
    "max_tb_per_job": 10.0,
    "object_cost_usd_per_tb_month": 20.0,
    "onprem_cost_usd_per_tb_year": 100.0,
}


def _project_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[1]


def _load_json_if_exists(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def load_base_config() -> Dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()
    root = _project_root()
    cfg.update(_load_json_if_exists(root / "config.json"))
    return cfg


def load_profiles() -> Dict[str, Dict[str, Any]]:
    root = _project_root()
    profiles_path = root / "profiles.json"
    data = _load_json_if_exists(profiles_path)
    profiles = data.get("profiles", {}) if isinstance(data, dict) else {}
    clean: Dict[str, Dict[str, Any]] = {}
    for k, v in profiles.items():
        if isinstance(k, str) and isinstance(v, dict):
            clean[k] = v
    return clean


BASE_CONFIG: Dict[str, Any] = load_base_config()
CONFIG: Dict[str, Any] = BASE_CONFIG.copy()
PROFILES: Dict[str, Dict[str, Any]] = load_profiles()


def select_profile(name: str | None) -> Dict[str, Any]:
    """Apply a profile on top of the base configuration for the current process."""

    CONFIG.clear()
    CONFIG.update(BASE_CONFIG)

    if not name:
        return CONFIG

    profile = PROFILES.get(name)
    if profile:
        CONFIG.update(profile)
    return CONFIG
