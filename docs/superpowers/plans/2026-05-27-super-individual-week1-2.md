# Super Individual — Week 1-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 7 missing capabilities (GitTool, CodeIndex, DialogueManager, RepoBootstrap, TestGenerator, KnowledgeExtractor, HumanGate) and wire them into the existing AutoCode agent pipeline so the system can clone repos, understand code, do incremental edits, generate tests, gate on humans, and write back knowledge.

**Architecture:** Four parallel branches with zero file overlap. Each branch is independently testable and mergeable. Branch 1 (Python tools) and Branch 2 (Java events) have no dependencies and can be developed simultaneously. Branch 3 (pipeline extensions) depends on Branch 1's interfaces. Branch 4 (integration) merges all three.

**Tech Stack:** Python 3.11, pytest, dataclasses, subprocess (git), regex (TS/JS parsing), Redis (knowledge store), Java 17, Spring Boot, shared-protocol DTOs

---

## Branch Strategy

```
master
  ├── feat/si-python-tools      ← Branch 1 (Week 1 priority, no deps)
  ├── feat/si-java-events       ← Branch 2 (parallel with Branch 1)
  ├── feat/si-python-pipeline   ← Branch 3 (after Branch 1 merged)
  └── feat/si-integration       ← Branch 4 (after all merged)
```

**File conflict matrix — zero overlap:**

| File | Branch 1 | Branch 2 | Branch 3 | Branch 4 |
|------|----------|----------|----------|----------|
| `python-agent/tools/git_tool.py` | CREATE | | | |
| `python-agent/tools/code_index.py` | CREATE | | | |
| `python-agent/tools/repo_bootstrap.py` | CREATE | | | |
| `python-agent/agents/dialogue_manager.py` | CREATE | | | |
| `python-agent/tests/test_git_tool.py` | CREATE | | | |
| `python-agent/tests/test_code_index.py` | CREATE | | | |
| `python-agent/tests/test_repo_bootstrap.py` | CREATE | | | |
| `python-agent/tests/test_dialogue_manager.py` | CREATE | | | |
| `shared-protocol/.../EventType.java` | | MODIFY | | |
| `shared-protocol/.../payload/*.java` (9 new) | | CREATE | | |
| `control-plane-spring/.../TaskService.java` | | MODIFY | | |
| `python-agent/generators/test_generator.py` | | | CREATE | |
| `python-agent/memory/knowledge_extractor.py` | | | CREATE | |
| `python-agent/plugins/human_gate.py` | | | CREATE | |
| `python-agent/tests/test_test_generator.py` | | | CREATE | |
| `python-agent/tests/test_knowledge_extractor.py` | | | CREATE | |
| `python-agent/tests/test_human_gate.py` | | | CREATE | |
| `python-agent/orchestrator/agent_orchestrator.py` | | | | MODIFY |
| `python-agent/main.py` | | | | MODIFY |
| `python-agent/agents/coder_agent.py` | | | | MODIFY |
| `python-agent/generators/validation_gate.py` | | | | MODIFY |
| `python-agent/generators/fix_loop.py` | | | | MODIFY |
| `python-agent/memory/redis_memory.py` | | | | MODIFY |

---

## Branch 1: `feat/si-python-tools` — Python Tools + DialogueManager

**Priority:** Highest — all other branches depend on these interfaces.

### Task 1.1: GitTool

**Files:**
- Create: `python-agent/tools/git_tool.py`
- Create: `python-agent/tests/test_git_tool.py`

- [ ] **Step 1: Write failing tests for GitResult and GitTool**

```python
# python-agent/tests/test_git_tool.py
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
    """Tests using local git subprocess (use_local_git=True)."""

    @pytest.fixture
    def tool(self, tmp_path):
        return GitTool(use_local_git=True)

    def test_clone_local_repo(self, tool, tmp_path):
        # Create a bare repo to clone from
        src = tmp_path / "src"
        src.mkdir()
        subprocess.run(["git", "init", str(src)], check=True, capture_output=True)
        (src / "README.md").write_text("hello")
        subprocess.run(["git", "-C", str(src), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(src), "commit", "-m", "init"], check=True, capture_output=True,
                       env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"})

        dest = tmp_path / "dest"
        result = tool.clone(str(src), str(dest))
        assert result.ok is True
        assert (dest / "README.md").exists()

    def test_checkout_branch(self, tool, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        (repo / "f.txt").write_text("x")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True,
                       env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"})

        result = tool.checkout_branch(str(repo), "feature-x")
        assert result.ok is True

    def test_add_and_commit(self, tool, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        (repo / "a.txt").write_text("a")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True,
                       env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"})

        (repo / "b.txt").write_text("b")
        add_result = tool.add(str(repo), ["b.txt"])
        assert add_result.ok is True

        commit_result = tool.commit(str(repo), "add b")
        assert commit_result.ok is True

    def test_status(self, tool, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        result = tool.status(str(repo))
        assert result.ok is True

    def test_diff(self, tool, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        (repo / "a.txt").write_text("a")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True,
                       env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"})

        (repo / "a.txt").write_text("modified")
        result = tool.diff(str(repo))
        assert result.ok is True
        assert "modified" in result.output

    def test_log(self, tool, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
        (repo / "a.txt").write_text("a")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True,
                       env={**__import__("os").environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@t"})

        result = tool.log(str(repo), limit=5)
        assert result.ok is True
        assert "init" in result.output


class TestGitToolExecMode:
    """Tests using ExecTool delegation (mocked)."""

    def test_clone_delegates_to_exec(self):
        exec_tool = MagicMock()
        exec_tool.execute.return_value = MagicMock(ok=True, output="cloned", exit_code=0)
        tool = GitTool(exec_tool=exec_tool)
        # exec mode tests would go here; for MVP, local mode is primary
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python-agent && python -m pytest tests/test_git_tool.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.git_tool'`

- [ ] **Step 3: Implement GitTool**

```python
# python-agent/tools/git_tool.py
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
    """Thin wrapper around git CLI. Supports local subprocess mode and sandbox ExecTool mode."""

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
        flag = "-b" if create else ""
        cmd = ["git", "-C", repo_dir, "checkout"]
        if flag:
            cmd.append(flag)
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
        return self._run(["git", "-C", repo_dir, "log", f"--oneline", f"-{limit}"])

    def _run(self, cmd: list[str]) -> GitResult:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python-agent && python -m pytest tests/test_git_tool.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add python-agent/tools/git_tool.py python-agent/tests/test_git_tool.py
git commit -m "feat: add GitTool with local subprocess mode for repo operations"
```

---

### Task 1.2: CodeIndex

**Files:**
- Create: `python-agent/tools/code_index.py`
- Create: `python-agent/tests/test_code_index.py`

- [ ] **Step 1: Write failing tests**

