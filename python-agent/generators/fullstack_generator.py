from __future__ import annotations

import re
from typing import Any

from generators import GeneratedProjectResult
from generators.backend_generator import BackendGenerator
from utils.web_template import WebTemplateGenerator


class FullstackGenerator:
    def __init__(
        self,
        *,
        backend_generator: BackendGenerator | None = None,
        web_template_generator: WebTemplateGenerator | None = None,
    ) -> None:
        self.backend_generator = backend_generator or BackendGenerator()
        self.web_template_generator = web_template_generator or WebTemplateGenerator()

    def generate(self, prompt: str, task: dict[str, Any] | None = None) -> GeneratedProjectResult:
        backend = self.backend_generator.generate(prompt)
        frontend = self.web_template_generator.generate(prompt, target="web", task=task)
        # Extract backend API metadata for frontend integration
        api_config = _extract_api_config(backend.files)

        files: dict[str, str] = {}
        
        # Add frontend files with API integration
        for relative, content in frontend.files.items():
            if relative == "app.js":
                # Enhance frontend JavaScript with backend API integration
                files[f"frontend/{relative}"] = _integrate_api_client(content, api_config)
            elif relative == "index.html":
                # Enhance HTML with API-aware UI elements
                files[f"frontend/{relative}"] = _enhance_html_for_api(content, api_config)
            else:
                files[f"frontend/{relative}"] = content
        
        # Add backend files
        for relative, content in backend.files.items():
            if relative == "README.generated.md":
                continue
            files[relative] = content
        
        # Add integrated API configuration file
        files["frontend/api-config.js"] = _build_api_config_file(api_config)
        
        # Add integrated README with deployment instructions
        files["README.generated.md"] = _build_integrated_readme(prompt, api_config)
        
        # Add deployment configuration
        files["docker-compose.yml"] = _build_docker_compose(api_config)
        files["Dockerfile.backend"] = _build_backend_dockerfile()
        files["nginx.conf"] = _build_nginx_conf(api_config)
        files[".env.example"] = _build_env_example(api_config)

        return GeneratedProjectResult(
            files=files,
            used_fallback=backend.used_fallback or frontend.used_fallback,
            reason=f"{backend.reason};{frontend.reason}",
        )


def _extract_api_config(backend_files: dict[str, str]) -> dict[str, Any]:
    """Extract API configuration from backend files for frontend integration."""
    config: dict[str, Any] = {
        "base_url": "http://localhost:8000",
        "resource_name": "items",
        "resource_label": "Item",
        "endpoints": {},
        "fields": {},
    }
    
    # Try to extract from models.py
    models_content = backend_files.get("backend/models.py", "")
    if models_content:
        # Extract resource metadata
        resource_name_match = re.search(r'RESOURCE_NAME\s*=\s*["\']([^"\']+)["\']', models_content)
        if resource_name_match:
            config["resource_name"] = resource_name_match.group(1)
        
        resource_label_match = re.search(r'RESOURCE_LABEL\s*=\s*["\']([^"\']+)["\']', models_content)
        if resource_label_match:
            config["resource_label"] = resource_label_match.group(1)
        
        table_name_match = re.search(r'TABLE_NAME\s*=\s*["\']([^"\']+)["\']', models_content)
        if table_name_match:
            table_name = table_name_match.group(1)
            config["endpoints"] = {
                "list": f"/api/{table_name}",
                "create": f"/api/{table_name}",
                "get": f"/api/{table_name}/{{id}}",
                "update": f"/api/{table_name}/{{id}}",
                "delete": f"/api/{table_name}/{{id}}",
            }
        
        # Extract field names
        primary_field_match = re.search(r'PRIMARY_FIELD\s*=\s*["\']([^"\']+)["\']', models_content)
        if primary_field_match:
            config["fields"]["primary"] = primary_field_match.group(1)
        
        secondary_field_match = re.search(r'SECONDARY_FIELD\s*=\s*["\']([^"\']+)["\']', models_content)
        if secondary_field_match:
            config["fields"]["secondary"] = secondary_field_match.group(1)
    
    return config


