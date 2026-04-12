"""Command-line interface for Chrome Policy Merge."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from ._version import __version__
from .exceptions import PolicyMergeError
from .merge import (
    DEFAULT_BACKUP_DIRNAME,
    DEFAULT_OUTPUT_FILENAME,
    merge_policy_directory,
    restore_backup_snapshot,
)
from .models import MergeConfig, RestoreConfig


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Formatter that preserves line breaks in examples."""


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""

    parser = argparse.ArgumentParser(
        prog="chrome-policy-merge",
        description=(
            "Merge Chrome enterprise policy JSON files deterministically, write the result "
            "atomically, and archive source files into timestamped backup snapshots."
        ),
        formatter_class=HelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", metavar="{merge,restore}", required=True)

    merge_parser = subparsers.add_parser(
        "merge",
        description=(
            "Merge all eligible JSON policy files from the input directory. The directory is "
            "scanned non-recursively."
        ),
        help="merge policy files from a directory",
        formatter_class=HelpFormatter,
        epilog=(
            "Examples:\n"
            "  chrome-policy-merge merge ./policies\n"
            "  chrome-policy-merge merge ./policies "
            "--merge-key ExtensionSettings --merge-key URLAllowlist\n"
            "  chrome-policy-merge merge ./policies --dry-run --verbose"
        ),
    )
    merge_parser.add_argument(
        "input_directory",
        type=Path,
        help="Directory containing JSON policy files to merge.",
    )
    merge_parser.add_argument(
        "--merge-key",
        action="append",
        default=[],
        metavar="KEY",
        help="Top-level policy key that should use deep-merge semantics. Repeat as needed.",
    )
    merge_parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Path for the merged output file. Defaults to "
            f"{DEFAULT_OUTPUT_FILENAME} in the input directory."
        ),
    )
    merge_parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Directory used for timestamped backup snapshots. Defaults to "
            f"{DEFAULT_BACKUP_DIRNAME} in the input directory."
        ),
    )
    merge_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and merge in memory without writing output or moving files.",
    )
    merge_parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Fail on conflicting non-merge replacements and incompatible "
            "deep-merge container types."
        ),
    )
    _add_logging_arguments(merge_parser)
    merge_parser.set_defaults(handler=_run_merge)

    restore_parser = subparsers.add_parser(
        "restore",
        description=(
            "Copy policy files from a backup snapshot back into the input directory. The newest "
            "snapshot is used by default."
        ),
        help="restore a backup snapshot",
        formatter_class=HelpFormatter,
        epilog=(
            "Examples:\n"
            "  chrome-policy-merge restore ./policies\n"
            "  chrome-policy-merge restore ./policies --snapshot snapshot-20260411T120000Z\n"
            "  chrome-policy-merge restore ./policies --remove-output"
        ),
    )
    restore_parser.add_argument(
        "input_directory",
        type=Path,
        help="Directory that should receive the restored policy files.",
    )
    restore_parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "Directory containing timestamped backup snapshots. Defaults to "
            f"{DEFAULT_BACKUP_DIRNAME} in the input directory."
        ),
    )
    restore_parser.add_argument(
        "--snapshot",
        dest="snapshot_name",
        default=None,
        metavar="NAME",
        help=(
            "Specific snapshot directory name to restore. Defaults to the "
            "newest available snapshot."
        ),
    )
    restore_parser.add_argument(
        "--output-file",
        type=Path,
        default=None,
        metavar="PATH",
        help="Merged output file to remove when --remove-output is used.",
    )
    restore_parser.add_argument(
        "--remove-output",
        action="store_true",
        help="Remove the merged output file after a successful restore.",
    )
    restore_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the restore plan without copying files.",
    )
    _add_logging_arguments(restore_parser)
    restore_parser.set_defaults(handler=_run_restore)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI."""

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    _configure_logging(quiet=getattr(args, "quiet", False), verbose=getattr(args, "verbose", 0))
    handler = cast(Callable[[argparse.Namespace], int], args.handler)

    try:
        return handler(args)
    except PolicyMergeError as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 2


def _run_merge(args: argparse.Namespace) -> int:
    """Execute the merge command."""

    result = merge_policy_directory(
        MergeConfig(
            input_directory=args.input_directory,
            output_file=args.output_file,
            backup_dir=args.backup_dir,
            merge_keys=tuple(args.merge_key),
            dry_run=args.dry_run,
            strict=args.strict,
        )
    )

    logger = logging.getLogger(__name__)
    if not result.processed_files:
        logger.info("Nothing to do. No eligible JSON policy files were discovered.")
        return 0

    if result.dry_run:
        logger.info(
            "Dry run complete. %s file(s) would be merged into %s and archived in %s.",
            len(result.processed_files),
            result.output_file,
            result.backup_snapshot,
        )
        return 0

    logger.info(
        "Merge complete. Wrote %s and archived %s file(s) in %s.",
        result.output_file,
        len(result.processed_files),
        result.backup_snapshot,
    )
    return 0


def _run_restore(args: argparse.Namespace) -> int:
    """Execute the restore command."""

    result = restore_backup_snapshot(
        RestoreConfig(
            input_directory=args.input_directory,
            backup_dir=args.backup_dir,
            snapshot_name=args.snapshot_name,
            output_file=args.output_file,
            remove_output=args.remove_output,
            dry_run=args.dry_run,
        )
    )

    logger = logging.getLogger(__name__)
    if result.dry_run:
        logger.info(
            "Dry run complete. %s file(s) would be restored from %s.",
            len(result.restored_files),
            result.snapshot_dir,
        )
        return 0

    logger.info(
        "Restore complete. Restored %s file(s) from %s.",
        len(result.restored_files),
        result.snapshot_dir,
    )
    if result.output_removed:
        logger.info("Removed merged output file %s.", result.output_file)
    return 0


def _add_logging_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach shared verbosity flags to a subcommand parser."""

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity. Repeat for more detail.",
    )
    verbosity.add_argument(
        "--quiet",
        action="store_true",
        help="Only emit error messages.",
    )


def _configure_logging(*, quiet: bool, verbose: int) -> None:
    """Configure root logging for CLI execution."""

    if quiet:
        level = logging.ERROR
    elif verbose >= 1:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(level=level, format="%(levelname)s %(message)s")