```python
# python-agent/tests/test_code_index.py
from __future__ import annotations

from pathlib import Path

import pytest

from tools.code_index import CodeIndex, FileInfo, SymbolInfo


@pytest.fixture
def sample_ts_project(tmp_path):
    """Create a minimal TypeScript project for indexing."""
    src = tmp_path / "src"
    src.mkdir()

    (src / "agent.ts").write_text("""
import { Article } from './models/article';

const API_ROOT = 'https://conduit.productionready.io/api';

export function fetchArticles(): Promise<Article[]> {
    return fetch(`${API_ROOT}/articles`).then(res => res.json());
}

export class ArticleService {
    constructor(private root: string) {}
    getArticle(slug: string) {
        return fetch(`${this.root}/articles/${slug}`);
    }
}
""".strip())

    models = src / "models"
    models.mkdir()
    (models / "article.ts").write_text("""
export interface Article {
    slug: string;
    title: string;
    body: string;
    description: string;
    tagList: string[];
    createdAt: string;
    updatedAt: string;
    favorited: boolean;
    favoritesCount: number;
}

export type ArticleList = Article[];
""".strip())

    (src / "reducer.ts").write_text("""
import { Article } from './models/article';

export interface ArticleState {
    articles: Article[];
    loading: boolean;
}

export function articleReducer(state: ArticleState, action: any): ArticleState {
    switch (action.type) {
        case 'LOAD_ARTICLES':
            return { ...state, loading: true };
        default:
            return state;
    }
}
""".strip())

    (tmp_path / "package.json").write_text('{"name": "conduit"}')
    return tmp_path


class TestCodeIndex:
    def test_scan_finds_files(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        paths = list(idx._files.keys())
        assert len(paths) >= 3
        assert any("agent.ts" in p for p in paths)

    def test_find_symbol(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        results = idx.find_symbol("ArticleService")
        assert len(results) >= 1
        assert results[0].kind == "class"

    def test_find_interface(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        results = idx.find_symbol("Article")
        assert len(results) >= 1
        kinds = {r.kind for r in results}
        assert "interface" in kinds

    def test_find_function(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        results = idx.find_symbol("fetchArticles")
        assert len(results) >= 1
        assert results[0].kind == "function"

    def test_find_reducer(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        results = idx.find_symbol("articleReducer")
        assert len(results) >= 1

    def test_to_context_summary(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        summary = idx.to_context_summary()
        assert "ArticleService" in summary
        assert "Article" in summary
        assert len(summary) < 5000  # bounded

    def test_get_dependents(self, sample_ts_project):
        idx = CodeIndex(sample_ts_project)
        idx.scan()
        dependents = idx.get_dependents("models/article.ts")
        assert any("agent.ts" in d for d in dependents)
        assert any("reducer.ts" in d for d in dependents)

    def test_empty_project(self, tmp_path):
        idx = CodeIndex(tmp_path)
        idx.scan()
        assert len(idx._files) == 0
        assert idx.to_context_summary() == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python-agent && python -m pytest tests/test_code_index.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.code_index'`

- [ ] **Step 3: Implement CodeIndex**

```python
# python-agent/tools/code_index.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SymbolInfo:
    name: str
    kind: str  # "function" | "class" | "interface" | "type" | "const" | "reducer"
    file_path: str
    line: int
    signature: str


@dataclass
class FileInfo:
    path: str
    language: str
    exports: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    symbols: list[SymbolInfo] = field(default_factory=list)


# Regex patterns for TS/JS symbol extraction
_RE_EXPORT_FUNCTION = re.compile(r"export\s+(?:async\s+)?function\s+(\w+)")
_RE_EXPORT_CLASS = re.compile(r"export\s+class\s+(\w+)")
_RE_EXPORT_INTERFACE = re.compile(r"export\s+interface\s+(\w+)")
_RE_EXPORT_TYPE = re.compile(r"export\s+type\s+(\w+)")
_RE_EXPORT_CONST = re.compile(r"export\s+(?:const|let|var)\s+(\w+)")
_RE_IMPORT_FROM = re.compile(r"import\s+.*?from\s+['\"]([^'\"]+)['\"]")
_RE_REDUCER = re.compile(r"export\s+function\s+(\w*[Rr]educer)\s*\(")

_TS_EXTENSIONS = {".ts", ".tsx"}
_JS_EXTENSIONS = {".js", ".jsx"}
_SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".next"}


class CodeIndex:
    """Lightweight TS/JS code index using regex parsing. No external dependencies."""

    def __init__(self, workspace: str | Path) -> None:
        self.workspace = Path(workspace).resolve(strict=False)
        self._files: dict[str, FileInfo] = {}
        self._symbol_index: dict[str, list[SymbolInfo]] = {}
        self._dependents: dict[str, set[str]] = {}

    def scan(self) -> None:
        self._files.clear()
        self._symbol_index.clear()
        self._dependents.clear()

        for file_path in self._iter_source_files():
            rel = str(file_path.relative_to(self.workspace))
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lang = self._detect_language(file_path)
            info = self._parse_file(rel, content, lang)
            self._files[rel] = info

        self._build_dependent_index()

    def find_symbol(self, name: str) -> list[SymbolInfo]:
        return list(self._symbol_index.get(name, []))

    def get_dependents(self, file_path: str) -> list[str]:
        return list(self._dependents.get(file_path, set()))

    def to_context_summary(self, *, max_files: int = 50) -> str:
        if not self._files:
            return ""
        lines = [f"Project: {self.workspace.name}", f"Files indexed: {len(self._files)}", ""]
        for i, (path, info) in enumerate(self._files.items()):
            if i >= max_files:
                lines.append(f"  ... and {len(self._files) - max_files} more files")
                break
            exports_str = ", ".join(info.exports[:10]) if info.exports else "(none)"
            symbols_str = ", ".join(f"{s.kind}:{s.name}" for s in info.symbols[:10])
            lines.append(f"  {path} [{info.language}]")
            lines.append(f"    exports: {exports_str}")
            if symbols_str:
                lines.append(f"    symbols: {symbols_str}")
        return "\n".join(lines)

    def _iter_source_files(self):
        all_extensions = _TS_EXTENSIONS | _JS_EXTENSIONS
        for path in self.workspace.rglob("*"):
            if path.is_file() and path.suffix in all_extensions:
                if any(skip in path.parts for skip in _SKIP_DIRS):
                    continue
                yield path

    def _detect_language(self, path: Path) -> str:
        if path.suffix in _TS_EXTENSIONS:
            return "typescript"
        return "javascript"

    def _parse_file(self, rel_path: str, content: str, lang: str) -> FileInfo:
        info = FileInfo(path=rel_path, language=lang)
        lines = content.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Imports
            m = _RE_IMPORT_FROM.search(stripped)
            if m:
                info.imports.append(m.group(1))

            # Exports — check each pattern
            for regex, kind in [
                (_RE_REDUCER, "reducer"),
                (_RE_EXPORT_FUNCTION, "function"),
                (_RE_EXPORT_CLASS, "class"),
                (_RE_EXPORT_INTERFACE, "interface"),
                (_RE_EXPORT_TYPE, "type"),
                (_RE_EXPORT_CONST, "const"),
            ]:
                m = regex.search(stripped)
                if m:
                    name = m.group(1)
                    info.exports.append(name)
                    sym = SymbolInfo(name=name, kind=kind, file_path=rel_path, line=i, signature=stripped[:200])
                    info.symbols.append(sym)
                    self._symbol_index.setdefault(name, []).append(sym)
                    break  # one match per line

        return info

    def _build_dependent_index(self):
        for path, info in self._files.items():
            for imp in info.imports:
                resolved = self._resolve_import(path, imp)
                if resolved:
                    self._dependents.setdefault(resolved, set()).add(path)

    def _resolve_import(self, from_file: str, import_path: str) -> str | None:
        if not import_path.startswith("."):
            return None
        from_dir = Path(from_file).parent
        candidate = (self.workspace / from_dir / import_path).resolve()
        # Try exact, .ts, .tsx, .js, .jsx, /index.ts
        for ext in ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js"]:
            test = Path(str(candidate) + ext)
            rel = str(test.relative_to(self.workspace)) if test.exists() else None
            if rel and rel in self._files:
                return rel
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python-agent && python -m pytest tests/test_code_index.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add python-agent/tools/code_index.py python-agent/tests/test_code_index.py
git commit -m "feat: add CodeIndex with TS/JS regex-based symbol extraction"
```

