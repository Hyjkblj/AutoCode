from __future__ import annotations

from pathlib import Path

from generators import GeneratedProjectResult


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "requirements"
_GENERATED_FASTAPI_REQUIREMENTS = _TEMPLATE_DIR / "generated-fastapi.txt"


class FastAPIGenerator:
    def generate(self, prompt: str) -> GeneratedProjectResult:
        config = _resource_config(prompt)
        files = {
            "backend/app.py": _build_app_py(config),
            "backend/models.py": _build_models_py(config),
            "backend/schemas.py": _build_schemas_py(config),
            "backend/database.py": _build_database_py(),
            "requirements.txt": _load_generated_fastapi_requirements(),
            "README.generated.md": _build_readme(prompt, config),
        }
        return GeneratedProjectResult(files=files, used_fallback=True, reason="fastapi_backend_generated")


def _load_generated_fastapi_requirements() -> str:
    fallback = "fastapi==0.115.0\nuvicorn[standard]==0.32.0\nsqlalchemy==2.0.30\n"
    try:
        content = _GENERATED_FASTAPI_REQUIREMENTS.read_text(encoding="utf-8")
    except OSError:
        return fallback

    normalized = content.strip()
    if not normalized:
        return fallback
    return f"{normalized}\n"


def _resource_config(prompt: str) -> dict[str, str]:
    text = (prompt or "").strip().lower()
    if any(token in text for token in ("todo", "待办", "task")):
        return {
            "table_name": "todos",
            "resource_name": "todo",
            "resource_label": "Todo",
            "list_field": "title",
            "secondary_field": "completed",
            "secondary_default": "False",
            "secondary_type": "Boolean",
            "secondary_python_type": "bool",
            "secondary_pydantic_default": "False",
        }
    if any(token in text for token in ("blog", "博客", "post", "article")):
        return {
            "table_name": "posts",
            "resource_name": "post",
            "resource_label": "Post",
            "list_field": "title",
            "secondary_field": "content",
            "secondary_default": '""',
            "secondary_type": "Text",
            "secondary_python_type": "str",
            "secondary_pydantic_default": '""',
        }
    if any(token in text for token in ("user", "用户", "account", "member")):
        return {
            "table_name": "users",
            "resource_name": "user",
            "resource_label": "User",
            "list_field": "name",
            "secondary_field": "email",
            "secondary_default": '""',
            "secondary_type": "String",
            "secondary_python_type": "str",
            "secondary_pydantic_default": '""',
        }
    return {
        "table_name": "records",
        "resource_name": "record",
        "resource_label": "Record",
        "list_field": "name",
        "secondary_field": "description",
        "secondary_default": '""',
        "secondary_type": "String",
        "secondary_python_type": "str",
        "secondary_pydantic_default": '""',
    }


def _build_schemas_py(config: dict[str, str]) -> str:
    """Generate Pydantic schemas for request/response validation."""
    resource_label = config["resource_label"]
    primary_field = config["list_field"]
    secondary_field = config["secondary_field"]
    secondary_python_type = config["secondary_python_type"]
    secondary_pydantic_default = config["secondary_pydantic_default"]
    
    return f"""from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class {resource_label}Base(BaseModel):
    \"\"\"
    Base schema for {resource_label} with shared attributes.
    \"\"\"
    {primary_field}: str = Field(..., min_length=1, max_length=200, description="Primary field for the resource")
    {secondary_field}: {secondary_python_type} = Field({secondary_pydantic_default}, description="Secondary field for additional data")


class {resource_label}Create(BaseModel):
    \"\"\"
    Schema for creating a new {resource_label}.
    
    Attributes:
        {primary_field}: Primary field (required, 1-200 characters)
        {secondary_field}: Secondary field
    \"\"\"
    {primary_field}: str = Field(..., min_length=1, max_length=200)
    {secondary_field}: {secondary_python_type} = Field({secondary_pydantic_default})


class {resource_label}Update(BaseModel):
    \"\"\"
    Schema for updating an existing {resource_label}.
    
    All fields are optional to support partial updates.
    \"\"\"
    {primary_field}: str | None = Field(None, min_length=1, max_length=200)
    {secondary_field}: {secondary_python_type} | None = None


class {resource_label}Response(BaseModel):
    \"\"\"
    Schema for {resource_label} responses.
    
    Attributes:
        id: Unique identifier
        {primary_field}: Primary field
        {secondary_field}: Secondary field
        created_at: Creation timestamp
        updated_at: Last update timestamp
    \"\"\"
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    {primary_field}: str
    {secondary_field}: {secondary_python_type}
    created_at: datetime
    updated_at: datetime


class {resource_label}ListResponse(BaseModel):
    \"\"\"
    Schema for list responses containing multiple {resource_label} items.
    \"\"\"
    items: list[{resource_label}Response]
    total: int


class ErrorResponse(BaseModel):
    \"\"\"
    Standard error response schema.
    \"\"\"
    error: str
    message: str
    detail: str | None = None


class SuccessResponse(BaseModel):
    \"\"\"
    Standard success response schema.
    \"\"\"
    message: str
    item: {resource_label}Response | None = None
"""


