from __future__ import annotations

import os
from pathlib import Path


class FileTool:
    def __init__(self, allowed_workspace_prefixes: list[str] | None = None) -> None:
        self.allowed_workspace_prefixes = self._normalize_prefixes(
            allowed_workspace_prefixes if allowed_workspace_prefixes is not None else self._read_allowed_prefixes_from_env()
        )

    @staticmethod
    def _read_allowed_prefixes_from_env() -> list[str]:
        raw = os.getenv("MVP_ALLOWED_WORKSPACE_PREFIXES", "")
        if not raw.strip():
            return []
        return [segment.strip() for segment in raw.split(",") if segment.strip()]

    @staticmethod
    def _normalize_prefixes(prefixes: list[str]) -> list[Path]:
        normalized: list[Path] = []
        for prefix in prefixes:
            p = Path(prefix).expanduser()
            try:
                normalized.append(p.resolve(strict=False))
            except OSError:
                continue
        return normalized

    @staticmethod
    def _resolve_path(path: str | Path) -> Path:
        p = Path(path).expanduser()
        return p.resolve(strict=False)

    def read_text(self, path: str | Path, encoding: str = "utf-8") -> str:
        resolved = self._resolve_path(path)
        return resolved.read_text(encoding=encoding)

    def write_text(self, path: str | Path, content: str, encoding: str = "utf-8") -> None:
        resolved = self._resolve_path(path)
        self._assert_write_allowed(resolved)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding=encoding)

    def _assert_write_allowed(self, target_path: Path) -> None:
        if not self.allowed_workspace_prefixes:
            raise PermissionError("MVP_ALLOWED_WORKSPACE_PREFIXES is empty; write denied")
        for prefix in self.allowed_workspace_prefixes:
            if _is_relative_to(target_path, prefix):
                return
        raise PermissionError(f"path is outside MVP_ALLOWED_WORKSPACE_PREFIXES: {target_path}")


def _is_relative_to(path: Path, candidate_parent: Path) -> bool:
    try:
        path.relative_to(candidate_parent)
        return True
    except ValueError:
        return False

