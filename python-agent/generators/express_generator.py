from __future__ import annotations

from pathlib import Path

from generators import GeneratedProjectResult


_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "requirements"
_GENERATED_EXPRESS_REQUIREMENTS = _TEMPLATE_DIR / "generated-express.txt"


class ExpressGenerator:
    """Generator for Express.js backends with configurable database support."""
    
    def generate(self, prompt: str, database: str = "sqlite") -> GeneratedProjectResult:
        """
        Generate an Express.js backend application.
        
        Args:
            prompt: User requirement description
            database: Database type (sqlite, postgresql, mongodb)
            
        Returns:
            GeneratedProjectResult with all necessary Express.js files
        """
        config = _resource_config(prompt)
        config["database"] = database
        
        files = {
            "backend/server.js": _build_server_js(config),
            "backend/models/index.js": _build_models_index_js(config),
            "backend/models/resource.js": _build_resource_model_js(config),
            "backend/routes/index.js": _build_routes_index_js(config),
            "backend/routes/resource.js": _build_resource_routes_js(config),
            "backend/middleware/errorHandler.js": _build_error_handler_js(),
            "backend/config/database.js": _build_database_config_js(config),
            "backend/.env.example": _build_env_example(config),
            "package.json": _build_package_json(config),
            ".gitignore": _build_gitignore(),
            "README.generated.md": _build_readme(prompt, config),
        }
        
        return GeneratedProjectResult(
            files=files,
            used_fallback=True,
            reason=f"express_backend_generated_with_{database}"
        )


def _load_generated_express_requirements(database: str) -> str:
    """Load Express.js package.json dependencies."""
    try:
        content = _GENERATED_EXPRESS_REQUIREMENTS.read_text(encoding="utf-8")
        if content.strip():
            return content
    except OSError:
        pass
    
    return ""


def _resource_config(prompt: str) -> dict[str, str]:
    """Extract resource configuration from prompt."""
    text = (prompt or "").strip().lower()
    
    if any(token in text for token in ("todo", "待办", "task")):
        return {
            "resource_name": "todo",
            "resource_name_cap": "Todo",
            "resource_plural": "todos",
            "primary_field": "title",
            "secondary_field": "completed",
            "secondary_type": "Boolean",
            "secondary_default": "false",
            "secondary_mongoose_type": "Boolean",
        }
    if any(token in text for token in ("blog", "博客", "post", "article")):
        return {
            "resource_name": "post",
            "resource_name_cap": "Post",
            "resource_plural": "posts",
            "primary_field": "title",
            "secondary_field": "content",
            "secondary_type": "String",
            "secondary_default": "''",
            "secondary_mongoose_type": "String",
        }
    if any(token in text for token in ("user", "用户", "account", "member")):
        return {
            "resource_name": "user",
            "resource_name_cap": "User",
            "resource_plural": "users",
            "primary_field": "name",
            "secondary_field": "email",
            "secondary_type": "String",
            "secondary_default": "''",
            "secondary_mongoose_type": "String",
        }
    
    return {
        "resource_name": "record",
        "resource_name_cap": "Record",
        "resource_plural": "records",
        "primary_field": "name",
        "secondary_field": "description",
        "secondary_type": "String",
        "secondary_default": "''",
        "secondary_mongoose_type": "String",
    }


def _build_server_js(config: dict[str, str]) -> str:
    """Generate Express.js server entry point."""
    return f'''const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
require('dotenv').config();

const {{ initDatabase }} = require('./config/database');
const routes = require('./routes');
const errorHandler = require('./middleware/errorHandler');

const app = express();
const PORT = process.env.PORT || 8000;

// Middleware
app.use(helmet());
app.use(cors());
app.use(morgan('combined'));
app.use(express.json());
app.use(express.urlencoded({{ extended: true }}));

// Health check endpoint
app.get('/health', (req, res) => {{
  res.json({{
    status: 'ok',
    framework: 'express',
    database: process.env.DB_TYPE || 'sqlite',
  }});
}});

// API routes
app.use('/api', routes);

// Error handling middleware
app.use(errorHandler);

// Initialize database and start server
initDatabase()
  .then(() => {{
    app.listen(PORT, '0.0.0.0', () => {{
      console.log(`Server running on http://0.0.0.0:${{PORT}}`);
      console.log(`Database: ${{process.env.DB_TYPE || 'sqlite'}}`);
    }});
  }})
  .catch((error) => {{
    console.error('Failed to initialize database:', error);
    process.exit(1);
  }});

module.exports = app;
'''


