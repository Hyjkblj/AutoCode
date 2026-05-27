from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tools.git_tool import GitResult
from tools.repo_bootstrap import BootstrapResult, RepoBootstrap


class TestRepoBootstrap:
    @pytest.fixture
    def mock_git(self):
        git = MagicMock()
        git.clone.return_value = GitResult(ok=True, output="cloned", exit_code=0, error=None)
        git.checkout_branch.return_value = GitResult(ok=True, output="", exit_code=0, error=None)
        return git

    @pytest.fixture
    def bootstrap(self, mock_git):
        return RepoBootstrap(git_tool=mock_git)

    def test_bootstrap_success(self, bootstrap, mock_git, tmp_path):
        def fake_clone(url, target, **kw):
            Path(target).mkdir(parents=True, exist_ok=True)
            (Path(target) / "package.json").write_text('{"name":"test"}')
            return GitResult(ok=True, output="cloned", exit_code=0, error=None)

        mock_git.clone.side_effect = fake_clone
        result = bootstrap.bootstrap("https://github.com/test/repo", str(tmp_path))
        assert result.ok is True
        assert result.file_count >= 1

    def test_bootstrap_clone_failure(self, bootstrap, mock_git, tmp_path):
        mock_git.clone.return_value = GitResult(ok=False, output="", exit_code=128, error="auth failed")
        result = bootstrap.bootstrap("https://github.com/test/repo", str(tmp_path))
        assert result.ok is False
        assert "auth failed" in (result.error or "")

    def test_install_dependencies_no_package_json(self, bootstrap, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        result = bootstrap.install_dependencies(str(repo))
        assert result.ok is True
        assert result.dependencies_installed is False
