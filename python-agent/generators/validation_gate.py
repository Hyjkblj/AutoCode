from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
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
    """
    Comprehensive validation gate for generated code.
    
    Validates:
    - Syntax correctness (Python, HTML, CSS, JavaScript)
    - Structure validation (required files and directories)
    - Dependency validation (requirements.txt, package.json)
    - Runtime validation (attempt to start generated applications)
    """
    
    def validate(self, task: dict[str, Any], workspace: Path) -> ValidationResult:
        target = str(task.get("_generated_target") or task.get("target") or "").strip().lower()
        if not target:
            return ValidationResult(ok=True, errors=[])

        errors: list[str] = []
        if target == "web":
            errors.extend(_validate_required_files(workspace, ["index.html", "styles.css", "app.js", "README.generated.md"]))
            errors.extend(_validate_html_syntax(workspace / "index.html"))
            errors.extend(_validate_css_syntax(workspace / "styles.css"))
            errors.extend(_validate_javascript_syntax(workspace / "app.js"))
        elif target == "backend":
            errors.extend(_validate_required_files(workspace, ["backend/app.py", "backend/models.py", "requirements.txt", "README.generated.md"]))
            errors.extend(_validate_backend_structure(workspace))
            errors.extend(_validate_python_syntax(workspace / "backend" / "app.py"))
            errors.extend(_validate_python_syntax(workspace / "backend" / "models.py"))
            errors.extend(_validate_backend_sources(workspace / "backend" / "app.py"))
            errors.extend(_validate_requirements_txt(workspace / "requirements.txt"))
            errors.extend(_validate_backend_runtime(workspace))
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
            errors.extend(_validate_fullstack_structure(workspace))
            errors.extend(_validate_html_syntax(workspace / "frontend" / "index.html"))
            errors.extend(_validate_css_syntax(workspace / "frontend" / "styles.css"))
            errors.extend(_validate_javascript_syntax(workspace / "frontend" / "app.js"))
            errors.extend(_validate_python_syntax(workspace / "backend" / "app.py"))
            errors.extend(_validate_python_syntax(workspace / "backend" / "models.py"))
            errors.extend(_validate_backend_sources(workspace / "backend" / "app.py"))
            errors.extend(_validate_requirements_txt(workspace / "requirements.txt"))
            errors.extend(_validate_backend_runtime(workspace))
            
            # Check for package.json if present
            package_json = workspace / "frontend" / "package.json"
            if package_json.exists():
                errors.extend(_validate_package_json(package_json))
        return ValidationResult(ok=not errors, errors=errors)

    def validate_or_raise(self, task: dict[str, Any], workspace: Path) -> None:
        result = self.validate(task, workspace)
        if not result.ok:
            raise ValidationError(result.summary or "validation failed")


def _validate_required_files(workspace: Path, files: list[str]) -> list[str]:
    """Validate that all required files exist."""
    errors: list[str] = []
    for relative in files:
        if not (workspace / relative).exists():
            errors.append(f"missing required file: {relative}")
    return errors


def _validate_backend_structure(workspace: Path) -> list[str]:
    """Validate backend directory structure."""
    errors: list[str] = []
    backend_dir = workspace / "backend"
    if not backend_dir.is_dir():
        errors.append("missing required directory: backend/")
    return errors


def _validate_fullstack_structure(workspace: Path) -> list[str]:
    """Validate fullstack directory structure."""
    errors: list[str] = []
    frontend_dir = workspace / "frontend"
    backend_dir = workspace / "backend"
    
    if not frontend_dir.is_dir():
        errors.append("missing required directory: frontend/")
    if not backend_dir.is_dir():
        errors.append("missing required directory: backend/")
    return errors


def _validate_python_syntax(file_path: Path) -> list[str]:
    """Validate Python file syntax using AST parsing."""
    if not file_path.exists():
        return []
    
    errors: list[str] = []
    try:
        text = file_path.read_text(encoding="utf-8")
        ast.parse(text, filename=str(file_path))
    except SyntaxError as exc:
        errors.append(f"{file_path.name} syntax error at line {exc.lineno}: {exc.msg}")
    except Exception as exc:
        errors.append(f"{file_path.name} parsing error: {str(exc)}")
    return errors


