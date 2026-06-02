"""
Technology Stack Selection and Optimization Logic

This module provides intelligent selection of backend frameworks and databases
based on project requirements, team preferences, and technical constraints.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Framework(Enum):
    """Supported backend frameworks."""
    FLASK = "flask"
    FASTAPI = "fastapi"
    DJANGO = "django"
    EXPRESS = "express"


class Database(Enum):
    """Supported database systems."""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"


@dataclass
class StackRequirements:
    """Requirements for stack selection."""
    # Performance requirements
    expected_concurrent_users: int = 100
    response_time_requirement_ms: int = 500
    
    # Feature requirements
    needs_admin_interface: bool = False
    needs_async_support: bool = False
    needs_orm: bool = True
    needs_automatic_api_docs: bool = False
    
    # Team preferences
    team_language_preference: str = "python"  # python or javascript
    team_experience_level: str = "intermediate"  # beginner, intermediate, advanced
    
    # Technical constraints
    deployment_platform: str = "docker"  # docker, serverless, traditional
    database_preference: Optional[str] = None
    framework_preference: Optional[str] = None
    
    # Project characteristics
    project_complexity: str = "simple"  # simple, moderate, complex
    needs_rapid_prototyping: bool = True
    needs_production_ready: bool = False


@dataclass
class StackRecommendation:
    """Recommended technology stack with reasoning."""
    framework: Framework
    database: Database
    confidence_score: float  # 0.0 to 1.0
    reasoning: list[str]
    alternatives: list[tuple[Framework, Database, str]]  # (framework, db, reason)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "framework": self.framework.value,
            "database": self.database.value,
            "confidence_score": self.confidence_score,
            "reasoning": self.reasoning,
            "alternatives": [
                {
                    "framework": fw.value,
                    "database": db.value,
                    "reason": reason
                }
                for fw, db, reason in self.alternatives
            ]
        }


class StackSelector:
    """Intelligent technology stack selector."""
    
    def __init__(self):
        """Initialize the stack selector with scoring weights."""
        self.framework_scores = {
            Framework.FLASK: 0.0,
            Framework.FASTAPI: 0.0,
            Framework.DJANGO: 0.0,
            Framework.EXPRESS: 0.0,
        }
        self.database_scores = {
            Database.SQLITE: 0.0,
            Database.POSTGRESQL: 0.0,
            Database.MONGODB: 0.0,
        }
    
    def select_stack(self, requirements: StackRequirements) -> StackRecommendation:
        """
        Select optimal technology stack based on requirements.
        
        Args:
            requirements: Project requirements and constraints
            
        Returns:
            StackRecommendation with selected stack and reasoning
        """
        # Reset scores
        self._reset_scores()
        
        # Apply scoring rules
        self._score_by_language_preference(requirements)
        self._score_by_performance_requirements(requirements)
        self._score_by_feature_requirements(requirements)
        self._score_by_team_experience(requirements)
        self._score_by_project_characteristics(requirements)
        self._score_by_deployment_platform(requirements)
        
        # Apply explicit preferences (highest weight)
        self._apply_explicit_preferences(requirements)
        
        # Select best framework and database
        best_framework = max(self.framework_scores.items(), key=lambda x: x[1])
        best_database = max(self.database_scores.items(), key=lambda x: x[1])
        
        # Calculate confidence score
        confidence = self._calculate_confidence(best_framework[1], best_database[1])
        
        # Generate reasoning
        reasoning = self._generate_reasoning(requirements, best_framework[0], best_database[0])
        
        # Generate alternatives
        alternatives = self._generate_alternatives(best_framework[0], best_database[0])
        
        return StackRecommendation(
            framework=best_framework[0],
            database=best_database[0],
            confidence_score=confidence,
            reasoning=reasoning,
            alternatives=alternatives
        )
    
    def _reset_scores(self):
        """Reset all scores to zero."""
        for key in self.framework_scores:
            self.framework_scores[key] = 0.0
        for key in self.database_scores:
            self.database_scores[key] = 0.0
    
    def _score_by_language_preference(self, req: StackRequirements):
        """Score based on team language preference."""
        if req.team_language_preference == "python":
            self.framework_scores[Framework.FLASK] += 2.0
            self.framework_scores[Framework.FASTAPI] += 2.0
            self.framework_scores[Framework.DJANGO] += 2.0
        elif req.team_language_preference == "javascript":
            self.framework_scores[Framework.EXPRESS] += 3.0
    
    def _score_by_performance_requirements(self, req: StackRequirements):
        """Score based on performance requirements."""
        if req.expected_concurrent_users > 1000 or req.response_time_requirement_ms < 200:
            # High performance requirements
            self.framework_scores[Framework.FASTAPI] += 3.0
            self.framework_scores[Framework.EXPRESS] += 2.5
            self.framework_scores[Framework.FLASK] += 1.0
            self.framework_scores[Framework.DJANGO] += 0.5
            
            # Prefer PostgreSQL for high concurrency (increased weight)
            self.database_scores[Database.POSTGRESQL] += 3.0
            self.database_scores[Database.MONGODB] += 2.0
            self.database_scores[Database.SQLITE] += 0.5
        
        if req.needs_async_support:
            self.framework_scores[Framework.FASTAPI] += 3.0
            self.framework_scores[Framework.EXPRESS] += 2.0
            self.framework_scores[Framework.DJANGO] += 1.0  # Django has async support
    
    def _score_by_feature_requirements(self, req: StackRequirements):
        """Score based on feature requirements."""
        if req.needs_admin_interface:
            self.framework_scores[Framework.DJANGO] += 5.0  # Django admin is excellent (increased weight)
            self.framework_scores[Framework.FLASK] += 0.5
            self.framework_scores[Framework.FASTAPI] += 0.5
        
        if req.needs_automatic_api_docs:
            self.framework_scores[Framework.FASTAPI] += 3.0  # FastAPI has best docs
            self.framework_scores[Framework.DJANGO] += 2.0  # DRF has good docs
            self.framework_scores[Framework.EXPRESS] += 1.0  # Can add Swagger
        
        if req.needs_orm:
            self.framework_scores[Framework.DJANGO] += 2.0  # Django ORM
            self.framework_scores[Framework.FASTAPI] += 1.5  # SQLAlchemy
            self.framework_scores[Framework.FLASK] += 1.5  # SQLAlchemy
            self.framework_scores[Framework.EXPRESS] += 1.0  # Sequelize/Mongoose
    
    def _score_by_team_experience(self, req: StackRequirements):
        """Score based on team experience level."""
        if req.team_experience_level == "beginner":
            self.framework_scores[Framework.FLASK] += 2.0  # Simple and easy
            self.framework_scores[Framework.EXPRESS] += 2.0  # Simple and popular
            self.framework_scores[Framework.DJANGO] += 1.0  # More opinionated
            self.framework_scores[Framework.FASTAPI] += 1.5  # Modern but requires async knowledge
            
            self.database_scores[Database.SQLITE] += 2.0  # Easy to set up
            self.database_scores[Database.POSTGRESQL] += 1.0
            self.database_scores[Database.MONGODB] += 1.0
        
        elif req.team_experience_level == "advanced":
            self.framework_scores[Framework.FASTAPI] += 2.0  # Modern features
            self.framework_scores[Framework.DJANGO] += 1.5  # Full-featured
            
            self.database_scores[Database.POSTGRESQL] += 2.0  # Advanced features
            self.database_scores[Database.MONGODB] += 1.5  # Flexible schema
    
    def _score_by_project_characteristics(self, req: StackRequirements):
        """Score based on project characteristics."""
        if req.needs_rapid_prototyping:
            self.framework_scores[Framework.FLASK] += 2.0
            self.framework_scores[Framework.FASTAPI] += 2.0
            self.framework_scores[Framework.EXPRESS] += 2.0
            
            self.database_scores[Database.SQLITE] += 2.0
        
        if req.needs_production_ready:
            self.framework_scores[Framework.DJANGO] += 2.0
            self.framework_scores[Framework.FASTAPI] += 1.5
            
            self.database_scores[Database.POSTGRESQL] += 3.0
            self.database_scores[Database.MONGODB] += 2.0
        
        if req.project_complexity == "complex":
            self.framework_scores[Framework.DJANGO] += 4.0  # Batteries included (increased weight)
            self.framework_scores[Framework.FASTAPI] += 2.0
            
            self.database_scores[Database.POSTGRESQL] += 2.0
        elif req.project_complexity == "simple":
            self.framework_scores[Framework.FLASK] += 2.0
            self.framework_scores[Framework.EXPRESS] += 2.0
            
            self.database_scores[Database.SQLITE] += 2.0
    
    def _score_by_deployment_platform(self, req: StackRequirements):
        """Score based on deployment platform."""
        if req.deployment_platform == "serverless":
            self.framework_scores[Framework.FASTAPI] += 2.0
            self.framework_scores[Framework.EXPRESS] += 2.0
            self.framework_scores[Framework.FLASK] += 1.5
            
            self.database_scores[Database.MONGODB] += 2.0  # Good for serverless
            self.database_scores[Database.POSTGRESQL] += 1.0
        
        elif req.deployment_platform == "docker":
            # All frameworks work well with Docker
            self.database_scores[Database.POSTGRESQL] += 1.5
            self.database_scores[Database.MONGODB] += 1.5
    
    def _apply_explicit_preferences(self, req: StackRequirements):
        """Apply explicit user preferences with highest weight."""
        if req.framework_preference:
            try:
                preferred_fw = Framework(req.framework_preference.lower())
                self.framework_scores[preferred_fw] += 10.0  # Very high weight
            except ValueError:
                pass  # Invalid preference, ignore
        
        if req.database_preference:
            try:
                preferred_db = Database(req.database_preference.lower())
                self.database_scores[preferred_db] += 10.0  # Very high weight
            except ValueError:
                pass  # Invalid preference, ignore
    
    def _calculate_confidence(self, fw_score: float, db_score: float) -> float:
        """Calculate confidence score based on score margins."""
        # Get second-best scores
        sorted_fw = sorted(self.framework_scores.values(), reverse=True)
        sorted_db = sorted(self.database_scores.values(), reverse=True)
        
        fw_margin = (sorted_fw[0] - sorted_fw[1]) / max(sorted_fw[0], 1.0) if len(sorted_fw) > 1 else 1.0
        db_margin = (sorted_db[0] - sorted_db[1]) / max(sorted_db[0], 1.0) if len(sorted_db) > 1 else 1.0
        
        # Average margin as confidence
        confidence = (fw_margin + db_margin) / 2.0
        return min(max(confidence, 0.0), 1.0)
    
    def _generate_reasoning(self, req: StackRequirements, framework: Framework, database: Database) -> list[str]:
        """Generate human-readable reasoning for the selection."""
        reasons = []
        
        # Framework reasoning
        if framework == Framework.FLASK:
            reasons.append("Flask selected for its simplicity and flexibility")
            if req.needs_rapid_prototyping:
                reasons.append("Flask is excellent for rapid prototyping")
        elif framework == Framework.FASTAPI:
            reasons.append("FastAPI selected for modern async support and automatic API documentation")
            if req.needs_async_support:
                reasons.append("FastAPI provides native async/await support")
            if req.needs_automatic_api_docs:
                reasons.append("FastAPI generates interactive API documentation automatically")
        elif framework == Framework.DJANGO:
            reasons.append("Django selected for its batteries-included approach")
            if req.needs_admin_interface:
                reasons.append("Django provides a powerful built-in admin interface")
            if req.project_complexity == "complex":
                reasons.append("Django is well-suited for complex applications")
        elif framework == Framework.EXPRESS:
            reasons.append("Express.js selected for its minimalist and flexible design")
            if req.team_language_preference == "javascript":
                reasons.append("Express.js matches team's JavaScript preference")
        
        # Database reasoning
        if database == Database.SQLITE:
            reasons.append("SQLite selected for easy setup and zero configuration")
            if req.needs_rapid_prototyping:
                reasons.append("SQLite is perfect for prototyping and development")
        elif database == Database.POSTGRESQL:
            reasons.append("PostgreSQL selected for production-grade reliability and features")
            if req.needs_production_ready:
                reasons.append("PostgreSQL is battle-tested for production workloads")
            if req.expected_concurrent_users > 1000:
                reasons.append("PostgreSQL handles high concurrency well")
        elif database == Database.MONGODB:
            reasons.append("MongoDB selected for flexible schema and scalability")
            if req.deployment_platform == "serverless":
                reasons.append("MongoDB works well with serverless architectures")
        
        return reasons
    
    def _generate_alternatives(self, selected_fw: Framework, selected_db: Database) -> list[tuple[Framework, Database, str]]:
        """Generate alternative stack recommendations."""
        alternatives = []
        
        # Get top 2 frameworks and databases (excluding selected)
        sorted_fw = sorted(
            [(fw, score) for fw, score in self.framework_scores.items() if fw != selected_fw],
            key=lambda x: x[1],
            reverse=True
        )[:2]
        
        sorted_db = sorted(
            [(db, score) for db, score in self.database_scores.items() if db != selected_db],
            key=lambda x: x[1],
            reverse=True
        )[:2]
        
        # Generate alternative combinations
        if sorted_fw and sorted_db:
            alternatives.append((
                sorted_fw[0][0],
                sorted_db[0][0],
                f"Alternative with {sorted_fw[0][0].value} and {sorted_db[0][0].value}"
            ))
        
        if len(sorted_fw) > 1 and sorted_db:
            alternatives.append((
                sorted_fw[1][0],
                selected_db,
                f"Keep {selected_db.value} but use {sorted_fw[1][0].value} framework"
            ))
        
        return alternatives[:2]  # Return top 2 alternatives


def select_optimal_stack(
    prompt: str = "",
    concurrent_users: int = 100,
    needs_admin: bool = False,
    needs_async: bool = False,
    team_language: str = "python",
    framework_hint: Optional[str] = None,
    database_hint: Optional[str] = None,
) -> StackRecommendation:
    """
    Convenience function to select optimal stack with common parameters.
    
    Args:
        prompt: User requirement description
        concurrent_users: Expected concurrent users
        needs_admin: Whether admin interface is needed
        needs_async: Whether async support is needed
        team_language: Team's preferred language (python or javascript)
        framework_hint: Optional framework preference
        database_hint: Optional database preference
        
    Returns:
        StackRecommendation with selected stack
    """
    # Analyze prompt for hints
    prompt_lower = prompt.lower()
    
    # Detect complexity from prompt
    complexity = "simple"
    if any(word in prompt_lower for word in ["complex", "enterprise", "large-scale"]):
        complexity = "complex"
    elif any(word in prompt_lower for word in ["moderate", "medium"]):
        complexity = "moderate"
    
    # Detect if production-ready is needed
    production_ready = any(word in prompt_lower for word in ["production", "deploy", "scale"])
    
    # Detect if rapid prototyping is needed
    rapid_prototype = any(word in prompt_lower for word in ["prototype", "quick", "mvp", "demo"])
    
    requirements = StackRequirements(
        expected_concurrent_users=concurrent_users,
        needs_admin_interface=needs_admin,
        needs_async_support=needs_async,
        team_language_preference=team_language,
        framework_preference=framework_hint,
        database_preference=database_hint,
        project_complexity=complexity,
        needs_production_ready=production_ready,
        needs_rapid_prototyping=rapid_prototype,
    )
    
    selector = StackSelector()
    return selector.select_stack(requirements)
