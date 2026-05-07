"""
Comprehensive unit tests for BackendGenerator.

**Validates: Requirements 6.4**

Tests cover:
- Flask/FastAPI code generation
- SQLite database integration
- CRUD route generation
- Requirements.txt generation
- Resource type detection from prompts
- Generated code structure and completeness
"""
from __future__ import annotations

import pytest

from generators.backend_generator import BackendGenerator


class TestBackendGeneratorBasicGeneration:
    """Test BackendGenerator basic code generation."""

    def test_backend_generator_generates_all_required_files(self):
        """Verify BackendGenerator generates all required files."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        assert "backend/app.py" in result.files
        assert "backend/models.py" in result.files
        assert "requirements.txt" in result.files
        assert "README.generated.md" in result.files

    def test_backend_generator_marks_result_as_fallback(self):
        """Verify BackendGenerator marks result as using fallback template."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        assert result.used_fallback is True
        assert result.reason == "backend_template_generated"

    def test_backend_generator_generates_valid_python_syntax(self):
        """Verify BackendGenerator generates syntactically valid Python code."""
        generator = BackendGenerator()

        result = generator.generate("build a user backend")

        app_code = result.files["backend/app.py"]

        # Should compile without syntax errors
        compile(app_code, "app.py", "exec")


class TestBackendGeneratorFlaskIntegration:
    """Test BackendGenerator Flask application generation."""

    def test_backend_generator_includes_flask_import(self):
        """Verify generated code imports Flask."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert "from flask import Flask" in app_code

    def test_backend_generator_creates_flask_application_instance(self):
        """Verify generated code creates Flask application instance."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert "app = Flask(__name__)" in app_code

    def test_backend_generator_includes_flask_cors(self):
        """Verify generated code includes CORS support."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert "from flask_cors import CORS" in app_code
        assert "CORS(app)" in app_code

    def test_backend_generator_includes_main_block(self):
        """Verify generated code includes main execution block."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert 'if __name__ == "__main__":' in app_code
        assert "app.run(" in app_code


class TestBackendGeneratorDatabaseIntegration:
    """Test BackendGenerator database integration (sqlite3-based)."""

    def test_backend_generator_includes_sqlite3_import(self):
        """Verify generated app.py imports sqlite3."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert "import sqlite3" in app_code

    def test_backend_generator_includes_database_init_function(self):
        """Verify generated app.py includes init_db function."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert "def init_db()" in app_code
        assert "CREATE TABLE IF NOT EXISTS" in app_code

    def test_backend_generator_includes_get_connection(self):
        """Verify generated app.py includes get_connection helper."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert "def get_connection()" in app_code
        assert "sqlite3.connect" in app_code

    def test_backend_generator_calls_init_db_in_main(self):
        """Verify generated app.py calls init_db in __main__ block."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert "init_db()" in app_code


