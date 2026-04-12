# Deployment

## Docker Compose

Run the local containerized deployment:

```bash
docker compose up --build
```

The service listens on `http://localhost:8000/run`.

By default the compose file:

- builds the image from the current repository
- exposes port `8000`
- mounts `config.json` and `profiles.json` read-only into `/app`

## Direct Docker Build

```bash
docker build -t veeam-designer .
docker run --rm -p 8000:8000 veeam-designer
```

## Source Run

```bash
python -m pip install -e ".[dev]"
veeam-designer-web --reload
```

or:

```bash
python -m uvicorn --app-dir . ui.main:app --reload
```

## GitHub Pages

The repository ships a static Pages edition that runs Veeam Designer entirely in the browser.

Build it locally with:

```bash
python -m build --wheel
python tools/build_pages.py --output _site
```

Then serve the generated `_site/` directory with any static file server, or let
`.github/workflows/pages.yml` publish it from `main`.

Notes:

- The Pages edition uses the packaged wheel plus Pyodide in the browser.
- It preserves the calculator UI, YAML workflow, JSON/CSV exports, and print view.
- The local FastAPI/Docker deployment remains the right choice for `/api/design` and server-side
  export routes.
