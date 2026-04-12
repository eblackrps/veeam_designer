# Deployment Guide

## Local Web Deployment

Install the project and launch the web console:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install .
chrome-policy-merge-web --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

The default workspace root is a local `workspace/` directory. The app creates it on startup if it
does not already exist.

## Docker Deployment

The repository includes a ready-to-run Docker setup:

```bash
docker compose up --build
```

The compose file:

- builds the included `Dockerfile`
- exposes the app on port `8000`
- mounts `./workspace` on the host to `/workspace` in the container
- sets `CHROME_POLICY_MERGE_WORKSPACE_ROOT=/workspace`

## Health Check

The web app exposes:

- `GET /api/health`

The Docker image also includes a container health check against that endpoint.

## Workspace Layout

Recommended host layout:

```text
workspace/
  policies/
    10-base-policy.json
    20-override-policy.json
```

Inside the web UI, use `policies` as the input directory. Output and backup paths are relative to
that directory by default.

## Compatibility Entry Point

For direct source-tree Uvicorn workflows:

```bash
python -m uvicorn --app-dir src chrome_policy_merge.web:app --host 0.0.0.0 --port 8000
```
