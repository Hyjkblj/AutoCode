"""
Property-based tests for backend generation completeness.

Task 10.4: Write property tests for backend generation
Property 9: Backend Generation Completeness
Validates: Requirements 3.1, 3.2

These tests validate that "For any backend generation task, the Backend_Generator 
SHALL produce all required components (Flask app, SQLite database, models, routes, 
requirements.txt, README)."
"""

from __future__ import annotations

import ast
import re
from hypothesis import given, strategies as st, assume, settings
from generators.backend_generator import BackendGenerator


# Strategy for generating valid prompts with various resource types
resource_keywords_strategy = st.sampled_from([
    "todo", "待办", "task",
    "blog", "博客", "post", "article",
    "user", "用户", "account", "member",
    "product", "item", "record", "data"
])

# Strategy for generating prompt prefixes
prompt_prefix_strategy = st.sampled_from([
    "build a", "create a", "generate a", "make a",
    "构建一个", "创建一个", "生成一个",
    "Build a", "Create a", "Generate a",
    "I need a", "I want a", "Please create a"
])

# Strategy for generating prompt suffixes
prompt_suffix_strategy = st.sampled_from([
    "backend", "backend app", "backend service", "API",
    "后端", "后端应用", "后端服务",
    "REST API", "web service", "application"
])

# Strategy for generating complete prompts
valid_prompt_strategy = st.builds(
    lambda prefix, resource, suffix: f"{prefix} {resource} {suffix}",
    prompt_prefix_strategy,
    resource_keywords_strategy,
    prompt_suffix_strategy
)

# Strategy for generating edge case prompts
edge_case_prompt_strategy = st.one_of(
    st.just(""),  # Empty prompt
    st.text(min_size=0, max_size=5, alphabet=st.characters(whitelist_categories=("Zs",))),  # Whitespace only
    st.text(min_size=1, max_size=10),  # Random short text
    st.builds(lambda word: word * 50, st.text(min_size=1, max_size=10)),  # Very long repetitive text
)

# Strategy for all prompts (valid + edge cases)
all_prompts_strategy = st.one_of(
    valid_prompt_strategy,
    edge_case_prompt_strategy
)


