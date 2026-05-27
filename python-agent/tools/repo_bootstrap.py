from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from tools.git_tool import GitTool


@dataclass(frozen=True)
class BootstrapResult:
    ok: bool
    repo_dir: str
    file_count: int
    dependencies_installed: bool
    error: str | None = None


class RepoBootstrap:
    """Clone a repo and install dependencies. No sandbox dependency for MVP."""

    def __init__(self, git_tool: GitTool | None = None) -> None:
        self.git_tool = git_tool or GitTool(use_local_git=True)

    def bootstrap(self, repo_url: str, workspace_base: str, *, branch: str = "main") -> BootstrapResult:
        target = str(Path(workspace_base) / _repo_name(repo_url))
        result = self.git_tool.clone(repo_url, target, branch=branch)
        if not result.ok:
            return BootstrapResult(ok=False, repo_dir=target, file_count=0, dependencies_installed=False, error=result.error)
        file_count = sum(1 for _ in Path(target).rglob("*") if _.is_file())
        return BootstrapResult(ok=True, repo_dir=target, file_count=file_count, dependencies_installed=False)

    def install_dependencies(self, repo_dir: str) -> BootstrapResult:
        pkg = Path(repo_dir) / "package.json"
        if not pkg.exists():
            return BootstrapResult(ok=True, repo_dir=repo_dir, file_count=0, dependencies_installed=False)
        try:
            result = subprocess.run(["npm", "install"], cwd=repo_dir, capture_output=True, text=True, timeout=300)
            ok = result.returncode == 0
            file_count = sum(1 for _ in Path(repo_dir).rglob("*") if _.is_file())
            return BootstrapResult(ok=ok, repo_dir=repo_dir, file_count=file_count, dependencies_installed=ok,
                                   error=result.stderr.strip() if not ok else None)
        except subprocess.TimeoutExpired:
            return BootstrapResult(ok=False, repo_dir=repo_dir, file_count=0, dependencies_installed=False, error="npm install timed out")
        except FileNotFoundError:
            return BootstrapResult(ok=False, repo_dir=repo_dir, file_count=0, dependencies_installed=False, error="npm not found in PATH")


def _repo_name(url: str) -> str:
    name = url.rstrip("/").rsplit("/", 1)[-1]
    return name.removesuffix(".git")
