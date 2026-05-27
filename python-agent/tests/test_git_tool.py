from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.git_tool import GitResult, GitTool


class TestGitResult:
    def test_ok_result(self):
        r = GitResult(ok=True, output="cloned", exit_code=0, error=None)
        assert r.ok is True
        assert r.exit_code == 0
        assert r.error is None

    def test_fail_result(self):
        r = GitResult(ok=False, output="", exit_code=128, error="not a git repo")
        assert r.ok is False
        assert r.error == "not a git repo"


class TestGitToolLocalMode:
    @pytest.fixture
    def tool(self, tmp_path):
        return GitTool(use_local_git=True)

    def _init_repo(self, path: Path) -> None:
        """Initialize a git repo with local identity config."""
        path.mkdir(exist_ok=True)
        subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(path), "config", "user.email", "test@test"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(path), "config", "user.name", "test"],
            check=True, capture_output=True,
        )

    def test_clone_local_repo(self, tool, tmp_path):
        src = tmp_path / "src"
        self._init_repo(src)
        (src / "README.md").write_text("hello")
        subprocess.run(["git", "-C", str(src), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(src), "commit", "-m", "init"], check=True, capture_output=True)
        dest = tmp_path / "dest"
        result = tool.clone(str(src), str(dest))
        assert result.ok is True
        assert (dest / "README.md").exists()

    def test_checkout_branch(self, tool, tmp_path):
        repo = tmp_path / "repo"
        self._init_repo(repo)
        (repo / "f.txt").write_text("x")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        result = tool.checkout_branch(str(repo), "feature-x")
        assert result.ok is True

    def test_add_and_commit(self, tool, tmp_path):
        repo = tmp_path / "repo"
        self._init_repo(repo)
        (repo / "a.txt").write_text("a")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        (repo / "b.txt").write_text("b")
        add_result = tool.add(str(repo), ["b.txt"])
        assert add_result.ok is True
        commit_result = tool.commit(str(repo), "add b")
        assert commit_result.ok is True

    def test_status(self, tool, tmp_path):
        repo = tmp_path / "repo"
        self._init_repo(repo)
        result = tool.status(str(repo))
        assert result.ok is True

    def test_diff(self, tool, tmp_path):
        repo = tmp_path / "repo"
        self._init_repo(repo)
        (repo / "a.txt").write_text("a")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        (repo / "a.txt").write_text("modified")
        result = tool.diff(str(repo))
        assert result.ok is True
        assert "modified" in result.output

    def test_log(self, tool, tmp_path):
        repo = tmp_path / "repo"
        self._init_repo(repo)
        (repo / "a.txt").write_text("a")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        result = tool.log(str(repo), limit=5)
        assert result.ok is True
        assert "init" in result.output


class TestGitToolExecMode:
    def test_exec_tool_stored_for_future_use(self):
        exec_tool = MagicMock()
        tool = GitTool(exec_tool=exec_tool)
        assert tool.exec_tool is exec_tool
        assert tool.use_local_git is False
