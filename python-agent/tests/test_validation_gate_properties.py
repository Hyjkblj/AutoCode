"""
Property-based tests for validation gate completeness.

Task 11.3: Write property tests for validation completeness
Property 14: Validation Gate Completeness
Validates: Requirements 4.1, 4.2, 4.3, 4.4

These tests validate that "For any generated code, the Validation_Gate SHALL
verify syntax correctness, file presence, route definitions, and database
initialization logic."
"""

from __future__ import annotations

import shutil
import tempfile
import textwrap
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from generators.validation_gate import ValidationGate


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for valid Python app.py code snippets (Flask with routes + DB)
valid_python_strategy = st.sampled_from([
    textwrap.dedent("""\
        from __future__ import annotations
        from flask import Flask
        from flask_cors import CORS
        from database import db
        app = Flask(__name__)
        CORS(app)
        db.init_app(app)
        @app.get("/api/items")
        def list_items():
            return {"items": []}
        @app.post("/api/items")
        def create_item():
            return {}, 201
        @app.get("/api/items/<int:item_id>")
        def get_item(item_id):
            return {}
        @app.put("/api/items/<int:item_id>")
        def update_item(item_id):
            return {}
        @app.delete("/api/items/<int:item_id>")
        def delete_item(item_id):
            return {}, 204
        import sqlite3
        if __name__ == "__main__":
            app.run(debug=True)
    """),
    textwrap.dedent("""\
        from __future__ import annotations
        from flask import Flask
        from flask_cors import CORS
        from database import db
        app = Flask(__name__)
        CORS(app)
        db.init_app(app)
        @app.route("/api/records", methods=["GET"])
        def list_items():
            return {"records": []}
        @app.route("/api/records", methods=["POST"])
        def create_item():
            return {}, 201
        @app.route("/api/records/<int:record_id>", methods=["GET"])
        def get_item(record_id):
            return {}
        @app.route("/api/records/<int:record_id>", methods=["PUT"])
        def update_item(record_id):
            return {}
        @app.route("/api/records/<int:record_id>", methods=["DELETE"])
        def delete_item(record_id):
            return {}, 204
        import sqlite3
        if __name__ == "__main__":
            app.run()
    """),
    textwrap.dedent("""\
        from __future__ import annotations
        from flask import Flask
        from flask_cors import CORS
        from database import db
        import sqlite3
        app = Flask(__name__)
        CORS(app)
        db.init_app(app)
        @app.get("/api/todos")
        def list_items():
            return {"todos": []}
        @app.post("/api/todos")
        def create_item():
            return {}, 201
        @app.get("/api/todos/<int:todo_id>")
        def get_item(todo_id):
            return {}
        @app.put("/api/todos/<int:todo_id>")
        def update_item(todo_id):
            return {}
        @app.delete("/api/todos/<int:todo_id>")
        def delete_item(todo_id):
            return {}, 204
        if __name__ == "__main__":
            app.run(debug=True)
    """),
])

# Strategy for syntactically invalid Python code
invalid_python_strategy = st.sampled_from([
    "def foo(\n    pass",          # unclosed paren
    "class Foo\n    pass",         # missing colon
    "x = (1 + 2",                  # unclosed paren
    "if True\n    pass",           # missing colon
    "def bar():\n  return (",      # unclosed paren
])

# Strategy for valid models.py content
valid_models_strategy = st.sampled_from([
    textwrap.dedent("""\
        from __future__ import annotations
        from database import db
        class Item(db.Model):
            __tablename__ = "items"
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(200), nullable=False)
            def to_dict(self):
                return {"id": self.id, "name": self.name}
    """),
    textwrap.dedent("""\
        from __future__ import annotations
        from database import db
        class Record(db.Model):
            __tablename__ = "records"
            id = db.Column(db.Integer, primary_key=True)
            title = db.Column(db.String(500))
            def to_dict(self):
                return {"id": self.id, "title": self.title}
    """),
])

