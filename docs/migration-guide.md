# Migration Guide

## Chrome Policy Merge 4.0.0

Chrome Policy Merge 4.0.0 turns the legacy merge utility into a packaged tool with a stable
CLI and library API.

## What Changed

- Invocation is now `chrome-policy-merge merge <input_directory>`.
- Merge keys are passed explicitly with repeated `--merge-key` flags.
- Output and backup paths are now first-class CLI options.
- Backups are written to timestamped snapshot directories with a manifest.
- Restore is a documented command instead of a manual recovery step.

## Suggested Upgrade Path

1. Replace any direct script calls with the packaged CLI entry point.
2. Review automation that depended on silent overwrite behavior and decide whether to enable `--strict`.
3. Update operational runbooks to include the backup snapshot and restore workflow.
4. Treat `--snapshot` values as snapshot directory names inside the backup root, not filesystem paths.
