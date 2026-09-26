# Deployment

Veeam Designer supports three web deployment paths plus the CLI. The FastAPI app, Docker image,
and GitHub Pages edition share the same packaged sizing engine and web interface.

## GitHub Pages

The public browser edition is published from `main`:

https://eblackrps.github.io/veeam_designer/

Build the static site locally with:

```bash
python -m build --wheel
python tools/build_pages.py --output _site
```

The Pages build packages the current wheel and runs the Python engine in-browser with Pyodide.
It supports the guided form, YAML workflow, JSON/CSV export, and printable reports.

## Docker

For production, deploy an explicit release tag with the hardened runtime controls:

```bash
docker run --rm \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit 256 \
  --tmpfs /tmp:size=64m,mode=1777 \
  -p 127.0.0.1:8000:8000 \
  emb079/veeam-designer:5.0.0
```

The image runs as dedicated non-root UID/GID `10001:10001` and includes a Docker `HEALTHCHECK`
against `/api/health`. The sample Compose file applies the same hardening defaults, defaults to
the exact stable release image, and binds only to loopback. Change the host-side bind address
deliberately if the service must be reachable from other systems, and place it behind the
environment's normal reverse proxy, TLS, and access controls.

The same release is published to GitHub Container Registry:

```text
ghcr.io/eblackrps/veeam-designer:5.0.0
```

For production, prefer an explicit version tag over `latest`. Published container images include
SBOM and provenance attestations.

Build locally with Compose:

```bash
docker compose up --build
```

Or build the image directly for local development:

```bash
docker build -t veeam-designer .
docker run --rm -p 8000:8000 veeam-designer
```

Open `http://localhost:8000/run`.

## Source

```bash
python -m pip install -e ".[dev]"
veeam-designer-web --reload
```

Equivalent Uvicorn command:

```bash
python -m uvicorn --app-dir . ui.main:app --reload
```

## Upgrade and Rollback

The application is stateless. Production upgrades should replace the running container with the
new explicit version after the release CI and container-security jobs pass.

Example upgrade:

```bash
docker pull emb079/veeam-designer:5.0.0
docker compose up -d --force-recreate
docker compose ps
curl --fail http://127.0.0.1:8000/api/health
```

To roll back, set `VEEAM_DESIGNER_IMAGE` to the previously approved version and recreate the
service:

```bash
export VEEAM_DESIGNER_IMAGE=emb079/veeam-designer:<previous-version>
docker compose up -d --force-recreate
curl --fail http://127.0.0.1:8000/api/health
```

Keep local `config.json` and `profiles.json` under change control when overriding the packaged
defaults. They are mounted read-only by the sample Compose deployment.

## Publishing

Pull requests run:

- the calculation-freeze gate
- lint, formatting, type checking, unit/regression tests, package build, and Pages build
- browser E2E testing across VM, NAS, Physical, and Replication modes
- Python dependency auditing and dependency-review
- CodeQL analysis
- hardened-container smoke testing and HIGH/CRITICAL fixable-vulnerability scanning

Pushing an approved stable version to `main` additionally:

- rebuilds and deploys GitHub Pages
- publishes Docker Hub and GHCR images as `latest` and the exact package version
- publishes container SBOM and provenance attestations
- creates the matching stable GitHub Release after Docker and CI are both successful
- attaches wheel, source distribution, and SHA-256 checksums to the GitHub Release

The package version, UI version badge, Git tag, GitHub Release, and versioned container tag should
describe the same release.

## Server-only Capabilities

The GitHub Pages edition runs entirely in the browser. Use FastAPI or Docker when you need:

- `/api/design`
- stateless `POST /export/csv` with project YAML as `text/plain`
- stateless `POST /export/report` for VM/multi-site project YAML
- integration with another service over HTTP

## Project Status

Veeam Designer is an independent community project. It is not affiliated with or endorsed by
Veeam Software. Veeam and related marks are the property of their respective owners.