def _build_database_config_js(config: dict[str, str]) -> str:
    """Generate database configuration."""
    database = config.get("database", "sqlite")
    
    if database == "mongodb":
        return '''const mongoose = require('mongoose');

const initDatabase = async () => {
  try {
    const mongoUri = process.env.MONGO_URI || 'mongodb://localhost:27017/express_db';
    
    await mongoose.connect(mongoUri, {
      useNewUrlParser: true,
      useUnifiedTopology: true,
    });
    
    console.log('MongoDB connected successfully');
    
    mongoose.connection.on('error', (err) => {
      console.error('MongoDB connection error:', err);
    });
    
    mongoose.connection.on('disconnected', () => {
      console.log('MongoDB disconnected');
    });
    
  } catch (error) {
    console.error('MongoDB connection failed:', error);
    throw error;
  }
};

module.exports = { initDatabase };
'''
    elif database == "postgresql":
        return '''const { Sequelize } = require('sequelize');

const sequelize = new Sequelize({
  dialect: 'postgres',
  host: process.env.DB_HOST || 'localhost',
  port: process.env.DB_PORT || 5432,
  database: process.env.DB_NAME || 'express_db',
  username: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
  logging: process.env.NODE_ENV === 'development' ? console.log : false,
  pool: {
    max: 10,
    min: 0,
    acquire: 30000,
    idle: 10000,
  },
});

const initDatabase = async () => {
  try {
    await sequelize.authenticate();
    console.log('PostgreSQL connected successfully');
    
    // Sync models (create tables if they don't exist)
    await sequelize.sync({ alter: process.env.NODE_ENV === 'development' });
    console.log('Database synchronized');
    
  } catch (error) {
    console.error('PostgreSQL connection failed:', error);
    throw error;
  }
};

module.exports = { sequelize, initDatabase };
'''
    else:  # sqlite
        return '''const { Sequelize } = require('sequelize');
const path = require('path');

const sequelize = new Sequelize({
  dialect: 'sqlite',
  storage: path.join(__dirname, '..', 'database.sqlite'),
  logging: process.env.NODE_ENV === 'development' ? console.log : false,
});

const initDatabase = async () => {
  try {
    await sequelize.authenticate();
    console.log('SQLite connected successfully');
    
    // Sync models (create tables if they don't exist)
    await sequelize.sync({ alter: process.env.NODE_ENV === 'development' });
    console.log('Database synchronized');
    
  } catch (error) {
    console.error('SQLite connection failed:', error);
    throw error;
  }
};

module.exports = { sequelize, initDatabase };
'''


def _build_models_index_js(config: dict[str, str]) -> str:
    """Generate models index file."""
    resource_name_cap = config["resource_name_cap"]
    
    return f'''const {resource_name_cap} = require('./{config["resource_name"]}');

module.exports = {{
  {resource_name_cap},
}};
'''


