from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class GitResult:
    ok: bool
    output: str
    exit_code: int | None
    error: str | None


class GitTool:
    def __init__(self, exec_tool=None, *, use_local_git: bool = False) -> None:
        self.exec_tool = exec_tool
        self.use_local_git = use_local_git or os.getenv(
            "MVP_USE_LOCAL_GIT", ""
        ).strip().lower() in ("1", "true", "yes")

    def clone(self, repo_url: str, target_dir: str, *, branch: str = "", depth: int | None = None) -> GitResult:
        cmd = ["git", "clone"]
        if branch:
            cmd += ["--branch", branch]
        if depth is not None:
            cmd += ["--depth", str(depth)]
        cmd += [repo_url, target_dir]
        return self._run(cmd)

    def checkout_branch(self, repo_dir: str, branch_name: str, *, create: bool = True) -> GitResult:
        cmd = ["git", "-C", repo_dir, "checkout"]
        if create:
            cmd.append("-b")
        cmd.append(branch_name)
        return self._run(cmd)

    def add(self, repo_dir: str, paths: list[str] | None = None) -> GitResult:
        cmd = ["git", "-C", repo_dir, "add"]
        cmd += paths if paths else ["."]
        return self._run(cmd)

    def commit(self, repo_dir: str, message: str) -> GitResult:
        return self._run(["git", "-C", repo_dir, "commit", "-m", message])

    def push(self, repo_dir: str, branch: str = "", *, force: bool = False) -> GitResult:
        cmd = ["git", "-C", repo_dir, "push"]
        if force:
            cmd.append("--force")
        if branch:
            cmd.append(branch)
        return self._run(cmd)

    def status(self, repo_dir: str) -> GitResult:
        return self._run(["git", "-C", repo_dir, "status"])

    def diff(self, repo_dir: str, *, staged: bool = False) -> GitResult:
        cmd = ["git", "-C", repo_dir, "diff"]
        if staged:
            cmd.append("--staged")
        return self._run(cmd)

    def log(self, repo_dir: str, limit: int = 10) -> GitResult:
        return self._run(["git", "-C", repo_dir, "log", "--oneline", f"-{limit}"])

    def _run(self, cmd: list[str]) -> GitResult:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            ok = result.returncode == 0
            return GitResult(
                ok=ok,
                output=result.stdout.strip(),
                exit_code=result.returncode,
                error=result.stderr.strip() if not ok else None,
            )
        except subprocess.TimeoutExpired:
            return GitResult(ok=False, output="", exit_code=None, error="git command timed out")
        except FileNotFoundError:
            return GitResult(ok=False, output="", exit_code=None, error="git not found in PATH")
        except Exception as exc:
            return GitResult(ok=False, output="", exit_code=None, error=str(exc))