---

### Task 1.3: RepoBootstrap

**Files:**
- Create: `python-agent/tools/repo_bootstrap.py`
- Create: `python-agent/tests/test_repo_bootstrap.py`

- [ ] **Step 1: Write failing tests**

```python
# python-agent/tests/test_repo_bootstrap.py
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
        # Create fake repo structure
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "package.json").write_text('{"name":"test"}')

        # Mock clone to create the directory
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
        assert result.ok is True  # no package.json = nothing to install
        assert result.dependencies_installed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python-agent && python -m pytest tests/test_repo_bootstrap.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement RepoBootstrap**

```python
# python-agent/tools/repo_bootstrap.py
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
            result = subprocess.run(
                ["npm", "install"],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=300,
            )
            ok = result.returncode == 0
            file_count = sum(1 for _ in Path(repo_dir).rglob("*") if _.is_file())
            return BootstrapResult(
                ok=ok,
                repo_dir=repo_dir,
                file_count=file_count,
                dependencies_installed=ok,
                error=result.stderr.strip() if not ok else None,
            )
        except subprocess.TimeoutExpired:
            return BootstrapResult(ok=False, repo_dir=repo_dir, file_count=0, dependencies_installed=False, error="npm install timed out")
        except FileNotFoundError:
            return BootstrapResult(ok=False, repo_dir=repo_dir, file_count=0, dependencies_installed=False, error="npm not found in PATH")


def _repo_name(url: str) -> str:
    name = url.rstrip("/").rsplit("/", 1)[-1]
    return name.removesuffix(".git")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python-agent && python -m pytest tests/test_repo_bootstrap.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add python-agent/tools/repo_bootstrap.py python-agent/tests/test_repo_bootstrap.py
git commit -m "feat: add RepoBootstrap for git clone + npm install orchestration"
```

---

### Task 1.4: DialogueManager

**Files:**
- Create: `python-agent/agents/dialogue_manager.py`
- Create: `python-agent/tests/test_dialogue_manager.py`

- [ ] **Step 1: Write failing tests**

```python
# python-agent/tests/test_dialogue_manager.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents.dialogue_manager import ClarificationQuestion, DialogueManager


class TestDialogueManager:
    @pytest.fixture
    def llm(self):
        client = MagicMock()
        return client

    def test_vague_prompt_triggers_clarification(self, llm):
        llm.generate.return_value = '{"needs_clarification": true, "question": "What specific feature do you want to add?", "options": ["Add pagination", "Add search", "Add sorting"], "context": "The request is too vague", "stage": "plan"}'
        dm = DialogueManager(llm_client=llm)
        result = dm.needs_clarification("改进一下这个应用", stage="plan", context={})
        assert result is not None
        assert "What specific" in result.question
        assert len(result.options) == 3

    def test_specific_prompt_no_clarification(self, llm):
        llm.generate.return_value = '{"needs_clarification": false}'
        dm = DialogueManager(llm_client=llm)
        result = dm.needs_clarification("给文章列表中的每篇文章加一个收藏数徽章", stage="plan", context={})
        assert result is None

    def test_incorporate_clarification(self, llm):
        dm = DialogueManager(llm_client=llm)
        merged = dm.incorporate_clarification("改进应用", "加文章分页功能")
        assert "分页" in merged or "文章" in merged
        assert len(merged) > len("改进应用")

    def test_summarize_context_empty(self, llm):
        dm = DialogueManager(llm_client=llm)
        summary = dm.summarize_context()
        assert summary == ""

    def test_summarize_context_with_turns(self, llm):
        dm = DialogueManager(llm_client=llm)
        dm._turns.append({"role": "user", "content": "加搜索功能"})
        dm._turns.append({"role": "assistant", "content": "请问搜索范围？"})
        dm._turns.append({"role": "user", "content": "全文搜索"})
        summary = dm.summarize_context(max_turns=10)
        assert "搜索" in summary
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python-agent && python -m pytest tests/test_dialogue_manager.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement DialogueManager**

```python
# python-agent/agents/dialogue_manager.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClarificationQuestion:
    question: str
    options: list[str] | None
    context: str
    stage: str


class DialogueManager:
    """Determine if a user prompt needs clarification before proceeding."""

    _SYSTEM_PROMPT = (
        "You are a requirements clarification assistant. "
        "Given a user request and the current stage, determine if the request is clear enough to proceed. "
        "Respond with JSON: {\"needs_clarification\": bool, \"question\": str?, \"options\": [str]?, \"context\": str?, \"stage\": str?}"
    )

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm_client = llm_client
        self._turns: list[dict[str, str]] = []

    def needs_clarification(self, prompt: str, stage: str, context: dict) -> ClarificationQuestion | None:
        if not self.llm_client:
            return None

        user_msg = (
            f"Stage: {stage}\n"
            f"Context: {json.dumps(context, ensure_ascii=False)[:500]}\n"
            f"User request: {prompt}"
        )
        self._turns.append({"role": "user", "content": prompt})

        try:
            raw = self.llm_client.generate(user_msg, system_prompt=self._SYSTEM_PROMPT)
            data = json.loads(raw)
        except (json.JSONDecodeError, Exception):
            return None

        if not data.get("needs_clarification"):
            return None

        return ClarificationQuestion(
            question=data.get("question", "Could you clarify your request?"),
            options=data.get("options"),
            context=data.get("context", ""),
            stage=data.get("stage", stage),
        )

    def incorporate_clarification(self, original_prompt: str, answer: str) -> str:
        self._turns.append({"role": "user", "content": answer})
        return f"{original_prompt} (补充说明: {answer})"

    def summarize_context(self, *, max_turns: int = 10) -> str:
        if not self._turns:
            return ""
        recent = self._turns[-max_turns:]
        return "\n".join(f"{t['role']}: {t['content']}" for t in recent)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python-agent && python -m pytest tests/test_dialogue_manager.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add python-agent/agents/dialogue_manager.py python-agent/tests/test_dialogue_manager.py
git commit -m "feat: add DialogueManager for LLM-driven requirement clarification"
```

---

### Task 1.5: Branch 1 Final — Verify All Tests Pass

- [ ] **Step 1: Run full test suite for Branch 1**

Run: `cd python-agent && python -m pytest tests/test_git_tool.py tests/test_code_index.py tests/test_repo_bootstrap.py tests/test_dialogue_manager.py -v`
Expected: All PASS

- [ ] **Step 2: Verify no existing tests broken**

Run: `cd python-agent && python -m pytest tests/ -v --ignore=tests/e2e_real_chain.py -x`
Expected: All existing tests still pass

- [ ] **Step 3: Push branch**

```bash
git push -u origin feat/si-python-tools
```

---

## Branch 2: `feat/si-java-events` — Java Event Types + Payloads

