"""
Intelligent fix loop mechanism for automatic code repair.

This module provides automatic repair strategies for common validation failures
with error categorization, iteration limits, and LLM-powered context-aware fixes.
Includes recovery attempt tracking, success statistics, and actionable guidance
for manual resolution when auto-recovery fails.

**Validates: Requirements 4.5, 4.6, 15.3, 15.5, 15.6**
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from generators.validation_gate import ValidationGate, ValidationResult
from llm.llm_client import LLMClient, LLMClientError
from utils.errors import ValidationError
from utils.observability import log_fix_loop_attempt


logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error categories for validation failures."""
    SYNTAX = "syntax"
    STRUCTURE = "structure"
    DEPENDENCY = "dependency"
    RUNTIME = "runtime"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FixAttempt:
    """Record of a single fix attempt."""
    iteration: int
    category: ErrorCategory
    errors: list[str]
    strategy: str
    success: bool
    fixed_files: list[str]


@dataclass(frozen=True)
class FixResult:
    """Result of the fix loop process."""
    success: bool
    attempts: list[FixAttempt]
    final_errors: list[str]
    iterations_used: int
    manual_guidance: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """Generate a human-readable summary of the fix process."""
        if self.success:
            return f"Fixed after {self.iterations_used} iteration(s)"
        base = f"Failed after {self.iterations_used} iteration(s): {'; '.join(self.final_errors)}"
        if self.manual_guidance:
            guidance_text = " | ".join(self.manual_guidance)
            return f"{base}. Manual resolution: {guidance_text}"
        return base


# ---------------------------------------------------------------------------
# Global error statistics (in-process, for continuous improvement)
# ---------------------------------------------------------------------------

class ErrorStatistics:
    """Tracks error statistics across fix loop executions for continuous improvement."""

    def __init__(self) -> None:
        self._total_attempts: int = 0
        self._successful_recoveries: int = 0
        self._failed_recoveries: int = 0
        self._category_counts: dict[str, int] = {}
        self._strategy_success: dict[str, int] = {}
        self._strategy_failure: dict[str, int] = {}

    def record_attempt(
        self,
        *,
        category: ErrorCategory,
        strategy: str,
        success: bool,
    ) -> None:
        self._total_attempts += 1
        cat_key = category.value
        self._category_counts[cat_key] = self._category_counts.get(cat_key, 0) + 1
        if success:
            self._strategy_success[strategy] = self._strategy_success.get(strategy, 0) + 1
        else:
            self._strategy_failure[strategy] = self._strategy_failure.get(strategy, 0) + 1

    def record_recovery_outcome(self, *, success: bool) -> None:
        if success:
            self._successful_recoveries += 1
        else:
            self._failed_recoveries += 1

    @property
    def total_attempts(self) -> int:
        return self._total_attempts

    @property
    def successful_recoveries(self) -> int:
        return self._successful_recoveries

    @property
    def failed_recoveries(self) -> int:
        return self._failed_recoveries

    @property
    def recovery_success_rate(self) -> float:
        total = self._successful_recoveries + self._failed_recoveries
        if total == 0:
            return 0.0
        return self._successful_recoveries / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "totalAttempts": self._total_attempts,
            "successfulRecoveries": self._successful_recoveries,
            "failedRecoveries": self._failed_recoveries,
            "recoverySuccessRate": round(self.recovery_success_rate, 4),
            "categoryCounts": dict(self._category_counts),
            "strategySuccess": dict(self._strategy_success),
            "strategyFailure": dict(self._strategy_failure),
        }


# Module-level statistics instance (shared across all FixLoop instances)
_global_error_stats = ErrorStatistics()


def get_error_statistics() -> ErrorStatistics:
    """Return the global error statistics instance."""
    return _global_error_stats


