"""
Unit tests for Django backend generator.
"""

import pytest
from generators.django_generator import DjangoGenerator


class TestDjangoGenerator:
    """Test suite for Django backend generator."""
    
    def test_generate_basic_backend(self):
        """Test basic Django backend generation."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        assert result is not None
        assert result.used_fallback is True
        assert "django_backend_generated" in result.reason
        assert len(result.files) > 0
    
    def test_generate_with_sqlite(self):
        """Test Django generation with SQLite database."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app", database="sqlite")
        
        assert "backend/manage.py" in result.files
        assert "backend/project/settings.py" in result.files
        assert "backend/api/models.py" in result.files
        assert "backend/api/views.py" in result.files
        assert "backend/api/serializers.py" in result.files
        assert "requirements.txt" in result.files
        assert "README.generated.md" in result.files
        
        # Check SQLite configuration in settings
        settings = result.files["backend/project/settings.py"]
        assert "sqlite3" in settings
        assert "db.sqlite3" in settings
    
    def test_generate_with_postgresql(self):
        """Test Django generation with PostgreSQL database."""
        generator = DjangoGenerator()
        result = generator.generate("Build a blog", database="postgresql")
        
        settings = result.files["backend/project/settings.py"]
        assert "postgresql" in settings
        assert "DB_NAME" in settings
        assert "DB_USER" in settings
        assert "DB_PASSWORD" in settings
        
        requirements = result.files["requirements.txt"]
        assert "psycopg2-binary" in requirements
    
    def test_generate_with_mongodb(self):
        """Test Django generation with MongoDB database."""
        generator = DjangoGenerator()
        result = generator.generate("Build a user system", database="mongodb")
        
        settings = result.files["backend/project/settings.py"]
        assert "djongo" in settings
        assert "MONGO_URI" in settings
        
        requirements = result.files["requirements.txt"]
        assert "djongo" in requirements
        assert "pymongo" in requirements
    
    def test_todo_resource_detection(self):
        """Test detection of todo resource from prompt."""
        generator = DjangoGenerator()
        result = generator.generate("Create a task management system")
        
        models = result.files["backend/api/models.py"]
        assert "Todo" in models
        assert "title" in models
        assert "completed" in models
    
    def test_blog_resource_detection(self):
        """Test detection of blog resource from prompt."""
        generator = DjangoGenerator()
        result = generator.generate("Build a blog platform")
        
        models = result.files["backend/api/models.py"]
        assert "Post" in models
        assert "title" in models
        assert "content" in models
    
    def test_user_resource_detection(self):
        """Test detection of user resource from prompt."""
        generator = DjangoGenerator()
        result = generator.generate("Create a user management system")
        
        models = result.files["backend/api/models.py"]
        assert "User" in models
        assert "name" in models
        assert "email" in models
    
    def test_models_structure(self):
        """Test Django models structure."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        models = result.files["backend/api/models.py"]
        assert "class Todo(models.Model):" in models
        assert "created_at" in models
        assert "updated_at" in models
        assert "auto_now_add=True" in models
        assert "auto_now=True" in models
    
    def test_views_structure(self):
        """Test Django REST Framework views structure."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        views = result.files["backend/api/views.py"]
        assert "class TodoViewSet(viewsets.ModelViewSet):" in views
        assert "def list(self, request" in views
        assert "def create(self, request" in views
        assert "def retrieve(self, request" in views
        assert "def update(self, request" in views
        assert "def destroy(self, request" in views
    
    def test_serializers_structure(self):
        """Test Django REST Framework serializers."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        serializers = result.files["backend/api/serializers.py"]
        assert "class TodoSerializer(serializers.ModelSerializer):" in serializers
        assert "class Meta:" in serializers
        assert "fields = " in serializers
        assert "read_only_fields = " in serializers
    
    def test_urls_configuration(self):
        """Test URL configuration."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        api_urls = result.files["backend/api/urls.py"]
        assert "DefaultRouter" in api_urls
        assert "router.register" in api_urls
        
        project_urls = result.files["backend/project/urls.py"]
        assert "path('admin/', admin.site.urls)" in project_urls
        assert "path('health/', health_check" in project_urls
        assert "path('api/', include('api.urls'))" in project_urls
    
    def test_admin_configuration(self):
        """Test Django admin configuration."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        admin = result.files["backend/api/admin.py"]
        assert "@admin.register(Todo)" in admin
        assert "class TodoAdmin(admin.ModelAdmin):" in admin
        assert "list_display = " in admin
        assert "search_fields = " in admin
    
    def test_settings_configuration(self):
        """Test Django settings configuration."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        settings = result.files["backend/project/settings.py"]
        assert "INSTALLED_APPS = [" in settings
        assert "'rest_framework'" in settings
        assert "'corsheaders'" in settings
        assert "'api'" in settings
        assert "REST_FRAMEWORK = {" in settings
        assert "CORS_ALLOW_ALL_ORIGINS = True" in settings
    
    def test_manage_py_generation(self):
        """Test manage.py generation."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        manage = result.files["backend/manage.py"]
        assert "#!/usr/bin/env python" in manage
        assert "execute_from_command_line" in manage
        assert "DJANGO_SETTINGS_MODULE" in manage
    
    def test_wsgi_asgi_generation(self):
        """Test WSGI and ASGI configuration generation."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        wsgi = result.files["backend/project/wsgi.py"]
        assert "get_wsgi_application" in wsgi
        
        asgi = result.files["backend/project/asgi.py"]
        assert "get_asgi_application" in asgi
    
    def test_readme_generation(self):
        """Test README generation."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo management system")
        
        readme = result.files["README.generated.md"]
        assert "# Generated Django REST Framework Backend" in readme
        assert "Build a todo management system" in readme
        assert "## Stack" in readme
        assert "Django" in readme
        assert "## Installation" in readme
        assert "pip install -r requirements.txt" in readme
        assert "python manage.py migrate" in readme
    
    def test_requirements_generation(self):
        """Test requirements.txt generation."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app", database="sqlite")
        
        requirements = result.files["requirements.txt"]
        assert "django==" in requirements
        assert "djangorestframework==" in requirements
        assert "django-cors-headers==" in requirements
    
    def test_init_files_generation(self):
        """Test __init__.py files generation."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        assert "backend/project/__init__.py" in result.files
        assert "backend/api/__init__.py" in result.files
        assert "backend/api/migrations/__init__.py" in result.files
        assert result.files["backend/project/__init__.py"] == ""
        assert result.files["backend/api/__init__.py"] == ""
    
    def test_apps_configuration(self):
        """Test Django apps configuration."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        apps = result.files["backend/api/apps.py"]
        assert "class ApiConfig(AppConfig):" in apps
        assert "name = 'api'" in apps
        assert "default_auto_field" in apps
    
    def test_error_handling_in_views(self):
        """Test error handling in views."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        views = result.files["backend/api/views.py"]
        # Django REST Framework ViewSet handles errors automatically
        # Check for status codes in responses
        assert "status.HTTP_201_CREATED" in views
        assert "get_object()" in views  # This raises 404 automatically
    
    def test_validation_in_serializers(self):
        """Test validation in serializers."""
        generator = DjangoGenerator()
        result = generator.generate("Build a todo app")
        
        serializers = result.files["backend/api/serializers.py"]
        assert "def validate_" in serializers
        assert "ValidationError" in serializers
    
    def test_default_resource_fallback(self):
        """Test fallback to default resource when no match."""
        generator = DjangoGenerator()
        result = generator.generate("Build something generic")
        
        models = result.files["backend/api/models.py"]
        assert "Record" in models
        assert "name" in models
        assert "description" in models
