"""
Integration tests for FastAPI generator to verify generated code quality.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**
"""
from __future__ import annotations

import ast
import tempfile
from pathlib import Path

import pytest

from generators.fastapi_generator import FastAPIGenerator


class TestFastAPIGeneratorIntegration:
    """Integration tests for FastAPI generator."""

    def test_generated_code_has_valid_syntax(self):
        """Verify all generated Python files have valid syntax."""
        generator = FastAPIGenerator()
        result = generator.generate("build a todo backend")

        for filename, content in result.files.items():
            if filename.endswith(".py"):
                try:
                    ast.parse(content)
                except SyntaxError as e:
                    pytest.fail(f"Invalid syntax in {filename}: {e}")

    def test_generated_code_can_be_written_to_filesystem(self):
        """Verify generated code can be written to filesystem."""
        generator = FastAPIGenerator()
        result = generator.generate("build a todo backend")

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            
            for filename, content in result.files.items():
                file_path = base_path / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                
                assert file_path.exists()
                assert file_path.read_text(encoding="utf-8") == content

    def test_generated_models_have_proper_structure(self):
        """Verify generated models have proper SQLAlchemy structure."""
        generator = FastAPIGenerator()
        result = generator.generate("build a user backend")
        
        models_code = result.files["backend/models.py"]
        
        # Check for essential SQLAlchemy components
        assert "from sqlalchemy import" in models_code
        assert "from database import Base" in models_code
        assert "class User(Base):" in models_code
        assert "__tablename__" in models_code
        assert "Column" in models_code
        assert "primary_key=True" in models_code

    def test_generated_schemas_have_proper_pydantic_structure(self):
        """Verify generated schemas have proper Pydantic structure."""
        generator = FastAPIGenerator()
        result = generator.generate("build a user backend")
        
        schemas_code = result.files["backend/schemas.py"]
        
        # Check for essential Pydantic components
        assert "from pydantic import BaseModel" in schemas_code
        assert "class UserCreate(BaseModel):" in schemas_code
        assert "class UserUpdate(BaseModel):" in schemas_code
        assert "class UserResponse(BaseModel):" in schemas_code
        assert "Field(" in schemas_code

    def test_generated_app_has_proper_fastapi_structure(self):
        """Verify generated app has proper FastAPI structure."""
        generator = FastAPIGenerator()
        result = generator.generate("build a todo backend")
        
        app_code = result.files["backend/app.py"]
        
        # Check for essential FastAPI components
        assert "from fastapi import FastAPI" in app_code
        assert "app = FastAPI(" in app_code
        assert "@app.get" in app_code
        assert "@app.post" in app_code
        assert "@app.put" in app_code
        assert "@app.delete" in app_code

    def test_generated_database_has_proper_async_structure(self):
        """Verify generated database module has proper async structure."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        database_code = result.files["backend/database.py"]
        
        # Check for essential async SQLAlchemy components
        assert "from sqlalchemy.ext.asyncio import" in database_code
        assert "AsyncSession" in database_code
        assert "create_async_engine" in database_code
        assert "async def init_db()" in database_code
        assert "async def get_db()" in database_code

    def test_generated_readme_has_comprehensive_documentation(self):
        """Verify generated README has comprehensive documentation."""
        generator = FastAPIGenerator()
        result = generator.generate("build a todo backend")
        
        readme = result.files["README.generated.md"]
        
        # Check for essential documentation sections
        assert "# Generated FastAPI Backend" in readme
        assert "## Stack" in readme
        assert "## Features" in readme
        assert "## Installation" in readme
        assert "## Running the Application" in readme
        assert "## API Endpoints" in readme
        assert "## Request/Response Examples" in readme
        assert "## Error Handling" in readme
        assert "## Automatic Validation" in readme

    def test_generated_requirements_have_all_dependencies(self):
        """Verify generated requirements.txt has all necessary dependencies."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        requirements = result.files["requirements.txt"]
        
        # Check for essential dependencies
        assert "fastapi==" in requirements
        assert "uvicorn" in requirements
        assert "sqlalchemy==" in requirements
        assert "aiosqlite==" in requirements
        assert "pydantic==" in requirements

    def test_generated_code_follows_async_patterns(self):
        """Verify generated code follows async/await patterns."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        app_code = result.files["backend/app.py"]
        
        # Check for async patterns
        assert "async def" in app_code
        assert "await db.execute" in app_code
        assert "await db.commit" in app_code
        assert "await db.rollback" in app_code

    def test_generated_code_includes_proper_error_responses(self):
        """Verify generated code includes proper error response handling."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        app_code = result.files["backend/app.py"]
        schemas_code = result.files["backend/schemas.py"]
        
        # Check for error handling
        assert "HTTPException" in app_code
        assert "status.HTTP_404_NOT_FOUND" in app_code
        assert "status.HTTP_500_INTERNAL_SERVER_ERROR" in app_code
        assert "class ErrorResponse(BaseModel):" in schemas_code

    def test_generated_code_includes_openapi_configuration(self):
        """Verify generated code includes OpenAPI documentation configuration."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        app_code = result.files["backend/app.py"]
        
        # Check for OpenAPI configuration
        assert "title=" in app_code
        assert "description=" in app_code
        assert "version=" in app_code
        assert 'docs_url="/docs"' in app_code
        assert 'redoc_url="/redoc"' in app_code

    def test_generated_code_includes_cors_configuration(self):
        """Verify generated code includes CORS configuration."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        app_code = result.files["backend/app.py"]
        
        # Check for CORS configuration
        assert "from fastapi.middleware.cors import CORSMiddleware" in app_code
        assert "app.add_middleware" in app_code
        assert "CORSMiddleware" in app_code
        assert "allow_origins" in app_code

    def test_generated_code_includes_database_initialization(self):
        """Verify generated code includes database initialization."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        app_code = result.files["backend/app.py"]
        database_code = result.files["backend/database.py"]
        
        # Check for database initialization
        assert "await init_db()" in app_code
        assert "async def init_db()" in database_code
        assert "Base.metadata.create_all" in database_code

    def test_generated_code_supports_multiple_resource_types(self):
        """Verify generator supports different resource types."""
        generator = FastAPIGenerator()
        
        # Test todo resource
        todo_result = generator.generate("build a todo backend")
        assert "class Todo(Base):" in todo_result.files["backend/models.py"]
        assert "completed" in todo_result.files["backend/models.py"]
        
        # Test user resource
        user_result = generator.generate("build a user backend")
        assert "class User(Base):" in user_result.files["backend/models.py"]
        assert "email" in user_result.files["backend/models.py"]
        
        # Test post resource
        post_result = generator.generate("build a blog backend")
        assert "class Post(Base):" in post_result.files["backend/models.py"]
        assert "content" in post_result.files["backend/models.py"]

    def test_generated_code_includes_validation_constraints(self):
        """Verify generated schemas include validation constraints."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        schemas_code = result.files["backend/schemas.py"]
        
        # Check for validation constraints
        assert "Field(...," in schemas_code
        assert "min_length=" in schemas_code
        assert "max_length=" in schemas_code
        assert "description=" in schemas_code

    def test_generated_code_includes_response_model_configuration(self):
        """Verify generated code includes response model configuration."""
        generator = FastAPIGenerator()
        result = generator.generate("build a todo backend")
        
        app_code = result.files["backend/app.py"]
        
        # Check for response model configuration
        assert "response_model=" in app_code
        assert "TodoResponse" in app_code
        assert "TodoListResponse" in app_code
        assert "SuccessResponse" in app_code

    def test_generated_code_includes_proper_http_methods(self):
        """Verify generated code includes all CRUD HTTP methods."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        app_code = result.files["backend/app.py"]
        
        # Check for HTTP methods
        assert "@app.get(" in app_code
        assert "@app.post(" in app_code
        assert "@app.put(" in app_code
        assert "@app.delete(" in app_code

    def test_generated_code_includes_dependency_injection(self):
        """Verify generated code uses FastAPI dependency injection."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        app_code = result.files["backend/app.py"]
        
        # Check for dependency injection
        assert "Depends(get_db)" in app_code
        assert "db: AsyncSession = Depends(get_db)" in app_code

    def test_generated_code_includes_lifespan_management(self):
        """Verify generated code includes lifespan management."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        app_code = result.files["backend/app.py"]
        
        # Check for lifespan management
        assert "@asynccontextmanager" in app_code
        assert "async def lifespan" in app_code
        assert "lifespan=lifespan" in app_code

    def test_generated_code_includes_proper_status_codes(self):
        """Verify generated code uses proper HTTP status codes."""
        generator = FastAPIGenerator()
        result = generator.generate("build a backend")
        
        app_code = result.files["backend/app.py"]
        
        # Check for status codes
        assert "status_code=status.HTTP_201_CREATED" in app_code
        assert "status.HTTP_404_NOT_FOUND" in app_code
        assert "status.HTTP_500_INTERNAL_SERVER_ERROR" in app_code