class TestBackendGeneratorCRUDRoutes:
    """Test BackendGenerator CRUD route generation."""

    def test_backend_generator_includes_health_endpoint(self):
        """Verify generated code includes health check endpoint."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert '@app.get("/health")' in app_code
        assert "def health()" in app_code

    def test_backend_generator_includes_list_endpoint(self):
        """Verify generated code includes list endpoint."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        app_code = result.files["backend/app.py"]
        assert '@app.get("/api/todos")' in app_code
        assert "def list_items()" in app_code

    def test_backend_generator_includes_create_endpoint(self):
        """Verify generated code includes create endpoint."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        app_code = result.files["backend/app.py"]
        assert '@app.post("/api/todos")' in app_code
        assert "def create_item()" in app_code

    def test_backend_generator_includes_update_endpoint(self):
        """Verify generated code includes update endpoint."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        app_code = result.files["backend/app.py"]
        assert '@app.put("/api/todos/<int:item_id>")' in app_code
        assert "def update_item(item_id: int)" in app_code

    def test_backend_generator_includes_delete_endpoint(self):
        """Verify generated code includes delete endpoint."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        app_code = result.files["backend/app.py"]
        assert '@app.delete("/api/todos/<int:item_id>")' in app_code
        assert "def delete_item(item_id: int)" in app_code

    def test_backend_generator_includes_error_handling(self):
        """Verify generated code includes proper error handling."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert "return {" in app_code  # JSON responses
        assert ", 400" in app_code or ", 404" in app_code  # HTTP status codes


class TestBackendGeneratorResourceDetection:
    """Test BackendGenerator resource type detection from prompts."""

    def test_backend_generator_detects_todo_resource(self):
        """Verify generator detects todo resource from prompt."""
        generator = BackendGenerator()

        result = generator.generate("build a todo app backend")

        models_code = result.files["backend/models.py"]
        assert 'TABLE_NAME = "todos"' in models_code
        assert 'RESOURCE_NAME = "todo"' in models_code

    def test_backend_generator_detects_blog_resource(self):
        """Verify generator detects blog/post resource from prompt."""
        generator = BackendGenerator()

        result = generator.generate("build a blog backend")

        models_code = result.files["backend/models.py"]
        assert 'TABLE_NAME = "posts"' in models_code
        assert 'RESOURCE_NAME = "post"' in models_code

    def test_backend_generator_detects_user_resource(self):
        """Verify generator detects user resource from prompt."""
        generator = BackendGenerator()

        result = generator.generate("build a user management backend")

        models_code = result.files["backend/models.py"]
        assert 'TABLE_NAME = "users"' in models_code
        assert 'RESOURCE_NAME = "user"' in models_code

    def test_backend_generator_defaults_to_generic_resource(self):
        """Verify generator defaults to generic resource for unknown prompts."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        models_code = result.files["backend/models.py"]
        assert 'TABLE_NAME = "records"' in models_code
        assert 'RESOURCE_NAME = "record"' in models_code

    def test_backend_generator_handles_chinese_prompts(self):
        """Verify generator handles Chinese language prompts."""
        generator = BackendGenerator()

        result = generator.generate("构建一个待办事项后端")

        models_code = result.files["backend/models.py"]
        assert 'TABLE_NAME = "todos"' in models_code


class TestBackendGeneratorModelsFile:
    """Test BackendGenerator models.py generation."""

    def test_backend_generator_includes_table_name_constant(self):
        """Verify models.py includes TABLE_NAME constant."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        models_code = result.files["backend/models.py"]
        assert "TABLE_NAME = " in models_code

    def test_backend_generator_includes_resource_name_constant(self):
        """Verify models.py includes RESOURCE_NAME constant."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        models_code = result.files["backend/models.py"]
        assert "RESOURCE_NAME = " in models_code

    def test_backend_generator_includes_resource_label_constant(self):
        """Verify models.py includes RESOURCE_LABEL constant."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        models_code = result.files["backend/models.py"]
        assert "RESOURCE_LABEL = " in models_code

    def test_backend_generator_includes_field_constants(self):
        """Verify models.py includes field name constants."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        models_code = result.files["backend/models.py"]
        assert "PRIMARY_FIELD = " in models_code
        assert "SECONDARY_FIELD = " in models_code


class TestBackendGeneratorRequirementsTxt:
    """Test BackendGenerator requirements.txt generation."""

    def test_backend_generator_includes_flask_dependency(self):
        """Verify requirements.txt includes Flask."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        requirements = result.files["requirements.txt"]
        assert "flask==" in requirements

    def test_backend_generator_includes_flask_cors_dependency(self):
        """Verify requirements.txt includes flask-cors."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        requirements = result.files["requirements.txt"]
        assert "flask-cors==" in requirements

    def test_backend_generator_pins_dependency_versions(self):
        """Verify requirements.txt pins specific versions."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        requirements = result.files["requirements.txt"]
        assert "flask==3.0.3" in requirements
        assert "flask-cors==4.0.1" in requirements

    def test_backend_generator_requirements_ends_with_newline(self):
        """Verify requirements.txt ends with newline."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        requirements = result.files["requirements.txt"]
        assert requirements.endswith("\n")


class TestBackendGeneratorReadme:
    """Test BackendGenerator README.generated.md generation."""

    def test_backend_generator_includes_readme(self):
        """Verify generator creates README.generated.md."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        assert "README.generated.md" in result.files

    def test_backend_generator_readme_includes_prompt(self):
        """Verify README includes the original prompt."""
        generator = BackendGenerator()
        prompt = "build a todo backend with SQLite"

        result = generator.generate(prompt)

        readme = result.files["README.generated.md"]
        assert prompt in readme

    def test_backend_generator_readme_includes_stack_info(self):
        """Verify README includes technology stack information."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        readme = result.files["README.generated.md"]
        assert "Flask" in readme
        assert "SQLite" in readme

    def test_backend_generator_readme_includes_run_instructions(self):
        """Verify README includes run instructions."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        readme = result.files["README.generated.md"]
        assert "pip install" in readme
        assert "python backend/app.py" in readme

    def test_backend_generator_readme_includes_endpoints(self):
        """Verify README includes API endpoint documentation."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        readme = result.files["README.generated.md"]
        assert "/api/todos" in readme
        assert "GET" in readme
        assert "POST" in readme


class TestBackendGeneratorDataTypes:
    """Test BackendGenerator data type handling for different resources."""

    def test_backend_generator_todo_secondary_type_is_integer(self):
        """Verify generator uses INTEGER type for todo completed field."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        app_code = result.files["backend/app.py"]
        # Todo resources should have completed field as INTEGER in SQL
        assert "INTEGER DEFAULT 0" in app_code

    def test_backend_generator_blog_secondary_type_is_text(self):
        """Verify generator uses TEXT type for blog content field."""
        generator = BackendGenerator()

        result = generator.generate("build a blog backend")

        app_code = result.files["backend/app.py"]
        # Blog resources should have content field as TEXT in SQL
        assert "TEXT DEFAULT ''" in app_code

    def test_backend_generator_user_secondary_type_is_text(self):
        """Verify generator uses TEXT type for user email field."""
        generator = BackendGenerator()

        result = generator.generate("build a user backend")

        app_code = result.files["backend/app.py"]
        # User resources should have email field as TEXT in SQL
        assert "TEXT DEFAULT ''" in app_code


class TestBackendGeneratorEdgeCases:
    """Test BackendGenerator edge cases and boundary conditions."""

    def test_backend_generator_handles_empty_prompt(self):
        """Verify generator handles empty prompt gracefully."""
        generator = BackendGenerator()

        result = generator.generate("")

        assert "backend/app.py" in result.files
        assert "backend/models.py" in result.files

    def test_backend_generator_handles_whitespace_only_prompt(self):
        """Verify generator handles whitespace-only prompt."""
        generator = BackendGenerator()

        result = generator.generate("   \n\t  ")

        assert "backend/app.py" in result.files
        # Should default to generic resource
        models_code = result.files["backend/models.py"]
        assert 'TABLE_NAME = "records"' in models_code

    def test_backend_generator_handles_very_long_prompt(self):
        """Verify generator handles very long prompts."""
        generator = BackendGenerator()
        long_prompt = "build a " + "very " * 100 + "complex todo backend system"

        result = generator.generate(long_prompt)

        assert "backend/app.py" in result.files
        # Should still detect todo resource
        models_code = result.files["backend/models.py"]
        assert 'TABLE_NAME = "todos"' in models_code

    def test_backend_generator_handles_mixed_case_keywords(self):
        """Verify generator handles mixed case keywords in prompts."""
        generator = BackendGenerator()

        result = generator.generate("Build a TODO Backend")

        models_code = result.files["backend/models.py"]
        assert 'TABLE_NAME = "todos"' in models_code

    def test_backend_generator_handles_multiple_resource_keywords(self):
        """Verify generator handles prompts with multiple resource keywords."""
        generator = BackendGenerator()

        # First matching keyword should win
        result = generator.generate("build a todo and blog backend")

        models_code = result.files["backend/models.py"]
        # Should match todo first
        assert 'TABLE_NAME = "todos"' in models_code


class TestBackendGeneratorCodeQuality:
    """Test BackendGenerator code quality and best practices."""

    def test_backend_generator_includes_type_hints(self):
        """Verify generated code includes type hints."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert "-> " in app_code  # Return type hints

    def test_backend_generator_includes_docstrings_or_comments(self):
        """Verify generated code is well-documented."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        # Should have some form of documentation
        assert "#" in app_code or '"""' in app_code or "'''" in app_code

    def test_backend_generator_uses_consistent_naming(self):
        """Verify generated code uses consistent naming conventions."""
        generator = BackendGenerator()

        result = generator.generate("build a todo backend")

        app_code = result.files["backend/app.py"]
        # Function names should be snake_case
        assert "def list_items()" in app_code
        assert "def create_item()" in app_code
        assert "def update_item(" in app_code
        assert "def delete_item(" in app_code

    def test_backend_generator_includes_proper_imports(self):
        """Verify generated code includes all necessary imports."""
        generator = BackendGenerator()

        result = generator.generate("build a backend")

        app_code = result.files["backend/app.py"]
        assert "from __future__ import annotations" in app_code
        assert "from flask import Flask, jsonify, request" in app_code
        assert "from models import" in app_code