def _integrate_api_client(js_content: str, api_config: dict[str, Any]) -> str:
    """Enhance frontend JavaScript with backend API integration."""
    base_url = api_config.get("base_url", "http://localhost:8000")
    endpoints = api_config.get("endpoints", {})
    
    api_client_code = f"""
// API Configuration (auto-generated)
const API_BASE_URL = "{base_url}";
const API_ENDPOINTS = {{
    list: "{endpoints.get('list', '/api/items')}",
    create: "{endpoints.get('create', '/api/items')}",
    get: "{endpoints.get('get', '/api/items/{{id}}')}",
    update: "{endpoints.get('update', '/api/items/{{id}}')}",
    delete: "{endpoints.get('delete', '/api/items/{{id}}')}",
}};

// API Client Helper Functions
const apiClient = {{
    async list() {{
        const response = await fetch(`${{API_BASE_URL}}${{API_ENDPOINTS.list}}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${{response.status}}`);
        return await response.json();
    }},
    
    async create(data) {{
        const response = await fetch(`${{API_BASE_URL}}${{API_ENDPOINTS.create}}`, {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data),
        }});
        if (!response.ok) throw new Error(`HTTP error! status: ${{response.status}}`);
        return await response.json();
    }},
    
    async get(id) {{
        const url = `${{API_BASE_URL}}${{API_ENDPOINTS.get}}`.replace('{{id}}', id);
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${{response.status}}`);
        return await response.json();
    }},
    
    async update(id, data) {{
        const url = `${{API_BASE_URL}}${{API_ENDPOINTS.update}}`.replace('{{id}}', id);
        const response = await fetch(url, {{
            method: 'PUT',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify(data),
        }});
        if (!response.ok) throw new Error(`HTTP error! status: ${{response.status}}`);
        return await response.json();
    }},
    
    async delete(id) {{
        const url = `${{API_BASE_URL}}${{API_ENDPOINTS.delete}}`.replace('{{id}}', id);
        const response = await fetch(url, {{
            method: 'DELETE',
        }});
        if (!response.ok) throw new Error(`HTTP error! status: ${{response.status}}`);
        return await response.json();
    }},
}};

// Original app code below
"""
    
    return api_client_code + js_content


def _enhance_html_for_api(html_content: str, api_config: dict[str, Any]) -> str:
    """Enhance HTML with API-aware UI elements and metadata."""
    resource_label = api_config.get("resource_label", "Item")
    
    # Add API status indicator before closing body tag
    api_status_html = f"""
    <!-- API Integration Status -->
    <div id="api-status" style="position: fixed; bottom: 10px; right: 10px; padding: 8px 12px; background: #f0f0f0; border-radius: 6px; font-size: 12px; display: none;">
        <span id="api-status-text">API: Checking...</span>
    </div>
    <script>
        // Check API health on page load
        fetch('{api_config.get("base_url", "http://localhost:8000")}/health')
            .then(res => res.json())
            .then(data => {{
                const statusEl = document.getElementById('api-status');
                const textEl = document.getElementById('api-status-text');
                if (data.status === 'ok') {{
                    textEl.textContent = 'API: Connected ✓';
                    statusEl.style.background = '#d4edda';
                    statusEl.style.color = '#155724';
                }} else {{
                    textEl.textContent = 'API: Error';
                    statusEl.style.background = '#f8d7da';
                    statusEl.style.color = '#721c24';
                }}
                statusEl.style.display = 'block';
                setTimeout(() => statusEl.style.display = 'none', 3000);
            }})
            .catch(() => {{
                const statusEl = document.getElementById('api-status');
                const textEl = document.getElementById('api-status-text');
                textEl.textContent = 'API: Offline';
                statusEl.style.background = '#f8d7da';
                statusEl.style.color = '#721c24';
                statusEl.style.display = 'block';
            }});
    </script>
"""
    
    # Insert before closing body tag
    if "</body>" in html_content:
        html_content = html_content.replace("</body>", f"{api_status_html}\n  </body>")
    
    # Add data-resource attribute to body for frontend reference
    if "<body>" in html_content:
        html_content = html_content.replace(
            "<body>",
            f'<body data-resource="{resource_label.lower()}" data-api-base="{api_config.get("base_url", "http://localhost:8000")}">'
        )
    
    return html_content


def _build_api_config_file(api_config: dict[str, Any]) -> str:
    """Generate a standalone API configuration file for frontend."""
    import json
    
    config_json = json.dumps(api_config, indent=2)
    
    return f"""// API Configuration
// This file is auto-generated and contains backend API endpoints and data models

const API_CONFIG = {config_json};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {{
    module.exports = API_CONFIG;
}}
"""


