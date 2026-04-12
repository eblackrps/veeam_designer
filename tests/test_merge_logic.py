"""Unit tests for merge semantics and sorting."""

from __future__ import annotations

import pytest

from chrome_policy_merge import (
    JSONObject,
    MergeConflictError,
    merge_policy_objects,
    natural_sort_key,
)


def test_natural_sort_orders_numeric_filename_segments() -> None:
    names = ["policy10.json", "policy2.json", "policy1.json", "policy20.json"]

    assert sorted(names, key=natural_sort_key) == [
        "policy1.json",
        "policy2.json",
        "policy10.json",
        "policy20.json",
    ]


def test_deep_merge_merges_nested_dicts_for_allowed_keys() -> None:
    existing: JSONObject = {
        "ExtensionSettings": {
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": {
                "installation_mode": "allowed",
            }
        }
    }
    incoming: JSONObject = {
        "ExtensionSettings": {
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": {
                "toolbar_pin": "force_pinned",
            },
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb": {
                "installation_mode": "blocked",
            },
        }
    }

    result = merge_policy_objects(existing, incoming, merge_keys=("ExtensionSettings",))

    assert result == {
        "ExtensionSettings": {
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa": {
                "installation_mode": "allowed",
                "toolbar_pin": "force_pinned",
            },
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb": {
                "installation_mode": "blocked",
            },
        }
    }


def test_deep_merge_uses_ordered_union_for_lists() -> None:
    existing: JSONObject = {"URLAllowlist": ["https://portal.example.com", {"name": "one"}]}
    incoming: JSONObject = {
        "URLAllowlist": [
            "https://portal.example.com",
            "https://support.example.com",
            {"name": "one"},
            {"name": "two"},
        ]
    }

    result = merge_policy_objects(existing, incoming, merge_keys=("URLAllowlist",))

    assert result["URLAllowlist"] == [
        "https://portal.example.com",
        {"name": "one"},
        "https://support.example.com",
        {"name": "two"},
    ]


def test_non_merge_keys_replace_by_default() -> None:
    result = merge_policy_objects(
        {"HomepageLocation": "https://intranet.example.com"},
        {"HomepageLocation": "https://portal.example.com"},
    )

    assert result["HomepageLocation"] == "https://portal.example.com"


def test_strict_mode_rejects_conflicting_non_merge_replacements() -> None:
    with pytest.raises(MergeConflictError):
        merge_policy_objects(
            {"HomepageLocation": "https://intranet.example.com"},
            {"HomepageLocation": "https://portal.example.com"},
            strict=True,
        )


def test_strict_mode_rejects_incompatible_deep_merge_types() -> None:
    with pytest.raises(MergeConflictError):
        merge_policy_objects(
            {"ExtensionSettings": {"managed": {"nested": True}}},
            {"ExtensionSettings": {"managed": ["unexpected"]}},
            merge_keys=("ExtensionSettings",),
            strict=True,
        )
