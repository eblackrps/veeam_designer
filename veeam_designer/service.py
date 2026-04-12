"""Shared service helpers used by the CLI, UI, and API layers."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from ._version import __version__
from .agent import size_agent
from .models import AgentInput, NasInput, ReplicationInput, VeeamDesign, VeeamInput
from .nas import size_nas
from .parser import load_project, load_project_text
from .replication import size_replication
from .sizing import design_multi_site, design_veeam_environment

JSONDict = dict[str, Any]


def _optional_dataclass(value: Any) -> Any:
    return asdict(value) if value is not None else None


def _roles_dict(roles: Any) -> JSONDict:
    return {
        "backup_server": asdict(roles.backup_server),
        "proxies": asdict(roles.proxies),
        "hardened_repos": _optional_dataclass(roles.hardened_repos),
        "gateways": _optional_dataclass(roles.gateways),
    }


def _vm_payload(design: VeeamDesign) -> JSONDict:
    return {
        "kind": "vm",
        "version": __version__,
        "input": asdict(design.input),
        "repo": asdict(design.repo),
        "roles": _roles_dict(design.roles),
        "jobs": [asdict(job) for job in design.jobs.jobs],
        "sobr": asdict(design.sobr),
        "repo_perf": asdict(design.repo_perf),
        "network": asdict(design.network),
        "cost": asdict(design.cost),
        "risk": asdict(design.risk),
        "orca": _optional_dataclass(design.orca),
        "replication": _optional_dataclass(design.replication),
        "nas": _optional_dataclass(design.nas),
        "wan_accel": _optional_dataclass(design.wan_accel),
        "license_estimate": _optional_dataclass(design.license_estimate),
        "tape": _optional_dataclass(design.tape),
        "veeam_one": _optional_dataclass(design.veeam_one),
        "compliance": _optional_dataclass(design.compliance),
        "notes": design.notes,
        "blueprint": {
            "role_plan": _roles_dict(design.blueprint.role_plan),
            "jobs": [asdict(job) for job in design.blueprint.jobs.jobs],
            "sobr": asdict(design.blueprint.sobr),
            "repo_perf": asdict(design.blueprint.repo_perf),
            "network": asdict(design.blueprint.network),
            "cost": asdict(design.blueprint.cost),
            "orca": _optional_dataclass(design.blueprint.orca),
            "notes": design.blueprint.notes,
        },
    }


def design_payload_from_project_file(path: Path) -> JSONDict:
    """Load a project file and return the normalized JSON payload."""

    return design_payload_from_input(load_project(path))


def design_payload_from_project_text(text: str, *, suffix: str = ".yml") -> JSONDict:
    """Load a project definition from YAML or JSON text."""

    return design_payload_from_input(load_project_text(text, suffix=suffix))


def design_payload_from_input(project_input: Any) -> JSONDict:
    """Return the canonical JSON payload for a supported project input object."""

    if isinstance(project_input, list):
        multi = design_multi_site(project_input)
        return {
            "kind": "multi-site",
            "version": __version__,
            "total_repo_tb": multi.total_repo_tb,
            "notes": multi.notes,
            "sites": [
                {
                    "name": site.name,
                    "design": _vm_payload(site.design),
                }
                for site in multi.sites
            ],
        }

    if isinstance(project_input, NasInput):
        return {
            "kind": "nas",
            "version": __version__,
            "input": asdict(project_input),
            "result": asdict(size_nas(project_input)),
        }

    if isinstance(project_input, AgentInput):
        return {
            "kind": "physical",
            "version": __version__,
            "input": asdict(project_input),
            "result": asdict(size_agent(project_input)),
        }

    if isinstance(project_input, ReplicationInput):
        return {
            "kind": "replication",
            "version": __version__,
            "input": asdict(project_input),
            "result": asdict(size_replication(project_input)),
        }

    if isinstance(project_input, VeeamInput):
        return _vm_payload(design_veeam_environment(project_input))

    raise TypeError(f"Unsupported project input type: {type(project_input)!r}")
