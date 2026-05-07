"""
Enhanced validation gate tests for comprehensive syntax, structure, dependency, and runtime checks.

Tests the new validation capabilities added in task 11.1:
- Syntax validation for Python, HTML, CSS, JavaScript
- Structure validation for required files and directories
- Dependency validation for requirements.txt and package.json
- Runtime validation by attempting to start generated applications

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**
"""

from pathlib import Path

import pytest

from generators.validation_gate import ValidationGate


class TestPythonSyntaxValidation:
    """Test Python syntax validation."""

    def test_validates_correct_python_syntax(self, tmp_path):
        """Verify validation passes for syntactically correct Python code."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text("""
from flask import Flask
import sqlite3

app = Flask(__name__)

@app.route('/')
def index():
    return 'Hello World'

if __name__ == '__main__':
    app.run()
""")
        (backend_dir / "models.py").write_text("# Models file")
        (workspace / "requirements.txt").write_text("Flask==2.0.1")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "backend"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is True

    def test_detects_python_syntax_errors(self, tmp_path):
        """Verify validation detects Python syntax errors."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text("""
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index()  # Missing colon
    return 'Hello World'
""")
        (backend_dir / "models.py").write_text("# Models")
        (workspace / "requirements.txt").write_text("Flask==2.0.1")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "backend"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("syntax error" in error.lower() for error in result.errors)


class TestHTMLSyntaxValidation:
    """Test HTML syntax validation."""

    def test_validates_correct_html_structure(self, tmp_path):
        """Verify validation passes for well-formed HTML."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("""
<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
</head>
<body>
    <h1>Hello World</h1>
</body>
</html>
""")
        (workspace / "styles.css").write_text("body { margin: 0; }")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "web"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is True

    def test_detects_missing_html_tag(self, tmp_path):
        """Verify validation detects missing HTML tag."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("<body>Content</body>")
        (workspace / "styles.css").write_text("body { margin: 0; }")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "web"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("missing <html> tag" in error for error in result.errors)

    def test_detects_unclosed_html_tags(self, tmp_path):
        """Verify validation detects unclosed HTML tags."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("""
<html>
<body>
    <div>
        <p>Unclosed paragraph
    </div>
</body>
</html>
""")
        (workspace / "styles.css").write_text("body { margin: 0; }")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "web"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("tag mismatch" in error for error in result.errors)


class TestCSSSyntaxValidation:
    """Test CSS syntax validation."""

    def test_validates_correct_css_syntax(self, tmp_path):
        """Verify validation passes for well-formed CSS."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("<html><body>Test</body></html>")
        (workspace / "styles.css").write_text("""
body {
    margin: 0;
    padding: 0;
}

.container {
    width: 100%;
}
""")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "web"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is True

    def test_detects_unbalanced_css_braces(self, tmp_path):
        """Verify validation detects unbalanced braces in CSS."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("<html><body>Test</body></html>")
        (workspace / "styles.css").write_text("""