def _build_models_py(config: dict[str, str]) -> str:
    """Generate SQLAlchemy models with proper relationships and constraints."""
    table_name = config["table_name"]
    resource_label = config["resource_label"]
    primary_field = config["list_field"]
    secondary_field = config["secondary_field"]
    secondary_type = config["secondary_type"]
    
    # Map type names to SQLAlchemy types
    if secondary_type == "Boolean":
        secondary_type_sa = "Boolean"
        secondary_default = "default=False"
    elif secondary_type == "Text":
        secondary_type_sa = "Text"
        secondary_default = 'default=""'
    else:  # String
        secondary_type_sa = "String(500)"
        secondary_default = 'default=""'
    
    return f"""from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class {resource_label}(Base):
    \"\"\"
    {resource_label} model with SQLAlchemy ORM.
    
    Attributes:
        id: Primary key, auto-incrementing integer
        {primary_field}: Primary field for the resource
        {secondary_field}: Secondary field for additional data
        created_at: Timestamp of creation (auto-managed)
        updated_at: Timestamp of last update (auto-managed)
    \"\"\"
    __tablename__ = "{table_name}"
    
    # Primary key with auto-increment
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False, index=True)
    
    # Resource fields with constraints
    {primary_field} = Column(String(200), nullable=False, index=True)
    {secondary_field} = Column({secondary_type_sa}, {secondary_default}, nullable=False)
    
    # Timestamps with automatic management
    created_at = Column(DateTime, default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self) -> str:
        \"\"\"String representation of the model.\"\"\"
        return f"<{resource_label}(id={{self.id}}, {primary_field}={{self.{primary_field}!r}})>"


# Model metadata for API generation
TABLE_NAME = "{table_name}"
RESOURCE_NAME = "{config["resource_name"]}"
RESOURCE_LABEL = "{resource_label}"
PRIMARY_FIELD = "{primary_field}"
SECONDARY_FIELD = "{secondary_field}"
"""


def _build_database_py() -> str:
    """Generate database configuration module with async SQLAlchemy setup."""
    return """from __future__ import annotations

from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base


# Create declarative base for models
Base = declarative_base()

# Database configuration
_DB_PATH = Path(__file__).resolve().parent / "database.db"
DATABASE_URL = f"sqlite+aiosqlite:///{_DB_PATH}"

# Create async engine with connection pooling
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"check_same_thread": False},
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    \"\"\"
    Initialize database by creating all tables.
    
    This should be called on application startup.
    \"\"\"
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    \"\"\"
    Dependency function to get database session.
    
    Yields:
        AsyncSession: Database session for request handling
    \"\"\"
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
"""


