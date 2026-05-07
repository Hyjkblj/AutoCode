"""Integration tests for enhanced fullstack generator."""

from __future__ import annotations

import json
import re

import pytest

from generators.fullstack_generator import FullstackGenerator


class TestFullstackGeneratorIntegration:
    """Test fullstack generator integration enhancements."""

    def test_generates_api_config_file(self):
        """Verify API configuration file is generated."""
        generator = FullstackGenerator()
        result = generator.generate("Build a todo app")
        
        assert "frontend/api-config.js" in result.files
        api_config_content = result.files["frontend/api-config.js"]
        
        # Verify it contains API_CONFIG object
        assert "API_CONFIG" in api_config_content
        assert "base_url" in api_config_content
        assert "endpoints" in api_config_content

    def test_frontend_js_includes_api_client(self):
        """Verify frontend JavaScript includes integrated API client."""
        generator = FullstackGenerator()
        result = generator.generate("Build a blog app")
        
        assert "frontend/app.js" in result.files
        app_js_content = result.files["frontend/app.js"]
        
        # Verify API client is present
        assert "API_BASE_URL" in app_js_content
        assert "API_ENDPOINTS" in app_js_content
        assert "apiClient" in app_js_content
        
        # Verify CRUD methods exist
        assert "async list()" in app_js_content
        assert "async create(data)" in app_js_content
        assert "async get(id)" in app_js_content
        assert "async update(id, data)" in app_js_content
        assert "async delete(id)" in app_js_content

    def test_frontend_html_includes_api_status(self):
        """Verify frontend HTML includes API status indicator."""
        generator = FullstackGenerator()
        result = generator.generate("Build a user management app")
        
        assert "frontend/index.html" in result.files
        html_content = result.files["frontend/index.html"]
        
        # Verify API status indicator is present
        assert "api-status" in html_content
        assert "/health" in html_content
        assert "API: Connected" in html_content or "API: Checking" in html_content

    def test_generates_docker_compose(self):
        """Verify Docker Compose configuration is generated."""
        generator = FullstackGenerator()
        result = generator.generate("Build a task manager")
        
        assert "docker-compose.yml" in result.files
        docker_compose = result.files["docker-compose.yml"]
        
        # Verify services are defined
        assert "services:" in docker_compose
        assert "backend:" in docker_compose
        assert "frontend:" in docker_compose
        
        # Verify ports are configured
        assert "8000:8000" in docker_compose
        assert "3000:80" in docker_compose

    def test_generates_env_example(self):
        """Verify environment variables template is generated."""
        generator = FullstackGenerator()
        result = generator.generate("Build a notes app")
        
        assert ".env.example" in result.files
        env_content = result.files[".env.example"]
        
        # Verify key configuration variables
        assert "FLASK_ENV" in env_content
        assert "API_BASE_URL" in env_content
        assert "CORS_ORIGINS" in env_content
        assert "DATABASE_URL" in env_content

    def test_readme_includes_deployment_instructions(self):
        """Verify README includes comprehensive deployment instructions."""
        generator = FullstackGenerator()
        result = generator.generate("Build a contact manager")
        
        assert "README.generated.md" in result.files
        readme = result.files["README.generated.md"]
        
        # Verify deployment sections
        assert "Quick Start" in readme
        assert "Docker Deployment" in readme
        assert "Frontend-Backend Integration" in readme
        assert "Configuration" in readme
        assert "Deployment" in readme
        
        # Verify API documentation
        assert "API Endpoints" in readme
        assert "Data Model" in readme

    def test_api_config_extraction_from_backend(self):
        """Verify API configuration is correctly extracted from backend files."""
        generator = FullstackGenerator()
        result = generator.generate("Build a todo app")
        
        # Check that API config file contains correct endpoints
        api_config_content = result.files["frontend/api-config.js"]
        
        # Extract JSON from the file
        match = re.search(r'const API_CONFIG = ({.*?});', api_config_content, re.DOTALL)
        assert match is not None
        
        config_json = match.group(1)
        config = json.loads(config_json)
        
        # Verify structure
        assert "base_url" in config
        assert "resource_name" in config
        assert "endpoints" in config
        assert "fields" in config
        
        # Verify endpoints are present
        assert "list" in config["endpoints"]
        assert "create" in config["endpoints"]
        assert "get" in config["endpoints"]
        assert "update" in config["endpoints"]
        assert "delete" in config["endpoints"]

    def test_consistent_data_models_across_stack(self):
        """Verify data models are consistent between frontend and backend."""
        generator = FullstackGenerator()
        result = generator.generate("Build a blog app")
        
        # Extract backend model fields
        models_content = result.files["backend/models.py"]
        primary_field_match = re.search(r'PRIMARY_FIELD\s*=\s*["\']([^"\']+)["\']', models_content)
        secondary_field_match = re.search(r'SECONDARY_FIELD\s*=\s*["\']([^"\']+)["\']', models_content)
        
        assert primary_field_match is not None
        assert secondary_field_match is not None
        
        primary_field = primary_field_match.group(1)
        secondary_field = secondary_field_match.group(1)
        
        # Verify these fields are referenced in frontend API config
        api_config_content = result.files["frontend/api-config.js"]
        assert primary_field in api_config_content
        assert secondary_field in api_config_content
        
        # Verify README documents these fields
        readme = result.files["README.generated.md"]
        assert primary_field in readme
        assert secondary_field in readme

    def test_all_required_files_generated(self):
        """Verify all required files for fullstack app are generated."""
        generator = FullstackGenerator()
        result = generator.generate("Build a simple app")

        # Frontend files
        assert "frontend/index.html" in result.files
        assert "frontend/styles.css" in result.files
        assert "frontend/app.js" in result.files
        assert "frontend/api-config.js" in result.files

        # Backend files
        assert "backend/app.py" in result.files
        assert "backend/models.py" in result.files

        # Configuration files
        assert "requirements.txt" in result.files
        assert "docker-compose.yml" in result.files
        assert "Dockerfile.backend" in result.files
        assert "nginx.conf" in result.files
        assert ".env.example" in result.files
        assert "README.generated.md" in result.files

    def test_api_endpoints_match_backend_routes(self):
        """Verify frontend API endpoints match backend route definitions."""
        generator = FullstackGenerator()
        result = generator.generate("Build a user app")
        
        # Extract backend routes (skip health endpoint)
        app_py = result.files["backend/app.py"]
        
        # Find CRUD route decorators (not health)
        list_routes = re.findall(r'@app\.get\(["\']([^"\']+)["\']\)', app_py)
        create_routes = re.findall(r'@app\.post\(["\']([^"\']+)["\']\)', app_py)
        
        # Filter out health endpoint
        list_route = [r for r in list_routes if "/health" not in r][0] if list_routes else None
        create_route = create_routes[0] if create_routes else None
        
        assert list_route is not None
        assert create_route is not None
        
        # Extract frontend API config
        api_config_content = result.files["frontend/api-config.js"]
        
        # Verify routes are present in API config
        assert list_route in api_config_content
        assert create_route in api_config_content