def _build_resource_model_js(config: dict[str, str]) -> str:
    """Generate resource model."""
    database = config.get("database", "sqlite")
    resource_name_cap = config["resource_name_cap"]
    primary_field = config["primary_field"]
    secondary_field = config["secondary_field"]
    
    if database == "mongodb":
        secondary_type = config["secondary_mongoose_type"]
        secondary_default = config["secondary_default"]
        
        return f'''const mongoose = require('mongoose');

const {config["resource_name"]}Schema = new mongoose.Schema({{
  {primary_field}: {{
    type: String,
    required: true,
    maxlength: 200,
    index: true,
  }},
  {secondary_field}: {{
    type: {secondary_type},
    default: {secondary_default},
  }},
}}, {{
  timestamps: true,
  toJSON: {{
    transform: (doc, ret) => {{
      ret.id = ret._id.toString();
      delete ret._id;
      delete ret.__v;
      ret.createdAt = ret.createdAt;
      ret.updatedAt = ret.updatedAt;
      return ret;
    }},
  }},
}});

const {resource_name_cap} = mongoose.model('{resource_name_cap}', {config["resource_name"]}Schema);

module.exports = {resource_name_cap};
'''
    else:  # sequelize (sqlite/postgresql)
        secondary_type = config["secondary_type"]
        secondary_default = config["secondary_default"]
        
        return f'''const {{ DataTypes }} = require('sequelize');
const {{ sequelize }} = require('../config/database');

const {resource_name_cap} = sequelize.define('{resource_name_cap}', {{
  id: {{
    type: DataTypes.INTEGER,
    primaryKey: true,
    autoIncrement: true,
  }},
  {primary_field}: {{
    type: DataTypes.STRING(200),
    allowNull: false,
  }},
  {secondary_field}: {{
    type: DataTypes.{secondary_type.upper()},
    defaultValue: {secondary_default},
    allowNull: false,
  }},
}}, {{
  tableName: '{config["resource_plural"]}',
  timestamps: true,
  createdAt: 'createdAt',
  updatedAt: 'updatedAt',
  indexes: [
    {{ fields: ['{primary_field}'] }},
    {{ fields: ['createdAt'] }},
  ],
}});

module.exports = {resource_name_cap};
'''


def _build_routes_index_js(config: dict[str, str]) -> str:
    """Generate routes index file."""
    resource_plural = config["resource_plural"]
    
    return f'''const express = require('express');
const router = express.Router();

const {config["resource_name"]}Routes = require('./{config["resource_name"]}');

router.use('/{resource_plural}', {config["resource_name"]}Routes);

module.exports = router;
'''


def _build_resource_routes_js(config: dict[str, str]) -> str:
    """Generate resource routes."""
    resource_name_cap = config["resource_name_cap"]
    primary_field = config["primary_field"]
    secondary_field = config["secondary_field"]
    
    return f'''const express = require('express');
const router = express.Router();
const {{ {resource_name_cap} }} = require('../models');

// List all items
router.get('/', async (req, res, next) => {{
  try {{
    const items = await {resource_name_cap}.find ? 
      await {resource_name_cap}.find().sort({{ _id: -1 }}) : // MongoDB
      await {resource_name_cap}.findAll({{ order: [['id', 'DESC']] }}); // Sequelize
    
    res.json({{
      items: items,
      total: items.length,
    }});
  }} catch (error) {{
    next(error);
  }}
}});

// Create new item
router.post('/', async (req, res, next) => {{
  try {{
    const {{ {primary_field}, {secondary_field} }} = req.body;
    
    // Validation
    if (!{primary_field} || !{primary_field}.trim()) {{
      return res.status(400).json({{
        error: 'Validation error',
        message: '{primary_field} is required and cannot be empty',
      }});
    }}
    
    if ({secondary_field} === undefined || {secondary_field} === null) {{
      return res.status(400).json({{
        error: 'Validation error',
        message: '{secondary_field} is required',
      }});
    }}
    
    const item = await {resource_name_cap}.create({{
      {primary_field}: {primary_field}.trim(),
      {secondary_field},
    }});
    
    res.status(201).json({{
      item: item,
      message: '{resource_name_cap} created successfully',
    }});
  }} catch (error) {{
    next(error);
  }}
}});

// Get single item
router.get('/:id', async (req, res, next) => {{
  try {{
    const {{ id }} = req.params;
    
    const item = await {resource_name_cap}.findByPk ? 
      await {resource_name_cap}.findByPk(id) : // Sequelize
      await {resource_name_cap}.findById(id); // MongoDB
    
    if (!item) {{
      return res.status(404).json({{
        error: 'Not found',
        message: `{resource_name_cap} with id ${{id}} not found`,
      }});
    }}
    
    res.json({{ item }});
  }} catch (error) {{
    next(error);
  }}
}});

// Update item
router.put('/:id', async (req, res, next) => {{
  try {{
    const {{ id }} = req.params;
    const {{ {primary_field}, {secondary_field} }} = req.body;
    
    const item = await {resource_name_cap}.findByPk ? 
      await {resource_name_cap}.findByPk(id) : // Sequelize
      await {resource_name_cap}.findById(id); // MongoDB
    
    if (!item) {{
      return res.status(404).json({{
        error: 'Not found',
        message: `{resource_name_cap} with id ${{id}} not found`,
      }});
    }}
    
    // Validation
    if (!{primary_field} || !{primary_field}.trim()) {{
      return res.status(400).json({{
        error: 'Validation error',
        message: '{primary_field} is required and cannot be empty',
      }});
    }}
    
    if ({secondary_field} === undefined || {secondary_field} === null) {{
      return res.status(400).json({{
        error: 'Validation error',
        message: '{secondary_field} is required',
      }});
    }}
    
    // Update item
    if (item.update) {{
      // Sequelize
      await item.update({{
        {primary_field}: {primary_field}.trim(),
        {secondary_field},
      }});
    }} else {{
      // MongoDB
      item.{primary_field} = {primary_field}.trim();
      item.{secondary_field} = {secondary_field};
      await item.save();
    }}
    
    res.json({{
      item,
      message: '{resource_name_cap} updated successfully',
    }});
  }} catch (error) {{
    next(error);
  }}
}});

// Delete item
router.delete('/:id', async (req, res, next) => {{
  try {{
    const {{ id }} = req.params;
    
    const item = await {resource_name_cap}.findByPk ? 
      await {resource_name_cap}.findByPk(id) : // Sequelize
      await {resource_name_cap}.findById(id); // MongoDB
    
    if (!item) {{
      return res.status(404).json({{
        error: 'Not found',
        message: `{resource_name_cap} with id ${{id}} not found`,
      }});
    }}
    
    await item.destroy ? item.destroy() : item.deleteOne(); // Sequelize or MongoDB
    
    res.json({{
      deleted: true,
      id: id,
      message: '{resource_name_cap} deleted successfully',
    }});
  }} catch (error) {{
    next(error);
  }}
}});

module.exports = router;
'''


