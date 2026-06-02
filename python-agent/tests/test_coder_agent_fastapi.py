"""
Tests for CoderAgent FastAPI generator integration.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from agents.coder_agent import CoderAgent
from agents.planner_agent import PlanResult
from generators.fastapi_generator import FastAPIGenerator
from plugins.registry import PluginRegistry
from tools.file_tool import FileTool


class _FakeClient:
    """Fake client for testing."""
    pass


def test_coder_agent_uses_fastapi_generator_when_prompt_contains_fastapi():
    """Verify CoderAgent uses FastAPI generator when prompt contains 'fastapi'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        # Create CoderAgent with FastAPI generator
        fastapi_gen = FastAPIGenerator()
        coder = CoderAgent(
            file_tool=FileTool([str(workspace)]),
            fastapi_generator=fastapi_gen,
            plugin_registry=PluginRegistry(),
        )
        
        # Mock dependencies
        plan = PlanResult(plan_name="test-plan", steps=["generate", "package"])
        
        events = []
        def publish_event(payload, event_type="ASSISTANT_OUTPUT"):
            events.append({"payload": payload, "type": event_type})
        
        # Execute with FastAPI prompt
        task = {
            "taskId": "test-task",
            "prompt": "build a fastapi todo backend",
            "workspacePath": str(workspace),
            "target": "backend",
        }
        
        result = coder.execute(task, _FakeClient(), plan, publish_event)
        
        # Verify success
        assert result is True
        
        # Verify FastAPI files were generated
        assert (workspace / "backend" / "app.py").exists()
        assert (workspace / "backend" / "models.py").exists()
        assert (workspace / "backend" / "schemas.py").exists()
        assert (workspace / "backend" / "database.py").exists()
        assert (workspace / "requirements.txt").exists()
        
        # Verify FastAPI-specific content
        app_content = (workspace / "backend" / "app.py").read_text()
        assert "from fastapi import FastAPI" in app_content
        assert "async def" in app_content
        
        schemas_content = (workspace / "backend" / "schemas.py").read_text()
        assert "from pydantic import BaseModel" in schemas_content
        
        requirements_content = (workspace / "requirements.txt").read_text()
        assert "fastapi==" in requirements_content
        assert "uvicorn" in requirements_content


def test_coder_agent_uses_flask_generator_when_prompt_does_not_contain_fastapi():
    """Verify CoderAgent uses Flask generator when prompt doesn't contain 'fastapi'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        # Create CoderAgent
        coder = CoderAgent(
            file_tool=FileTool([str(workspace)]),
            plugin_registry=PluginRegistry(),
        )
        
        # Mock dependencies
        plan = PlanResult(plan_name="test-plan", steps=["generate", "package"])
        
        events = []
        def publish_event(payload, event_type="ASSISTANT_OUTPUT"):
            events.append({"payload": payload, "type": event_type})
        
        # Execute with generic backend prompt
        task = {
            "taskId": "test-task",
            "prompt": "build a todo backend",
            "workspacePath": str(workspace),
            "target": "backend",
        }
        
        result = coder.execute(task, _FakeClient(), plan, publish_event)
        
        # Verify success
        assert result is True
        
        # Verify Flask files were generated (no schemas.py)
        assert (workspace / "backend" / "app.py").exists()
        assert (workspace / "backend" / "models.py").exists()
        assert (workspace / "backend" / "database.py").exists()
        assert not (workspace / "backend" / "schemas.py").exists()
        
        # Verify Flask-specific content
        app_content = (workspace / "backend" / "app.py").read_text()
        assert "from flask import Flask" in app_content
        assert "def list_items()" in app_content  # Flask uses sync functions
        
        requirements_content = (workspace / "requirements.txt").read_text()
        assert "flask==" in requirements_content


def test_coder_agent_detects_fastapi_with_space():
    """Verify CoderAgent detects 'fast api' with space."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        coder = CoderAgent(
            file_tool=FileTool([str(workspace)]),
            plugin_registry=PluginRegistry(),
        )
        
        plan = PlanResult(plan_name="test-plan", steps=["generate", "package"])
        
        events = []
        def publish_event(payload, event_type="ASSISTANT_OUTPUT"):
            events.append({"payload": payload, "type": event_type})
        
        task = {
            "taskId": "test-task",
            "prompt": "build a fast api backend for users",
            "workspacePath": str(workspace),
            "target": "backend",
        }
        
        result = coder.execute(task, _FakeClient(), plan, publish_event)
        
        assert result is True
        
        # Verify FastAPI was used
        app_content = (workspace / "backend" / "app.py").read_text()
        assert "from fastapi import FastAPI" in app_content