# Strategy for valid requirements.txt content
valid_requirements_strategy = st.sampled_from([
    "flask==3.0.0\nflask-cors==4.0.0\nflask-sqlalchemy==3.1.1\nsqlalchemy==2.0.23\n",
    "flask==2.3.3\nflask-cors==4.0.0\nflask-sqlalchemy==3.0.5\nsqlalchemy==2.0.20\n",
    "fastapi==0.104.1\nflask==3.0.0\nflask-cors==4.0.0\n",
])


# ---------------------------------------------------------------------------
# Helper: build a minimal valid backend workspace
# ---------------------------------------------------------------------------

def _build_backend_workspace(
    workspace: Path,
    *,
    app_py: str | None = None,
    models_py: str | None = None,
    requirements_txt: str | None = None,
    include_readme: bool = True,
) -> Path:
    """Create a minimal backend workspace under *workspace*."""
    backend_dir = workspace / "backend"
    backend_dir.mkdir(parents=True, exist_ok=True)

    default_app = textwrap.dedent("""\
        from __future__ import annotations
        from flask import Flask
        from flask_cors import CORS
        from database import db
        app = Flask(__name__)
        CORS(app)
        db.init_app(app)
        @app.get("/api/items")
        def list_items():
            return {"items": []}
        @app.post("/api/items")
        def create_item():
            return {}, 201
        @app.get("/api/items/<int:item_id>")
        def get_item(item_id):
            return {}
        @app.put("/api/items/<int:item_id>")
        def update_item(item_id):
            return {}
        @app.delete("/api/items/<int:item_id>")
        def delete_item(item_id):
            return {}, 204
        import sqlite3
        if __name__ == "__main__":
            app.run(debug=True)
    """)

    default_models = textwrap.dedent("""\
        from __future__ import annotations
        from database import db
        class Item(db.Model):
            __tablename__ = "items"
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(200), nullable=False)
            def to_dict(self):
                return {"id": self.id, "name": self.name}
    """)

    default_requirements = "flask==3.0.0\nflask-cors==4.0.0\nflask-sqlalchemy==3.1.1\nsqlalchemy==2.0.23\n"

    (backend_dir / "app.py").write_text(app_py if app_py is not None else default_app, encoding="utf-8")
    (backend_dir / "models.py").write_text(models_py if models_py is not None else default_models, encoding="utf-8")
    (workspace / "requirements.txt").write_text(
        requirements_txt if requirements_txt is not None else default_requirements,
        encoding="utf-8",
    )
    if include_readme:
        (workspace / "README.generated.md").write_text("# Generated Backend\n", encoding="utf-8")

    return workspace


# ---------------------------------------------------------------------------
# Property 14: Validation Gate Completeness
# ---------------------------------------------------------------------------