def _build_error_handler_js() -> str:
    """Generate error handling middleware."""
    return '''const errorHandler = (err, req, res, next) => {
  console.error('Error:', err);
  
  // Mongoose validation error
  if (err.name === 'ValidationError') {
    return res.status(400).json({
      error: 'Validation error',
      message: err.message,
      details: err.errors,
    });
  }
  
  // Mongoose cast error (invalid ID)
  if (err.name === 'CastError') {
    return res.status(400).json({
      error: 'Invalid ID',
      message: 'The provided ID is not valid',
    });
  }
  
  // Sequelize validation error
  if (err.name === 'SequelizeValidationError') {
    return res.status(400).json({
      error: 'Validation error',
      message: err.message,
      details: err.errors,
    });
  }
  
  // Default error
  res.status(err.status || 500).json({
    error: err.name || 'Internal Server Error',
    message: err.message || 'An unexpected error occurred',
  });
};

module.exports = errorHandler;
'''


def _build_package_json(config: dict[str, str]) -> str:
    """Generate package.json."""
    database = config.get("database", "sqlite")
    
    dependencies = {
        "express": "^4.18.2",
        "cors": "^2.8.5",
        "helmet": "^7.1.0",
        "morgan": "^1.10.0",
        "dotenv": "^16.3.1",
    }
    
    if database == "mongodb":
        dependencies["mongoose"] = "^8.0.3"
    elif database == "postgresql":
        dependencies["sequelize"] = "^6.35.2"
        dependencies["pg"] = "^8.11.3"
        dependencies["pg-hstore"] = "^2.3.4"
    else:  # sqlite
        dependencies["sequelize"] = "^6.35.2"
        dependencies["sqlite3"] = "^5.1.6"
    
    import json
    
    package = {
        "name": "express-backend",
        "version": "1.0.0",
        "description": "Generated Express.js backend with CRUD operations",
        "main": "backend/server.js",
        "scripts": {
            "start": "node backend/server.js",
            "dev": "nodemon backend/server.js",
            "test": 'echo "Error: no test specified" && exit 1'
        },
        "keywords": ["express", "rest", "api", "crud"],
        "author": "",
        "license": "MIT",
        "dependencies": dependencies,
        "devDependencies": {
            "nodemon": "^3.0.2"
        },
        "engines": {
            "node": ">=18.0.0"
        }
    }
    
    return json.dumps(package, indent=2)