def _build_integrated_readme(prompt: str, api_config: dict[str, Any]) -> str:
    """Generate comprehensive README with deployment instructions."""
    resource_name = api_config.get("resource_name", "items")
    resource_label = api_config.get("resource_label", "Item")
    base_url = api_config.get("base_url", "http://localhost:8000")
    endpoints = api_config.get("endpoints", {})
    fields = api_config.get("fields", {})
    
    return f"""# Generated Fullstack Application

This fullstack application was generated from:

> {prompt.strip() or "Build a fullstack application"}

## Architecture

This is a complete fullstack application with:

- **Frontend**: Static HTML/CSS/JavaScript with integrated API client
- **Backend**: Flask REST API with SQLite database
- **Integration**: Consistent data models and automatic API endpoint configuration

## Project Structure

```
.
├── frontend/
│   ├── index.html          # Main UI
│   ├── styles.css          # Styling
│   ├── app.js              # Application logic with API integration
│   └── api-config.js       # API endpoint configuration
├── backend/
│   ├── app.py              # Flask application with CRUD endpoints
│   └── models.py           # Resource configuration constants
├── requirements.txt        # Python dependencies
├── docker-compose.yml      # Docker deployment configuration
├── Dockerfile.backend      # Backend container image
├── nginx.conf              # Frontend web server config
├── .env.example            # Environment variables template
└── README.generated.md     # This file
```

## Data Model

**Resource**: {resource_label}

**Fields**:
- `id`: Auto-incrementing primary key
- `{fields.get("primary", "name")}`: Primary field (string, required)
- `{fields.get("secondary", "description")}`: Secondary field
- `created_at`: Timestamp (auto-managed)
- `updated_at`: Timestamp (auto-managed)

## API Endpoints

All endpoints are prefixed with `{base_url}`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `{endpoints.get("list", "/api/items")}` | List all {resource_name} |
| POST   | `{endpoints.get("create", "/api/items")}` | Create new {resource_label.lower()} |
| GET    | `{endpoints.get("get", "/api/items/{{id}}")}` | Get specific {resource_label.lower()} by ID |
| PUT    | `{endpoints.get("update", "/api/items/{{id}}")}` | Update {resource_label.lower()} |
| DELETE | `{endpoints.get("delete", "/api/items/{{id}}")}` | Delete {resource_label.lower()} |

## Quick Start

### Option 1: Manual Setup

1. **Install backend dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the backend server**:
   ```bash
   python backend/app.py
   ```
   Backend will be available at `{base_url}`

3. **Serve the frontend**:
   ```bash
   # Using Python's built-in server
   cd frontend
   python -m http.server 3000
   ```
   Frontend will be available at `http://localhost:3000`

4. **Open your browser**:
   Navigate to `http://localhost:3000`

### Option 2: Docker Deployment

1. **Start all services with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

2. **Access the application**:
   - Frontend: `http://localhost:3000`
   - Backend API: `{base_url}`
   - API Health: `{base_url}/health`

3. **Stop services**:
   ```bash
   docker-compose down
   ```

## Frontend-Backend Integration

The frontend automatically integrates with the backend through:

1. **API Client**: Pre-configured API client in `app.js` with methods for all CRUD operations
2. **API Configuration**: Centralized endpoint configuration in `api-config.js`
3. **Health Check**: Automatic backend connectivity verification on page load
4. **Consistent Models**: Field names and types match between frontend and backend

### Using the API Client

```javascript
// List all items
const {{ items }} = await apiClient.list();

// Create new item
const result = await apiClient.create({{
    {fields.get("primary", "name")}: "Example",
    {fields.get("secondary", "description")}: "Description"
}});

// Get specific item
const {{ item }} = await apiClient.get(1);

// Update item
const updated = await apiClient.update(1, {{
    {fields.get("primary", "name")}: "Updated"
}});

// Delete item
await apiClient.delete(1);
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Backend Configuration
FLASK_ENV=development
FLASK_DEBUG=1
DATABASE_URL=sqlite:///backend/database.db

# Frontend Configuration
API_BASE_URL={base_url}

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

### API Base URL

To change the backend URL, update:
1. `frontend/api-config.js` - Update `API_BASE_URL`
2. `.env` - Update `API_BASE_URL`

## Development

### Backend Development

The backend uses Flask with SQLite:

- **Hot reload**: Set `FLASK_DEBUG=1` in `.env`
- **Database reset**: Delete `backend/database.db` and restart
- **Add endpoints**: Edit `backend/app.py`
- **Modify models**: Edit `backend/models.py`

### Frontend Development

The frontend is static HTML/CSS/JavaScript:

- **Live reload**: Use a development server with hot reload
- **API integration**: All API calls use the `apiClient` object
- **Styling**: Edit `frontend/styles.css`
- **Logic**: Edit `frontend/app.js`

## Testing

### Test Backend API

```bash
# Health check
curl {base_url}/health

# List items
curl {base_url}{endpoints.get("list", "/api/items")}

# Create item
curl -X POST {base_url}{endpoints.get("create", "/api/items")} \\
  -H "Content-Type: application/json" \\
  -d '{{"{ fields.get("primary", "name") }": "Test", "{ fields.get("secondary", "description") }": "Test item"}}'
```

### Test Frontend

1. Open browser developer console (F12)
2. Check for API connectivity messages
3. Test CRUD operations through the UI
4. Monitor network requests in the Network tab

## Deployment

### Production Checklist

- [ ] Set `FLASK_ENV=production` in `.env`
- [ ] Set `FLASK_DEBUG=0` in `.env`
- [ ] Configure proper CORS origins
- [ ] Use production-grade database (PostgreSQL/MySQL)
- [ ] Enable HTTPS for both frontend and backend
- [ ] Set up proper logging and monitoring
- [ ] Configure rate limiting and security headers
- [ ] Use environment-specific API URLs

### Deployment Options

1. **Traditional Hosting**:
   - Frontend: Static hosting (Netlify, Vercel, S3)
   - Backend: Python hosting (Heroku, Railway, AWS)

2. **Container Deployment**:
   - Use provided `docker-compose.yml`
   - Deploy to Kubernetes, ECS, or similar

3. **Serverless**:
   - Frontend: CDN + Static hosting
   - Backend: AWS Lambda, Google Cloud Functions

## Troubleshooting

### Backend Issues

- **Port already in use**: Change port in `backend/app.py`
- **Database errors**: Delete `backend/database.db` and restart
- **CORS errors**: Update `CORS_ORIGINS` in backend configuration

### Frontend Issues

- **API connection failed**: Verify backend is running at `{base_url}`
- **CORS errors**: Check backend CORS configuration
- **404 errors**: Verify API endpoints match configuration

### Integration Issues

- **Data mismatch**: Verify field names in `api-config.js` match backend models
- **Authentication errors**: Check CORS and authentication headers
- **Timeout errors**: Increase timeout in API client configuration

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review backend logs for error messages
3. Check browser console for frontend errors
4. Verify API endpoints with curl/Postman

## License

Generated code is provided as-is for your use and modification.
"""


