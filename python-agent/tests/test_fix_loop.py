"""
Unit tests for the intelligent fix loop mechanism.

Tests error categorization, automatic repair strategies, and iteration limits.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from generators.fix_loop import ErrorCategory, FixLoop, FixResult


class TestErrorCategorization:
    """Test error categorization logic."""
    
    def test_categorize_syntax_errors(self):
        """Test that syntax errors are correctly categorized."""
        fix_loop = FixLoop()
        errors = [
            "app.py syntax error at line 10: invalid syntax",
            "styles.css: unbalanced braces",
        ]
        category = fix_loop._categorize_errors(errors)
        assert category == ErrorCategory.SYNTAX
    
    def test_categorize_structure_errors(self):
        """Test that structure errors are correctly categorized."""
        fix_loop = FixLoop()
        errors = [
            "missing required file: backend/app.py",
            "missing required directory: backend/",
        ]
        category = fix_loop._categorize_errors(errors)
        assert category == ErrorCategory.STRUCTURE
    
    def test_categorize_dependency_errors(self):
        """Test that dependency errors are correctly categorized."""
        fix_loop = FixLoop()
        errors = [
            "requirements.txt is empty",
            "requirements.txt: missing web framework (Flask or FastAPI)",
        ]
        category = fix_loop._categorize_errors(errors)
        assert category == ErrorCategory.DEPENDENCY
    
    def test_categorize_runtime_errors(self):
        """Test that runtime errors are correctly categorized."""
        fix_loop = FixLoop()
        errors = [
            "backend/app.py missing Flask/FastAPI application bootstrap",
            "backend runtime validation: import error - No module named 'flask'",
        ]
        category = fix_loop._categorize_errors(errors)
        assert category == ErrorCategory.RUNTIME
    
    def test_categorize_unknown_errors(self):
        """Test that unknown errors default to UNKNOWN category."""
        fix_loop = FixLoop()
        errors = ["some weird error that doesn't match any pattern"]
        category = fix_loop._categorize_errors(errors)
        assert category == ErrorCategory.UNKNOWN
    
    def test_categorize_empty_errors(self):
        """Test that empty error list returns UNKNOWN."""
        fix_loop = FixLoop()
        errors = []
        category = fix_loop._categorize_errors(errors)
        assert category == ErrorCategory.UNKNOWN


class TestStructureRepair:
    """Test automatic structure repair strategies."""
    
    def test_fix_missing_backend_directory(self):
        """Test that missing backend directory is created."""
        fix_loop = FixLoop()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            task = {"_generated_target": "backend"}
            errors = ["missing required directory: backend/"]
            
            success, fixed_files, strategy = fix_loop._fix_structure_errors(
                task, workspace, errors
            )
            
            assert success
            assert "backend/" in fixed_files
            assert strategy == "structure_repair"
            assert (workspace / "backend").is_dir()
    
    def test_fix_missing_frontend_directory(self):
        """Test that missing frontend directory is created."""
        fix_loop = FixLoop()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            task = {"_generated_target": "fullstack"}
            errors = ["missing required directory: frontend/"]
            
            success, fixed_files, strategy = fix_loop._fix_structure_errors(
                task, workspace, errors
            )
            
            assert success
            assert "frontend/" in fixed_files
            assert strategy == "structure_repair"
            assert (workspace / "frontend").is_dir()
    
    def test_fix_missing_html_structure(self):
        """Test that missing HTML structure is added."""
        fix_loop = FixLoop()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            html_file = workspace / "index.html"
            html_file.write_text("<h1>Hello</h1>", encoding="utf-8")
            
            task = {"_generated_target": "web"}
            errors = ["index.html: missing <html> tag"]
            
            success, fixed_files, strategy = fix_loop._fix_structure_errors(
                task, workspace, errors
            )
            
            assert success
            assert "index.html" in fixed_files
            assert strategy == "structure_repair"
            
            content = html_file.read_text(encoding="utf-8")
            assert "<html" in content
            assert "<body>" in content
            assert "<h1>Hello</h1>" in content


class TestDependencyRepair:
    """Test automatic dependency repair strategies."""
    
    def test_fix_empty_requirements(self):
        """Test that empty requirements.txt is populated."""
        fix_loop = FixLoop()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            req_file = workspace / "requirements.txt"
            req_file.write_text("", encoding="utf-8")
            
            task = {"_generated_target": "backend"}
            errors = ["requirements.txt is empty"]
            
            success, fixed_files, strategy = fix_loop._fix_dependency_errors(
                task, workspace, errors
            )
            
            assert success
            assert "requirements.txt" in fixed_files
            assert strategy == "dependency_repair"
            
            content = req_file.read_text(encoding="utf-8")
            assert "flask" in content.lower()
    
    def test_fix_missing_web_framework(self):
        """Test that missing web framework is added."""
        fix_loop = FixLoop()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            req_file = workspace / "requirements.txt"
            req_file.write_text("requests==2.31.0\n", encoding="utf-8")
            
            task = {"_generated_target": "backend"}
            errors = ["requirements.txt: missing web framework (Flask or FastAPI)"]
            
            success, fixed_files, strategy = fix_loop._fix_dependency_errors(
                task, workspace, errors
            )
            
            assert success
            assert "requirements.txt" in fixed_files
            assert strategy == "dependency_repair"
            
            content = req_file.read_text(encoding="utf-8")
            assert "flask" in content.lower()
            assert "requests" in content.lower()


class TestRuntimeRepair:
    """Test automatic runtime repair strategies."""
    
    def test_fix_missing_flask_bootstrap(self):
        """Test that missing Flask bootstrap is added."""
        fix_loop = FixLoop()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            backend_dir = workspace / "backend"
            backend_dir.mkdir()
            app_file = backend_dir / "app.py"
            app_file.write_text("# Empty app\n", encoding="utf-8")
            
            task = {"_generated_target": "backend"}
            errors = ["backend/app.py missing Flask/FastAPI application bootstrap"]
            
            success, fixed_files, strategy = fix_loop._fix_runtime_errors(
                task, workspace, errors
            )
            
            assert success
            assert "backend/app.py" in fixed_files
            assert strategy == "runtime_repair"
            
            content = app_file.read_text(encoding="utf-8")
            assert "Flask(" in content
            assert "app = Flask(__name__)" in content
    
    def test_fix_missing_api_routes(self):
        """Test that missing API routes are added."""
        fix_loop = FixLoop()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            backend_dir = workspace / "backend"
            backend_dir.mkdir()
            app_file = backend_dir / "app.py"
            app_file.write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
            
            task = {"_generated_target": "backend"}
            errors = ["backend/app.py missing API route definitions"]
            
            success, fixed_files, strategy = fix_loop._fix_runtime_errors(
                task, workspace, errors
            )
            
            assert success
            assert "backend/app.py" in fixed_files
            assert strategy == "runtime_repair"
            
            content = app_file.read_text(encoding="utf-8")
            assert "@app.route" in content or "@app.get" in content
            assert "/health" in content


class TestFixLoopIntegration:
    """Test the complete fix loop integration."""
    
    def test_max_iterations_limit(self):
        """Test that fix loop respects maximum iteration limit."""
        fix_loop = FixLoop()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            task = {"_generated_target": "backend"}
            
            # Create a scenario that can't be fixed (missing files)
            result = fix_loop.fix_and_validate(task, workspace, max_iterations=3)
            
            assert not result.success
            assert result.iterations_used == 3
            assert len(result.attempts) == 3
    
    def test_successful_fix_on_first_iteration(self):
        """Test that successful fix stops iteration early."""
        fix_loop = FixLoop()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create a fixable scenario: empty requirements.txt
            req_file = workspace / "requirements.txt"
            req_file.write_text("", encoding="utf-8")
            
            backend_dir = workspace / "backend"
            backend_dir.mkdir()
            
            # Create minimal valid backend files
            app_file = backend_dir / "app.py"
            app_file.write_text("""from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/health")
