from __future__ import annotations

from pathlib import Path


class SearchTool:
    def search_files(
        self,
        root: str | Path,
        query: str,
        *,
        include_exts: tuple[str, ...] = (".py", ".java", ".kt", ".md", ".txt", ".json", ".yaml", ".yml"),
        max_results: int = 20,
    ) -> list[Path]:
        base = Path(root).resolve(strict=False)
        if not base.exists() or not base.is_dir():
            return []

        needle = (query or "").strip().lower()
        if not needle:
            return []

        hits: list[Path] = []
        for file_path in base.rglob("*"):
            if len(hits) >= max_results:
                break
            if not file_path.is_file():
                continue
            if include_exts and file_path.suffix.lower() not in include_exts:
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if needle in content.lower():
                hits.append(file_path)
        return hits