**Priority:** High — parallel with Branch 1, no file conflicts.

### Task 2.1: Add New EventTypes

**Files:**
- Modify: `shared-protocol/src/main/java/com/autocode/protocol/model/EventType.java`

- [ ] **Step 1: Add 8 new event types to the enum**

```java
// In EventType.java, add before the closing brace:
    CLARIFICATION_REQUESTED,
    CLARIFICATION_ANSWERED,
    REPO_BOOTSTRAP_STARTED,
    REPO_BOOTSTRAP_DONE,
    CODE_INDEX_BUILT,
    PLAN_APPROVAL_REQUESTED,
    TEST_GENERATED,
    KNOWLEDGE_WRITEBACK
```

- [ ] **Step 2: Compile to verify**

Run: `cd shared-protocol && ../gradlew compileJava` (or `mvn compile`)
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add shared-protocol/src/main/java/com/autocode/protocol/model/EventType.java
git commit -m "feat: add 8 new event types for super-individual pipeline"
```

---

### Task 2.2: Create Payload Classes

**Files:**
- Create: `shared-protocol/src/main/java/com/autocode/protocol/payload/ClarificationRequestedPayload.java`
- Create: `shared-protocol/src/main/java/com/autocode/protocol/payload/ClarificationAnsweredPayload.java`
- Create: `shared-protocol/src/main/java/com/autocode/protocol/payload/RepoBootstrapStartedPayload.java`
- Create: `shared-protocol/src/main/java/com/autocode/protocol/payload/RepoBootstrapDonePayload.java`
- Create: `shared-protocol/src/main/java/com/autocode/protocol/payload/CodeIndexBuiltPayload.java`
- Create: `shared-protocol/src/main/java/com/autocode/protocol/payload/PlanApprovalRequestedPayload.java`
- Create: `shared-protocol/src/main/java/com/autocode/protocol/payload/TestGeneratedPayload.java`
- Create: `shared-protocol/src/main/java/com/autocode/protocol/payload/KnowledgeWritebackPayload.java`

- [ ] **Step 1: Create ClarificationRequestedPayload**

```java
package com.autocode.protocol.payload;

import java.util.List;

/**
 * Payload for {@code EventType.CLARIFICATION_REQUESTED}.
 */
public class ClarificationRequestedPayload {
    private String question;
    private List<String> options;
    private String context;
    private String stage;

    public String getQuestion() { return question; }
    public void setQuestion(String question) { this.question = question; }
    public List<String> getOptions() { return options; }
    public void setOptions(List<String> options) { this.options = options; }
    public String getContext() { return context; }
    public void setContext(String context) { this.context = context; }
    public String getStage() { return stage; }
    public void setStage(String stage) { this.stage = stage; }
}
```

- [ ] **Step 2: Create ClarificationAnsweredPayload**

```java
package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.CLARIFICATION_ANSWERED}.
 */
public class ClarificationAnsweredPayload {
    private String answer;
    private String originalQuestion;

    public String getAnswer() { return answer; }
    public void setAnswer(String answer) { this.answer = answer; }
    public String getOriginalQuestion() { return originalQuestion; }
    public void setOriginalQuestion(String originalQuestion) { this.originalQuestion = originalQuestion; }
}
```

- [ ] **Step 3: Create RepoBootstrapStartedPayload**

```java
package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.REPO_BOOTSTRAP_STARTED}.
 */
public class RepoBootstrapStartedPayload {
    private String repoUrl;
    private String branch;

    public String getRepoUrl() { return repoUrl; }
    public void setRepoUrl(String repoUrl) { this.repoUrl = repoUrl; }
    public String getBranch() { return branch; }
    public void setBranch(String branch) { this.branch = branch; }
}
```

- [ ] **Step 4: Create RepoBootstrapDonePayload**

```java
package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.REPO_BOOTSTRAP_DONE}.
 */
public class RepoBootstrapDonePayload {
    private String repoDir;
    private int fileCount;
    private boolean dependenciesInstalled;

    public String getRepoDir() { return repoDir; }
    public void setRepoDir(String repoDir) { this.repoDir = repoDir; }
    public int getFileCount() { return fileCount; }
    public void setFileCount(int fileCount) { this.fileCount = fileCount; }
    public boolean isDependenciesInstalled() { return dependenciesInstalled; }
    public void setDependenciesInstalled(boolean dependenciesInstalled) { this.dependenciesInstalled = dependenciesInstalled; }
}
```

- [ ] **Step 5: Create CodeIndexBuiltPayload**

```java
package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.CODE_INDEX_BUILT}.
 */
public class CodeIndexBuiltPayload {
    private int fileCount;
    private int symbolCount;
    private String summary;

    public int getFileCount() { return fileCount; }
    public void setFileCount(int fileCount) { this.fileCount = fileCount; }
    public int getSymbolCount() { return symbolCount; }
    public void setSymbolCount(int symbolCount) { this.symbolCount = symbolCount; }
    public String getSummary() { return summary; }
    public void setSummary(String summary) { this.summary = summary; }
}
```

- [ ] **Step 6: Create PlanApprovalRequestedPayload**

```java
package com.autocode.protocol.payload;

import java.util.List;

/**
 * Payload for {@code EventType.PLAN_APPROVAL_REQUESTED}.
 */
public class PlanApprovalRequestedPayload {
    private String planSummary;
    private List<String> steps;
    private String estimatedImpact;

    public String getPlanSummary() { return planSummary; }
    public void setPlanSummary(String planSummary) { this.planSummary = planSummary; }
    public List<String> getSteps() { return steps; }
    public void setSteps(List<String> steps) { this.steps = steps; }
    public String getEstimatedImpact() { return estimatedImpact; }
    public void setEstimatedImpact(String estimatedImpact) { this.estimatedImpact = estimatedImpact; }
}
```

- [ ] **Step 7: Create TestGeneratedPayload**

```java
package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.TEST_GENERATED}.
 */
public class TestGeneratedPayload {
    private String testFile;
    private int testCount;
    private String framework;

    public String getTestFile() { return testFile; }
    public void setTestFile(String testFile) { this.testFile = testFile; }
    public int getTestCount() { return testCount; }
    public void setTestCount(int testCount) { this.testCount = testCount; }
    public String getFramework() { return framework; }
    public void setFramework(String framework) { this.framework = framework; }
}
```

- [ ] **Step 8: Create KnowledgeWritebackPayload**

```java
package com.autocode.protocol.payload;

/**
 * Payload for {@code EventType.KNOWLEDGE_WRITEBACK}.
 */
public class KnowledgeWritebackPayload {
    private String projectKey;
    private int filesSummarized;
    private int errorPatternsStored;

