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
            rel = file_path.relative_to(self.workspace).as_posix()
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
            m = _RE_IMPORT_FROM.search(stripped)
            if m:
                info.imports.append(m.group(1))
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
                    sym = SymbolInfo(
                        name=name, kind=kind, file_path=rel_path, line=i, signature=stripped[:200]
                    )
                    info.symbols.append(sym)
                    self._symbol_index.setdefault(name, []).append(sym)
                    break
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
        for ext in ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js"]:
            test = Path(str(candidate) + ext)
            rel = test.relative_to(self.workspace).as_posix() if test.exists() else None
            if rel and rel in self._files:
                return rel
        return None
