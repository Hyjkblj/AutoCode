from __future__ import annotations

import difflib


def generate_unified_diff(before: str, after: str, path: str) -> str:
    if before == after:
        return ""
    normalized_path = (path or "unknown").replace("\\", "/")
    if not normalized_path:
        normalized_path = "unknown"
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{normalized_path}",
            tofile=f"b/{normalized_path}",
            lineterm="\n",
        )
    )


def has_substantial_change(diff_text: str) -> bool:
    if not diff_text or not diff_text.strip():
        return False
    for line in diff_text.splitlines():
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith("+") or line.startswith("-"):
            return True
    return False