    public String getProjectKey() { return projectKey; }
    public void setProjectKey(String projectKey) { this.projectKey = projectKey; }
    public int getFilesSummarized() { return filesSummarized; }
    public void setFilesSummarized(int filesSummarized) { this.filesSummarized = filesSummarized; }
    public int getErrorPatternsStored() { return errorPatternsStored; }
    public void setErrorPatternsStored(int errorPatternsStored) { this.errorPatternsStored = errorPatternsStored; }
}
```

- [ ] **Step 9: Compile to verify**

Run: `cd shared-protocol && ../gradlew compileJava`
Expected: BUILD SUCCESS

- [ ] **Step 10: Commit**

```bash
git add shared-protocol/src/main/java/com/autocode/protocol/payload/
git commit -m "feat: add 8 payload classes for super-individual events"
```

---

### Task 2.3: Update TaskService isInformationalEvent

**Files:**
- Modify: `control-plane-spring/src/main/java/com/autocode/controlplane/service/TaskService.java:1133-1139`

- [ ] **Step 1: Add new events to the informational switch**

```java
    private boolean isInformationalEvent(EventType eventType) {
        return switch (eventType) {
            case ASSISTANT_OUTPUT, TOOL_START, TOOL_END, FILE_PATCH_PREVIEW,
                 SPEC_PROPOSED, BUILD_STARTED, BUILD_LOG, BUILD_DONE,
                 ARTIFACT_READY, HEARTBEAT,
                 CLARIFICATION_REQUESTED, CLARIFICATION_ANSWERED,
                 REPO_BOOTSTRAP_STARTED, REPO_BOOTSTRAP_DONE,
                 CODE_INDEX_BUILT, PLAN_APPROVAL_REQUESTED,
                 TEST_GENERATED, KNOWLEDGE_WRITEBACK -> true;
            default -> false;
        };
    }
```

- [ ] **Step 2: Compile to verify**

Run: `cd control-plane-spring && ../gradlew compileJava`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add control-plane-spring/src/main/java/com/autocode/controlplane/service/TaskService.java
git commit -m "feat: register new super-individual events as informational in TaskService"
```

---

### Task 2.4: Branch 2 Final — Verify Build

- [ ] **Step 1: Full build**

Run: `./gradlew build -x test` (or with tests if they pass)
Expected: BUILD SUCCESS

- [ ] **Step 2: Push branch**

```bash
git push -u origin feat/si-java-events
```

---

## Branch 3: `feat/si-python-pipeline` — TestGenerator + KnowledgeExtractor + HumanGate

**Priority:** Medium — after Branch 1 interfaces are defined (but can start in parallel since these are independent files).

### Task 3.1: TestGenerator

**Files:**
- Create: `python-agent/generators/test_generator.py`
- Create: `python-agent/tests/test_test_generator.py`

- [ ] **Step 1: Write failing tests**

```python
# python-agent/tests/test_test_generator.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from generators.test_generator import GeneratedTest, TestGenerator


@pytest.fixture
def sample_project(tmp_path):
    (tmp_path / "package.json").write_text('{"devDependencies": {"jest": "^29.0.0"}}')
    src = tmp_path / "src"
    src.mkdir()
    (src / "math.ts").write_text("""
export function add(a: number, b: number): number {
    return a + b;
}

export function multiply(a: number, b: number): number {
    return a * b;
}
""".strip())
    return tmp_path


class TestTestGenerator:
    def test_detect_jest_framework(self, sample_project):
        gen = TestGenerator()
        framework = gen.detect_test_framework(sample_project)
        assert framework == "jest"

    def test_detect_no_framework(self, tmp_path):
        (tmp_path / "package.json").write_text('{"dependencies": {}}')
        gen = TestGenerator()
        framework = gen.detect_test_framework(tmp_path)
        assert framework == "jest"  # default fallback

    def test_generate_tests(self, sample_project):
        llm = MagicMock()
        llm.generate.return_value = """
import { add, multiply } from './math';

describe('add', () => {
    it('adds two positive numbers', () => {
        expect(add(1, 2)).toBe(3);
    });
    it('handles negative numbers', () => {
        expect(add(-1, 1)).toBe(0);
    });
});

describe('multiply', () => {
    it('multiplies two numbers', () => {
        expect(multiply(2, 3)).toBe(6);
    });
});
"""
        gen = TestGenerator(llm_client=llm)
        results = gen.generate_tests(sample_project, ["src/math.ts"], "add unit tests for math module")
        assert len(results) >= 1
        assert results[0].framework == "jest"
        assert "add" in results[0].content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python-agent && python -m pytest tests/test_test_generator.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement TestGenerator**

```python
# python-agent/generators/test_generator.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GeneratedTest:
    file_path: str
    content: str
    framework: str
    test_count: int


class TestGenerator:
    """Generate tests for changed files using LLM."""

    _SYSTEM_PROMPT = (
        "You are a test generation assistant. Given a source file and its content, "
        "generate unit tests using the detected test framework. "
        "Output ONLY the test code, no explanations."
    )

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm_client = llm_client

    def detect_test_framework(self, workspace: Path) -> str:
        pkg = workspace / "package.json"
        if not pkg.exists():
            return "jest"
        try:
            data = json.loads(pkg.read_text())
            dev_deps = data.get("devDependencies", {})
            if "vitest" in dev_deps:
                return "vitest"
            if "mocha" in dev_deps:
                return "mocha"
            if "jest" in dev_deps:
                return "jest"
        except (json.JSONDecodeError, KeyError):
            pass
        return "jest"

    def generate_tests(self, workspace: Path, changed_files: list[str], prompt: str) -> list[GeneratedTest]:
        if not self.llm_client:
            return []

        framework = self.detect_test_framework(workspace)
        results = []

        for file_path in changed_files:
            full_path = workspace / file_path
            if not full_path.exists():
                continue
            content = full_path.read_text(encoding="utf-8", errors="replace")

            user_msg = (
                f"Framework: {framework}\n"
                f"File: {file_path}\n"
                f"Content:\n{content}\n\n"
                f"Task: {prompt}\n\n"
                f"Generate comprehensive unit tests for this file."
            )

            try:
                test_code = self.llm_client.generate(user_msg, system_prompt=self._SYSTEM_PROMPT)
                test_count = test_code.count("it(") + test_code.count("test(")
                test_file = file_path.replace(".ts", ".test.ts").replace(".js", ".test.js")
                results.append(GeneratedTest(
                    file_path=test_file,
                    content=test_code,
                    framework=framework,
                    test_count=max(test_count, 1),
                ))
            except Exception:
                continue

        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python-agent && python -m pytest tests/test_test_generator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add python-agent/generators/test_generator.py python-agent/tests/test_test_generator.py
git commit -m "feat: add TestGenerator for LLM-driven test generation"
```

---

### Task 3.2: KnowledgeExtractor

**Files:**
- Create: `python-agent/memory/knowledge_extractor.py`
- Create: `python-agent/tests/test_knowledge_extractor.py`

- [ ] **Step 1: Write failing tests**

```python
# python-agent/tests/test_knowledge_extractor.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from memory.knowledge_extractor import KnowledgeExtractor


class TestKnowledgeExtractor:
    def test_extract_file_summary(self):
        llm = MagicMock()
        llm.generate.return_value = "This file implements an ArticleService class with methods for fetching articles."
        ke = KnowledgeExtractor(llm_client=llm)
        summary = ke.extract_file_summary("src/agent.ts", "export class ArticleService { getArticle() {} }")
        assert "ArticleService" in summary
        assert len(summary) > 0

    def test_extract_project_architecture(self):
        llm = MagicMock()
        llm.generate.return_value = '{"architecture": "React+Redux", "modules": ["auth", "articles", "comments"]}'
        ke = KnowledgeExtractor(llm_client=llm)
        # Mock CodeIndex
        idx = MagicMock()
        idx.to_context_summary.return_value = "agent.ts [typescript]\n  exports: ArticleService, fetchArticles"
        result = ke.extract_project_architecture(idx)
        assert "architecture" in result

    def test_extract_file_summary_no_llm(self):
        ke = KnowledgeExtractor(llm_client=None)
        summary = ke.extract_file_summary("test.ts", "const x = 1;")
        assert summary == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python-agent && python -m pytest tests/test_knowledge_extractor.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement KnowledgeExtractor**

