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
It supports the guided builder, YAML workflow, JSON/CSV export, and printable reports.

## Docker

Run the published image with production-oriented runtime controls:

```bash
docker run --rm \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit 256 \
  --tmpfs /tmp:size=64m,mode=1777 \
  -p 127.0.0.1:8000:8000 \
  emb079/veeam-designer:latest
```

The image runs as dedicated non-root UID/GID `10001:10001` and includes a Docker `HEALTHCHECK`
against `/api/health`. The sample Compose file applies the same hardening defaults and binds only
to loopback. Change the host-side bind address deliberately if the service must be reachable from
other systems, and place it behind the environment's normal reverse proxy, TLS, and access controls.

The same image is also published to GitHub Container Registry:

```text
ghcr.io/eblackrps/veeam-designer:latest
```

Build locally with Compose:

```bash
docker compose up --build
```

Or build the image directly:

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

## Publishing

Pushing to `main`:

- runs the full CI matrix on Python 3.10, 3.11, and 3.12
- validates browser JavaScript syntax
- audits Python dependencies for known vulnerabilities
- builds and smoke-tests the container as non-root with the hardened runtime controls
- scans the candidate container for fixable HIGH and CRITICAL OS/library vulnerabilities
- rebuilds and deploys GitHub Pages
- rebuilds and pushes Docker images to both registries as `latest` and the package version
  (for example, `5.0.0a4`)

Pushing a version tag such as `v5.0.0` also publishes the Git tag as an additional Docker tag to:

- `emb079/veeam-designer`
- `ghcr.io/eblackrps/veeam-designer`

The package version, UI version badge, release tag, and versioned container tag should describe the
same release.

## Server-only Capabilities

The GitHub Pages edition runs entirely in the browser. Use FastAPI or Docker when you need:

- `/api/design`
- stateless `POST /export/csv` with project YAML as `text/plain`
- stateless `POST /export/report` for VM/multi-site project YAML
- integration with another service over HTTP
