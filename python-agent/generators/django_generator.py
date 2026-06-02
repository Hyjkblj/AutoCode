from __future__ import annotations

from pathlib import Path

from generators import GeneratedProjectResult


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "requirements"
_GENERATED_DJANGO_REQUIREMENTS = _TEMPLATE_DIR / "generated-django.txt"


class DjangoGenerator:
    """Generator for Django REST Framework backends with configurable database support."""
    
    def generate(self, prompt: str, database: str = "sqlite") -> GeneratedProjectResult:
        """
        Generate a Django REST Framework backend application.
        
        Args:
            prompt: User requirement description
            database: Database type (sqlite, postgresql, mongodb)
            
        Returns:
            GeneratedProjectResult with all necessary Django files
        """
        config = _resource_config(prompt)
        config["database"] = database
        
        files = {
            "backend/manage.py": _build_manage_py(),
            "backend/project/__init__.py": "",
            "backend/project/settings.py": _build_settings_py(config),
            "backend/project/urls.py": _build_project_urls_py(config),
            "backend/project/wsgi.py": _build_wsgi_py(),
            "backend/project/asgi.py": _build_asgi_py(),
            "backend/api/__init__.py": "",
            "backend/api/models.py": _build_models_py(config),
            "backend/api/serializers.py": _build_serializers_py(config),
            "backend/api/views.py": _build_views_py(config),
            "backend/api/urls.py": _build_api_urls_py(config),
            "backend/api/admin.py": _build_admin_py(config),
            "backend/api/apps.py": _build_apps_py(),
            "backend/api/migrations/__init__.py": "",
            "requirements.txt": _load_generated_django_requirements(database),
            "README.generated.md": _build_readme(prompt, config),
        }
        
        return GeneratedProjectResult(
            files=files,
            used_fallback=True,
            reason=f"django_backend_generated_with_{database}"
        )


def _load_generated_django_requirements(database: str) -> str:
    """Load Django requirements with database-specific dependencies."""
    base_requirements = "django==5.0.0\ndjangorestframework==3.14.0\ndjango-cors-headers==4.3.1\n"
    
    # Add database-specific requirements
    if database == "postgresql":
        base_requirements += "psycopg2-binary==2.9.9\n"
    elif database == "mongodb":
        base_requirements += "djongo==1.3.6\npymongo==4.6.0\n"
    
    try:
        content = _GENERATED_DJANGO_REQUIREMENTS.read_text(encoding="utf-8")
        if content.strip():
            # If file exists and has content, use it as base and add database deps
            base_from_file = content.strip() + "\n"
            if database == "postgresql" and "psycopg2" not in base_from_file:
                base_from_file += "psycopg2-binary==2.9.9\n"
            elif database == "mongodb" and "djongo" not in base_from_file:
                base_from_file += "djongo==1.3.6\npymongo==4.6.0\n"
            return base_from_file
    except OSError:
        pass
    
    return base_requirements


def _resource_config(prompt: str) -> dict[str, str]:
    """Extract resource configuration from prompt."""
    text = (prompt or "").strip().lower()
    
    if any(token in text for token in ("todo", "待办", "task")):
        return {
            "app_name": "api",
            "model_name": "Todo",
            "model_name_lower": "todo",
            "model_name_plural": "todos",
            "primary_field": "title",
            "secondary_field": "completed",
            "secondary_type": "BooleanField",
            "secondary_default": "default=False",
        }
    if any(token in text for token in ("blog", "博客", "post", "article")):
        return {
            "app_name": "api",
            "model_name": "Post",
            "model_name_lower": "post",
            "model_name_plural": "posts",
            "primary_field": "title",
            "secondary_field": "content",
            "secondary_type": "TextField",
            "secondary_default": "blank=True",
        }
    if any(token in text for token in ("user", "用户", "account", "member")):
        return {
            "app_name": "api",
            "model_name": "User",
            "model_name_lower": "user",
            "model_name_plural": "users",
            "primary_field": "name",
            "secondary_field": "email",
            "secondary_type": "EmailField",
            "secondary_default": "blank=True",
        }
    
    return {
        "app_name": "api",
        "model_name": "Record",
        "model_name_lower": "record",
        "model_name_plural": "records",
        "primary_field": "name",
        "secondary_field": "description",
        "secondary_type": "TextField",
        "secondary_default": "blank=True",
    }


