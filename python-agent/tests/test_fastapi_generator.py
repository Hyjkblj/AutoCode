from __future__ import annotations

import ast

from generators.fastapi_generator import FastAPIGenerator


def test_fastapi_generator_uses_managed_requirements_template() -> None:
    """Verify FastAPIGenerator uses the correct requirements template."""
    result = FastAPIGenerator().generate("build a todo backend")

    assert result.files["requirements.txt"] == "fastapi==0.115.0\nuvicorn[standard]==0.32.0\nsqlalchemy==2.0.30\naiosqlite==0.20.0\npydantic==2.9.2\n"


def test_fastapi_generator_creates_expected_backend_files() -> None:
    """Verify FastAPIGenerator creates all required files."""
    result = FastAPIGenerator().generate("build a user backend")

    assert "backend/app.py" in result.files
    assert "backend/models.py" in result.files
    assert "backend/schemas.py" in result.files
    assert "backend/database.py" in result.files
    assert "requirements.txt" in result.files
    assert "README.generated.md" in result.files


def test_fastapi_generator_marks_result_as_fastapi() -> None:
    """Verify FastAPIGenerator marks result with correct reason."""
    result = FastAPIGenerator().generate("build a backend")

    assert result.used_fallback is True
    assert result.reason == "fastapi_backend_generated"


def test_fastapi_generator_generates_valid_python_syntax() -> None:
    """Verify FastAPIGenerator generates syntactically valid Python code."""
    result = FastAPIGenerator().generate("build a user backend")

    # Verify all Python files have valid syntax
    for filename, content in result.files.items():
        if filename.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as e:
                raise AssertionError(f"Invalid Python syntax in {filename}: {e}")


def test_fastapi_generator_includes_fastapi_import() -> None:
    """Verify generated code imports FastAPI."""
    result = FastAPIGenerator().generate("build a backend")
    app_code = result.files["backend/app.py"]

    assert "from fastapi import FastAPI" in app_code


def test_fastapi_generator_creates_fastapi_application_instance() -> None:
    """Verify generated code creates FastAPI application instance."""
    result = FastAPIGenerator().generate("build a backend")
    app_code = result.files["backend/app.py"]

    assert "app = FastAPI(" in app_code


def test_fastapi_generator_includes_cors_middleware() -> None:
    """Verify generated code includes CORS middleware."""
    result = FastAPIGenerator().generate("build a backend")
    app_code = result.files["backend/app.py"]

    assert "from fastapi.middleware.cors import CORSMiddleware" in app_code
    assert "app.add_middleware" in app_code
    assert "CORSMiddleware" in app_code


def test_fastapi_generator_includes_async_database_support() -> None:
    """Verify generated code includes async database support."""
    result = FastAPIGenerator().generate("build a backend")
    database_code = result.files["backend/database.py"]

    assert "from sqlalchemy.ext.asyncio import" in database_code
    assert "AsyncSession" in database_code
    assert "create_async_engine" in database_code
    assert "async_sessionmaker" in database_code


def test_fastapi_generator_includes_pydantic_schemas() -> None:
    """Verify generated code includes Pydantic schemas."""
    result = FastAPIGenerator().generate("build a todo backend")
    schemas_code = result.files["backend/schemas.py"]

    assert "from pydantic import BaseModel" in schemas_code
    assert "TodoCreate" in schemas_code
    assert "TodoUpdate" in schemas_code
    assert "TodoResponse" in schemas_code


def test_fastapi_generator_includes_async_crud_operations() -> None:
    """Verify generated code includes async CRUD operations."""
    result = FastAPIGenerator().generate("build a todo backend")
    app_code = result.files["backend/app.py"]

    # Check for async function definitions
    assert "async def list_items" in app_code
    assert "async def create_item" in app_code
    assert "async def get_item" in app_code
    assert "async def update_item" in app_code
    assert "async def delete_item" in app_code


def test_fastapi_generator_includes_health_endpoint() -> None:
    """Verify generated code includes health check endpoint."""
    result = FastAPIGenerator().generate("build a backend")
    app_code = result.files["backend/app.py"]

    assert "@app.get" in app_code
    assert '"/health"' in app_code
    assert "async def health_check" in app_code


def test_fastapi_generator_includes_proper_error_handling() -> None:
    """Verify generated code includes proper error handling."""
    result = FastAPIGenerator().generate("build a backend")
    app_code = result.files["backend/app.py"]

    assert "HTTPException" in app_code
    assert "status.HTTP_404_NOT_FOUND" in app_code
    assert "status.HTTP_500_INTERNAL_SERVER_ERROR" in app_code


def test_fastapi_generator_includes_openapi_documentation() -> None:
    """Verify generated code includes OpenAPI documentation configuration."""
    result = FastAPIGenerator().generate("build a backend")
    app_code = result.files["backend/app.py"]

    assert 'docs_url="/docs"' in app_code
    assert 'redoc_url="/redoc"' in app_code
    assert 'openapi_url="/openapi.json"' in app_code


def test_fastapi_generator_includes_response_models() -> None:
    """Verify generated code includes response model annotations."""
    result = FastAPIGenerator().generate("build a todo backend")
    app_code = result.files["backend/app.py"]

    assert "response_model=" in app_code
    assert "TodoResponse" in app_code
    assert "TodoListResponse" in app_code