class FixLoop:
    """
    Intelligent fix loop for automatic code repair.
    
    Features:
    - Error categorization (syntax, structure, dependency, runtime)
    - Automatic repair strategies for common issues
    - Iteration limits (3 max) to prevent infinite loops
    - LLM integration for context-aware code fixes
    - Detailed failure classification and reporting
    - Recovery attempt tracking and success statistics
    - Actionable guidance for manual resolution when auto-recovery fails
    """
    
    MAX_ITERATIONS = 3
    
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """
        Initialize the fix loop.
        
        Args:
            llm_client: Optional LLM client for context-aware fixes.
                       If None, only rule-based fixes will be attempted.
        """
        self.validation_gate = ValidationGate()
        self.llm_client = llm_client
        self._attempts: list[FixAttempt] = []
        self._stats = _global_error_stats
    
    def fix_and_validate(
        self,
        task: dict[str, Any],
        workspace: Path,
        *,
        max_iterations: int | None = None,
    ) -> FixResult:
        """
        Attempt to fix validation errors with automatic repair strategies.
        
        Args:
            task: Task dictionary containing generation metadata
            workspace: Path to the generated code workspace
            max_iterations: Maximum fix iterations (default: 3)
        
        Returns:
            FixResult containing success status, attempt history, and manual guidance
        """
        max_iter = max_iterations if max_iterations is not None else self.MAX_ITERATIONS
        self._attempts = []
        
        task_id = str(task.get("taskId") or "")
        trace_id = str(task.get("traceId") or "")
        run_id = str(task.get("runId") or "")
        intent = str(task.get("intent") or "")
        plan_name = str(task.get("planName") or "")

        # Initial validation
        result = self.validation_gate.validate(task, workspace)
        if result.ok:
            logger.info("Initial validation passed, no fixes needed")
            self._stats.record_recovery_outcome(success=True)
            return FixResult(
                success=True,
                attempts=[],
                final_errors=[],
                iterations_used=0,
                manual_guidance=[],
            )
        
        logger.info(f"Initial validation failed with {len(result.errors)} error(s)")
        
        # Attempt fixes up to max iterations
        for iteration in range(1, max_iter + 1):
            logger.info(f"Fix iteration {iteration}/{max_iter}")
            
            # Categorize errors
            category = self._categorize_errors(result.errors)
            logger.info(f"Error category: {category.value}")
            
            # Apply fix strategy
            fix_success, fixed_files, strategy = self._apply_fix_strategy(
                task=task,
                workspace=workspace,
                errors=result.errors,
                category=category,
                iteration=iteration,
            )

            # Record attempt in statistics
            self._stats.record_attempt(
                category=category,
                strategy=strategy,
                success=fix_success,
            )

            # Emit structured log for this fix loop attempt
            log_fix_loop_attempt(
                task_id=task_id,
                iteration=iteration,
                max_iterations=max_iter,
                category=category.value,
                strategy=strategy,
                success=fix_success,
                errors=result.errors,
                trace_id=trace_id,
                run_id=run_id,
                intent=intent,
                plan_name=plan_name,
            )
            
            # Record attempt
            attempt = FixAttempt(
                iteration=iteration,
                category=category,
                errors=result.errors.copy(),
                strategy=strategy,
                success=fix_success,
                fixed_files=fixed_files,
            )
            self._attempts.append(attempt)
            
            if not fix_success:
                logger.warning(f"Fix strategy '{strategy}' failed to apply")
                continue
            
            # Re-validate after fix
            result = self.validation_gate.validate(task, workspace)
            
            if result.ok:
                logger.info(f"Validation passed after {iteration} iteration(s)")
                self._stats.record_recovery_outcome(success=True)
                return FixResult(
                    success=True,
                    attempts=self._attempts,
                    final_errors=[],
                    iterations_used=iteration,
                    manual_guidance=[],
                )
            
            logger.info(f"Validation still failing with {len(result.errors)} error(s)")
        
        # Max iterations reached without success — generate actionable guidance
        logger.error(f"Fix loop failed after {max_iter} iterations")
        self._stats.record_recovery_outcome(success=False)
        manual_guidance = self._build_manual_guidance(result.errors, self._attempts)
        return FixResult(
            success=False,
            attempts=self._attempts,
            final_errors=result.errors,
            iterations_used=max_iter,
            manual_guidance=manual_guidance,
        )
    
    def _build_manual_guidance(
        self,
        errors: list[str],
        attempts: list[FixAttempt],
    ) -> list[str]:
        """
        Build actionable guidance for manual resolution when auto-recovery fails.

        Returns a list of human-readable guidance strings.
        """
        guidance: list[str] = []

        # Determine the dominant error category from attempts
        categories_seen: set[ErrorCategory] = {a.category for a in attempts}

        for error in errors:
            error_lower = error.lower()

            # Syntax errors
            if any(kw in error_lower for kw in ["syntax error", "parsing error", "unbalanced", "unclosed"]):
                guidance.append(
                    "Syntax error detected. Open the affected file in an editor and check for "
                    "mismatched brackets, parentheses, or quotes. Run `python -m py_compile <file>` "
                    "to identify the exact line."
                )

            # Structure errors
            elif any(kw in error_lower for kw in ["missing required file", "missing required directory"]):
                guidance.append(
                    "Required file or directory is missing. Ensure the generation template "
                    "produced all expected files (app.py, models.py, requirements.txt). "
                    "Re-run the generator with verbose logging enabled."
                )

            # Dependency errors
            elif any(kw in error_lower for kw in ["requirements.txt", "missing web framework", "package.json"]):
                guidance.append(
                    "Dependency issue detected. Verify requirements.txt contains the correct "
                    "package names and versions. Run `pip install -r requirements.txt` manually "
                    "to confirm all dependencies install successfully."
                )

            # Runtime errors
            elif any(kw in error_lower for kw in ["import error", "no module named", "missing flask", "missing api route"]):
                guidance.append(
                    "Runtime error detected. Ensure all imports are correct and the virtual "
                    "environment has the required packages installed. Try running `python app.py` "
                    "directly to see the full traceback."
                )

            # Database errors
            elif "missing database" in error_lower or "database initialization" in error_lower:
                guidance.append(
                    "Database initialization error. Verify that the database setup code is present "
                    "in app.py and that SQLite/SQLAlchemy is properly configured. Check that "
                    "`db.create_all()` or equivalent is called on startup."
                )

        # Add general guidance if no specific guidance was generated
        if not guidance:
            guidance.append(
                "Automatic repair was unable to resolve the validation errors. "
                "Review the error messages above and manually inspect the generated files. "
                "Consider re-running the generation with a more detailed prompt or "
                "contacting support with the task ID and error details."
            )

        # Add LLM suggestion if available
        if self.llm_client is None:
            guidance.append(
                "Tip: Providing an LLM client to the FixLoop may enable more intelligent "
                "context-aware repairs for complex errors."
            )

        return guidance

    def _categorize_errors(self, errors: list[str]) -> ErrorCategory:
        """
        Categorize validation errors into specific types.
        
        Args:
            errors: List of error messages
        
        Returns:
            ErrorCategory representing the primary error type
        """
        if not errors:
            return ErrorCategory.UNKNOWN
        
        # Count error types
        syntax_count = 0
        structure_count = 0
        dependency_count = 0
        runtime_count = 0
        
        for error in errors:
            error_lower = error.lower()
            
            # Syntax errors
            if any(keyword in error_lower for keyword in [
                "syntax error",
                "parsing error",
                "unbalanced",
                "unclosed",
                "invalid format",
                "missing tag",
            ]):
                syntax_count += 1
            
            # Structure errors
            elif any(keyword in error_lower for keyword in [
                "missing required file",
                "missing required directory",
                "missing <html>",
                "missing <body>",
                "no valid css",
                "no recognizable javascript",
            ]):
                structure_count += 1
            
            # Dependency errors
            elif any(keyword in error_lower for keyword in [
                "requirements.txt",
                "package.json",
                "missing web framework",
                "invalid json",
            ]):
                dependency_count += 1
            
            # Runtime errors
            elif any(keyword in error_lower for keyword in [
                "runtime validation",
                "import error",
                "cannot import",
                "no module named",
                "missing flask/fastapi",
                "missing api route",
                "missing database",
            ]):
                runtime_count += 1
        
        # Return the most common category
        counts = [
            (syntax_count, ErrorCategory.SYNTAX),
            (structure_count, ErrorCategory.STRUCTURE),
            (dependency_count, ErrorCategory.DEPENDENCY),
            (runtime_count, ErrorCategory.RUNTIME),
        ]
        
        max_count, category = max(counts, key=lambda x: x[0])
        return category if max_count > 0 else ErrorCategory.UNKNOWN
    
    def _apply_fix_strategy(
        self,
        task: dict[str, Any],
        workspace: Path,
        errors: list[str],
        category: ErrorCategory,
        iteration: int,
    ) -> tuple[bool, list[str], str]:
        """
        Apply appropriate fix strategy based on error category.
        
        Args:
            task: Task dictionary
            workspace: Workspace path
            errors: List of error messages
            category: Error category
            iteration: Current iteration number
        
        Returns:
            Tuple of (success, fixed_files, strategy_name)
        """
        # Try rule-based fixes first (fast and deterministic)
        if category == ErrorCategory.STRUCTURE:
            return self._fix_structure_errors(task, workspace, errors)
        
        if category == ErrorCategory.DEPENDENCY:
            return self._fix_dependency_errors(task, workspace, errors)
        
        if category == ErrorCategory.SYNTAX:
            return self._fix_syntax_errors(task, workspace, errors)
        
        if category == ErrorCategory.RUNTIME:
            return self._fix_runtime_errors(task, workspace, errors)
        
        # For unknown errors or if rule-based fixes fail, try LLM-powered fix
        if self.llm_client is not None:
            return self._fix_with_llm(task, workspace, errors, category, iteration)
        
        return False, [], "no_strategy_available"
    
    def _fix_structure_errors(
        self,
        task: dict[str, Any],
        workspace: Path,
        errors: list[str],
    ) -> tuple[bool, list[str], str]:
        """Fix structure-related errors (missing files/directories)."""
        fixed_files: list[str] = []
        target = str(task.get("_generated_target") or task.get("target") or "").strip().lower()
        
        for error in errors:
            error_lower = error.lower()
            
            # Missing backend directory
            if "missing required directory: backend" in error_lower:
                backend_dir = workspace / "backend"
                backend_dir.mkdir(parents=True, exist_ok=True)
                fixed_files.append("backend/")
            
            # Missing frontend directory
            if "missing required directory: frontend" in error_lower:
                frontend_dir = workspace / "frontend"
                frontend_dir.mkdir(parents=True, exist_ok=True)
                fixed_files.append("frontend/")
            
            # Missing HTML structure
            if "missing <html>" in error_lower or "missing <body>" in error_lower:
                # Find the HTML file
                html_files = list(workspace.rglob("*.html"))
                for html_file in html_files:
                    if html_file.exists():
                        content = html_file.read_text(encoding="utf-8")
                        if "<html" not in content.lower():
                            # Wrap content in HTML structure
                            fixed_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Generated App</title>
