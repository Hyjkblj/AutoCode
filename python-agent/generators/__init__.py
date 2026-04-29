from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GeneratedProjectResult:
    files: dict[str, str]
    used_fallback: bool
    reason: str