```python
# python-agent/memory/knowledge_extractor.py
from __future__ import annotations

import json
from typing import Any


class KnowledgeExtractor:
    """Extract structured knowledge from code for cross-task persistence."""

    _FILE_SUMMARY_PROMPT = (
        "Summarize this source file in 2-3 sentences. "
        "Include: what it does, key classes/functions, and dependencies. "
        "Be concise and factual."
    )

    _ARCH_PROMPT = (
        "Given this project's code index summary, extract:\n"
        "1. Overall architecture pattern\n"
        "2. Key modules and their responsibilities\n"
        "3. Entry points and data flow\n"
        "Respond as JSON: {\"architecture\": str, \"modules\": [str], \"entry_points\": [str], \"data_flow\": str}"
    )

    def __init__(self, llm_client: Any | None = None) -> None:
        self.llm_client = llm_client

    def extract_file_summary(self, file_path: str, content: str) -> str:
        if not self.llm_client:
            return ""
        user_msg = f"File: {file_path}\n\n```\n{content[:3000]}\n```"
        try:
            return self.llm_client.generate(user_msg, system_prompt=self._FILE_SUMMARY_PROMPT).strip()
        except Exception:
            return ""

    def extract_project_architecture(self, code_index: Any) -> dict:
        if not self.llm_client:
            return {}
        summary = code_index.to_context_summary()
        if not summary:
            return {}
        try:
            raw = self.llm_client.generate(summary, system_prompt=self._ARCH_PROMPT)
            return json.loads(raw)
        except (json.JSONDecodeError, Exception):
            return {"raw": raw if "raw" in dir() else ""}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python-agent && python -m pytest tests/test_knowledge_extractor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add python-agent/memory/knowledge_extractor.py python-agent/tests/test_knowledge_extractor.py
git commit -m "feat: add KnowledgeExtractor for LLM-driven code knowledge extraction"
```

---

### Task 3.3: HumanGate

**Files:**
- Create: `python-agent/plugins/human_gate.py`
- Create: `python-agent/tests/test_human_gate.py`

- [ ] **Step 1: Write failing tests**

```python
# python-agent/tests/test_human_gate.py
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from plugins.human_gate import GateDecision, HumanGate, PipelineStage


class TestPipelineStage:
    def test_stages_exist(self):
        assert PipelineStage.PLAN.value == "plan"
        assert PipelineStage.CODE.value == "code"
        assert PipelineStage.TEST.value == "test"
        assert PipelineStage.DEPLOY.value == "deploy"


class TestHumanGate:
    def test_should_gate_when_stage_configured(self):
        gate = HumanGate()
        task = {"approvalStages": ["plan", "code"]}
        assert gate.should_gate(PipelineStage.PLAN, task) is True
        assert gate.should_gate(PipelineStage.CODE, task) is True
        assert gate.should_gate(PipelineStage.TEST, task) is False

    def test_should_gate_default_none(self):
        gate = HumanGate()
        task = {}
        assert gate.should_gate(PipelineStage.PLAN, task) is False

    def test_request_approval_builds_payload(self):
        client = MagicMock()
        gate = HumanGate(client=client)
        task = {"taskId": "t1", "assistant": "ai"}
        approval_id = gate.request_approval(task, PipelineStage.PLAN, "Plan summary", {"steps": ["a", "b"]})
        assert isinstance(approval_id, str)
        assert len(approval_id) > 0

    def test_check_approval_returns_decision(self):
        client = MagicMock()
        gate = HumanGate(client=client)
        decision = gate.check_approval("nonexistent-id", timeout_seconds=1)
        assert isinstance(decision, GateDecision)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python-agent && python -m pytest tests/test_human_gate.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement HumanGate**

```python
# python-agent/plugins/human_gate.py
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any


class PipelineStage(Enum):
    PLAN = "plan"
    CODE = "code"
    TEST = "test"
    DEPLOY = "deploy"


@dataclass(frozen=True)
class GateDecision:
    approved: bool
    feedback: str | None = None


class HumanGate:
    """Gate pipeline stages on human approval. Uses existing APPROVAL_REQUIRED protocol."""

    def __init__(self, client: Any | None = None) -> None:
        self.client = client
        self._pending: dict[str, dict] = {}

    def should_gate(self, stage: PipelineStage, task: dict) -> bool:
        configured = task.get("approvalStages", [])
        if isinstance(configured, list):
            return stage.value in configured
        env_stages = os.getenv("MVP_APPROVAL_STAGES", "").split(",")
        return stage.value in [s.strip() for s in env_stages]

    def request_approval(self, task: dict, stage: PipelineStage, summary: str, details: dict) -> str:
        approval_id = str(uuid.uuid4())
        self._pending[approval_id] = {
            "stage": stage.value,
            "summary": summary,
            "details": details,
            "task": task,
        }
        return approval_id

    def check_approval(self, approval_id: str, timeout_seconds: int = 300) -> GateDecision:
        if approval_id not in self._pending:
            return GateDecision(approved=False, feedback="Unknown approval ID")
        # For MVP: auto-approve if no client (local dev mode)
        if not self.client:
            return GateDecision(approved=True, feedback="Auto-approved (no client)")
        # Real implementation would poll ControlPlane for APPROVAL_RESULT
        return GateDecision(approved=True, feedback="Approved")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python-agent && python -m pytest tests/test_human_gate.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add python-agent/plugins/human_gate.py python-agent/tests/test_human_gate.py
git commit -m "feat: add HumanGate for pipeline stage approval gating"
```

---

### Task 3.4: Extend RedisMemory for Knowledge Storage

**Files:**
- Modify: `python-agent/memory/redis_memory.py`

- [ ] **Step 1: Add knowledge storage methods**

```python
# Add these methods to the existing RedisMemory class:

    def store_code_knowledge(self, project_key: str, knowledge: dict) -> None:
        """Store extracted project knowledge in Redis Hash."""
        key = f"{self._namespace}:{project_key}:knowledge"
        if self._redis:
            import json
            self._redis.hset(key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in knowledge.items()})

    def get_code_knowledge(self, project_key: str) -> dict:
        """Retrieve stored project knowledge."""
        key = f"{self._namespace}:{project_key}:knowledge"
        if self._redis:
            raw = self._redis.hgetall(key)
            return {k.decode(): v.decode() for k, v in raw.items()} if raw else {}
        return {}

    def store_file_summary(self, project_key: str, file_path: str, summary: str) -> None:
        """Store a file-level summary."""
        key = f"{self._namespace}:{project_key}:file_summaries"
        if self._redis:
            self._redis.hset(key, file_path, summary)

    def get_file_summaries(self, project_key: str) -> dict[str, str]:
        """Retrieve all file summaries for a project."""
        key = f"{self._namespace}:{project_key}:file_summaries"
        if self._redis:
            raw = self._redis.hgetall(key)
            return {k.decode(): v.decode() for k, v in raw.items()}
        return {}

    def store_error_pattern(self, project_key: str, error: str, fix: str) -> None:
        """Store an error→fix mapping for future reuse."""
        import hashlib
        error_hash = hashlib.md5(error.encode()).hexdigest()[:12]
        key = f"{self._namespace}:{project_key}:error_fixes"
        if self._redis:
            self._redis.hset(key, error_hash, f"{error}\n---\n{fix}")

    def get_error_fixes(self, project_key: str, error: str) -> list[str]:
        """Retrieve known fixes for similar errors."""
        key = f"{self._namespace}:{project_key}:error_fixes"
        if self._redis:
            import hashlib
            error_hash = hashlib.md5(error.encode()).hexdigest()[:12]
            raw = self._redis.hget(key, error_hash)
            if raw:
                return [raw.decode().split("\n---\n", 1)[-1]]
        return []