class TestBackendGenerationCompletenessProperty:
    """
    Property-based tests for backend generation completeness.
    
    **Task 10.4: Write property tests for backend generation**
    **Property 9: Backend Generation Completeness**
    **Validates: Requirements 3.1, 3.2**
    
    These tests verify that for any backend generation task, the Backend_Generator
    produces all required components.
    """
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_9_all_required_files_present(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Required Files**
        
        For any backend generation task, the Backend_Generator SHALL produce 
        all required files: Flask app, models, database config, requirements.txt, 
        and README.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        
        # Generate backend from prompt
        result = generator.generate(prompt)
        
        # Verify all required files are present
        required_files = [
            "backend/app.py",
            "backend/models.py",
            "backend/database.py",
            "requirements.txt",
            "README.generated.md"
        ]
        
        for required_file in required_files:
            assert required_file in result.files, \
                f"Required file '{required_file}' missing for prompt: {prompt!r}"
            assert result.files[required_file], \
                f"Required file '{required_file}' is empty for prompt: {prompt!r}"
            assert len(result.files[required_file]) > 0, \
                f"Required file '{required_file}' has no content for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_9_flask_app_structure(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Flask App Structure**
        
        For any backend generation task, the generated Flask app SHALL contain 
        all essential components: Flask instance, CORS, database initialization, 
        and route definitions.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify Flask app structure
        assert "from flask import Flask" in app_code, \
            f"Flask import missing for prompt: {prompt!r}"
        assert "app = Flask(__name__)" in app_code, \
            f"Flask app instance missing for prompt: {prompt!r}"
        assert "from flask_cors import CORS" in app_code, \
            f"CORS import missing for prompt: {prompt!r}"
        assert "CORS(app)" in app_code, \
            f"CORS initialization missing for prompt: {prompt!r}"
        assert "init_db(app)" in app_code, \
            f"Database initialization missing for prompt: {prompt!r}"
        assert 'if __name__ == "__main__":' in app_code, \
            f"Main block missing for prompt: {prompt!r}"
        assert "app.run(" in app_code, \
            f"App run call missing for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_9_sqlalchemy_models_structure(self, prompt):
        """
        **Property 9: Backend Generation Completeness - SQLAlchemy Models**
        
        For any backend generation task, the generated models SHALL use SQLAlchemy 
        ORM with proper model definition, fields, and serialization methods.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        models_code = result.files["backend/models.py"]
        
        # Verify SQLAlchemy model structure
        assert "from database import db" in models_code, \
            f"Database import missing for prompt: {prompt!r}"
        assert "db.Model" in models_code, \
            f"SQLAlchemy Model inheritance missing for prompt: {prompt!r}"
        assert "__tablename__" in models_code, \
            f"Table name definition missing for prompt: {prompt!r}"
        assert "db.Column" in models_code, \
            f"Column definitions missing for prompt: {prompt!r}"
        assert "primary_key=True" in models_code, \
            f"Primary key definition missing for prompt: {prompt!r}"
        assert "def to_dict(self)" in models_code, \
            f"Serialization method missing for prompt: {prompt!r}"
        
        # Verify model metadata constants
        assert "TABLE_NAME = " in models_code, \
            f"TABLE_NAME constant missing for prompt: {prompt!r}"
        assert "RESOURCE_NAME = " in models_code, \
            f"RESOURCE_NAME constant missing for prompt: {prompt!r}"
        assert "RESOURCE_LABEL = " in models_code, \
            f"RESOURCE_LABEL constant missing for prompt: {prompt!r}"
        assert "PRIMARY_FIELD = " in models_code, \
            f"PRIMARY_FIELD constant missing for prompt: {prompt!r}"
        assert "SECONDARY_FIELD = " in models_code, \
            f"SECONDARY_FIELD constant missing for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_9_database_configuration(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Database Configuration**
        
        For any backend generation task, the generated database configuration 
        SHALL include SQLAlchemy setup, database initialization, and table creation.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        database_code = result.files["backend/database.py"]
        
        # Verify database configuration
        assert "from flask_sqlalchemy import SQLAlchemy" in database_code, \
            f"SQLAlchemy import missing for prompt: {prompt!r}"
        assert "db = SQLAlchemy()" in database_code, \
            f"SQLAlchemy instance missing for prompt: {prompt!r}"
        assert "def init_db(app)" in database_code, \
            f"Database initialization function missing for prompt: {prompt!r}"
        assert "SQLALCHEMY_DATABASE_URI" in database_code, \
            f"Database URI configuration missing for prompt: {prompt!r}"
        assert "sqlite:///" in database_code, \
            f"SQLite database path missing for prompt: {prompt!r}"
        assert "db.init_app(app)" in database_code, \
            f"Database app initialization missing for prompt: {prompt!r}"
        assert "db.create_all()" in database_code, \
            f"Table creation missing for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_9_crud_routes_completeness(self, prompt):
        """
        **Property 9: Backend Generation Completeness - CRUD Routes**
        
        For any backend generation task, the generated Flask app SHALL include 
        all CRUD operations: Create (POST), Read (GET), Update (PUT), Delete (DELETE).
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify CRUD route decorators
        assert "@app.get(" in app_code, \
            f"GET route decorator missing for prompt: {prompt!r}"
        assert "@app.post(" in app_code, \
            f"POST route decorator missing for prompt: {prompt!r}"
        assert "@app.put(" in app_code, \
            f"PUT route decorator missing for prompt: {prompt!r}"
        assert "@app.delete(" in app_code, \
            f"DELETE route decorator missing for prompt: {prompt!r}"
        
        # Verify CRUD function definitions
        assert "def list_items()" in app_code, \
            f"List function missing for prompt: {prompt!r}"
        assert "def create_item()" in app_code, \
            f"Create function missing for prompt: {prompt!r}"
        assert "def get_item(" in app_code, \
            f"Get function missing for prompt: {prompt!r}"
        assert "def update_item(" in app_code, \
            f"Update function missing for prompt: {prompt!r}"
        assert "def delete_item(" in app_code, \
            f"Delete function missing for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_9_health_check_endpoint(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Health Check**
        
        For any backend generation task, the generated Flask app SHALL include 
        a health check endpoint for monitoring.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify health check endpoint
        assert '@app.get("/health")' in app_code, \
            f"Health check route missing for prompt: {prompt!r}"
        assert "def health()" in app_code, \
            f"Health check function missing for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_9_requirements_txt_completeness(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Requirements.txt**
        
        For any backend generation task, the generated requirements.txt SHALL 
        include all necessary dependencies with pinned versions.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        requirements = result.files["requirements.txt"]
        
        # Verify required dependencies
        assert "flask==" in requirements, \
            f"Flask dependency missing for prompt: {prompt!r}"
        assert "flask-cors==" in requirements, \
            f"Flask-CORS dependency missing for prompt: {prompt!r}"
        assert "flask-sqlalchemy==" in requirements, \
            f"Flask-SQLAlchemy dependency missing for prompt: {prompt!r}"
        assert "sqlalchemy==" in requirements, \
            f"SQLAlchemy dependency missing for prompt: {prompt!r}"
        
        # Verify versions are pinned (not using >= or ~=)
        assert ">=" not in requirements, \
            f"Unpinned dependency version found for prompt: {prompt!r}"
        assert "~=" not in requirements, \
            f"Unpinned dependency version found for prompt: {prompt!r}"
        
        # Verify requirements ends with newline
        assert requirements.endswith("\n"), \
            f"Requirements.txt should end with newline for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_9_readme_completeness(self, prompt):
        """
        **Property 9: Backend Generation Completeness - README**
        
        For any backend generation task, the generated README SHALL include 
        documentation about the stack, installation, running, and API endpoints.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        readme = result.files["README.generated.md"]
        
        # Verify README sections
        assert "# Generated Backend App" in readme or "Generated Backend" in readme, \
            f"README title missing for prompt: {prompt!r}"
        assert "Flask" in readme, \
            f"Flask stack info missing in README for prompt: {prompt!r}"
        assert "SQLite" in readme or "SQLAlchemy" in readme, \
            f"Database stack info missing in README for prompt: {prompt!r}"
        assert "pip install" in readme, \
            f"Installation instructions missing in README for prompt: {prompt!r}"
        assert "python backend/app.py" in readme or "python" in readme, \
            f"Run instructions missing in README for prompt: {prompt!r}"
        assert "/api/" in readme, \
            f"API endpoint documentation missing in README for prompt: {prompt!r}"
        assert "GET" in readme or "POST" in readme, \
            f"HTTP method documentation missing in README for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_9_generated_code_is_valid_python(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Valid Python Syntax**
        
        For any backend generation task, all generated Python files SHALL be 
        syntactically valid and compilable.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        python_files = {
            "backend/app.py": result.files["backend/app.py"],
            "backend/models.py": result.files["backend/models.py"],
            "backend/database.py": result.files["backend/database.py"]
        }
        
        for filename, code in python_files.items():
            try:
                # Attempt to compile the code
                compile(code, filename, "exec")
            except SyntaxError as e:
                pytest.fail(
                    f"Generated {filename} has syntax error for prompt {prompt!r}: {e}"
                )
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_9_generated_code_has_proper_imports(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Proper Imports**
        
        For any backend generation task, all generated Python files SHALL include 
        proper imports and future annotations.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        python_files = {
            "backend/app.py": result.files["backend/app.py"],
            "backend/models.py": result.files["backend/models.py"],
            "backend/database.py": result.files["backend/database.py"]
        }
        
        for filename, code in python_files.items():
            assert "from __future__ import annotations" in code, \
                f"Future annotations import missing in {filename} for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_9_result_metadata_consistency(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Result Metadata**
        
        For any backend generation task, the result SHALL include consistent 
        metadata indicating fallback usage and generation reason.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        # Verify result metadata
        assert result.used_fallback is True, \
            f"Result should indicate fallback usage for prompt: {prompt!r}"
        assert result.reason == "backend_template_generated", \
            f"Result reason should be 'backend_template_generated' for prompt: {prompt!r}"
        assert isinstance(result.files, dict), \
            f"Result files should be a dictionary for prompt: {prompt!r}"
        assert len(result.files) >= 5, \
            f"Result should contain at least 5 files for prompt: {prompt!r}"


class TestBackendGenerationResourceDetectionProperty:
    """
    Property-based tests for resource type detection in backend generation.
    
    **Task 10.4: Write property tests for backend generation**
    **Property 9: Backend Generation Completeness - Resource Detection**
    **Validates: Requirements 3.1, 3.2**
    """
    
    @given(st.sampled_from(["todo", "待办", "task"]))
    @settings(deadline=None, max_examples=10)
    def test_property_9_todo_resource_detection(self, keyword):
        """
        **Property 9: Backend Generation Completeness - Todo Resource Detection**
        
        For any backend generation task containing todo-related keywords, 
        the generator SHALL create a todos resource with appropriate fields.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        prompt = f"build a {keyword} backend"
        
        result = generator.generate(prompt)
        models_code = result.files["backend/models.py"]
        
        # Verify todo resource configuration
        assert 'TABLE_NAME = "todos"' in models_code, \
            f"Todo table name not detected for keyword: {keyword}"
        assert 'RESOURCE_NAME = "todo"' in models_code, \
            f"Todo resource name not detected for keyword: {keyword}"
        assert 'RESOURCE_LABEL = "Todo"' in models_code, \
            f"Todo resource label not detected for keyword: {keyword}"
    
    @given(st.sampled_from(["blog", "博客", "post", "article"]))
    @settings(deadline=None, max_examples=10)
    def test_property_9_blog_resource_detection(self, keyword):
        """
        **Property 9: Backend Generation Completeness - Blog Resource Detection**
        
        For any backend generation task containing blog-related keywords, 
        the generator SHALL create a posts resource with appropriate fields.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        prompt = f"build a {keyword} backend"
        
        result = generator.generate(prompt)
        models_code = result.files["backend/models.py"]
        
        # Verify blog resource configuration
        assert 'TABLE_NAME = "posts"' in models_code, \
            f"Blog table name not detected for keyword: {keyword}"
        assert 'RESOURCE_NAME = "post"' in models_code, \
            f"Blog resource name not detected for keyword: {keyword}"
        assert 'RESOURCE_LABEL = "Post"' in models_code, \
            f"Blog resource label not detected for keyword: {keyword}"
    
    @given(st.sampled_from(["user", "用户", "account", "member"]))
    @settings(deadline=None, max_examples=10)
    def test_property_9_user_resource_detection(self, keyword):
        """
        **Property 9: Backend Generation Completeness - User Resource Detection**
        
        For any backend generation task containing user-related keywords, 
        the generator SHALL create a users resource with appropriate fields.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        prompt = f"build a {keyword} backend"
        
        result = generator.generate(prompt)
        models_code = result.files["backend/models.py"]
        
        # Verify user resource configuration
        assert 'TABLE_NAME = "users"' in models_code, \
            f"User table name not detected for keyword: {keyword}"
        assert 'RESOURCE_NAME = "user"' in models_code, \
            f"User resource name not detected for keyword: {keyword}"
        assert 'RESOURCE_LABEL = "User"' in models_code, \
            f"User resource label not detected for keyword: {keyword}"
    
    @given(st.text(min_size=1, max_size=50).filter(
        lambda s: not any(kw in s.lower() for kw in ["todo", "待办", "task", "blog", "博客", "post", "article", "user", "用户", "account", "member"])
    ))
    @settings(deadline=None, max_examples=20)
    def test_property_9_default_resource_detection(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Default Resource Detection**
        
        For any backend generation task without recognized keywords, 
        the generator SHALL create a generic records resource.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        
        result = generator.generate(prompt)
        models_code = result.files["backend/models.py"]
        
        # Verify default resource configuration
        assert 'TABLE_NAME = "records"' in models_code, \
            f"Default table name not used for prompt: {prompt!r}"
        assert 'RESOURCE_NAME = "record"' in models_code, \
            f"Default resource name not used for prompt: {prompt!r}"
        assert 'RESOURCE_LABEL = "Record"' in models_code, \
            f"Default resource label not used for prompt: {prompt!r}"


class TestBackendGenerationErrorHandlingProperty:
    """
    Property-based tests for error handling in generated backend code.
    
    **Task 10.4: Write property tests for backend generation**
    **Property 9: Backend Generation Completeness - Error Handling**
    **Validates: Requirements 3.1, 3.2**
    """
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_9_error_handlers_present(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Error Handlers**
        
        For any backend generation task, the generated Flask app SHALL include 
        error handlers for common HTTP error codes.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify error handler decorators
        assert "@app.errorhandler(400)" in app_code or "errorhandler(400)" in app_code, \
            f"400 error handler missing for prompt: {prompt!r}"
        assert "@app.errorhandler(404)" in app_code or "errorhandler(404)" in app_code, \
            f"404 error handler missing for prompt: {prompt!r}"
        assert "@app.errorhandler(500)" in app_code or "errorhandler(500)" in app_code, \
            f"500 error handler missing for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_9_http_status_codes_in_responses(self, prompt):
        """
        **Property 9: Backend Generation Completeness - HTTP Status Codes**
        
        For any backend generation task, the generated Flask app SHALL return 
        appropriate HTTP status codes in responses.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify HTTP status codes are used
        assert ", 200" in app_code, \
            f"200 OK status code missing for prompt: {prompt!r}"
        assert ", 201" in app_code, \
            f"201 Created status code missing for prompt: {prompt!r}"
        assert ", 400" in app_code, \
            f"400 Bad Request status code missing for prompt: {prompt!r}"
        assert ", 404" in app_code, \
            f"404 Not Found status code missing for prompt: {prompt!r}"
        assert ", 500" in app_code, \
            f"500 Internal Server Error status code missing for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_9_database_error_handling(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Database Error Handling**
        
        For any backend generation task, the generated Flask app SHALL include 
        proper database error handling with rollback.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify database error handling
        assert "SQLAlchemyError" in app_code or "Exception" in app_code, \
            f"Database exception handling missing for prompt: {prompt!r}"
        assert "db.session.rollback()" in app_code, \
            f"Database rollback missing for prompt: {prompt!r}"
        assert "db.session.commit()" in app_code, \
            f"Database commit missing for prompt: {prompt!r}"


class TestBackendGenerationAPIStructureProperty:
    """
    Property-based tests for API structure in generated backend code.
    
    **Task 10.4: Write property tests for backend generation**
    **Property 9: Backend Generation Completeness - API Structure**
    **Validates: Requirements 3.1, 3.2**
    """
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_9_api_routes_use_rest_conventions(self, prompt):
        """
        **Property 9: Backend Generation Completeness - REST Conventions**
        
        For any backend generation task, the generated API routes SHALL follow 
        RESTful conventions with proper HTTP methods and URL patterns.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify REST conventions
        # List endpoint: GET /api/resource
        assert re.search(r'@app\.get\(["\']\/api\/\w+["\']\)', app_code), \
            f"REST list endpoint pattern missing for prompt: {prompt!r}"
        
        # Create endpoint: POST /api/resource
        assert re.search(r'@app\.post\(["\']\/api\/\w+["\']\)', app_code), \
            f"REST create endpoint pattern missing for prompt: {prompt!r}"
        
        # Detail endpoints: GET/PUT/DELETE /api/resource/<id>
        assert re.search(r'@app\.(get|put|delete)\(["\']\/api\/\w+\/<int:\w+>["\']\)', app_code), \
            f"REST detail endpoint pattern missing for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_9_json_request_handling(self, prompt):
        """
        **Property 9: Backend Generation Completeness - JSON Request Handling**
        
        For any backend generation task, the generated Flask app SHALL properly 
        handle JSON request bodies.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify JSON request handling
        assert "request.get_json(" in app_code, \
            f"JSON request parsing missing for prompt: {prompt!r}"
        assert "payload" in app_code or "data" in app_code, \
            f"Request payload handling missing for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_9_input_validation(self, prompt):
        """
        **Property 9: Backend Generation Completeness - Input Validation**
        
        For any backend generation task, the generated Flask app SHALL include 
        input validation for required fields.
        
        **Validates: Requirements 3.1, 3.2**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify input validation
        assert "if not" in app_code or "is None" in app_code, \
            f"Input validation missing for prompt: {prompt!r}"
        assert "Validation error" in app_code or "required" in app_code, \
            f"Validation error messages missing for prompt: {prompt!r}"


# Import pytest for test execution
import pytest