def _build_app_py(config: dict[str, str]) -> str:
    """Generate FastAPI application with async CRUD routes."""
    table_name = config["table_name"]
    resource_name = config["resource_name"]
    resource_label = config["resource_label"]
    primary_field = config["list_field"]
    secondary_field = config["secondary_field"]
    list_path = f"/api/{table_name}"
    detail_path = f"/api/{table_name}/{{item_id}}"

    return f"""from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from database import init_db, get_db
from models import {resource_label}, RESOURCE_LABEL, RESOURCE_NAME, PRIMARY_FIELD, SECONDARY_FIELD
from schemas import (
    {resource_label}Create,
    {resource_label}Update,
    {resource_label}Response,
    {resource_label}ListResponse,
    ErrorResponse,
    SuccessResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    \"\"\"
    Lifespan context manager for application startup and shutdown.
    \"\"\"
    # Startup: Initialize database
    await init_db()
    yield
    # Shutdown: Cleanup if needed


# Create FastAPI application with automatic OpenAPI documentation
app = FastAPI(
    title=f"{{RESOURCE_LABEL}} API",
    description=f"RESTful API for managing {{RESOURCE_NAME}} resources with automatic validation and documentation",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check endpoint",
    response_model=dict,
)
async def health_check(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    \"\"\"
    Health check endpoint to verify API and database connectivity.
    
    Returns:
        Dictionary with status, resource name, and database status
    \"\"\"
    try:
        # Test database connection
        await db.execute(select(func.count()).select_from({resource_label}))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
    
    return {{
        "status": "ok",
        "resource": RESOURCE_NAME,
        "database": db_status,
    }}


@app.get(
    "{list_path}",
    tags=[RESOURCE_LABEL],
    summary=f"List all {{RESOURCE_NAME}} items",
    response_model={resource_label}ListResponse,
    responses={{
        200: {{"description": "Successful response with list of items"}},
        500: {{"model": ErrorResponse, "description": "Database error"}},
    }},
)
async def list_items(
    db: AsyncSession = Depends(get_db),
) -> {resource_label}ListResponse:
    \"\"\"
    Retrieve all {resource_name} items ordered by ID (descending).
    
    Returns:
        List of all {resource_name} items with total count
    \"\"\"
    try:
        # Query all items ordered by ID descending
        result = await db.execute(
            select({resource_label}).order_by({resource_label}.id.desc())
        )
        items = result.scalars().all()
        
        return {resource_label}ListResponse(
            items=[{resource_label}Response.model_validate(item) for item in items],
            total=len(items),
        )
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={{
                "error": "Database error",
                "message": str(e),
            }},
        )


@app.post(
    "{list_path}",
    tags=[RESOURCE_LABEL],
    summary=f"Create a new {{RESOURCE_NAME}}",
    response_model=SuccessResponse,
    status_code=status.HTTP_201_CREATED,
    responses={{
        201: {{"description": "Item created successfully"}},
        400: {{"model": ErrorResponse, "description": "Validation error"}},
        500: {{"model": ErrorResponse, "description": "Database error"}},
    }},
)
async def create_item(
    item_data: {resource_label}Create,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    \"\"\"
    Create a new {resource_name} item.
    
    Args:
        item_data: {resource_label} creation data (validated by Pydantic)
        db: Database session (injected)
    
    Returns:
        Success response with created item details
    \"\"\"
    try:
        # Create new item from validated data
        new_item = {resource_label}(
            **item_data.model_dump()
        )
        
        db.add(new_item)
        await db.commit()
        await db.refresh(new_item)
        
        return SuccessResponse(
            message=f"{{RESOURCE_LABEL}} created successfully",
            item={resource_label}Response.model_validate(new_item),
        )
        
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={{
                "error": "Database error",
                "message": str(e),
            }},
        )


@app.get(
    "{detail_path}",
    tags=[RESOURCE_LABEL],
    summary=f"Get a specific {{RESOURCE_NAME}} by ID",
    response_model={resource_label}Response,
    responses={{
        200: {{"description": "Item found and returned"}},
        404: {{"model": ErrorResponse, "description": "Item not found"}},
        500: {{"model": ErrorResponse, "description": "Database error"}},
    }},
)
async def get_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
) -> {resource_label}Response:
    \"\"\"
    Retrieve a single {resource_name} item by ID.
    
    Args:
        item_id: ID of the item to retrieve
        db: Database session (injected)
    
    Returns:
        {resource_label} item details
    
    Raises:
        HTTPException: 404 if item not found
    \"\"\"
    try:
        result = await db.execute(
            select({resource_label}).where({resource_label}.id == item_id)
        )
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={{
                    "error": "Not found",
                    "message": f"{{RESOURCE_LABEL}} with id {{item_id}} not found",
                }},
            )
        
        return {resource_label}Response.model_validate(item)
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={{
                "error": "Database error",
                "message": str(e),
            }},
        )


@app.put(
    "{detail_path}",
    tags=[RESOURCE_LABEL],
    summary=f"Update an existing {{RESOURCE_NAME}}",
    response_model=SuccessResponse,
    responses={{
        200: {{"description": "Item updated successfully"}},
        404: {{"model": ErrorResponse, "description": "Item not found"}},
        400: {{"model": ErrorResponse, "description": "Validation error"}},
        500: {{"model": ErrorResponse, "description": "Database error"}},
    }},
)
async def update_item(
    item_id: int,
    item_data: {resource_label}Update,
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    \"\"\"
    Update an existing {resource_name} item.
    
    Supports partial updates - only provided fields will be updated.
    
    Args:
        item_id: ID of the item to update
        item_data: Update data (validated by Pydantic)
        db: Database session (injected)
    
    Returns:
        Success response with updated item details
    
    Raises:
        HTTPException: 404 if item not found
    \"\"\"
    try:
        result = await db.execute(
            select({resource_label}).where({resource_label}.id == item_id)
        )
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={{
                    "error": "Not found",
                    "message": f"{{RESOURCE_LABEL}} with id {{item_id}} not found",
                }},
            )
        
        # Update only provided fields (partial update support)
        update_data = item_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)
        
        await db.commit()
        await db.refresh(item)
        
        return SuccessResponse(
            message=f"{{RESOURCE_LABEL}} updated successfully",
            item={resource_label}Response.model_validate(item),
        )
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={{
                "error": "Database error",
                "message": str(e),
            }},
        )


@app.delete(
    "{detail_path}",
    tags=[RESOURCE_LABEL],
    summary=f"Delete a {{RESOURCE_NAME}}",
    response_model=dict,
    responses={{
        200: {{"description": "Item deleted successfully"}},
        404: {{"model": ErrorResponse, "description": "Item not found"}},
        500: {{"model": ErrorResponse, "description": "Database error"}},
    }},
)
async def delete_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    \"\"\"
    Delete a {resource_name} item.
    
    Args:
        item_id: ID of the item to delete
        db: Database session (injected)
    
    Returns:
        Confirmation of deletion
    
    Raises:
        HTTPException: 404 if item not found
    \"\"\"
    try:
        result = await db.execute(
            select({resource_label}).where({resource_label}.id == item_id)
        )
        item = result.scalar_one_or_none()
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={{
                    "error": "Not found",
                    "message": f"{{RESOURCE_LABEL}} with id {{item_id}} not found",
                }},
            )
        
        await db.delete(item)
        await db.commit()
        
        return {{
            "deleted": True,
            "id": item_id,
            "message": f"{{RESOURCE_LABEL}} deleted successfully",
        }}
        
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={{
                "error": "Database error",
                "message": str(e),
            }},
        )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
"""


