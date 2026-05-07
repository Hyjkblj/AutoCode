"""
Comprehensive unit tests for ValidationGate.

**Validates: Requirements 6.4**

Tests cover:
- Syntax validation for generated code
- Structure validation for required files
- Backend-specific validation (Flask/FastAPI)
- Database initialization validation
- Error reporting and categorization
"""
from __future__ import annotations

from pathlib import Path

import pytest

from generators.validation_gate import ValidationGate, ValidationResult
from utils.errors import ValidationError


class TestValidationGateWebTarget:
    """Test ValidationGate for web generation target."""

    def test_validation_gate_passes_for_complete_web_project(self, tmp_path):
        """Verify validation passes for complete web project."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("<html><body>Test</body></html>")
        (workspace / "styles.css").write_text("body { margin: 0; }")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test Project")

        task = {"target": "web"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is True
        assert len(result.errors) == 0

    def test_validation_gate_fails_for_missing_index_html(self, tmp_path):
        """Verify validation fails when index.html is missing."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "styles.css").write_text("body { margin: 0; }")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test Project")

        task = {"target": "web"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("index.html" in error for error in result.errors)

    def test_validation_gate_fails_for_missing_styles_css(self, tmp_path):
        """Verify validation fails when styles.css is missing."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("<html><body>Test</body></html>")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test Project")

        task = {"target": "web"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("styles.css" in error for error in result.errors)

    def test_validation_gate_reports_all_missing_web_files(self, tmp_path):
        """Verify validation reports all missing files for web target."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        task = {"target": "web"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert len(result.errors) == 4  # All 4 files missing
        assert any("index.html" in error for error in result.errors)
        assert any("styles.css" in error for error in result.errors)
        assert any("app.js" in error for error in result.errors)
        assert any("README.generated.md" in error for error in result.errors)


class TestValidationGateBackendTarget:
    """Test ValidationGate for backend generation target."""

    def test_validation_gate_passes_for_complete_backend_project(self, tmp_path):
        """Verify validation passes for complete backend project."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text(
            "from flask import Flask\n"
            "import sqlite3\n"
            "app = Flask(__name__)\n"
            "@app.route('/')\n"
            "def index():\n"
            "    return 'ok'\n"
        )
        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("flask==3.0.3")
        (workspace / "README.generated.md").write_text("# Backend Project")

        task = {"target": "backend"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is True
        assert len(result.errors) == 0

    def test_validation_gate_fails_for_missing_backend_app_py(self, tmp_path):
        """Verify validation fails when backend/app.py is missing."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("flask==3.0.3")
        (workspace / "README.generated.md").write_text("# Backend Project")

        task = {"target": "backend"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("backend/app.py" in error for error in result.errors)

    def test_validation_gate_fails_for_missing_flask_application(self, tmp_path):
        """Verify validation fails when Flask application is not initialized."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text(
            "# Missing Flask initialization\n"
            "def index():\n"
            "    return 'ok'\n"
        )
        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("flask==3.0.3")
        (workspace / "README.generated.md").write_text("# Backend Project")

        task = {"target": "backend"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("Flask/FastAPI application bootstrap" in error for error in result.errors)

    def test_validation_gate_accepts_fastapi_application(self, tmp_path):
        """Verify validation accepts FastAPI as alternative to Flask."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text(
            "from fastapi import FastAPI\n"
            "import sqlite3\n"
            "app = FastAPI()\n"
            "@app.get('/')\n"
            "def index():\n"
            "    return {'status': 'ok'}\n"
        )
        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("fastapi==0.100.0")
        (workspace / "README.generated.md").write_text("# Backend Project")

        task = {"target": "backend"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is True

    def test_validation_gate_fails_for_missing_api_routes(self, tmp_path):
        """Verify validation fails when API routes are not defined."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text(
            "from flask import Flask\n"
            "import sqlite3\n"
            "app = Flask(__name__)\n"
            "# Missing route definitions\n"
        )
        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("flask==3.0.3")
        (workspace / "README.generated.md").write_text("# Backend Project")

        task = {"target": "backend"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("API route definitions" in error for error in result.errors)

    def test_validation_gate_fails_for_missing_database_initialization(self, tmp_path):
        """Verify validation fails when database initialization is missing."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text(
            "from flask import Flask\n"
            "app = Flask(__name__)\n"
            "@app.route('/')\n"
            "def index():\n"
            "    return 'ok'\n"
            "# Missing database initialization\n"
        )
        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("flask==3.0.3")
        (workspace / "README.generated.md").write_text("# Backend Project")

        task = {"target": "backend"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("database initialization" in error for error in result.errors)

    def test_validation_gate_accepts_sqlalchemy_for_database(self, tmp_path):
        """Verify validation accepts SQLAlchemy as alternative to sqlite3."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text(
            "from flask import Flask\n"
            "from flask_sqlalchemy import SQLAlchemy\n"
            "app = Flask(__name__)\n"
            "db = SQLAlchemy(app)\n"
            "@app.route('/')\n"
            "def index():\n"
            "    return 'ok'\n"
        )
        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("flask==3.0.3\nflask-sqlalchemy==3.0.0")
        (workspace / "README.generated.md").write_text("# Backend Project")

        task = {"target": "backend"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is True

    def test_validation_gate_detects_syntax_errors_in_backend_code(self, tmp_path):
        """Verify validation detects Python syntax errors."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text(
            "from flask import Flask\n"
            "import sqlite3\n"
            "app = Flask(__name__)\n"
            "@app.route('/')\n"
            "def index(:\n"  # Syntax error
            "    return 'ok'\n"
        )
        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("flask==3.0.3")
        (workspace / "README.generated.md").write_text("# Backend Project")

        task = {"target": "backend"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("syntax error" in error.lower() for error in result.errors)


class TestValidationGateFullstackTarget:
    """Test ValidationGate for fullstack generation target."""

    def test_validation_gate_passes_for_complete_fullstack_project(self, tmp_path):
        """Verify validation passes for complete fullstack project."""
        workspace = tmp_path / "fullstack_project"
        workspace.mkdir()
        frontend_dir = workspace / "frontend"
        frontend_dir.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (frontend_dir / "index.html").write_text("<html><body>Test</body></html>")
        (frontend_dir / "styles.css").write_text("body { margin: 0; }")
        (frontend_dir / "app.js").write_text("console.log('test');")

        (backend_dir / "app.py").write_text(
            "from flask import Flask\n"
            "import sqlite3\n"
            "app = Flask(__name__)\n"
            "@app.route('/api/health')\n"
            "def health():\n"
            "    return {'status': 'ok'}\n"
        )
        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("flask==3.0.3")
        (workspace / "README.generated.md").write_text("# Fullstack Project")
        (workspace / "docker-compose.yml").write_text("services:\n  backend:\n  frontend:\n")
        (workspace / "Dockerfile.backend").write_text("FROM python:3.11-slim\nCOPY . .\nCMD [\"python\"]")
        (workspace / "nginx.conf").write_text("server {\n    listen 80;\n    location / {}\n}")
        (workspace / ".env.example").write_text("FLASK_ENV=development\n")

        task = {"target": "fullstack"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is True
        assert len(result.errors) == 0

    def test_validation_gate_fails_for_missing_frontend_files(self, tmp_path):
        """Verify validation fails when frontend files are missing."""
        workspace = tmp_path / "fullstack_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text(
            "from flask import Flask\n"
            "import sqlite3\n"
            "app = Flask(__name__)\n"
            "@app.route('/')\n"
            "def index():\n"
            "    return 'ok'\n"
        )
        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("flask==3.0.3")
        (workspace / "README.generated.md").write_text("# Fullstack Project")

        task = {"target": "fullstack"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("frontend/index.html" in error for error in result.errors)
        assert any("frontend/styles.css" in error for error in result.errors)
        assert any("frontend/app.js" in error for error in result.errors)

    def test_validation_gate_validates_both_frontend_and_backend(self, tmp_path):
        """Verify validation checks both frontend and backend for fullstack."""
        workspace = tmp_path / "fullstack_project"
        workspace.mkdir()
        frontend_dir = workspace / "frontend"
        frontend_dir.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (frontend_dir / "index.html").write_text("<html><body>Test</body></html>")
        (frontend_dir / "styles.css").write_text("body { margin: 0; }")
        (frontend_dir / "app.js").write_text("console.log('test');")

        # Backend with missing Flask initialization
        (backend_dir / "app.py").write_text(
            "# Missing Flask initialization\n"
            "def index():\n"
            "    return 'ok'\n"
        )
        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("flask==3.0.3")
        (workspace / "README.generated.md").write_text("# Fullstack Project")

        task = {"target": "fullstack"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("Flask/FastAPI application bootstrap" in error for error in result.errors)


class TestValidationGateNoTarget:
    """Test ValidationGate when no target is specified."""

    def test_validation_gate_passes_when_no_target_specified(self, tmp_path):
        """Verify validation passes when no target is specified."""
        workspace = tmp_path / "no_target"
        workspace.mkdir()

        task = {}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is True
        assert len(result.errors) == 0

    def test_validation_gate_uses_generated_target_from_task(self, tmp_path):
        """Verify validation uses _generated_target when target is not set."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("<html><body>Test</body></html>")
        (workspace / "styles.css").write_text("body { margin: 0; }")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test Project")

        task = {"_generated_target": "web"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is True


class TestValidationGateErrorReporting:
    """Test ValidationGate error reporting and summary."""

    def test_validation_result_summary_joins_errors_with_semicolon(self, tmp_path):
        """Verify validation result summary joins errors correctly."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        task = {"target": "web"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert "; " in result.summary
        assert "index.html" in result.summary
        assert "styles.css" in result.summary

    def test_validation_gate_or_raise_raises_on_failure(self, tmp_path):
        """Verify validate_or_raise raises ValidationError on failure."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        task = {"target": "web"}
        gate = ValidationGate()

        with pytest.raises(ValidationError):
            gate.validate_or_raise(task, workspace)

    def test_validation_gate_or_raise_does_not_raise_on_success(self, tmp_path):
        """Verify validate_or_raise does not raise on success."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("<html><body>Test</body></html>")
        (workspace / "styles.css").write_text("body { margin: 0; }")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test Project")

        task = {"target": "web"}
        gate = ValidationGate()

        # Should not raise
        gate.validate_or_raise(task, workspace)


class TestValidationGateEdgeCases:
    """Test ValidationGate edge cases and boundary conditions."""

    def test_validation_gate_handles_empty_backend_app_file(self, tmp_path):
        """Verify validation handles empty backend/app.py file."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text("")
        (backend_dir / "models.py").write_text("TABLE_NAME = 'users'")
        (workspace / "requirements.txt").write_text("flask==3.0.3")
        (workspace / "README.generated.md").write_text("# Backend Project")

        task = {"target": "backend"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert len(result.errors) >= 3  # Missing Flask, routes, and database

    def test_validation_gate_handles_nonexistent_workspace(self, tmp_path):
        """Verify validation handles nonexistent workspace directory."""
        workspace = tmp_path / "nonexistent"

        task = {"target": "web"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is False
        assert len(result.errors) == 4  # All files missing

    def test_validation_gate_handles_case_insensitive_target(self, tmp_path):
        """Verify validation handles case-insensitive target values."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("<html><body>Test</body></html>")
        (workspace / "styles.css").write_text("body { margin: 0; }")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test Project")

        task = {"target": "WEB"}
        gate = ValidationGate()

        result = gate.validate(task, workspace)

        assert result.ok is True