def _build_manage_py() -> str:
    """Generate Django management script."""
    return '''#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
'''


def _build_settings_py(config: dict[str, str]) -> str:
    """Generate Django settings with database configuration."""
    database = config.get("database", "sqlite")
    
    if database == "postgresql":
        db_config = """DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'django_db'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'postgres'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}"""
    elif database == "mongodb":
        db_config = """DATABASES = {
    'default': {
        'ENGINE': 'djongo',
        'NAME': os.environ.get('DB_NAME', 'django_db'),
        'CLIENT': {
            'host': os.environ.get('MONGO_URI', 'mongodb://localhost:27017/'),
            'username': os.environ.get('MONGO_USER', ''),
            'password': os.environ.get('MONGO_PASSWORD', ''),
            'authSource': 'admin',
            'authMechanism': 'SCRAM-SHA-1',
        }
    }
}"""
    else:  # sqlite
        db_config = """DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}"""
    
    return f'''"""
Django settings for generated project.
"""

import os
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-generated-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'project.urls'

TEMPLATES = [
    {{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {{
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        }},
    }},
]

WSGI_APPLICATION = 'project.wsgi.application'

# Database configuration
{db_config}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}},
    {{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'}},
    {{'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}},
    {{'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework configuration
REST_FRAMEWORK = {{
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}}

# CORS configuration
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
'''


def _build_project_urls_py(config: dict[str, str]) -> str:
    """Generate project URL configuration."""
    return '''"""
URL configuration for Django project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    """Health check endpoint."""
    return JsonResponse({
        'status': 'ok',
        'framework': 'django',
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health'),
    path('api/', include('api.urls')),
]
'''


def _build_wsgi_py() -> str:
    """Generate WSGI configuration."""
    return '''"""
WSGI config for Django project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

application = get_wsgi_application()
'''


def _build_asgi_py() -> str:
    """Generate ASGI configuration."""
    return '''"""
ASGI config for Django project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

application = get_asgi_application()
'''


def _build_models_py(config: dict[str, str]) -> str:
    """Generate Django models."""
    model_name = config["model_name"]
    primary_field = config["primary_field"]
    secondary_field = config["secondary_field"]
    secondary_type = config["secondary_type"]
    secondary_default = config["secondary_default"]
    
    return f'''"""
Django models for API application.
"""
from django.db import models


class {model_name}(models.Model):
    """
    {model_name} model with Django ORM.
    
    Attributes:
        id: Primary key (auto-generated)
        {primary_field}: Primary field for the resource
        {secondary_field}: Secondary field for additional data
        created_at: Timestamp of creation
        updated_at: Timestamp of last update
    """
    {primary_field} = models.CharField(max_length=200, db_index=True)
    {secondary_field} = models.{secondary_type}({secondary_default})
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-id']
        verbose_name = '{model_name}'
        verbose_name_plural = '{config["model_name_plural"]}'
    
    def __str__(self):
        return f"{{self.{primary_field}}}"
'''


def _build_serializers_py(config: dict[str, str]) -> str:
    """Generate Django REST Framework serializers."""
    model_name = config["model_name"]
    primary_field = config["primary_field"]
    secondary_field = config["secondary_field"]
    
    return f'''"""
Django REST Framework serializers.
"""
from rest_framework import serializers
from .models import {model_name}


class {model_name}Serializer(serializers.ModelSerializer):
    """
    Serializer for {model_name} model with automatic validation.
    """
    class Meta:
        model = {model_name}
        fields = ['id', '{primary_field}', '{secondary_field}', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_{primary_field}(self, value):
        """Validate {primary_field} is not empty."""
        if not value or not value.strip():
            raise serializers.ValidationError("{primary_field} cannot be empty")
        return value.strip()
'''


