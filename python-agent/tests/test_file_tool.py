from __future__ import annotations

import pytest

from tools.file_tool import FileTool


def test_file_tool_write_text_allows_path_inside_prefix(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "notes" / "plan.md"
    tool = FileTool(allowed_workspace_prefixes=[str(workspace)])

    tool.write_text(target, "hello world")

    assert target.read_text(encoding="utf-8") == "hello world"


def test_file_tool_write_text_rejects_path_outside_prefix(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside.txt"
    tool = FileTool(allowed_workspace_prefixes=[str(workspace)])

    with pytest.raises(PermissionError, match="outside MVP_ALLOWED_WORKSPACE_PREFIXES"):
        tool.write_text(outside, "blocked")

