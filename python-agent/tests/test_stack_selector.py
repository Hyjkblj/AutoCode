"""
Unit tests for technology stack selector.
"""

import pytest
from generators.stack_selector import (
    StackSelector,
    StackRequirements,
    Framework,
    Database,
    select_optimal_stack,
)


class TestStackSelector:
    """Test suite for stack selector."""
    
    def test_basic_selection(self):
        """Test basic stack selection."""
        selector = StackSelector()
        requirements = StackRequirements()
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation is not None
        assert isinstance(recommendation.framework, Framework)
        assert isinstance(recommendation.database, Database)
        assert 0.0 <= recommendation.confidence_score <= 1.0
        assert len(recommendation.reasoning) > 0
    
    def test_python_preference_selects_python_framework(self):
        """Test that Python preference selects Python framework."""
        selector = StackSelector()
        requirements = StackRequirements(team_language_preference="python")
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.framework in [Framework.FLASK, Framework.FASTAPI, Framework.DJANGO]
    
    def test_javascript_preference_selects_express(self):
        """Test that JavaScript preference selects Express."""
        selector = StackSelector()
        requirements = StackRequirements(team_language_preference="javascript")
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.framework == Framework.EXPRESS
    
    def test_admin_interface_need_selects_django(self):
        """Test that admin interface need selects Django."""
        selector = StackSelector()
        requirements = StackRequirements(
            needs_admin_interface=True,
            team_language_preference="python"
        )
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.framework == Framework.DJANGO
    
    def test_async_support_need_selects_fastapi(self):
        """Test that async support need selects FastAPI."""
        selector = StackSelector()
        requirements = StackRequirements(
            needs_async_support=True,
            team_language_preference="python"
        )
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.framework == Framework.FASTAPI
    
    def test_automatic_api_docs_need_selects_fastapi(self):
        """Test that automatic API docs need selects FastAPI."""
        selector = StackSelector()
        requirements = StackRequirements(
            needs_automatic_api_docs=True,
            team_language_preference="python"
        )
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.framework == Framework.FASTAPI
    
    def test_high_concurrency_selects_postgresql(self):
        """Test that high concurrency selects PostgreSQL."""
        selector = StackSelector()
        requirements = StackRequirements(
            expected_concurrent_users=2000,
            needs_rapid_prototyping=False  # Disable rapid prototyping default
        )
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.database == Database.POSTGRESQL
    
    def test_rapid_prototyping_selects_sqlite(self):
        """Test that rapid prototyping selects SQLite."""
        selector = StackSelector()
        requirements = StackRequirements(
            needs_rapid_prototyping=True,
            needs_production_ready=False
        )
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.database == Database.SQLITE
    
    def test_production_ready_selects_postgresql(self):
        """Test that production ready selects PostgreSQL."""
        selector = StackSelector()
        requirements = StackRequirements(needs_production_ready=True)
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.database == Database.POSTGRESQL
    
    def test_beginner_team_selects_simple_framework(self):
        """Test that beginner team selects simple framework."""
        selector = StackSelector()
        requirements = StackRequirements(
            team_experience_level="beginner",
            team_language_preference="python"
        )
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.framework in [Framework.FLASK, Framework.FASTAPI]
    
    def test_complex_project_selects_django(self):
        """Test that complex project selects Django."""
        selector = StackSelector()
        requirements = StackRequirements(
            project_complexity="complex",
            team_language_preference="python"
        )
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.framework == Framework.DJANGO
    
    def test_explicit_framework_preference(self):
        """Test that explicit framework preference is respected."""
        selector = StackSelector()
        requirements = StackRequirements(
            framework_preference="flask",
            team_language_preference="python"
        )
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.framework == Framework.FLASK
    
    def test_explicit_database_preference(self):
        """Test that explicit database preference is respected."""
        selector = StackSelector()
        requirements = StackRequirements(database_preference="mongodb")
        
        recommendation = selector.select_stack(requirements)
        
        assert recommendation.database == Database.MONGODB
    
    def test_serverless_deployment_selects_appropriate_stack(self):
        """Test that serverless deployment selects appropriate stack."""
        selector = StackSelector()
        requirements = StackRequirements(deployment_platform="serverless")
        
        recommendation = selector.select_stack(requirements)
        
        # Serverless favors FastAPI/Express and MongoDB
        assert recommendation.framework in [Framework.FASTAPI, Framework.EXPRESS, Framework.FLASK]
    
    def test_confidence_score_calculation(self):
        """Test confidence score calculation."""
        selector = StackSelector()
        
        # Strong preference should give high confidence
        requirements_strong = StackRequirements(
            framework_preference="django",
            database_preference="postgresql"
        )
        recommendation_strong = selector.select_stack(requirements_strong)
        
        # Weak preference should give lower confidence
        requirements_weak = StackRequirements()
        recommendation_weak = selector.select_stack(requirements_weak)
        
        assert recommendation_strong.confidence_score >= recommendation_weak.confidence_score
    
    def test_reasoning_generation(self):
        """Test reasoning generation."""
        selector = StackSelector()
        requirements = StackRequirements(
            needs_admin_interface=True,
            needs_production_ready=True,
            team_language_preference="python"
        )
        
        recommendation = selector.select_stack(requirements)
        
        assert len(recommendation.reasoning) > 0
        assert any("admin" in reason.lower() for reason in recommendation.reasoning)
    
    def test_alternatives_generation(self):
        """Test alternatives generation."""
        selector = StackSelector()
        requirements = StackRequirements()
        
        recommendation = selector.select_stack(requirements)
        
        assert len(recommendation.alternatives) > 0
        for fw, db, reason in recommendation.alternatives:
            assert isinstance(fw, Framework)
            assert isinstance(db, Database)
            assert isinstance(reason, str)
            assert len(reason) > 0
    
    def test_to_dict_serialization(self):
        """Test recommendation serialization to dict."""
        selector = StackSelector()
        requirements = StackRequirements()
        
        recommendation = selector.select_stack(requirements)
        result_dict = recommendation.to_dict()
        
        assert "framework" in result_dict
        assert "database" in result_dict
        assert "confidence_score" in result_dict
        assert "reasoning" in result_dict
        assert "alternatives" in result_dict
        assert isinstance(result_dict["framework"], str)
        assert isinstance(result_dict["database"], str)
    
    def test_select_optimal_stack_convenience_function(self):
        """Test convenience function for stack selection."""
        recommendation = select_optimal_stack(
            prompt="Build a todo app",
            concurrent_users=100,
            needs_admin=False,
            team_language="python"
        )
        
        assert recommendation is not None
        assert isinstance(recommendation.framework, Framework)
        assert isinstance(recommendation.database, Database)
    
    def test_prompt_analysis_for_complexity(self):
        """Test prompt analysis for complexity detection."""
        # Simple project
        rec_simple = select_optimal_stack(prompt="Build a simple todo app")
        
        # Complex project
        rec_complex = select_optimal_stack(prompt="Build a complex enterprise system")
        
        # Complex should favor Django
        assert rec_complex.framework in [Framework.DJANGO, Framework.FASTAPI]
    
    def test_prompt_analysis_for_production(self):
        """Test prompt analysis for production readiness."""
        rec_prod = select_optimal_stack(prompt="Build a production-ready API")
        
        # Production should favor PostgreSQL
        assert rec_prod.database in [Database.POSTGRESQL, Database.MONGODB]
    
    def test_prompt_analysis_for_prototype(self):
        """Test prompt analysis for prototyping."""
        rec_proto = select_optimal_stack(prompt="Build a quick MVP prototype")
        
        # Prototype should favor SQLite
        assert rec_proto.database == Database.SQLITE
    
    def test_multiple_requirements_combination(self):
        """Test combination of multiple requirements."""
        selector = StackSelector()
        requirements = StackRequirements(
            expected_concurrent_users=1500,
            needs_async_support=True,
            needs_automatic_api_docs=True,
            needs_production_ready=True,
            team_language_preference="python"
        )
        
        recommendation = selector.select_stack(requirements)
        
        # Should select FastAPI + PostgreSQL
        assert recommendation.framework == Framework.FASTAPI
        assert recommendation.database == Database.POSTGRESQL
    
    def test_conflicting_requirements_resolution(self):
        """Test resolution of conflicting requirements."""
        selector = StackSelector()
        requirements = StackRequirements(
            needs_rapid_prototyping=True,  # Favors SQLite
            needs_production_ready=True,   # Favors PostgreSQL
            expected_concurrent_users=1000  # Favors PostgreSQL
        )
        
        recommendation = selector.select_stack(requirements)
        
        # Production and concurrency should outweigh prototyping
        assert recommendation.database == Database.POSTGRESQL
    
    def test_framework_enum_values(self):
        """Test Framework enum values."""
        assert Framework.FLASK.value == "flask"
        assert Framework.FASTAPI.value == "fastapi"
        assert Framework.DJANGO.value == "django"
        assert Framework.EXPRESS.value == "express"
    
    def test_database_enum_values(self):
        """Test Database enum values."""
        assert Database.SQLITE.value == "sqlite"
        assert Database.POSTGRESQL.value == "postgresql"
        assert Database.MONGODB.value == "mongodb"
    
    def test_invalid_framework_preference_ignored(self):
        """Test that invalid framework preference is ignored."""
        selector = StackSelector()
        requirements = StackRequirements(
            framework_preference="invalid_framework",
            team_language_preference="python"
        )
        
        # Should not raise error, just ignore invalid preference
        recommendation = selector.select_stack(requirements)
        assert recommendation is not None
    
    def test_invalid_database_preference_ignored(self):
        """Test that invalid database preference is ignored."""
        selector = StackSelector()
        requirements = StackRequirements(database_preference="invalid_database")
        
        # Should not raise error, just ignore invalid preference
        recommendation = selector.select_stack(requirements)
        assert recommendation is not None
    
    def test_score_reset_between_selections(self):
        """Test that scores are reset between selections."""
        selector = StackSelector()
        
        req1 = StackRequirements(framework_preference="flask")
        rec1 = selector.select_stack(req1)
        
        req2 = StackRequirements(framework_preference="django")
        rec2 = selector.select_stack(req2)
        
        assert rec1.framework == Framework.FLASK
        assert rec2.framework == Framework.DJANGO