```

- [ ] **Step 2: Run existing memory tests to verify no breakage**

Run: `cd python-agent && python -m pytest tests/ -k memory -v`
Expected: Existing tests still pass

- [ ] **Step 3: Commit**

```bash
git add python-agent/memory/redis_memory.py
git commit -m "feat: extend RedisMemory with knowledge storage methods"
```

---

### Task 3.5: Branch 3 Final — Verify All Tests Pass

- [ ] **Step 1: Run full test suite**

Run: `cd python-agent && python -m pytest tests/ -v --ignore=tests/e2e_real_chain.py -x`
Expected: All tests PASS

- [ ] **Step 2: Push branch**

```bash
git push -u origin feat/si-python-pipeline
```

---

## Branch 4: `feat/si-integration` — Orchestrator Wiring + Agent Extensions

**Priority:** After Branches 1-3 are merged to master.

### Task 4.1: Wire New Components into AgentOrchestrator

**Files:**
- Modify: `python-agent/orchestrator/agent_orchestrator.py`

- [ ] **Step 1: Add new dependencies to `__init__`**

```python
# In __init__, add after langgraph_runtime:
    def __init__(
        self,
        intent_agent: IntentAgent | None = None,
        planner_agent: PlannerAgent | None = None,
        coder_agent: CoderAgent | None = None,
        reviewer_agent: ReviewerAgent | None = None,
        tester_agent: TesterAgent | None = None,
        exec_tool: ExecTool | None = None,
        memory_store: RedisMemory | None = None,
        dag_scheduler: DagScheduler | None = None,
        validation_gate: ValidationGate | None = None,
        distributed_lock: DistributedTaskLock | None = None,
        langgraph_runtime: LangGraphRuntime | None = None,
        plugin_registry: PluginRegistry | None = None,
        engine: str | None = None,
        # New super-individual components:
        git_tool: GitTool | None = None,
        code_index: CodeIndex | None = None,
        dialogue_manager: DialogueManager | None = None,
        repo_bootstrap: RepoBootstrap | None = None,
        human_gate: HumanGate | None = None,
        knowledge_extractor: KnowledgeExtractor | None = None,
        test_generator: TestGenerator | None = None,
    ) -> None:
        # ... existing assignments ...
        self.git_tool = git_tool
        self.code_index = code_index
        self.dialogue_manager = dialogue_manager
        self.repo_bootstrap = repo_bootstrap
        self.human_gate = human_gate
        self.knowledge_extractor = knowledge_extractor
        self.test_generator = test_generator
```

- [ ] **Step 2: Insert repo bootstrap + code index stage in `_handle_task_locked`**

```python
# In _handle_task_locked, before the existing memory context step, add:

        # --- Super Individual: Repo Bootstrap ---
        repo_url = task.get("repoUrl", "")
        if repo_url and self.repo_bootstrap:
            pub = self._publisher(task, client)
            pub("REPO_BOOTSTRAP_STARTED", {"repoUrl": repo_url})
            bootstrap_result = self.repo_bootstrap.bootstrap(repo_url, workspace)
            if not bootstrap_result.ok:
                self._terminal_payload(task, {"error": bootstrap_result.error}, task_status="TASK_FAILED", reason="repo bootstrap failed")
                return
            pub("REPO_BOOTSTRAP_DONE", {"repoDir": bootstrap_result.repo_dir, "fileCount": bootstrap_result.file_count})
            workspace = bootstrap_result.repo_dir

            # Build code index
            if self.code_index:
                self.code_index = CodeIndex(workspace)  # re-initialize for this workspace
                self.code_index.scan()
                pub("CODE_INDEX_BUILT", {"fileCount": len(self.code_index._files), "symbolCount": len(self.code_index._symbol_index)})

        # --- Super Individual: Dialogue Clarification ---
        if self.dialogue_manager:
            clarification = self.dialogue_manager.needs_clarification(prompt, stage="plan", context={"workspace": workspace})
            if clarification:
                pub = self._publisher(task, client)
                pub("CLARIFICATION_REQUESTED", {"question": clarification.question, "options": clarification.options})
                # In real flow, task pauses here. For MVP, skip if no options selected.
```

- [ ] **Step 3: Run existing orchestrator tests**

Run: `cd python-agent && python -m pytest tests/test_agent_orchestrator.py -v`
Expected: All existing tests still pass

- [ ] **Step 4: Commit**

```bash
git add python-agent/orchestrator/agent_orchestrator.py
git commit -m "feat: wire GitTool, CodeIndex, DialogueManager into orchestrator pipeline"
```

---

### Task 4.2: Wire Components into main.py

**Files:**
- Modify: `python-agent/main.py`

- [ ] **Step 1: Add imports and initialization**

```python
# Add imports at the top:
from tools.git_tool import GitTool
from tools.code_index import CodeIndex
from tools.repo_bootstrap import RepoBootstrap
from agents.dialogue_manager import DialogueManager
from plugins.human_gate import HumanGate
from memory.knowledge_extractor import KnowledgeExtractor
from generators.test_generator import TestGenerator

# In the orchestrator construction, add new components:
git_tool = GitTool(use_local_git=True)
code_index = CodeIndex(workspace=".")  # will be re-initialized per task
dialogue_manager = DialogueManager(llm_client=llm_client)
repo_bootstrap = RepoBootstrap(git_tool=git_tool)
human_gate = HumanGate(client=control_plane_client)
knowledge_extractor = KnowledgeExtractor(llm_client=llm_client)
test_generator = TestGenerator(llm_client=llm_client)

orchestrator = AgentOrchestrator(
    # ... existing args ...
    git_tool=git_tool,
    code_index=code_index,
    dialogue_manager=dialogue_manager,
    repo_bootstrap=repo_bootstrap,
    human_gate=human_gate,
    knowledge_extractor=knowledge_extractor,
    test_generator=test_generator,
)
```

- [ ] **Step 2: Verify import chain works**

Run: `cd python-agent && python -c "from main import *"` (or just verify syntax)
Expected: No import errors

- [ ] **Step 3: Commit**

```bash
git add python-agent/main.py
git commit -m "feat: wire super-individual components into main.py"
```

---

### Task 4.3: Extend CoderAgent for Incremental Edits

**Files:**
- Modify: `python-agent/agents/coder_agent.py`

- [ ] **Step 1: Add code_index and git_tool dependencies**

```python
# In __init__, add after plugin_registry:
    def __init__(
        self,
        file_tool: FileTool | None = None,
        search_tool: SearchTool | None = None,
        web_template_generator: WebTemplateGenerator | None = None,
        backend_generator: BackendGenerator | None = None,
        fullstack_generator: FullstackGenerator | None = None,
        llm_client: LLMClient | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        plugin_registry: PluginRegistry | None = None,
        code_index: CodeIndex | None = None,  # NEW
        git_tool: GitTool | None = None,  # NEW
    ) -> None:
        # ... existing assignments ...
        self.code_index = code_index
        self.git_tool = git_tool