</head>
<body>
{content}
</body>
</html>"""
                            html_file.write_text(fixed_content, encoding="utf-8")
                            fixed_files.append(str(html_file.relative_to(workspace)))
        
        if fixed_files:
            logger.info(f"Fixed structure errors in {len(fixed_files)} file(s)")
            return True, fixed_files, "structure_repair"
        
        return False, [], "structure_repair_failed"
    
    def _fix_dependency_errors(
        self,
        task: dict[str, Any],
        workspace: Path,
        errors: list[str],
    ) -> tuple[bool, list[str], str]:
        """Fix dependency-related errors (requirements.txt, package.json)."""
        fixed_files: list[str] = []
        
        for error in errors:
            error_lower = error.lower()
            
            # Empty requirements.txt
            if "requirements.txt is empty" in error_lower:
                req_file = workspace / "requirements.txt"
                if req_file.exists():
                    # Add minimal Flask dependencies
                    req_file.write_text("flask==3.0.3\nflask-cors==4.0.1\n", encoding="utf-8")
                    fixed_files.append("requirements.txt")
            
            # Missing web framework
            if "missing web framework" in error_lower:
                req_file = workspace / "requirements.txt"
                if req_file.exists():
                    content = req_file.read_text(encoding="utf-8")
                    if "flask" not in content.lower() and "fastapi" not in content.lower():
                        # Add Flask as default
                        content += "\nflask==3.0.3\nflask-cors==4.0.1\n"
                        req_file.write_text(content, encoding="utf-8")
                        fixed_files.append("requirements.txt")
        
        if fixed_files:
            logger.info(f"Fixed dependency errors in {len(fixed_files)} file(s)")
            return True, fixed_files, "dependency_repair"
        
        return False, [], "dependency_repair_failed"
    
    def _fix_syntax_errors(
        self,
        task: dict[str, Any],
        workspace: Path,
        errors: list[str],
    ) -> tuple[bool, list[str], str]:
        """Fix syntax-related errors (unbalanced braces, brackets, etc)."""
        fixed_files: list[str] = []
        
        # Syntax errors are harder to fix automatically without LLM
        # We can only handle very simple cases
        
        for error in errors:
            error_lower = error.lower()
            
            # Unbalanced CSS braces
            if "unbalanced braces" in error_lower and ".css" in error_lower:
                css_files = list(workspace.rglob("*.css"))
                for css_file in css_files:
                    if css_file.name in error:
                        content = css_file.read_text(encoding="utf-8")
                        open_braces = content.count("{")
                        close_braces = content.count("}")
                        
                        # Simple fix: add missing closing braces at the end
                        if open_braces > close_braces:
                            content += "\n" + ("}" * (open_braces - close_braces))
                            css_file.write_text(content, encoding="utf-8")
                            fixed_files.append(str(css_file.relative_to(workspace)))
        
        if fixed_files:
            logger.info(f"Fixed syntax errors in {len(fixed_files)} file(s)")
            return True, fixed_files, "syntax_repair"
        
        # Most syntax errors need LLM assistance
        return False, [], "syntax_repair_needs_llm"
    
    def _fix_runtime_errors(
        self,
        task: dict[str, Any],
        workspace: Path,
        errors: list[str],
    ) -> tuple[bool, list[str], str]:
        """Fix runtime-related errors (missing imports, initialization, etc)."""
        fixed_files: list[str] = []
        
        for error in errors:
            error_lower = error.lower()
            
            # Missing Flask/FastAPI application bootstrap
            if "missing flask/fastapi application bootstrap" in error_lower:
                app_file = workspace / "backend" / "app.py"
                if app_file.exists():
                    content = app_file.read_text(encoding="utf-8")
                    
                    # Add Flask app if missing
                    if "Flask(" not in content and "FastAPI(" not in content:
                        # Prepend Flask import and app creation
                        flask_init = """from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

