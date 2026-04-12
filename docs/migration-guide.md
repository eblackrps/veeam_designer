# Migration Guide

## Chrome Policy Merge 4.0.1

Chrome Policy Merge 4.0.1 keeps the hardened merge engine introduced in 4.0.0 and restores a
first-class web experience around it.

## From 4.0.0 To 4.0.1

- Start the web console with `chrome-policy-merge-web` for interactive use
- Use Docker again with the included `Dockerfile` and `docker-compose.yml`
- Mount or create a workspace directory and operate on paths relative to that workspace root
- Keep using the CLI and Python API if you already automated them; those interfaces remain
  supported

## From Older Script-Based Workflows

- Replace direct script execution with either the web UI or `chrome-policy-merge merge`
- Replace legacy merge-key handling with one `--merge-key` flag per top-level policy key
- Adopt the backup snapshot and restore workflow instead of manual file movement
- Treat restore snapshot selectors as snapshot directory names inside the backup root

## Operational Notes

- The web UI workspace root defaults to a local `workspace/` directory unless
  `CHROME_POLICY_MERGE_WORKSPACE_ROOT` is set
- In Docker deployments, the recommended pattern is to mount `./workspace` to `/workspace`
- Browser upload previews do not mutate the mounted workspace
