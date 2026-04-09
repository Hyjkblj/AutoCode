from __future__ import annotations

from utils.diff_utils import generate_unified_diff, has_substantial_change


def test_generate_unified_diff_returns_empty_when_no_change() -> None:
    assert generate_unified_diff("same\n", "same\n", "README.md") == ""


def test_generate_unified_diff_contains_headers_and_hunks() -> None:
    diff_text = generate_unified_diff("line1\n", "line1\nline2\n", "README.md")

    assert diff_text.startswith("--- ")
    assert "\n+++ " in diff_text
    assert "@@" in diff_text
    assert has_substantial_change(diff_text) is True


def test_has_substantial_change_ignores_header_only_input() -> None:
    header_only = "--- a/file\n+++ b/file\n@@ -1,0 +1,0 @@\n"
    assert has_substantial_change(header_only) is False
