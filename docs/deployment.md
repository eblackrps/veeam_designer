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

Run the published image:

```bash
docker run --rm -p 8000:8000 emb079/veeam-designer:latest
```

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
- server-side CSV export
- server-rendered report routes
- integration with another service over HTTP
