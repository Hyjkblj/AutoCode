"""
Unit tests for Express.js backend generator.
"""

import json
import pytest
from generators.express_generator import ExpressGenerator


class TestExpressGenerator:
    """Test suite for Express.js backend generator."""
    
    def test_generate_basic_backend(self):
        """Test basic Express.js backend generation."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        assert result is not None
        assert result.used_fallback is True
        assert "express_backend_generated" in result.reason
        assert len(result.files) > 0
    
    def test_generate_with_sqlite(self):
        """Test Express generation with SQLite database."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app", database="sqlite")
        
        assert "backend/server.js" in result.files
        assert "backend/config/database.js" in result.files
        assert "backend/models/resource.js" in result.files
        assert "backend/routes/resource.js" in result.files
        assert "backend/middleware/errorHandler.js" in result.files
        assert "package.json" in result.files
        assert "README.generated.md" in result.files
        
        # Check SQLite configuration
        db_config = result.files["backend/config/database.js"]
        assert "sqlite" in db_config
        assert "Sequelize" in db_config
    
    def test_generate_with_postgresql(self):
        """Test Express generation with PostgreSQL database."""
        generator = ExpressGenerator()
        result = generator.generate("Build a blog", database="postgresql")
        
        db_config = result.files["backend/config/database.js"]
        assert "postgres" in db_config
        assert "DB_NAME" in db_config
        assert "DB_USER" in db_config
        assert "DB_PASSWORD" in db_config
        
        package_json = json.loads(result.files["package.json"])
        assert "pg" in package_json["dependencies"]
        assert "sequelize" in package_json["dependencies"]
    
    def test_generate_with_mongodb(self):
        """Test Express generation with MongoDB database."""
        generator = ExpressGenerator()
        result = generator.generate("Build a user system", database="mongodb")
        
        db_config = result.files["backend/config/database.js"]
        assert "mongoose" in db_config
        assert "MONGO_URI" in db_config
        
        package_json = json.loads(result.files["package.json"])
        assert "mongoose" in package_json["dependencies"]
    
    def test_todo_resource_detection(self):
        """Test detection of todo resource from prompt."""
        generator = ExpressGenerator()
        result = generator.generate("Create a task management system")
        
        model = result.files["backend/models/resource.js"]
        assert "todo" in model.lower()
        assert "title" in model
        assert "completed" in model
    
    def test_blog_resource_detection(self):
        """Test detection of blog resource from prompt."""
        generator = ExpressGenerator()
        result = generator.generate("Build a blog platform")
        
        model = result.files["backend/models/resource.js"]
        assert "Post" in model
        assert "title" in model
        assert "content" in model
    
    def test_user_resource_detection(self):
        """Test detection of user resource from prompt."""
        generator = ExpressGenerator()
        result = generator.generate("Create a user management system")
        
        model = result.files["backend/models/resource.js"]
        assert "User" in model
        assert "name" in model
        assert "email" in model
    
    def test_server_structure(self):
        """Test Express server structure."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        server = result.files["backend/server.js"]
        assert "const express = require('express')" in server
        assert "const cors = require('cors')" in server
        assert "const helmet = require('helmet')" in server
        assert "app.use(cors())" in server
        assert "app.use(helmet())" in server
        assert "app.listen(" in server
    
    def test_routes_structure(self):
        """Test Express routes structure."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        routes = result.files["backend/routes/resource.js"]
        assert "router.get('/'," in routes  # List
        assert "router.post('/'," in routes  # Create
        assert "router.get('/:id'," in routes  # Get
        assert "router.put('/:id'," in routes  # Update
        assert "router.delete('/:id'," in routes  # Delete
    
    def test_error_handler_middleware(self):
        """Test error handler middleware."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        error_handler = result.files["backend/middleware/errorHandler.js"]
        assert "const errorHandler = (err, req, res, next)" in error_handler
        assert "ValidationError" in error_handler
        assert "CastError" in error_handler
        assert "SequelizeValidationError" in error_handler
    
    def test_models_with_sequelize(self):
        """Test Sequelize models structure."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app", database="sqlite")
        
        model = result.files["backend/models/resource.js"]
        assert "const { DataTypes } = require('sequelize')" in model
        assert "sequelize.define" in model
        assert "timestamps: true" in model
        assert "createdAt:" in model
        assert "updatedAt:" in model
    
    def test_models_with_mongoose(self):
        """Test Mongoose models structure."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app", database="mongodb")
        
        model = result.files["backend/models/resource.js"]
        assert "const mongoose = require('mongoose')" in model
        assert "new mongoose.Schema" in model
        assert "timestamps: true" in model
    
    def test_package_json_structure(self):
        """Test package.json structure."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        package_json = json.loads(result.files["package.json"])
        assert package_json["name"] == "express-backend"
        assert "version" in package_json
        assert "dependencies" in package_json
        assert "devDependencies" in package_json
        assert "scripts" in package_json
        assert "start" in package_json["scripts"]
        assert "dev" in package_json["scripts"]
    
    def test_package_json_dependencies(self):
        """Test package.json dependencies."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        package_json = json.loads(result.files["package.json"])
        deps = package_json["dependencies"]
        assert "express" in deps
        assert "cors" in deps
        assert "helmet" in deps
        assert "morgan" in deps
        assert "dotenv" in deps
    
    def test_env_example_generation(self):
        """Test .env.example generation."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app", database="postgresql")
        
        env_example = result.files["backend/.env.example"]
        assert "PORT=" in env_example
        assert "NODE_ENV=" in env_example
        assert "DB_TYPE=" in env_example
        assert "DB_HOST=" in env_example
        assert "DB_NAME=" in env_example
    
    def test_gitignore_generation(self):
        """Test .gitignore generation."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        gitignore = result.files[".gitignore"]
        assert "node_modules/" in gitignore
        assert ".env" in gitignore
        assert "*.log" in gitignore
        assert "*.sqlite" in gitignore
    
    def test_readme_generation(self):
        """Test README generation."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo management system")
        
        readme = result.files["README.generated.md"]
        assert "# Generated Express.js Backend" in readme
        assert "Build a todo management system" in readme
        assert "## Stack" in readme
        assert "Express.js" in readme
        assert "## Installation" in readme
        assert "npm install" in readme
    
    def test_health_check_endpoint(self):
        """Test health check endpoint."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        server = result.files["backend/server.js"]
        assert "app.get('/health'" in server
        assert "status: 'ok'" in server
    
    def test_validation_in_routes(self):
        """Test validation in routes."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        routes = result.files["backend/routes/resource.js"]
        assert "Validation error" in routes
        assert "is required" in routes
        assert "400" in routes or "status(400)" in routes
    
    def test_error_responses_in_routes(self):
        """Test error responses in routes."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        routes = result.files["backend/routes/resource.js"]
        assert "404" in routes or "status(404)" in routes
        assert "Not found" in routes
        assert "201" in routes or "status(201)" in routes
    
    def test_database_initialization(self):
        """Test database initialization."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        server = result.files["backend/server.js"]
        assert "initDatabase()" in server
        db_config = result.files["backend/config/database.js"]
        assert "const initDatabase = async () =>" in db_config
    
    def test_models_index_generation(self):
        """Test models index file generation."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        models_index = result.files["backend/models/index.js"]
        assert "require('./" in models_index
        assert "module.exports = {" in models_index
    
    def test_routes_index_generation(self):
        """Test routes index file generation."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        routes_index = result.files["backend/routes/index.js"]
        assert "const express = require('express')" in routes_index
        assert "const router = express.Router()" in routes_index
        assert "router.use('/" in routes_index
    
    def test_default_resource_fallback(self):
        """Test fallback to default resource when no match."""
        generator = ExpressGenerator()
        result = generator.generate("Build something generic")
        
        model = result.files["backend/models/resource.js"]
        assert "Record" in model
        assert "name" in model
        assert "description" in model
    
    def test_async_await_usage(self):
        """Test async/await usage in routes."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        routes = result.files["backend/routes/resource.js"]
        assert "async (req, res, next)" in routes
        assert "await " in routes
        assert "try {" in routes
        assert "catch (error)" in routes
    
    def test_middleware_usage(self):
        """Test middleware usage in server."""
        generator = ExpressGenerator()
        result = generator.generate("Build a todo app")
        
        server = result.files["backend/server.js"]
        assert "app.use(express.json())" in server
        assert "app.use(express.urlencoded" in server
        assert "app.use(morgan(" in server