def _build_views_py(config: dict[str, str]) -> str:
    """Generate Django REST Framework views."""
    model_name = config["model_name"]
    model_name_lower = config["model_name_lower"]
    
    return f'''"""
Django REST Framework views.
"""
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import {model_name}
from .serializers import {model_name}Serializer


class {model_name}ViewSet(viewsets.ModelViewSet):
    """
    ViewSet for {model_name} CRUD operations.
    
    Provides:
    - list: GET /api/{config["model_name_plural"]}/
    - create: POST /api/{config["model_name_plural"]}/
    - retrieve: GET /api/{config["model_name_plural"]}/{{id}}/
    - update: PUT /api/{config["model_name_plural"]}/{{id}}/
    - partial_update: PATCH /api/{config["model_name_plural"]}/{{id}}/
    - destroy: DELETE /api/{config["model_name_plural"]}/{{id}}/
    """
    queryset = {model_name}.objects.all()
    serializer_class = {model_name}Serializer
    
    def list(self, request, *args, **kwargs):
        """List all {model_name_lower} items."""
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({{
            'items': serializer.data,
            'total': queryset.count()
        }})
    
    def create(self, request, *args, **kwargs):
        """Create a new {model_name_lower}."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response({{
            'item': serializer.data,
            'message': '{model_name} created successfully'
        }}, status=status.HTTP_201_CREATED)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve a single {model_name_lower}."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({{'item': serializer.data}})
    
    def update(self, request, *args, **kwargs):
        """Update a {model_name_lower}."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({{
            'item': serializer.data,
            'message': '{model_name} updated successfully'
        }})
    
    def destroy(self, request, *args, **kwargs):
        """Delete a {model_name_lower}."""
        instance = self.get_object()
        item_id = instance.id
        self.perform_destroy(instance)
        return Response({{
            'deleted': True,
            'id': item_id,
            'message': '{model_name} deleted successfully'
        }})
'''


def _build_api_urls_py(config: dict[str, str]) -> str:
    """Generate API URL configuration."""
    model_name = config["model_name"]
    model_name_plural = config["model_name_plural"]
    
    return f'''"""
API URL configuration.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import {model_name}ViewSet

router = DefaultRouter()
router.register(r'{model_name_plural}', {model_name}ViewSet, basename='{config["model_name_lower"]}')

urlpatterns = [
    path('', include(router.urls)),
]
'''


def _build_admin_py(config: dict[str, str]) -> str:
    """Generate Django admin configuration."""
    model_name = config["model_name"]
    primary_field = config["primary_field"]
    secondary_field = config["secondary_field"]
    
    return f'''"""
Django admin configuration.
"""
from django.contrib import admin
from .models import {model_name}


@admin.register({model_name})
class {model_name}Admin(admin.ModelAdmin):
    """Admin interface for {model_name} model."""
    list_display = ['id', '{primary_field}', '{secondary_field}', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['{primary_field}', '{secondary_field}']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-id']
'''


def _build_apps_py() -> str:
    """Generate Django app configuration."""
    return '''"""
Django app configuration.
"""
from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Configuration for API application."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
'''