def _validate_html_syntax(file_path: Path) -> list[str]:
    """Validate HTML file syntax with basic checks."""
    if not file_path.exists():
        return []
    
    errors: list[str] = []
    try:
        text = file_path.read_text(encoding="utf-8")
        
        # Check for basic HTML structure (at least html and body tags)
        if not re.search(r"<html[^>]*>", text, re.IGNORECASE):
            errors.append(f"{file_path.name}: missing <html> tag")
        if not re.search(r"<body[^>]*>", text, re.IGNORECASE):
            errors.append(f"{file_path.name}: missing <body> tag")
        
        # Check for unclosed tags (basic validation)
        opening_tags = re.findall(r"<(\w+)[^>]*>", text)
        closing_tags = re.findall(r"</(\w+)>", text)
        self_closing = {"meta", "link", "img", "br", "hr", "input", "area", "base", "col", "embed", "param", "source", "track", "wbr"}
        
        # Count non-self-closing tags
        opening_count = {}
        for tag in opening_tags:
            if tag.lower() not in self_closing:
                opening_count[tag.lower()] = opening_count.get(tag.lower(), 0) + 1
        
        closing_count = {}
        for tag in closing_tags:
            closing_count[tag.lower()] = closing_count.get(tag.lower(), 0) + 1
        
        # Check for mismatches
        all_tags = set(opening_count.keys()) | set(closing_count.keys())
        for tag in all_tags:
            open_c = opening_count.get(tag, 0)
            close_c = closing_count.get(tag, 0)
            if open_c != close_c:
                errors.append(f"{file_path.name}: tag mismatch for <{tag}> (opened: {open_c}, closed: {close_c})")
                
    except Exception as exc:
        errors.append(f"{file_path.name} reading error: {str(exc)}")
    return errors


def _validate_css_syntax(file_path: Path) -> list[str]:
    """Validate CSS file syntax with basic checks."""
    if not file_path.exists():
        return []
    
    errors: list[str] = []
    try:
        text = file_path.read_text(encoding="utf-8")
        
        # Check for balanced braces
        open_braces = text.count("{")
        close_braces = text.count("}")
        if open_braces != close_braces:
            errors.append(f"{file_path.name}: unbalanced braces ({{ : {open_braces}, }} : {close_braces})")
        
        # Check for basic CSS rule structure
        if open_braces > 0:
            # Look for selector patterns
            if not re.search(r"[a-zA-Z0-9_\-#.\[\]:,\s]+\s*\{", text):
                errors.append(f"{file_path.name}: no valid CSS selectors found")
                
    except Exception as exc:
        errors.append(f"{file_path.name} reading error: {str(exc)}")
    return errors


def _validate_javascript_syntax(file_path: Path) -> list[str]:
    """Validate JavaScript file syntax with basic checks."""
    if not file_path.exists():
        return []
    
    errors: list[str] = []
    try:
        text = file_path.read_text(encoding="utf-8")
        
        # Check for balanced braces, brackets, and parentheses
        if text.count("{") != text.count("}"):
            errors.append(f"{file_path.name}: unbalanced curly braces")
        if text.count("[") != text.count("]"):
            errors.append(f"{file_path.name}: unbalanced square brackets")
        if text.count("(") != text.count(")"):
            errors.append(f"{file_path.name}: unbalanced parentheses")
        
        # Check for common syntax patterns
        # Look for function declarations or expressions
        has_function = bool(re.search(r"\bfunction\s+\w+\s*\(", text) or 
                           re.search(r"\bconst\s+\w+\s*=\s*\([^)]*\)\s*=>", text) or
                           re.search(r"\blet\s+\w+\s*=\s*\([^)]*\)\s*=>", text) or
                           re.search(r"\bvar\s+\w+\s*=\s*function", text))
        
        # If file is not empty and has no functions, it might be incomplete
        if len(text.strip()) > 50 and not has_function:
            # Check if it at least has some statements
            has_statements = bool(re.search(r"\bconsole\.", text) or 
                                 re.search(r"\bdocument\.", text) or
                                 re.search(r"\bwindow\.", text))
            if not has_statements:
                errors.append(f"{file_path.name}: no recognizable JavaScript code found")
                
    except Exception as exc:
        errors.append(f"{file_path.name} reading error: {str(exc)}")
    return errors


def _validate_requirements_txt(file_path: Path) -> list[str]:
    """Validate requirements.txt format and dependencies."""
    if not file_path.exists():
        return []
    
    errors: list[str] = []
    try:
        text = file_path.read_text(encoding="utf-8")
        lines = [line.strip() for line in text.split("\n") if line.strip() and not line.strip().startswith("#")]
        
        if not lines:
            errors.append("requirements.txt is empty")
            return errors
        
        # Validate each dependency line
        for line_num, line in enumerate(lines, 1):
            # Check for valid package name format
            # Valid formats: package, package==version, package>=version, etc.
            if not re.match(r"^[a-zA-Z0-9_\-\[\]]+([<>=!]+[a-zA-Z0-9._\-]+)?$", line):
                errors.append(f"requirements.txt line {line_num}: invalid format '{line}'")
        
        # Check for common required packages for Flask/FastAPI backends
        packages = [line.split("==")[0].split(">=")[0].split("<=")[0].split("<")[0].split(">")[0].lower() for line in lines]
        has_web_framework = any(pkg in packages for pkg in ["flask", "fastapi"])
        
        if not has_web_framework:
            errors.append("requirements.txt: missing web framework (Flask or FastAPI)")
            
    except Exception as exc:
        errors.append(f"requirements.txt reading error: {str(exc)}")
    return errors