def _build_env_example(config: dict[str, str]) -> str:
    """Generate .env.example file."""
    database = config.get("database", "sqlite")
    
    env_vars = [
        "# Server configuration",
        "PORT=8000",
        "NODE_ENV=development",
        "",
        "# Database configuration",
        f"DB_TYPE={database}",
    ]
    
    if database == "postgresql":
        env_vars.extend([
            "DB_HOST=localhost",
            "DB_PORT=5432",
            "DB_NAME=express_db",
            "DB_USER=postgres",
            "DB_PASSWORD=postgres",
        ])
    elif database == "mongodb":
        env_vars.extend([
            "MONGO_URI=mongodb://localhost:27017/express_db",
        ])
    
    return "\n".join(env_vars) + "\n"


def _build_gitignore() -> str:
    """Generate .gitignore file."""
    return """# Dependencies
node_modules/
package-lock.json
yarn.lock

# Environment variables
.env

# Database
*.sqlite
*.db

# Logs
logs/
*.log
npm-debug.log*

# OS files
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo
"""


def _build_readme(prompt: str, config: dict[str, str]) -> str:
    """Generate comprehensive README."""
    resource_plural = config["resource_plural"]
    database = config.get("database", "sqlite")
    
    db_setup = ""
    if database == "postgresql":
        db_setup = """
## Database Setup (PostgreSQL)

1. Install PostgreSQL
2. Create database:
```bash
createdb express_db
```

3. Configure environment variables in `.env`:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=express_db
DB_USER=postgres
DB_PASSWORD=your_password
```
"""
    elif database == "mongodb":
        db_setup = """
## Database Setup (MongoDB)

1. Install MongoDB
2. Start MongoDB service
3. Configure environment variables in `.env`:
```
MONGO_URI=mongodb://localhost:27017/express_db
```
"""
    
    return f'''# Generated Express.js Backend

This backend was generated from the following requirement:

> {prompt.strip() or "Build a CRUD backend service"}

## Stack

- **Express.js 4.18.2**: Fast, unopinionated web framework for Node.js
- **Database**: {database.upper()}
- **Helmet**: Security middleware
- **Morgan**: HTTP request logger
- **CORS**: Cross-Origin Resource Sharing support

## Features

- ✅ RESTful API with Express.js
- ✅ Comprehensive CRUD operations
- ✅ Proper error handling and validation
- ✅ Security headers with Helmet
- ✅ Request logging with Morgan
- ✅ CORS support for frontend integration
- ✅ Environment-based configuration
- ✅ Automatic timestamp management
- ✅ Database connection pooling
- ✅ Production-ready architecture

## Installation

```bash
npm install
```
{db_setup}
## Configuration

1. Copy `.env.example` to `.env`:
```bash
cp backend/.env.example .env
```

2. Update environment variables as needed

## Running the Application

```bash
# Development mode with auto-reload
npm run dev

# Production mode
npm start
```

The application will start on `http://0.0.0.0:8000`

## API Endpoints

### Health Check
- `GET /health` - Check application and database health

### {config["resource_name_cap"]} CRUD Operations
- `GET /api/{resource_plural}` - List all items
- `POST /api/{resource_plural}` - Create a new item
- `GET /api/{resource_plural}/{{id}}` - Get a specific item
- `PUT /api/{resource_plural}/{{id}}` - Update an item
- `DELETE /api/{resource_plural}/{{id}}` - Delete an item

## Request/Response Examples

### Create Item
```bash
curl -X POST http://localhost:8000/api/{resource_plural} \\
  -H "Content-Type: application/json" \\
  -d '{{"title": "Example Task", "completed": false}}'
```

Response (201 Created):
```json
{{
  "item": {{
    "id": 1,
    "title": "Example Task",
    "completed": false,
    "createdAt": "2024-01-01T12:00:00.000Z",
    "updatedAt": "2024-01-01T12:00:00.000Z"
  }},
  "message": "{config["resource_name_cap"]} created successfully"
}}
```

### List Items
```bash
curl http://localhost:8000/api/{resource_plural}
```

Response (200 OK):
```json
{{
  "items": [
    {{
      "id": 1,
      "title": "Example Task",
      "completed": false,
      "createdAt": "2024-01-01T12:00:00.000Z",
      "updatedAt": "2024-01-01T12:00:00.000Z"
    }}
  ],
  "total": 1
}}
```

### Get Single Item
```bash
curl http://localhost:8000/api/{resource_plural}/1
```

Response (200 OK):
```json
{{
  "item": {{
    "id": 1,
    "title": "Example Task",
    "completed": false,
    "createdAt": "2024-01-01T12:00:00.000Z",
    "updatedAt": "2024-01-01T12:00:00.000Z"
  }}
}}
```

### Update Item
```bash
curl -X PUT http://localhost:8000/api/{resource_plural}/1 \\
  -H "Content-Type: application/json" \\
  -d '{{"title": "Updated Task", "completed": true}}'
```

Response (200 OK):
```json
{{
  "item": {{
    "id": 1,
    "title": "Updated Task",
    "completed": true,
    "createdAt": "2024-01-01T12:00:00.000Z",
    "updatedAt": "2024-01-01T12:30:00.000Z"
  }},
  "message": "{config["resource_name_cap"]} updated successfully"
}}
```

### Delete Item
```bash
curl -X DELETE http://localhost:8000/api/{resource_plural}/1
```

Response (200 OK):
```json
{{
  "deleted": true,
  "id": "1",
  "message": "{config["resource_name_cap"]} deleted successfully"
}}
```

## Error Handling

The API returns appropriate HTTP status codes:

- `200 OK` - Successful GET, PUT, DELETE operations
- `201 Created` - Successful POST operation
- `400 Bad Request` - Validation errors or invalid input
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server errors

Error response format:
```json
{{
  "error": "Validation error",
  "message": "title is required and cannot be empty"
}}
```

## Project Structure

```
backend/
├── server.js              # Application entry point
├── config/
│   └── database.js        # Database configuration
├── models/
│   ├── index.js           # Models index
│   └── {config["resource_name"]}.js         # Resource model
├── routes/
│   ├── index.js           # Routes index
│   └── {config["resource_name"]}.js         # Resource routes
└── middleware/
    └── errorHandler.js    # Error handling middleware
```

## Database Schema

The application automatically creates the database schema:

- **id**: Primary key (auto-increment)
- **{config["primary_field"]}**: Primary field (indexed, max 200 chars)
- **{config["secondary_field"]}**: Secondary field
- **createdAt**: Creation timestamp (auto-managed)
- **updatedAt**: Update timestamp (auto-managed)

## Development

### Hot Reload
The development server uses nodemon for automatic restart on file changes:
```bash
npm run dev
```

### Environment Variables
All configuration is managed through environment variables in `.env` file.

## Production Deployment

For production deployment:

1. **Set NODE_ENV**: `NODE_ENV=production`
2. **Use production database**: PostgreSQL or MongoDB recommended
3. **Enable HTTPS**: Use reverse proxy (nginx, Apache)
4. **Process manager**: Use PM2 or systemd
5. **Environment variables**: Set all required variables
6. **Security**: Review and update CORS settings
7. **Monitoring**: Add logging and monitoring tools

Example with PM2:
```bash
npm install -g pm2
pm2 start backend/server.js --name express-api
pm2 save
pm2 startup
```

## Performance

Express.js is known for:
- High performance and low overhead
- Excellent for microservices
- Large ecosystem of middleware
- Scalable architecture

## Security

Security features included:
- Helmet middleware for security headers
- CORS configuration
- Input validation
- Error handling without exposing internals
- Environment-based configuration

## Testing

To add tests, install testing framework:
```bash
npm install --save-dev jest supertest
```

Create tests in `__tests__/` directory.

## License

MIT
'''
