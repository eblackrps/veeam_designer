from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextvars import ContextVar
from importlib import resources
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "compression_ratio_default": 1.6,
    "dedupe_ratio_default": 1.0,
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


def _load_packaged_json(filename: str) -> Dict[str, Any]:
    try:
        resource_path = resources.files("veeam_designer.resources").joinpath(filename)
        data = json.loads(resource_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


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
    override_data = _load_json_if_exists(root / "config.json")
    if override_data:
        cfg.update(override_data)
    else:
        cfg.update(_load_packaged_json("config.json"))
    return cfg


def load_profiles() -> Dict[str, Dict[str, Any]]:
    root = _project_root()
    profiles_path = root / "profiles.json"
    data = _load_json_if_exists(profiles_path) or _load_packaged_json("profiles.json")
    profiles = data.get("profiles", {}) if isinstance(data, dict) else {}
    clean: Dict[str, Dict[str, Any]] = {}
    for k, v in profiles.items():
        if isinstance(k, str) and isinstance(v, dict):
            clean[k] = v
    return clean


BASE_CONFIG: Dict[str, Any] = load_base_config()
PROFILES: Dict[str, Dict[str, Any]] = load_profiles()
_CONFIG_STATE: ContextVar[Dict[str, Any]] = ContextVar(
    "veeam_designer_runtime_config",
    default=BASE_CONFIG.copy(),
)


class RuntimeConfig(Mapping[str, Any]):
    """Read-only view of the active profile configuration."""

    def _data(self) -> Dict[str, Any]:
        return _CONFIG_STATE.get()

    def __getitem__(self, key: str) -> Any:
        return self._data()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data())

    def __len__(self) -> int:
        return len(self._data())

    def get(self, key: str, default: Any = None) -> Any:
        return self._data().get(key, default)

    def snapshot(self) -> Dict[str, Any]:
        return self._data().copy()


CONFIG = RuntimeConfig()


def select_profile(name: str | None) -> Dict[str, Any]:
    """Apply a profile on top of the base configuration for the current execution context."""
    config = BASE_CONFIG.copy()

    if not name:
        _CONFIG_STATE.set(config)
        return config

    profile = PROFILES.get(name)
    if profile:
        config.update(profile)

    _CONFIG_STATE.set(config)
    return config
