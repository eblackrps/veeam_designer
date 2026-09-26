from __future__ import annotations

import re
from pathlib import Path

from veeam_designer import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_release_metadata_is_stable_5_0_0() -> None:
    assert __version__ == "5.0.0"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"Development Status :: 5 - Production/Stable"' in pyproject
    assert '"Development Status :: 3 - Alpha"' not in pyproject


def test_container_base_and_compose_image_are_immutable_or_versioned() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM python:3.12.14-slim@sha256:")
    assert "USER 10001:10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "emb079/veeam-designer:5.0.0" in compose
    assert "emb079/veeam-designer:latest" not in compose


def test_all_github_actions_are_pinned_to_commit_shas() -> None:
    workflow_dir = ROOT / ".github" / "workflows"
    uses_pattern = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)

    refs: list[tuple[str, str]] = []
    for workflow in sorted(workflow_dir.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        refs.extend((workflow.name, ref) for ref in uses_pattern.findall(text))

    assert refs
    for workflow_name, ref in refs:
        if ref.startswith("./"):
            continue
        assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", ref), (
            f"{workflow_name} contains an unpinned action reference: {ref}"
        )


def test_independent_project_notice_is_present_on_public_surfaces() -> None:
    notice = "Independent community project. Not affiliated with or endorsed by Veeam Software."
    for relative_path in (
        "README.md",
        "ui/templates/index.html",
        "ui/templates/report.html",
        "ui/static/app.js",
    ):
        assert notice in (ROOT / relative_path).read_text(encoding="utf-8")