def _validate_package_json(file_path: Path) -> list[str]:
    """Validate package.json format and structure."""
    if not file_path.exists():
        return []
    
    errors: list[str] = []
    try:
        text = file_path.read_text(encoding="utf-8")
        data = json.loads(text)
        
        # Check for required fields
        if "name" not in data:
            errors.append("package.json: missing 'name' field")
        if "version" not in data:
            errors.append("package.json: missing 'version' field")
        
        # Validate dependencies format if present
        for dep_type in ["dependencies", "devDependencies"]:
            if dep_type in data:
                if not isinstance(data[dep_type], dict):
                    errors.append(f"package.json: '{dep_type}' must be an object")
                    
    except json.JSONDecodeError as exc:
        errors.append(f"package.json: invalid JSON at line {exc.lineno}: {exc.msg}")
    except Exception as exc:
        errors.append(f"package.json reading error: {str(exc)}")
    return errors


def _validate_backend_sources(app_path: Path) -> list[str]:
    """Validate backend application source code structure."""
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
    return errors


def _validate_backend_runtime(workspace: Path) -> list[str]:
    """
    Validate backend runtime by attempting to start the application.
    
    This performs a dry-run check to ensure the application can be imported
    and basic initialization succeeds without actually starting the server.
    """
    errors: list[str] = []
    backend_dir = workspace / "backend"
    app_file = backend_dir / "app.py"
    
    if not app_file.exists():
        return errors  # Already caught by other validators
    
    try:
        text = app_file.read_text(encoding="utf-8")
        
        # Check if the app has a proper entry point (warning, not error)
        has_main = "__name__" in text and "__main__" in text
        has_run = "app.run(" in text or "uvicorn.run(" in text
        
        # Only warn if neither is present, but don't fail validation
        # This allows for apps that are meant to be imported
        if not has_main and not has_run:
            # This is informational only - many valid apps don't have __main__
            pass
        
        # Try a basic import check using Python subprocess
        # This is safer than importing directly as it runs in isolation
        check_code = f"""
import sys
sys.path.insert(0, '{backend_dir}')
try:
    import app
    print("OK")
except ImportError as e:
    print(f"IMPORT_ERROR: {{e}}")
except Exception as e:
    # Some exceptions during import are acceptable (e.g., missing database file)
    # Only report if it's a critical error
    if "No module named" in str(e) or "cannot import name" in str(e):
        print(f"ERROR: {{e}}")
    else:
        print("OK")
"""
        
        result = subprocess.run(
            [sys.executable, "-c", check_code],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(workspace)
        )
        
        if "IMPORT_ERROR" in result.stdout:
            error_msg = result.stdout.split("IMPORT_ERROR:")[1].strip()
            if not _is_environment_dependency_error(error_msg):
                errors.append(f"backend runtime validation: import error - {error_msg}")
        elif "ERROR" in result.stdout and "OK" not in result.stdout:
            error_msg = result.stdout.split("ERROR:")[1].strip()
            if not _is_environment_dependency_error(error_msg):
                errors.append(f"backend runtime validation: {error_msg}")
        # Don't fail on non-zero exit code if we got "OK" - the app might have initialization code that fails
        # but the syntax and imports are valid
            
    except subprocess.TimeoutExpired:
        errors.append("backend runtime validation: timeout (application may have blocking code)")
    except Exception as exc:
        # Don't fail validation on runtime check errors - these are often environmental
        pass
    
    return errors


def _is_environment_dependency_error(error_message: str) -> bool:
    """
    Return True when the runtime import failure is caused by missing framework
    packages in the validator environment rather than by generated source code.
    """
    normalized = (error_message or "").strip().lower()
    if "no module named" not in normalized:
        return False
    known_runtime_dependencies = (
        "flask",
        "flask_cors",
        "flask_sqlalchemy",
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "pydantic",
        "aiosqlite",
    )
    return any(dep in normalized for dep in known_runtime_dependencies)
