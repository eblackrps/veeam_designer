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
