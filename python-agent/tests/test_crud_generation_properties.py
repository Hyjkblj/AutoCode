"""
Property-based tests for CRUD endpoint generation.

Task 10.5: Write property tests for CRUD generation
Property 10: CRUD Endpoint Generation
Validates: Requirements 3.3

These tests validate that "For any model definition in a backend generation task, 
the Backend_Generator SHALL create all CRUD endpoints (Create, Read, Update, Delete)."
"""

from __future__ import annotations

import re
from hypothesis import given, strategies as st, settings
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
)

# Strategy for all prompts (valid + edge cases)
all_prompts_strategy = st.one_of(
    valid_prompt_strategy,
    edge_case_prompt_strategy
)


class TestCRUDEndpointGenerationProperty:
    """
    Property-based tests for CRUD endpoint generation.
    
    **Task 10.5: Write property tests for CRUD generation**
    **Property 10: CRUD Endpoint Generation**
    **Validates: Requirements 3.3**
    
    These tests verify that for any model definition in a backend generation task,
    the Backend_Generator creates all CRUD endpoints (Create, Read, Update, Delete).
    """
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_all_crud_http_methods_present(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - HTTP Methods**
        
        For any model definition in a backend generation task, the Backend_Generator 
        SHALL create endpoints with all CRUD HTTP methods: GET, POST, PUT, DELETE.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify all CRUD HTTP method decorators are present
        assert "@app.get(" in app_code, \
            f"GET method decorator missing for prompt: {prompt!r}"
        assert "@app.post(" in app_code, \
            f"POST method decorator missing for prompt: {prompt!r}"
        assert "@app.put(" in app_code, \
            f"PUT method decorator missing for prompt: {prompt!r}"
        assert "@app.delete(" in app_code, \
            f"DELETE method decorator missing for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_crud_function_definitions_present(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - Function Definitions**
        
        For any model definition in a backend generation task, the Backend_Generator 
        SHALL create function definitions for all CRUD operations.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify all CRUD function definitions are present
        assert "def list_items()" in app_code, \
            f"List function definition missing for prompt: {prompt!r}"
        assert "def create_item()" in app_code, \
            f"Create function definition missing for prompt: {prompt!r}"
        assert "def get_item(" in app_code, \
            f"Get function definition missing for prompt: {prompt!r}"
        assert "def update_item(" in app_code, \
            f"Update function definition missing for prompt: {prompt!r}"
        assert "def delete_item(" in app_code, \
            f"Delete function definition missing for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_crud_routes_have_correct_paths(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - Route Paths**
        
        For any model definition in a backend generation task, the Backend_Generator 
        SHALL create routes with correct paths for list/create and detail operations.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Extract all route paths
        get_routes = re.findall(r'@app\.get\(["\']([^"\']+)["\']\)', app_code)
        post_routes = re.findall(r'@app\.post\(["\']([^"\']+)["\']\)', app_code)
        put_routes = re.findall(r'@app\.put\(["\']([^"\']+)["\']\)', app_code)
        delete_routes = re.findall(r'@app\.delete\(["\']([^"\']+)["\']\)', app_code)
        
        # Filter out health check route
        api_get_routes = [r for r in get_routes if r != "/health"]
        
        # Verify we have at least one API route for each CRUD operation
        assert len(api_get_routes) >= 1, \
            f"No GET API routes found for prompt: {prompt!r}"
        assert len(post_routes) >= 1, \
            f"No POST routes found for prompt: {prompt!r}"
        assert len(put_routes) >= 1, \
            f"No PUT routes found for prompt: {prompt!r}"
        assert len(delete_routes) >= 1, \
            f"No DELETE routes found for prompt: {prompt!r}"
        
        # Verify routes follow RESTful pattern with /api/ prefix
        assert any(r.startswith("/api/") for r in api_get_routes), \
            f"GET routes don't follow /api/ pattern for prompt: {prompt!r}"
        assert any(r.startswith("/api/") for r in post_routes), \
            f"POST routes don't follow /api/ pattern for prompt: {prompt!r}"
        assert any(r.startswith("/api/") for r in put_routes), \
            f"PUT routes don't follow /api/ pattern for prompt: {prompt!r}"
        assert any(r.startswith("/api/") for r in delete_routes), \
            f"DELETE routes don't follow /api/ pattern for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_create_endpoint_accepts_json_payload(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - Create Endpoint**
        
        For any model definition in a backend generation task, the Create endpoint 
        SHALL accept JSON payload and extract data from request body.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify create function uses request.get_json()
        assert "request.get_json(" in app_code, \
            f"Create endpoint doesn't parse JSON for prompt: {prompt!r}"
        
        # Verify create function extracts payload data
        assert "payload.get(" in app_code, \
            f"Create endpoint doesn't extract payload data for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_read_endpoint_returns_item_by_id(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - Read Endpoint**
        
        For any model definition in a backend generation task, the Read endpoint 
        SHALL accept an ID parameter and return a single item.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify get_item function accepts item_id parameter
        assert "def get_item(item_id:" in app_code, \
            f"Get endpoint doesn't accept item_id parameter for prompt: {prompt!r}"
        
        # Verify get_item queries by ID
        assert ".query.get(item_id)" in app_code, \
            f"Get endpoint doesn't query by ID for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_update_endpoint_accepts_id_and_payload(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - Update Endpoint**
        
        For any model definition in a backend generation task, the Update endpoint 
        SHALL accept an ID parameter and JSON payload for updating.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify update_item function accepts item_id parameter
        assert "def update_item(item_id:" in app_code, \
            f"Update endpoint doesn't accept item_id parameter for prompt: {prompt!r}"
        
        # Verify update_item queries by ID
        assert ".query.get(item_id)" in app_code, \
            f"Update endpoint doesn't query by ID for prompt: {prompt!r}"
        
        # Verify update_item uses request.get_json()
        # Since update_item is always present in generated code, we can check directly
        assert "request.get_json(" in app_code, \
            f"Update endpoint doesn't parse JSON for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_delete_endpoint_accepts_id(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - Delete Endpoint**
        
        For any model definition in a backend generation task, the Delete endpoint 
        SHALL accept an ID parameter and remove the item.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify delete_item function accepts item_id parameter
        assert "def delete_item(item_id:" in app_code, \
            f"Delete endpoint doesn't accept item_id parameter for prompt: {prompt!r}"
        
        # Verify delete_item queries by ID
        assert ".query.get(item_id)" in app_code, \
            f"Delete endpoint doesn't query by ID for prompt: {prompt!r}"
        
        # Verify delete_item performs deletion
        assert "db.session.delete(" in app_code, \
            f"Delete endpoint doesn't perform deletion for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_list_endpoint_returns_all_items(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - List Endpoint**
        
        For any model definition in a backend generation task, the List endpoint 
        SHALL query and return all items.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify list_items function queries all items
        assert ".query." in app_code, \
            f"List endpoint doesn't query items for prompt: {prompt!r}"
        
        # Verify list_items returns items in response
        list_function_match = re.search(
            r'def list_items\(\).*?(?=\n(?:@app\.|def |if __name__))',
            app_code,
            re.DOTALL
        )
        assert list_function_match, \
            f"List function not found for prompt: {prompt!r}"
        
        list_function = list_function_match.group(0)
        assert ".all()" in list_function, \
            f"List endpoint doesn't retrieve all items for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_crud_endpoints_use_database_session(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - Database Integration**
        
        For any model definition in a backend generation task, all CRUD endpoints 
        SHALL use database session for persistence operations.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify create uses db.session.add and commit
        assert "db.session.add(" in app_code, \
            f"Create endpoint doesn't use db.session.add for prompt: {prompt!r}"
        assert "db.session.commit()" in app_code, \
            f"CRUD endpoints don't use db.session.commit for prompt: {prompt!r}"
        
        # Verify delete uses db.session.delete
        assert "db.session.delete(" in app_code, \
            f"Delete endpoint doesn't use db.session.delete for prompt: {prompt!r}"
        
        # Verify error handling includes rollback
        assert "db.session.rollback()" in app_code, \
            f"CRUD endpoints don't handle errors with rollback for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_crud_endpoints_return_proper_http_status_codes(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - HTTP Status Codes**
        
        For any model definition in a backend generation task, CRUD endpoints 
        SHALL return proper HTTP status codes (200, 201, 404, 500).
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify status codes are returned
        assert ", 200" in app_code, \
            f"200 status code not returned for prompt: {prompt!r}"
        assert ", 201" in app_code, \
            f"201 status code not returned for create endpoint for prompt: {prompt!r}"
        assert ", 404" in app_code, \
            f"404 status code not returned for not found cases for prompt: {prompt!r}"
        assert ", 500" in app_code, \
            f"500 status code not returned for errors for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_crud_endpoints_handle_not_found_errors(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - Error Handling**
        
        For any model definition in a backend generation task, CRUD endpoints 
        SHALL handle not found errors appropriately.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify not found checks exist
        assert "if not item:" in app_code, \
            f"CRUD endpoints don't check for not found items for prompt: {prompt!r}"
        
        # Verify not found error messages
        assert '"Not found"' in app_code or "'Not found'" in app_code, \
            f"CRUD endpoints don't return not found error messages for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_crud_endpoints_validate_input(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - Input Validation**
        
        For any model definition in a backend generation task, Create and Update 
        endpoints SHALL validate input data before processing.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Verify validation checks exist
        assert "if not" in app_code, \
            f"CRUD endpoints don't validate input for prompt: {prompt!r}"
        
        # Verify validation error responses
        assert '"Validation error"' in app_code or "'Validation error'" in app_code, \
            f"CRUD endpoints don't return validation errors for prompt: {prompt!r}"
        
        # Verify 400 status code for validation errors
        assert ", 400" in app_code, \
            f"400 status code not returned for validation errors for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_crud_endpoints_use_model_serialization(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - Model Serialization**
        
        For any model definition in a backend generation task, CRUD endpoints 
        SHALL use model serialization (to_dict) for JSON responses.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        models_code = result.files["backend/models.py"]
        
        # Verify to_dict method exists in model
        assert "def to_dict(" in models_code, \
            f"Model doesn't have to_dict method for prompt: {prompt!r}"
        
        # Verify CRUD endpoints use to_dict for serialization
        assert ".to_dict()" in app_code, \
            f"CRUD endpoints don't use to_dict for serialization for prompt: {prompt!r}"
    
    @given(all_prompts_strategy)
    @settings(deadline=None, max_examples=50)
    def test_property_10_crud_endpoints_follow_restful_conventions(self, prompt):
        """
        **Property 10: CRUD Endpoint Generation - RESTful Conventions**
        
        For any model definition in a backend generation task, CRUD endpoints 
        SHALL follow RESTful conventions with proper HTTP methods and paths.
        
        **Validates: Requirements 3.3**
        """
        generator = BackendGenerator()
        result = generator.generate(prompt)
        
        app_code = result.files["backend/app.py"]
        
        # Extract routes
        get_routes = re.findall(r'@app\.get\(["\']([^"\']+)["\']\)', app_code)
        post_routes = re.findall(r'@app\.post\(["\']([^"\']+)["\']\)', app_code)
        put_routes = re.findall(r'@app\.put\(["\']([^"\']+)["\']\)', app_code)
        delete_routes = re.findall(r'@app\.delete\(["\']([^"\']+)["\']\)', app_code)
        
        # Filter API routes
        api_get_routes = [r for r in get_routes if r.startswith("/api/")]
        api_post_routes = [r for r in post_routes if r.startswith("/api/")]
        api_put_routes = [r for r in put_routes if r.startswith("/api/")]
        api_delete_routes = [r for r in delete_routes if r.startswith("/api/")]
        
        # Verify RESTful pattern: collection routes (list, create) and item routes (get, update, delete)
        # Collection routes should not have ID parameter
        collection_routes = api_get_routes + api_post_routes
        assert any("<int:" not in r for r in collection_routes), \
            f"Collection routes should not have ID parameter for prompt: {prompt!r}"
        
        # Item routes should have ID parameter
        item_routes = api_put_routes + api_delete_routes
        assert all("<int:" in r for r in item_routes), \
            f"Item routes should have ID parameter for prompt: {prompt!r}"