def test_coder_agent_fastapi_generation_creates_pydantic_schemas():
    """Verify FastAPI generation creates Pydantic schemas."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        coder = CoderAgent(
            file_tool=FileTool([str(workspace)]),
            plugin_registry=PluginRegistry(),
        )
        
        plan = PlanResult(plan_name="test-plan", steps=["generate", "package"])
        
        events = []
        def publish_event(payload, event_type="ASSISTANT_OUTPUT"):
            events.append({"payload": payload, "type": event_type})
        
        task = {
            "taskId": "test-task",
            "prompt": "build a fastapi user backend",
            "workspacePath": str(workspace),
            "target": "backend",
        }
        
        result = coder.execute(task, _FakeClient(), plan, publish_event)
        
        assert result is True
        
        # Verify Pydantic schemas exist
        schemas_path = workspace / "backend" / "schemas.py"
        assert schemas_path.exists()
        
        schemas_content = schemas_path.read_text()
        assert "class UserCreate(BaseModel):" in schemas_content
        assert "class UserUpdate(BaseModel):" in schemas_content
        assert "class UserResponse(BaseModel):" in schemas_content
        assert "Field(" in schemas_content


def test_coder_agent_fastapi_generation_creates_async_routes():
    """Verify FastAPI generation creates async routes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        coder = CoderAgent(
            file_tool=FileTool([str(workspace)]),
            plugin_registry=PluginRegistry(),
        )
        
        plan = PlanResult(plan_name="test-plan", steps=["generate", "package"])
        
        events = []
        def publish_event(payload, event_type="ASSISTANT_OUTPUT"):
            events.append({"payload": payload, "type": event_type})
        
        task = {
            "taskId": "test-task",
            "prompt": "build a fastapi todo backend",
            "workspacePath": str(workspace),
            "target": "backend",
        }
        
        result = coder.execute(task, _FakeClient(), plan, publish_event)
        
        assert result is True
        
        # Verify async routes
        app_content = (workspace / "backend" / "app.py").read_text()
        assert "async def list_items" in app_content
        assert "async def create_item" in app_content
        assert "async def get_item" in app_content
        assert "async def update_item" in app_content
        assert "async def delete_item" in app_content
        assert "await db.execute" in app_content


def test_coder_agent_fastapi_generation_includes_openapi_docs():
    """Verify FastAPI generation includes OpenAPI documentation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        coder = CoderAgent(
            file_tool=FileTool([str(workspace)]),
            plugin_registry=PluginRegistry(),
        )
        
        plan = PlanResult(plan_name="test-plan", steps=["generate", "package"])
        
        events = []
        def publish_event(payload, event_type="ASSISTANT_OUTPUT"):
            events.append({"payload": payload, "type": event_type})
        
        task = {
            "taskId": "test-task",
            "prompt": "build a fastapi backend",
            "workspacePath": str(workspace),
            "target": "backend",
        }
        
        result = coder.execute(task, _FakeClient(), plan, publish_event)
        
        assert result is True
        
        # Verify OpenAPI configuration
        app_content = (workspace / "backend" / "app.py").read_text()
        assert 'docs_url="/docs"' in app_content
        assert 'redoc_url="/redoc"' in app_content
        assert 'openapi_url="/openapi.json"' in app_content
