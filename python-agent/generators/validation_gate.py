from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.errors import ValidationError


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]

    @property
    def summary(self) -> str:
        return "; ".join(self.errors)


class ValidationGate:
    def validate(self, task: dict[str, Any], workspace: Path) -> ValidationResult:
        target = str(task.get("_generated_target") or task.get("target") or "").strip().lower()
        if not target:
            return ValidationResult(ok=True, errors=[])

        errors: list[str] = []
        if target == "web":
            errors.extend(_validate_required_files(workspace, ["index.html", "styles.css", "app.js", "README.generated.md"]))
        elif target == "backend":
            errors.extend(_validate_required_files(workspace, ["backend/app.py", "backend/models.py", "requirements.txt", "README.generated.md"]))
            errors.extend(_validate_backend_sources(workspace / "backend" / "app.py"))
        elif target == "fullstack":
            errors.extend(
                _validate_required_files(
                    workspace,
                    [
                        "frontend/index.html",
                        "frontend/styles.css",
                        "frontend/app.js",
                        "backend/app.py",
                        "backend/models.py",
                        "requirements.txt",
                        "README.generated.md",
                    ],
                )
            )
            errors.extend(_validate_backend_sources(workspace / "backend" / "app.py"))
        return ValidationResult(ok=not errors, errors=errors)

    def validate_or_raise(self, task: dict[str, Any], workspace: Path) -> None:
        result = self.validate(task, workspace)
        if not result.ok:
            raise ValidationError(result.summary or "validation failed")


def _validate_required_files(workspace: Path, files: list[str]) -> list[str]:
    errors: list[str] = []
    for relative in files:
        if not (workspace / relative).exists():
            errors.append(f"missing required file: {relative}")
    return errors


def _validate_backend_sources(app_path: Path) -> list[str]:
    if not app_path.exists():
        return []
    text = app_path.read_text(encoding="utf-8")
    errors: list[str] = []
    if "Flask(" not in text and "FastAPI(" not in text:
        errors.append("backend/app.py missing Flask/FastAPI application bootstrap")
    if "@app.route" not in text and "@app.get" not in text and "@app.post" not in text:
        errors.append("backend/app.py missing API route definitions")
    if "sqlite3" not in text and "SQLAlchemy" not in text:
        errors.append("backend/app.py missing database initialization logic")
    try:
        compile(text, str(app_path), "exec")
    except SyntaxError as exc:
        errors.append(f"backend/app.py syntax error: {exc.msg}")
    return errors