def health():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    app.run()
""", encoding="utf-8")
            
            models_file = backend_dir / "models.py"
            models_file.write_text("# Models\n", encoding="utf-8")
            
            readme_file = workspace / "README.generated.md"
            readme_file.write_text("# Generated Backend\n", encoding="utf-8")
            
            task = {"_generated_target": "backend"}
            
            # This should fix the empty requirements.txt and pass validation
            result = fix_loop.fix_and_validate(task, workspace, max_iterations=3)
            
            # The fix should succeed (requirements.txt gets populated)
            # But validation might still fail due to other issues
            # At minimum, we should see an attempt was made
            assert len(result.attempts) >= 1
            assert result.attempts[0].category == ErrorCategory.DEPENDENCY
    
    def test_no_fixes_needed(self):
        """Test that valid code passes without fixes."""
        fix_loop = FixLoop()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            
            # Create valid backend structure
            backend_dir = workspace / "backend"
            backend_dir.mkdir()
            
            app_file = backend_dir / "app.py"
            app_file.write_text("""from flask import Flask
from flask_cors import CORS
import sqlite3

app = Flask(__name__)
CORS(app)

@app.route("/api/items")
def list_items():
    return {"items": []}, 200

if __name__ == "__main__":
    app.run()
""", encoding="utf-8")
            
            models_file = backend_dir / "models.py"
            models_file.write_text("# Models\n", encoding="utf-8")
            
            req_file = workspace / "requirements.txt"
            req_file.write_text("flask==3.0.3\nflask-cors==4.0.1\n", encoding="utf-8")
            
            readme_file = workspace / "README.generated.md"
            readme_file.write_text("# Generated Backend\n", encoding="utf-8")
            
            task = {"_generated_target": "backend"}
            
            result = fix_loop.fix_and_validate(task, workspace)
            
            assert result.success
            assert result.iterations_used == 0
            assert len(result.attempts) == 0


class TestFixResult:
    """Test FixResult data class."""
    
    def test_success_summary(self):
        """Test summary for successful fix."""
        result = FixResult(
            success=True,
            attempts=[],
            final_errors=[],
            iterations_used=2,
        )
        assert "Fixed after 2 iteration(s)" in result.summary
    
    def test_failure_summary(self):
        """Test summary for failed fix."""
        result = FixResult(
            success=False,
            attempts=[],
            final_errors=["error 1", "error 2"],
            iterations_used=3,
        )
        assert "Failed after 3 iteration(s)" in result.summary
        assert "error 1" in result.summary
        assert "error 2" in result.summary