body {
    margin: 0;
    padding: 0;

.container {
    width: 100%;
}
""")
        (workspace / "app.js").write_text("console.log('test');")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "web"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("unbalanced braces" in error for error in result.errors)


class TestJavaScriptSyntaxValidation:
    """Test JavaScript syntax validation."""

    def test_validates_correct_javascript_syntax(self, tmp_path):
        """Verify validation passes for well-formed JavaScript."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("<html><body>Test</body></html>")
        (workspace / "styles.css").write_text("body { margin: 0; }")
        (workspace / "app.js").write_text("""
function greet(name) {
    return `Hello, ${name}!`;
}

const result = greet('World');
console.log(result);
""")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "web"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is True

    def test_detects_unbalanced_javascript_braces(self, tmp_path):
        """Verify validation detects unbalanced braces in JavaScript."""
        workspace = tmp_path / "web_project"
        workspace.mkdir()

        (workspace / "index.html").write_text("<html><body>Test</body></html>")
        (workspace / "styles.css").write_text("body { margin: 0; }")
        (workspace / "app.js").write_text("""
function greet(name) {
    return `Hello, ${name}!`;

console.log('test');
""")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "web"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("unbalanced" in error for error in result.errors)


class TestRequirementsTxtValidation:
    """Test requirements.txt validation."""

    def test_validates_correct_requirements_format(self, tmp_path):
        """Verify validation passes for well-formed requirements.txt."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text("""
from flask import Flask
import sqlite3
app = Flask(__name__)
@app.route('/')
def index():
    return 'Hello'
""")
        (backend_dir / "models.py").write_text("# Models")
        (workspace / "requirements.txt").write_text("""
Flask==2.0.1
SQLAlchemy>=1.4.0
requests==2.26.0
""")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "backend"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is True

    def test_detects_empty_requirements_file(self, tmp_path):
        """Verify validation detects empty requirements.txt."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text("""
from flask import Flask
app = Flask(__name__)
@app.route('/')
def index():
    return 'Hello'
""")
        (backend_dir / "models.py").write_text("# Models")
        (workspace / "requirements.txt").write_text("")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "backend"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("empty" in error.lower() for error in result.errors)

    def test_detects_missing_web_framework_in_requirements(self, tmp_path):
        """Verify validation detects missing Flask/FastAPI in requirements.txt."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text("""
from flask import Flask
app = Flask(__name__)
@app.route('/')
def index():
    return 'Hello'
""")
        (backend_dir / "models.py").write_text("# Models")
        (workspace / "requirements.txt").write_text("""
requests==2.26.0
SQLAlchemy>=1.4.0
""")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "backend"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("web framework" in error.lower() for error in result.errors)

    def test_detects_invalid_requirements_format(self, tmp_path):
        """Verify validation detects invalid package format in requirements.txt."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (backend_dir / "app.py").write_text("""
from flask import Flask
app = Flask(__name__)
@app.route('/')
def index():
    return 'Hello'
""")
        (backend_dir / "models.py").write_text("# Models")
        (workspace / "requirements.txt").write_text("""
Flask==2.0.1
invalid package name with spaces
SQLAlchemy>=1.4.0
""")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "backend"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("invalid format" in error for error in result.errors)


class TestPackageJsonValidation:
    """Test package.json validation."""

    def test_validates_correct_package_json(self, tmp_path):
        """Verify validation passes for well-formed package.json."""
        workspace = tmp_path / "fullstack_project"
        workspace.mkdir()
        frontend_dir = workspace / "frontend"
        frontend_dir.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (frontend_dir / "index.html").write_text("<html><body>Test</body></html>")
        (frontend_dir / "styles.css").write_text("body { margin: 0; }")
        (frontend_dir / "app.js").write_text("console.log('test');")
        (frontend_dir / "package.json").write_text("""
{
    "name": "test-app",
    "version": "1.0.0",
    "dependencies": {
        "react": "^18.0.0"
    }
}
""")
        (backend_dir / "app.py").write_text("""
from flask import Flask
import sqlite3
app = Flask(__name__)
@app.route('/')
def index():
    return 'Hello'
""")
        (backend_dir / "models.py").write_text("# Models")
        (workspace / "requirements.txt").write_text("Flask==2.0.1")
        (workspace / "README.generated.md").write_text("# Test")
        (workspace / "docker-compose.yml").write_text("services:\n  backend:\n  frontend:\n")
        (workspace / "Dockerfile.backend").write_text("FROM python:3.11-slim\nCOPY . .\nCMD [\"python\"]")
        (workspace / "nginx.conf").write_text("server {\n    listen 80;\n    location / {}\n}")
        (workspace / ".env.example").write_text("FLASK_ENV=development\n")

        task = {"target": "fullstack"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is True

    def test_detects_invalid_package_json_syntax(self, tmp_path):
        """Verify validation detects invalid JSON in package.json."""
        workspace = tmp_path / "fullstack_project"
        workspace.mkdir()
        frontend_dir = workspace / "frontend"
        frontend_dir.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (frontend_dir / "index.html").write_text("<html><body>Test</body></html>")
        (frontend_dir / "styles.css").write_text("body { margin: 0; }")
        (frontend_dir / "app.js").write_text("console.log('test');")
        (frontend_dir / "package.json").write_text("""
{
    "name": "test-app",
    "version": "1.0.0",
    "dependencies": {
        "react": "^18.0.0"
    }
""")  # Missing closing brace
        (backend_dir / "app.py").write_text("""
from flask import Flask
app = Flask(__name__)
@app.route('/')
def index():
    return 'Hello'
""")
        (backend_dir / "models.py").write_text("# Models")
        (workspace / "requirements.txt").write_text("Flask==2.0.1")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "fullstack"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("invalid JSON" in error for error in result.errors)

    def test_detects_missing_required_fields_in_package_json(self, tmp_path):
        """Verify validation detects missing required fields in package.json."""
        workspace = tmp_path / "fullstack_project"
        workspace.mkdir()
        frontend_dir = workspace / "frontend"
        frontend_dir.mkdir()
        backend_dir = workspace / "backend"
        backend_dir.mkdir()

        (frontend_dir / "index.html").write_text("<html><body>Test</body></html>")
        (frontend_dir / "styles.css").write_text("body { margin: 0; }")
        (frontend_dir / "app.js").write_text("console.log('test');")
        (frontend_dir / "package.json").write_text("""
{
    "dependencies": {
        "react": "^18.0.0"
    }
}
""")  # Missing name and version
        (backend_dir / "app.py").write_text("""
from flask import Flask
app = Flask(__name__)
@app.route('/')
def index():
    return 'Hello'
""")
        (backend_dir / "models.py").write_text("# Models")
        (workspace / "requirements.txt").write_text("Flask==2.0.1")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "fullstack"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("missing 'name' field" in error for error in result.errors)
        assert any("missing 'version' field" in error for error in result.errors)


class TestStructureValidation:
    """Test directory structure validation."""

    def test_validates_backend_directory_structure(self, tmp_path):
        """Verify validation checks for backend directory."""
        workspace = tmp_path / "backend_project"
        workspace.mkdir()
        # Missing backend directory

        (workspace / "requirements.txt").write_text("Flask==2.0.1")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "backend"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("backend/" in error for error in result.errors)

    def test_validates_fullstack_directory_structure(self, tmp_path):
        """Verify validation checks for frontend and backend directories."""
        workspace = tmp_path / "fullstack_project"
        workspace.mkdir()
        # Missing both frontend and backend directories

        (workspace / "requirements.txt").write_text("Flask==2.0.1")
        (workspace / "README.generated.md").write_text("# Test")

        task = {"target": "fullstack"}
        gate = ValidationGate()
        result = gate.validate(task, workspace)

        assert result.ok is False
        assert any("frontend/" in error for error in result.errors)
        assert any("backend/" in error for error in result.errors)