def _build_readme(prompt: str, config: dict[str, str]) -> str:
    """Generate comprehensive README."""
    model_name_plural = config["model_name_plural"]
    database = config.get("database", "sqlite")
    
    db_setup = ""
    if database == "postgresql":
        db_setup = """
## Database Setup (PostgreSQL)

1. Install PostgreSQL
2. Create database:
```bash
createdb django_db
```

3. Set environment variables:
```bash
export DB_NAME=django_db
export DB_USER=postgres
export DB_PASSWORD=your_password
export DB_HOST=localhost
export DB_PORT=5432
```
"""
    elif database == "mongodb":
        db_setup = """
## Database Setup (MongoDB)

1. Install MongoDB
2. Start MongoDB service
3. Set environment variables:
```bash
export MONGO_URI=mongodb://localhost:27017/
export DB_NAME=django_db
export MONGO_USER=your_user
export MONGO_PASSWORD=your_password
```
"""
    
    return f'''# Generated Django REST Framework Backend

This backend was generated from the following requirement:

> {prompt.strip() or "Build a CRUD backend service"}

## Stack

- **Django 5.0.0**: High-level Python web framework
- **Django REST Framework 3.14.0**: Powerful toolkit for building Web APIs
- **Database**: {database.upper()}
- **CORS Headers**: Cross-Origin Resource Sharing support

## Features

- ✅ Django ORM with automatic migrations
- ✅ Django REST Framework ViewSets for CRUD operations
- ✅ Automatic API documentation with Browsable API
- ✅ Built-in admin interface at `/admin/`
- ✅ Serializer-based validation
- ✅ Proper HTTP status codes and error handling
- ✅ Database connection pooling
- ✅ Automatic timestamp management
- ✅ CORS support for frontend integration
- ✅ Production-ready with WSGI/ASGI support

## Installation

```bash
pip install -r requirements.txt
```
{db_setup}
## Database Migration

```bash
cd backend
python manage.py makemigrations
python manage.py migrate
```

## Create Admin User (Optional)

```bash
python manage.py createsuperuser
```

## Running the Application

```bash
# Development server
python manage.py runserver 0.0.0.0:8000

# Production with Gunicorn
gunicorn project.wsgi:application --bind 0.0.0.0:8000
```

The application will start on `http://0.0.0.0:8000`

## API Endpoints

### Health Check
- `GET /health/` - Check application health

### Admin Interface
- `GET /admin/` - Django admin interface (requires superuser)

### {config["model_name"]} CRUD Operations
- `GET /api/{model_name_plural}/` - List all items
- `POST /api/{model_name_plural}/` - Create a new item
- `GET /api/{model_name_plural}/{{id}}/` - Get a specific item
- `PUT /api/{model_name_plural}/{{id}}/` - Update an item (full)
- `PATCH /api/{model_name_plural}/{{id}}/` - Update an item (partial)
- `DELETE /api/{model_name_plural}/{{id}}/` - Delete an item

## API Documentation

Django REST Framework provides a browsable API interface:
- Visit http://localhost:8000/api/ to explore the API interactively

## Request/Response Examples

### Create Item
```bash
curl -X POST http://localhost:8000/api/{model_name_plural}/ \\
  -H "Content-Type: application/json" \\
  -d '{{"title": "Example", "completed": false}}'
```

Response (201 Created):
```json
{{
  "item": {{
    "id": 1,
    "title": "Example",
    "completed": false,
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z"
  }},
  "message": "{config["model_name"]} created successfully"
}}
```

### List Items
```bash
curl http://localhost:8000/api/{model_name_plural}/
```

Response (200 OK):
```json
{{
  "items": [
    {{
      "id": 1,
      "title": "Example",
      "completed": false,
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:00:00Z"
    }}
  ],
  "total": 1
}}
```

## Error Handling

Django REST Framework provides comprehensive error handling:

- `200 OK` - Successful GET, PUT, PATCH, DELETE
- `201 Created` - Successful POST
- `400 Bad Request` - Validation errors
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server errors

Error response format:
```json
{{
  "field_name": ["Error message"]
}}
```

## Database Schema

The application uses Django migrations to manage the database schema:

- **id**: Primary key (auto-increment)
- **{config["primary_field"]}**: Primary field (indexed, max 200 chars)
- **{config["secondary_field"]}**: Secondary field
- **created_at**: Creation timestamp (auto-managed)
- **updated_at**: Update timestamp (auto-managed)

## Admin Interface

Django provides a powerful admin interface:

1. Create a superuser: `python manage.py createsuperuser`
2. Visit http://localhost:8000/admin/
3. Manage {config["model_name"]} items through the web interface

## Development

### Running Tests
```bash
python manage.py test
```

### Database Shell
```bash
python manage.py dbshell
```

### Django Shell
```bash
python manage.py shell
```

### Create New Migrations
```bash
python manage.py makemigrations
```

## Production Deployment

For production deployment:

1. **Set SECRET_KEY**: Generate a secure secret key
2. **Disable DEBUG**: Set `DEBUG=False`
3. **Configure ALLOWED_HOSTS**: Set proper domain names
4. **Use production database**: PostgreSQL or MySQL recommended
5. **Collect static files**: `python manage.py collectstatic`
6. **Use WSGI server**: Gunicorn or uWSGI
7. **Set up reverse proxy**: nginx or Apache
8. **Enable HTTPS**: Use SSL certificates

Example production settings:
```bash
export SECRET_KEY=your-secret-key
export DEBUG=False
export ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
```

## Performance

Django is a mature, battle-tested framework:
- ORM query optimization with select_related and prefetch_related
- Built-in caching framework
- Database connection pooling
- Middleware for compression and security

## Security

Django includes security features by default:
- CSRF protection
- SQL injection prevention
- XSS protection
- Clickjacking protection
- Secure password hashing
'''