def test_fastapi_generator_includes_dependency_injection() -> None:
    """Verify generated code uses FastAPI dependency injection."""
    result = FastAPIGenerator().generate("build a backend")
    app_code = result.files["backend/app.py"]

    assert "Depends(get_db)" in app_code
    assert "db: AsyncSession = Depends(get_db)" in app_code


def test_fastapi_generator_includes_lifespan_context() -> None:
    """Verify generated code includes lifespan context manager."""
    result = FastAPIGenerator().generate("build a backend")
    app_code = result.files["backend/app.py"]

    assert "@asynccontextmanager" in app_code
    assert "async def lifespan" in app_code
    assert "await init_db()" in app_code


def test_fastapi_generator_includes_uvicorn_runner() -> None:
    """Verify generated code includes Uvicorn runner."""
    result = FastAPIGenerator().generate("build a backend")
    app_code = result.files["backend/app.py"]

    assert "import uvicorn" in app_code
    assert "uvicorn.run" in app_code


def test_fastapi_generator_todo_resource_configuration() -> None:
    """Verify FastAPIGenerator correctly configures todo resources."""
    result = FastAPIGenerator().generate("build a todo backend")
    
    models_code = result.files["backend/models.py"]
    schemas_code = result.files["backend/schemas.py"]
    app_code = result.files["backend/app.py"]

    # Check models
    assert "class Todo(Base):" in models_code
    assert '__tablename__ = "todos"' in models_code
    assert "title" in models_code
    assert "completed" in models_code

    # Check schemas
    assert "class TodoCreate" in schemas_code
    assert "class TodoUpdate" in schemas_code
    assert "class TodoResponse" in schemas_code

    # Check routes
    assert '"/api/todos"' in app_code


def test_fastapi_generator_user_resource_configuration() -> None:
    """Verify FastAPIGenerator correctly configures user resources."""
    result = FastAPIGenerator().generate("build a user backend")
    
    models_code = result.files["backend/models.py"]
    schemas_code = result.files["backend/schemas.py"]

    # Check models
    assert "class User(Base):" in models_code
    assert '__tablename__ = "users"' in models_code
    assert "name" in models_code
    assert "email" in models_code

    # Check schemas
    assert "class UserCreate" in schemas_code
    assert "class UserUpdate" in schemas_code
    assert "class UserResponse" in schemas_code


def test_fastapi_generator_post_resource_configuration() -> None:
    """Verify FastAPIGenerator correctly configures post resources."""
    result = FastAPIGenerator().generate("build a blog backend")
    
    models_code = result.files["backend/models.py"]
    schemas_code = result.files["backend/schemas.py"]

    # Check models
    assert "class Post(Base):" in models_code
    assert '__tablename__ = "posts"' in models_code
    assert "title" in models_code
    assert "content" in models_code

    # Check schemas
    assert "class PostCreate" in schemas_code
    assert "class PostUpdate" in schemas_code
    assert "class PostResponse" in schemas_code


def test_fastapi_generator_includes_partial_update_support() -> None:
    """Verify generated code supports partial updates."""
    result = FastAPIGenerator().generate("build a backend")
    app_code = result.files["backend/app.py"]

    assert "model_dump(exclude_unset=True)" in app_code


def test_fastapi_generator_includes_proper_http_status_codes() -> None:
    """Verify generated code uses proper HTTP status codes."""
    result = FastAPIGenerator().generate("build a backend")
    app_code = result.files["backend/app.py"]

    assert "status_code=status.HTTP_201_CREATED" in app_code
    assert "status.HTTP_404_NOT_FOUND" in app_code
    assert "status.HTTP_500_INTERNAL_SERVER_ERROR" in app_code


def test_fastapi_generator_includes_comprehensive_readme() -> None:
    """Verify generated README includes comprehensive documentation."""
    result = FastAPIGenerator().generate("build a todo backend")
    readme = result.files["README.generated.md"]

    assert "FastAPI" in readme
    assert "Installation" in readme
    assert "API Endpoints" in readme
    assert "Request/Response Examples" in readme
    assert "Swagger UI" in readme
    assert "/docs" in readme
    assert "Async" in readme


def test_fastapi_generator_includes_database_session_management() -> None:
    """Verify generated code includes proper database session management."""
    result = FastAPIGenerator().generate("build a backend")
    database_code = result.files["backend/database.py"]

    assert "async def get_db()" in database_code
    assert "AsyncGenerator" in database_code
    assert "await session.commit()" in database_code
    assert "await session.rollback()" in database_code
    assert "await session.close()" in database_code


def test_fastapi_generator_includes_sqlalchemy_models_with_timestamps() -> None:
    """Verify generated models include automatic timestamp management."""
    result = FastAPIGenerator().generate("build a backend")
    models_code = result.files["backend/models.py"]

    assert "created_at" in models_code
    assert "updated_at" in models_code
    assert "func.now()" in models_code
    assert "onupdate=func.now()" in models_code


def test_fastapi_generator_includes_validation_constraints() -> None:
    """Verify generated schemas include validation constraints."""
    result = FastAPIGenerator().generate("build a backend")
    schemas_code = result.files["backend/schemas.py"]

    assert "Field(...," in schemas_code
    assert "min_length=" in schemas_code
    assert "max_length=" in schemas_code