def _build_docker_compose(api_config: dict[str, Any]) -> str:
    """Generate Docker Compose configuration for integrated deployment."""
    return """version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=production
      - FLASK_DEBUG=0
      - DATABASE_URL=sqlite:///backend/database.db
    volumes:
      - ./backend:/app/backend
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped

  frontend:
    image: nginx:alpine
    ports:
      - "3000:80"
    volumes:
      - ./frontend:/usr/share/nginx/html:ro
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - backend
    restart: unless-stopped

networks:
  default:
    name: fullstack-network
"""


def _build_env_example(api_config: dict[str, Any]) -> str:
    """Generate environment variables template."""
    base_url = api_config.get("base_url", "http://localhost:8000")
    
    return f"""# Backend Configuration
FLASK_ENV=development
FLASK_DEBUG=1
DATABASE_URL=sqlite:///backend/database.db

# Frontend Configuration
API_BASE_URL={base_url}

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Server Configuration
BACKEND_PORT=8000
FRONTEND_PORT=3000

# Security (change in production)
SECRET_KEY=change-this-in-production

# Logging
LOG_LEVEL=INFO
"""


def _build_backend_dockerfile() -> str:
    """Generate a minimal backend Dockerfile matching the compose file."""
    return """FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

EXPOSE 8000

CMD ["python", "backend/app.py"]
"""


def _build_nginx_conf(api_config: dict[str, Any]) -> str:
    """Generate a minimal nginx config for serving the frontend."""
    server_name = api_config.get("server_name", "localhost")
    return f"""server {{
    listen 80;
    server_name {server_name};

    root /usr/share/nginx/html;
    index index.html;

    location / {{
        try_files $uri $uri/ /index.html;
    }}
}}
"""