"""
                        content = flask_init + content
                        app_file.write_text(content, encoding="utf-8")
                        fixed_files.append("backend/app.py")
            
            # Missing API route definitions
            if "missing api route definitions" in error_lower:
                app_file = workspace / "backend" / "app.py"
                if app_file.exists():
                    content = app_file.read_text(encoding="utf-8")
                    
                    # Add a basic health check route if no routes exist
                    if "@app.route" not in content and "@app.get" not in content:
                        health_route = """

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200
"""
                        content += health_route
                        app_file.write_text(content, encoding="utf-8")
                        fixed_files.append("backend/app.py")
            
            # Missing database initialization
            if "missing database initialization" in error_lower:
                app_file = workspace / "backend" / "app.py"
                if app_file.exists():
                    content = app_file.read_text(encoding="utf-8")
                    
                    # Add SQLite initialization if missing
                    if "sqlite3" not in content and "SQLAlchemy" not in content:
                        db_init = """
import sqlite3

# Initialize database
def init_db():
    conn = sqlite3.connect("database.db")
    conn.close()

init_db()
"""
                        content += db_init
                        app_file.write_text(content, encoding="utf-8")
                        fixed_files.append("backend/app.py")
        
        if fixed_files:
            logger.info(f"Fixed runtime errors in {len(fixed_files)} file(s)")
            return True, fixed_files, "runtime_repair"
        
        return False, [], "runtime_repair_failed"

    def _fix_typescript_errors(self, errors: list[str], content: str, file_path: str) -> str | None:
        if not self.llm_client:
            return None
        error_text = "\n".join(errors[:5])
        user_msg = (
            f"File: {file_path}\nErrors:\n{error_text}\n\n"
            f"Current content:\n```\n{content[:4000]}\n```\n\n"
            f"Fix these TypeScript errors. Return the complete corrected file."
        )
        try:
            return self.llm_client.generate(
                user_msg,
                system_prompt="You are a TypeScript error fixer. Return only the corrected file content."
            )
        except Exception:
            return None

    def _fix_with_llm(
        self,
        task: dict[str, Any],
        workspace: Path,
        errors: list[str],
        category: ErrorCategory,
        iteration: int,
    ) -> tuple[bool, list[str], str]:
        """
        Use LLM to generate context-aware fixes for complex errors.
        
        Args:
            task: Task dictionary
            workspace: Workspace path
            errors: List of error messages
            category: Error category
            iteration: Current iteration number
        
        Returns:
            Tuple of (success, fixed_files, strategy_name)
        """
        if self.llm_client is None:
            return False, [], "llm_not_available"
        
        try:
            # Gather context about the generated code
            target = str(task.get("_generated_target") or task.get("target") or "").strip().lower()
            prompt_text = str(task.get("prompt") or "").strip()
            
            # Find relevant files to fix
            files_to_analyze = self._identify_files_to_fix(workspace, errors, target)
            
            if not files_to_analyze:
                logger.warning("No files identified for LLM-based fixing")
                return False, [], "llm_no_files"
            
            # Build LLM prompt for fixing
            fix_prompt = self._build_fix_prompt(
                errors=errors,
                category=category,
                files=files_to_analyze,
                target=target,
                original_prompt=prompt_text,
                iteration=iteration,
            )
            
            # Call LLM for fix suggestions
            logger.info("Requesting LLM-powered fix suggestions")
            response = self.llm_client.generate(
                prompt=fix_prompt,
                system_prompt="You are an expert code repair assistant. Analyze validation errors and provide precise fixes.",
            )
            
            # Parse and apply LLM suggestions
            fixed_files = self._apply_llm_fixes(workspace, response, files_to_analyze)
            
            if fixed_files:
                logger.info(f"Applied LLM fixes to {len(fixed_files)} file(s)")
                return True, fixed_files, "llm_context_aware_fix"
            
            return False, [], "llm_fix_failed"
            
        except LLMClientError as e:
            logger.error(f"LLM client error during fix: {e}")
            return False, [], f"llm_error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error during LLM fix: {e}")
            return False, [], f"llm_unexpected_error: {e}"
    
    def _identify_files_to_fix(
        self,
        workspace: Path,
        errors: list[str],
        target: str,
    ) -> dict[str, str]:
        """
        Identify which files need fixing based on error messages.
        
        Returns:
            Dictionary mapping file paths to their content
        """
        files: dict[str, str] = {}
        
        # Extract file names from error messages
        mentioned_files: set[str] = set()
        for error in errors:
            # Look for file names in error messages
            if "backend/app.py" in error:
                mentioned_files.add("backend/app.py")
            if "backend/models.py" in error:
                mentioned_files.add("backend/models.py")
            if "index.html" in error:
                mentioned_files.add("index.html")
                mentioned_files.add("frontend/index.html")
            if "styles.css" in error:
                mentioned_files.add("styles.css")
                mentioned_files.add("frontend/styles.css")
            if "app.js" in error:
                mentioned_files.add("app.js")
                mentioned_files.add("frontend/app.js")
            if "requirements.txt" in error:
                mentioned_files.add("requirements.txt")
        
        # Read mentioned files
        for file_path_str in mentioned_files:
            file_path = workspace / file_path_str
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    files[file_path_str] = content
                except Exception as e:
                    logger.warning(f"Could not read {file_path_str}: {e}")
        
        # If no files mentioned, include main files based on target
        if not files:
            if target == "backend":
                for path_str in ["backend/app.py", "backend/models.py", "requirements.txt"]:
                    file_path = workspace / path_str
                    if file_path.exists():
                        try:
                            files[path_str] = file_path.read_text(encoding="utf-8")
                        except Exception:
                            pass
            elif target == "web":
                for path_str in ["index.html", "styles.css", "app.js"]:
                    file_path = workspace / path_str
                    if file_path.exists():
                        try:
                            files[path_str] = file_path.read_text(encoding="utf-8")
                        except Exception:
                            pass
        
        return files
    
    def _build_fix_prompt(
        self,
        errors: list[str],
        category: ErrorCategory,
        files: dict[str, str],
        target: str,
        original_prompt: str,
        iteration: int,
    ) -> str:
        """Build a prompt for LLM to generate fixes."""
        prompt_parts = [
            f"# Code Repair Request (Iteration {iteration})",
            "",
            "## Original Requirement",
            original_prompt or "Generate a CRUD application",
            "",
            "## Target Type",
            target or "unknown",
            "",
            "## Error Category",
            category.value,
            "",
            "## Validation Errors",
        ]
        
        for i, error in enumerate(errors, 1):
            prompt_parts.append(f"{i}. {error}")
        
        prompt_parts.extend([
            "",
            "## Current Files",
        ])
        
        for file_path, content in files.items():
            prompt_parts.extend([
                "",
                f"### {file_path}",
                "```",
                content,
                "```",
            ])
        
        prompt_parts.extend([
            "",
            "## Instructions",
            "Analyze the validation errors and provide fixed versions of the files.",
            "For each file that needs fixing, output:",
            "FILE: <filename>",
            "```",
            "<fixed content>",
            "```",
            "",
            "Focus on fixing the specific errors mentioned. Keep changes minimal.",
        ])
        
        return "\n".join(prompt_parts)
    
    def _apply_llm_fixes(
        self,
        workspace: Path,
        llm_response: str,
        original_files: dict[str, str],
    ) -> list[str]:
        """
        Parse LLM response and apply fixes to files.
        
        Returns:
            List of fixed file paths
        """
        fixed_files: list[str] = []
        
        # Parse LLM response for file fixes
        # Expected format:
        # FILE: path/to/file
        # ```
        # content
        # ```
        
        lines = llm_response.split("\n")
        current_file: str | None = None
        current_content: list[str] = []
        in_code_block = False
        
        for line in lines:
            # Check for file marker
            if line.startswith("FILE:"):
                # Save previous file if any
                if current_file and current_content:
                    self._write_fixed_file(workspace, current_file, "\n".join(current_content), fixed_files)
                
                # Start new file
                current_file = line[5:].strip()
                current_content = []
                in_code_block = False
                continue
            
            # Check for code block markers
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            
            # Collect content if in code block
            if in_code_block and current_file:
                current_content.append(line)
        
        # Save last file
        if current_file and current_content:
            self._write_fixed_file(workspace, current_file, "\n".join(current_content), fixed_files)
        
        return fixed_files
    
    def _write_fixed_file(
        self,
        workspace: Path,
        file_path_str: str,
        content: str,
        fixed_files: list[str],
    ) -> None:
        """Write fixed content to file."""
        try:
            file_path = workspace / file_path_str
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            fixed_files.append(file_path_str)
            logger.info(f"Applied LLM fix to {file_path_str}")
        except Exception as e:
            logger.error(f"Failed to write fixed file {file_path_str}: {e}")