def _build_readme(prompt: str, config: dict[str, str]) -> str:
    """Generate README with comprehensive documentation."""
    table_name = config["table_name"]
    resource_label = config["resource_label"]
    return f"""# Generated FastAPI Backend

This backend was generated from the following requirement:

> {prompt.strip() or "Build a CRUD backend service"}

## Stack

- **FastAPI 0.115.0**: Modern, high-performance Python web framework
- **SQLAlchemy 2.0.30**: Async ORM with relationship support
- **Pydantic**: Automatic request/response validation
- **SQLite with aiosqlite**: Async database operations
- **Uvicorn**: Lightning-fast ASGI server

## Features

- ✅ Async/await support for high concurrency
- ✅ Automatic OpenAPI (Swagger) documentation at `/docs`
- ✅ Pydantic models for automatic request validation
- ✅ Type hints throughout for better IDE support
- ✅ Comprehensive CRUD operations with proper HTTP semantics
- ✅ Structured error responses with detailed messages
- ✅ Database connection pooling and health checks
- ✅ Automatic timestamp management (created_at, updated_at)
- ✅ CORS support for frontend integration
- ✅ Partial update support (PATCH-like PUT behavior)

## Installation

```bash
pip install -r requirements.txt
```

## Running the Application

```bash
# Development mode with auto-reload
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000

# Production mode
python backend/app.py
```

The application will start on `http://0.0.0.0:8000`

## API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## API Endpoints

### Health Check
- `GET /health` - Check application and database health

### {resource_label} CRUD Operations
- `GET /api/{table_name}` - List all items with total count
- `POST /api/{table_name}` - Create a new item (with validation)
- `GET /api/{table_name}/{{id}}` - Get a specific item by ID
- `PUT /api/{table_name}/{{id}}` - Update an existing item (supports partial updates)
- `DELETE /api/{table_name}/{{id}}` - Delete an item

## Request/Response Examples

### Create Item
```bash
curl -X POST http://localhost:8000/api/{table_name} \\
  -H "Content-Type: application/json" \\
  -d '{{"title": "Example Task", "completed": false}}'
```

Response (201 Created):
```json
{{
  "message": "{resource_label} created successfully",
  "item": {{
    "id": 1,
    "title": "Example Task",
    "completed": false,
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:00:00"
  }}
}}
```

### List Items
```bash
curl http://localhost:8000/api/{table_name}
```

Response (200 OK):
```json
{{
  "items": [
    {{
      "id": 1,
      "title": "Example Task",
      "completed": false,
      "created_at": "2024-01-01T12:00:00",
      "updated_at": "2024-01-01T12:00:00"
    }}
  ],
  "total": 1
}}
```

### Get Single Item
```bash
curl http://localhost:8000/api/{table_name}/1
```

Response (200 OK):
```json
{{
  "id": 1,
  "title": "Example Task",
  "completed": false,
  "created_at": "2024-01-01T12:00:00",
  "updated_at": "2024-01-01T12:00:00"
}}
```

### Update Item (Partial Update)
```bash
curl -X PUT http://localhost:8000/api/{table_name}/1 \\
  -H "Content-Type: application/json" \\
  -d '{{"completed": true}}'
```

Response (200 OK):
```json
{{
  "message": "{resource_label} updated successfully",
  "item": {{
    "id": 1,
    "title": "Example Task",
    "completed": true,
    "created_at": "2024-01-01T12:00:00",
    "updated_at": "2024-01-01T12:30:00"
  }}
}}
```

### Delete Item
```bash
curl -X DELETE http://localhost:8000/api/{table_name}/1
```

Response (200 OK):
```json
{{
  "deleted": true,
  "id": 1,
  "message": "{resource_label} deleted successfully"
}}
```

## Error Handling

The API returns appropriate HTTP status codes with structured error responses:

- `200 OK` - Successful GET, PUT, DELETE operations
- `201 Created` - Successful POST operation
- `400 Bad Request` - Invalid input or validation errors
- `404 Not Found` - Resource not found
- `422 Unprocessable Entity` - Pydantic validation errors
- `500 Internal Server Error` - Database or server errors

Error response format:
```json
{{
  "detail": {{
    "error": "Validation error",
    "message": "title is required and cannot be empty"
  }}
}}
```

## Automatic Validation

FastAPI uses Pydantic for automatic request validation:

- **Type checking**: Ensures correct data types
- **Required fields**: Validates presence of mandatory fields
- **String length**: Enforces min/max length constraints
- **Custom validation**: Supports complex validation rules

Invalid requests receive detailed error messages with field-level feedback.

## Database Schema

The application automatically creates the database schema on first run:

- **id**: Primary key (auto-increment)
- **{config["list_field"]}**: Primary field (indexed, max 200 chars)
- **{config["secondary_field"]}**: Secondary field
- **created_at**: Creation timestamp (indexed, auto-managed)
- **updated_at**: Update timestamp (auto-managed)

## Async Architecture

FastAPI with async SQLAlchemy provides:

- **High concurrency**: Handle many requests simultaneously
- **Non-blocking I/O**: Database operations don't block other requests
- **Connection pooling**: Efficient database connection management
- **Automatic session management**: Context managers handle cleanup

## Development

### Interactive API Testing

Visit http://localhost:8000/docs to:
- Explore all available endpoints
- Test API calls directly in the browser
- View request/response schemas
- See validation requirements

### Database Management

The database file `database.db` is created automatically in the `backend/` directory.

To reset the database:
```bash
rm backend/database.db
# Restart the application to recreate
```

## Performance

FastAPI is one of the fastest Python frameworks:
- Comparable to NodeJS and Go
- Async support for high concurrency
- Automatic response caching
- Efficient JSON serialization

## Production Deployment

For production, consider:

1. **Use PostgreSQL or MySQL** instead of SQLite for better concurrency
2. **Enable HTTPS** with proper SSL certificates
3. **Configure CORS** to allow only trusted origins
4. **Add authentication** (OAuth2, JWT) for protected endpoints
5. **Set up monitoring** with Prometheus/Grafana
6. **Use process manager** like systemd or supervisor
7. **Deploy behind reverse proxy** (nginx, traefik)

Example production command:
```bash
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --workers 4
```
"""
