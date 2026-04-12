"""Build the static GitHub Pages edition of Veeam Designer."""

from __future__ import annotations

import argparse
import importlib
import shutil
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

__version__ = importlib.import_module("veeam_designer._version").__version__
load_profiles = importlib.import_module("veeam_designer.config").load_profiles

TEMPLATES_DIR = REPO_ROOT / "ui" / "templates"
STATIC_DIR = REPO_ROOT / "ui" / "static"
DIST_DIR = REPO_ROOT / "dist"

PYODIDE_VERSION = "0.29.3"
PYODIDE_BASE_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE_VERSION}/full/"
PYODIDE_SCRIPT_URL = f"{PYODIDE_BASE_URL}pyodide.js"
JS_YAML_URL = "https://cdn.jsdelivr.net/npm/js-yaml@4.1.0/dist/js-yaml.min.js"


def get_default_project_text() -> str:
    example_path = REPO_ROOT / "example-project.yml"
    return example_path.read_text(encoding="utf-8")


def load_profile_names() -> list[str]:
    profiles = load_profiles()
    names = sorted(profiles.keys())
    return names if names else ["enterprise", "msp", "smb", "dedupe"]


def find_release_wheel() -> Path:
    pattern = f"veeam_designer-{__version__}-py3-none-any.whl"
    wheel = DIST_DIR / pattern
    if not wheel.exists():
        raise FileNotFoundError(
            f"Expected wheel not found at {wheel}. Build the wheel first with `python -m build --wheel`."
        )
    return wheel


def build_pages(output_dir: Path) -> Path:
    if output_dir.exists():
        shutil.rmtree(output_dir)

    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(STATIC_DIR / "app.css", assets_dir / "app.css")
    shutil.copy2(STATIC_DIR / "app.js", assets_dir / "app.js")

    wheel_path = find_release_wheel()
    wheel_target = assets_dir / wheel_path.name
    shutil.copy2(wheel_path, wheel_target)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("index.html")

    html = template.render(
        version=__version__,
        runtime="static",
        yaml_content=get_default_project_text(),
        available_profiles=load_profile_names(),
        form_action="#",
        form_method="post",
        hero_pill="GitHub Pages browser edition",
        hero_meta_lines=[
            f"Version {__version__}",
            "Runs entirely in the browser on GitHub Pages",
            "Use Docker or the local app for server endpoints and API routes",
        ],
        static_css_href="./assets/app.css",
        app_js_href="./assets/app.js",
        pyodide_script_src=PYODIDE_SCRIPT_URL,
        yaml_library_src=JS_YAML_URL,
        bootstrap_payload={
            "runtime": "static",
            "version": __version__,
            "yamlContent": get_default_project_text(),
            "resultBundle": None,
            "errorMessage": None,
            "wheelHref": f"./assets/{wheel_target.name}",
            "pyodideBaseUrl": PYODIDE_BASE_URL,
        },
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the static GitHub Pages site.")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "_site",
        help="Output directory for the static site. Defaults to ./_site",
    )
    args = parser.parse_args()
    site_dir = build_pages(args.output.resolve())
    print(f"Built GitHub Pages site at {site_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
