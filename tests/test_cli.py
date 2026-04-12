"""CLI smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chrome_policy_merge.cli import build_parser, main


def test_cli_help_is_clean_and_informative() -> None:
    help_text = build_parser().format_help()

    assert "usage: chrome-policy-merge" in help_text
    assert "{merge,restore}" in help_text
    assert "Merge Chrome enterprise policy JSON files deterministically" in help_text
    assert "(default: None)" not in help_text
    assert "(default: False)" not in help_text


def test_cli_merge_command_runs_end_to_end(tmp_path: Path) -> None:
    input_dir = tmp_path / "policies"
    input_dir.mkdir()
    (input_dir / "10-policy.json").write_text(
        json.dumps({"HomepageLocation": "https://portal.example.com"}) + "\n",
        encoding="utf-8",
    )

    exit_code = main(["merge", str(input_dir)])

    assert exit_code == 0
    assert json.loads((input_dir / "merged-policy.json").read_text(encoding="utf-8")) == {
        "HomepageLocation": "https://portal.example.com"
    }


def test_cli_version_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])

    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == "chrome-policy-merge 4.0.1"


def test_cli_returns_error_code_for_invalid_merge_input(tmp_path: Path) -> None:
    missing_dir = tmp_path / "missing"

    exit_code = main(["merge", str(missing_dir)])

    assert exit_code == 2