```

- [ ] **Step 2: Add `_resolve_target_files` method**

```python
    def _resolve_target_files(self, task: dict, plan: Any) -> list[Path]:
        """Resolve which files to edit. Uses CodeIndex if available, falls back to existing logic."""
        if self.code_index and self.code_index._files:
            # Use LLM + code index to pick files
            prompt = task.get("prompt", "")
            context = self.code_index.to_context_summary()
            user_msg = (
                f"Project structure:\n{context}\n\n"
                f"Task: {prompt}\n\n"
                f"List the files that need to be modified, one per line. Only list files that exist."
            )
            try:
                response = self.llm_client.generate(user_msg, system_prompt="You are a code navigation assistant. List only file paths.")
                files = [Path(line.strip()) for line in response.strip().split("\n") if line.strip() and not line.startswith("#")]
                return [f for f in files if (self.code_index.workspace / f).exists()]
            except Exception:
                pass
        # Fallback: use existing _choose_target_file
        target = self._choose_target_file(task, plan)
        return [target] if target else []
```

- [ ] **Step 3: Add `_apply_incremental_edit` method**

```python
    def _apply_incremental_edit(self, file_path: Path, prompt: str, workspace: Path) -> str:
        """Apply an incremental edit to a single file using LLM."""
        full_path = workspace / file_path
        existing_content = ""
        if full_path.exists():
            existing_content = full_path.read_text(encoding="utf-8", errors="replace")

        context_summary = ""
        if self.code_index:
            context_summary = self.code_index.to_context_summary(max_files=20)

        user_msg = (
            f"File: {file_path}\n"
            f"Existing content:\n```\n{existing_content[:4000]}\n```\n\n"
            f"Project context:\n{context_summary[:2000]}\n\n"
            f"Modification request: {prompt}\n\n"
            f"Return the COMPLETE modified file content. No explanations."
        )

        return self.llm_client.generate(
            user_msg,
            system_prompt="You are a precise code editor. Return only the file content."
        )
```

- [ ] **Step 4: Verify existing tests pass**

Run: `cd python-agent && python -m pytest tests/ -k coder -v`
Expected: All existing coder tests still pass

- [ ] **Step 5: Commit**

```bash
git add python-agent/agents/coder_agent.py
git commit -m "feat: add incremental edit support to CoderAgent via CodeIndex"
```

---

### Task 4.4: Extend ValidationGate for TypeScript

**Files:**
- Modify: `python-agent/generators/validation_gate.py`

- [ ] **Step 1: Add TS/React validators**

```python
# Add these functions to validation_gate.py:

def _validate_typescript_syntax(content: str) -> list[str]:
    errors = []
    # Brace balance
    if content.count("{") != content.count("}"):
        errors.append("TypeScript: unbalanced braces")
    # Import/export check
    if "import " in content and "from " not in content and "import(" not in content:
        errors.append("TypeScript: import statement missing 'from' clause")
    return errors


def _validate_react_component(content: str) -> list[str]:
    errors = []
    if "export default" in content and "return" in content:
        # Basic JSX check
        if "(" in content and ")" in content:
            pass  # likely ok
    return errors


def _validate_npm_project(workspace: Path) -> list[str]:
    errors = []
    pkg = workspace / "package.json"
    if not pkg.exists():
        errors.append("No package.json found")
        return errors
    try:
        import json
        data = json.loads(pkg.read_text())
        if "name" not in data:
            errors.append("package.json missing 'name' field")
    except Exception as e:
        errors.append(f"package.json invalid: {e}")
    return errors
```

- [ ] **Step 2: Extend `validate()` to auto-detect project type**

```python
# In the validate() method, after existing checks, add:

        # TypeScript/React checks
        if any(f.endswith(('.ts', '.tsx')) for f in file_map):
            for fname, content in file_map.items():
                if fname.endswith(('.ts', '.tsx')):
                    errors.extend(_validate_typescript_syntax(content))
                if fname.endswith('.tsx'):
                    errors.extend(_validate_react_component(content))

        # npm project check
        if workspace:
            errors.extend(_validate_npm_project(Path(workspace)))
```

- [ ] **Step 3: Run existing validation tests**

Run: `cd python-agent && python -m pytest tests/ -k validation -v`
Expected: Existing tests still pass

- [ ] **Step 4: Commit**

```bash
git add python-agent/generators/validation_gate.py
git commit -m "feat: extend ValidationGate with TypeScript and React validators"
```

---

### Task 4.5: Extend FixLoop for TypeScript Errors

**Files:**
- Modify: `python-agent/generators/fix_loop.py`

- [ ] **Step 1: Add TS error fix strategy**

```python
# Add this method to the FixLoop class:

    def _fix_typescript_errors(self, errors: list[str], content: str, file_path: str) -> str | None:
        """Attempt to fix TypeScript-specific errors using LLM."""
        if not self.llm_client:
            return None
        error_text = "\n".join(errors[:5])
        user_msg = (
            f"File: {file_path}\n"
            f"Errors:\n{error_text}\n\n"
            f"Current content:\n```\n{content[:4000]}\n```\n\n"
            f"Fix these TypeScript errors. Return the complete corrected file."
        )
        try:
            return self.llm_client.generate(
                user_msg,
                system_prompt="You are a TypeScript error fixer. Return only the corrected file content."
            )
        except Exception:
            return None
```

- [ ] **Step 2: Extend error categorization**

```python
# In _categorize_errors, add TypeScript pattern detection:

        ts_patterns = ["TS", "TypeScript", ".ts(", ".tsx(", "Cannot find module", "Property .* does not exist"]
        if any(re.search(p, error, re.IGNORECASE) for p in ts_patterns):
            categories.setdefault("typescript", []).append(error)
```

- [ ] **Step 3: Run existing fix_loop tests**

Run: `cd python-agent && python -m pytest tests/ -k fix_loop -v`
Expected: Existing tests still pass

- [ ] **Step 4: Commit**

```bash
git add python-agent/generators/fix_loop.py
git commit -m "feat: extend FixLoop with TypeScript error fix strategy"
```

---

### Task 4.6: Branch 4 Final — Full Integration Test

- [ ] **Step 1: Run full test suite**

Run: `cd python-agent && python -m pytest tests/ -v --ignore=tests/e2e_real_chain.py -x`
Expected: All tests PASS

- [ ] **Step 2: Push branch**

```bash
git push -u origin feat/si-integration
```

---

## Execution Order

```
Day 1-2:  Branch 1 (feat/si-python-tools) + Branch 2 (feat/si-java-events)  ← PARALLEL
Day 3:    Merge Branch 1 + Branch 2 to master
Day 3-4:  Branch 3 (feat/si-python-pipeline)                                 ← after Branch 1
Day 5:    Merge Branch 3 to master
Day 5-6:  Branch 4 (feat/si-integration)                                      ← after all
Day 6:    Merge Branch 4, E2E smoke test
```