class TestValidationGateCompletenessProperty:
    """
    Property-based tests for Validation Gate Completeness.

    **Task 11.3: Write property tests for validation completeness**
    **Property 14: Validation Gate Completeness**
    **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

    For any generated code, the Validation_Gate SHALL verify:
    - Syntax correctness for all generated files (Req 4.1)
    - Presence of required files (Req 4.2)
    - That API routes are properly defined (Req 4.3)
    - That database initialization logic exists (Req 4.4)
    """

    # ------------------------------------------------------------------
    # Requirement 4.1 – Syntax correctness
    # ------------------------------------------------------------------

    @given(valid_python_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_14_valid_python_syntax_passes(self, app_code):
        """
        **Property 14: Validation Gate Completeness – Syntax Correctness (pass)**

        For any generated backend code with valid Python syntax, the
        Validation_Gate SHALL NOT report syntax errors.

        **Validates: Requirements 4.1**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            workspace = _build_backend_workspace(tmp, app_py=app_code)
            gate = ValidationGate()
            result = gate.validate({"target": "backend"}, workspace)

            syntax_errors = [e for e in result.errors if "syntax error" in e.lower() or "parsing error" in e.lower()]
            assert syntax_errors == [], (
                f"Unexpected syntax errors for valid Python code: {syntax_errors}"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @given(invalid_python_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_14_invalid_python_syntax_detected(self, bad_code):
        """
        **Property 14: Validation Gate Completeness – Syntax Correctness (fail)**

        For any generated backend code with invalid Python syntax, the
        Validation_Gate SHALL report at least one syntax error.

        **Validates: Requirements 4.1**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            workspace = _build_backend_workspace(tmp, app_py=bad_code)
            gate = ValidationGate()
            result = gate.validate({"target": "backend"}, workspace)

            assert not result.ok, "Validation should fail for syntactically invalid Python"
            syntax_errors = [
                e for e in result.errors
                if "syntax error" in e.lower() or "parsing error" in e.lower()
            ]
            assert syntax_errors, (
                f"Validation_Gate did not detect syntax error in: {bad_code!r}\n"
                f"All errors: {result.errors}"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Requirement 4.2 – Required file presence
    # ------------------------------------------------------------------

    @given(st.sampled_from(["backend/app.py", "backend/models.py", "requirements.txt", "README.generated.md"]))
    @settings(deadline=None, max_examples=20)
    def test_property_14_missing_required_file_detected(self, missing_file):
        """
        **Property 14: Validation Gate Completeness – Required File Presence**

        For any generated backend workspace missing a required file, the
        Validation_Gate SHALL report a missing-file error.

        **Validates: Requirements 4.2**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            workspace = _build_backend_workspace(tmp)

            # Remove the target file
            target = workspace / missing_file
            if target.exists():
                target.unlink()

            gate = ValidationGate()
            result = gate.validate({"target": "backend"}, workspace)

            assert not result.ok, f"Validation should fail when '{missing_file}' is absent"
            missing_errors = [e for e in result.errors if "missing required file" in e.lower()]
            assert missing_errors, (
                f"Validation_Gate did not report missing file '{missing_file}'\n"
                f"All errors: {result.errors}"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @given(valid_python_strategy, valid_models_strategy, valid_requirements_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_14_all_required_files_present_passes(
        self, app_code, models_code, requirements
    ):
        """
        **Property 14: Validation Gate Completeness – All Required Files Present**

        For any generated backend workspace that contains all required files,
        the Validation_Gate SHALL NOT report missing-file errors.

        **Validates: Requirements 4.2**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            workspace = _build_backend_workspace(
                tmp,
                app_py=app_code,
                models_py=models_code,
                requirements_txt=requirements,
            )
            gate = ValidationGate()
            result = gate.validate({"target": "backend"}, workspace)

            missing_errors = [e for e in result.errors if "missing required file" in e.lower()]
            assert missing_errors == [], (
                f"Unexpected missing-file errors: {missing_errors}"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Requirement 4.3 – API route definitions
    # ------------------------------------------------------------------

    @given(valid_python_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_14_api_routes_present_passes(self, app_code):
        """
        **Property 14: Validation Gate Completeness – API Routes Defined (pass)**

        For any generated backend code that contains proper route definitions,
        the Validation_Gate SHALL NOT report missing-route errors.

        **Validates: Requirements 4.3**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            workspace = _build_backend_workspace(tmp, app_py=app_code)
            gate = ValidationGate()
            result = gate.validate({"target": "backend"}, workspace)

            route_errors = [e for e in result.errors if "missing api route" in e.lower()]
            assert route_errors == [], (
                f"Unexpected route errors for code with routes: {route_errors}"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_property_14_missing_api_routes_detected(self):
        """
        **Property 14: Validation Gate Completeness – API Routes Defined (fail)**

        For any generated backend code that lacks route definitions, the
        Validation_Gate SHALL report a missing-route error.

        **Validates: Requirements 4.3**
        """
        no_routes_app = textwrap.dedent("""\
            from __future__ import annotations
            from flask import Flask
            from flask_cors import CORS
            from database import db
            import sqlite3
            app = Flask(__name__)
            CORS(app)
            db.init_app(app)
            if __name__ == "__main__":
                app.run(debug=True)
        """)
        tmp = Path(tempfile.mkdtemp())
        try:
            workspace = _build_backend_workspace(tmp, app_py=no_routes_app)
            gate = ValidationGate()
            result = gate.validate({"target": "backend"}, workspace)

            assert not result.ok, "Validation should fail when no API routes are defined"
            route_errors = [e for e in result.errors if "missing api route" in e.lower()]
            assert route_errors, (
                f"Validation_Gate did not detect missing API routes\n"
                f"All errors: {result.errors}"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Requirement 4.4 – Database initialization logic
    # ------------------------------------------------------------------

    @given(valid_python_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_14_database_init_present_passes(self, app_code):
        """
        **Property 14: Validation Gate Completeness – Database Init Present (pass)**

        For any generated backend code that contains database initialization
        logic, the Validation_Gate SHALL NOT report missing-database errors.

        **Validates: Requirements 4.4**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            workspace = _build_backend_workspace(tmp, app_py=app_code)
            gate = ValidationGate()
            result = gate.validate({"target": "backend"}, workspace)

            db_errors = [e for e in result.errors if "missing database" in e.lower()]
            assert db_errors == [], (
                f"Unexpected database errors for code with DB init: {db_errors}"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_property_14_missing_database_init_detected(self):
        """
        **Property 14: Validation Gate Completeness – Database Init Present (fail)**

        For any generated backend code that lacks database initialization
        logic, the Validation_Gate SHALL report a missing-database error.

        **Validates: Requirements 4.4**
        """
        no_db_app = textwrap.dedent("""\
            from __future__ import annotations
            from flask import Flask
            from flask_cors import CORS
            app = Flask(__name__)
            CORS(app)
            @app.get("/api/items")
            def list_items():
                return {"items": []}
            @app.post("/api/items")
            def create_item():
                return {}, 201
            @app.get("/api/items/<int:item_id>")
            def get_item(item_id):
                return {}
            @app.put("/api/items/<int:item_id>")
            def update_item(item_id):
                return {}
            @app.delete("/api/items/<int:item_id>")
            def delete_item(item_id):
                return {}, 204
            if __name__ == "__main__":
                app.run(debug=True)
        """)
        tmp = Path(tempfile.mkdtemp())
        try:
            workspace = _build_backend_workspace(tmp, app_py=no_db_app)
            gate = ValidationGate()
            result = gate.validate({"target": "backend"}, workspace)

            assert not result.ok, "Validation should fail when database init is absent"
            db_errors = [e for e in result.errors if "missing database" in e.lower()]
            assert db_errors, (
                f"Validation_Gate did not detect missing database initialization\n"
                f"All errors: {result.errors}"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Combined: all four checks together
    # ------------------------------------------------------------------

    @given(valid_python_strategy, valid_models_strategy, valid_requirements_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_14_complete_valid_workspace_passes(
        self, app_code, models_code, requirements
    ):
        """
        **Property 14: Validation Gate Completeness – Full Valid Workspace**

        For any complete, valid backend workspace, the Validation_Gate SHALL
        report no errors (syntax, file presence, routes, and DB init all pass).

        **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            workspace = _build_backend_workspace(
                tmp,
                app_py=app_code,
                models_py=models_code,
                requirements_txt=requirements,
            )
            gate = ValidationGate()
            result = gate.validate({"target": "backend"}, workspace)

            assert result.ok, (
                f"Validation should pass for a complete valid workspace.\n"
                f"Errors: {result.errors}"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_property_14_validate_returns_structured_result(self):
        """
        **Property 14: Validation Gate Completeness – Structured Result**

        The Validation_Gate SHALL always return a ValidationResult with
        boolean ok and a list of error strings.

        **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            workspace = _build_backend_workspace(tmp)
            gate = ValidationGate()
            result = gate.validate({"target": "backend"}, workspace)

            assert isinstance(result.ok, bool)
            assert isinstance(result.errors, list)
            for err in result.errors:
                assert isinstance(err, str), f"Error entry is not a string: {err!r}"
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_property_14_empty_target_always_passes(self):
        """
        **Property 14: Validation Gate Completeness – Empty Target**

        When no target is specified, the Validation_Gate SHALL return ok=True
        (nothing to validate).

        **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            gate = ValidationGate()
            result = gate.validate({}, tmp)
            assert result.ok
            assert result.errors == []
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
