"""
Property-based tests for fix loop iteration bounds.

Task 11.4: Write property tests for fix loop bounds
Property 15: Fix Loop Iteration Bounds
Validates: Requirements 4.5, 4.6

These tests validate that "For any validation failure, the Fix_Loop SHALL
attempt automatic repair up to 3 iterations with specific error categorization."
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, strategies as st

from generators.fix_loop import ErrorCategory, FixLoop, FixResult
from generators.validation_gate import ValidationGate, ValidationResult


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for error messages that map to each category
syntax_error_messages = st.sampled_from([
    "app.py syntax error at line 5: invalid syntax",
    "models.py parsing error: unexpected EOF",
    "index.html: unbalanced braces",
    "styles.css: unbalanced braces",
    "app.js: unbalanced curly braces",
    "app.py syntax error at line 1: invalid syntax",
])

structure_error_messages = st.sampled_from([
    "missing required file: backend/app.py",
    "missing required file: requirements.txt",
    "missing required directory: backend/",
    "missing required file: README.generated.md",
    "missing required file: backend/models.py",
])

dependency_error_messages = st.sampled_from([
    "requirements.txt: missing web framework (Flask or FastAPI)",
    "requirements.txt is empty",
    "package.json: missing 'name' field",
    "package.json: invalid JSON at line 1: Expecting value",
    "requirements.txt: missing required packages",
])

runtime_error_messages = st.sampled_from([
    "backend runtime validation: import error - No module named 'flask'",
    "backend/app.py missing Flask/FastAPI application bootstrap",
    "backend/app.py missing API route definitions",
    "backend/app.py missing database initialization logic",
    "backend runtime validation: timeout (application may have blocking code)",
])

# Strategy for any single error message
any_error_message = st.one_of(
    syntax_error_messages,
    structure_error_messages,
    dependency_error_messages,
    runtime_error_messages,
)

# Strategy for lists of 1–5 error messages
error_list_strategy = st.lists(any_error_message, min_size=1, max_size=5)

# Strategy for max_iterations values (1, 2, or 3)
max_iterations_strategy = st.integers(min_value=1, max_value=3)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_always_failing_gate() -> ValidationGate:
    """Return a ValidationGate that always reports a single error."""
    gate = MagicMock(spec=ValidationGate)
    gate.validate.return_value = ValidationResult(
        ok=False,
        errors=["backend/app.py missing Flask/FastAPI application bootstrap"],
    )
    return gate


def _make_always_passing_gate() -> ValidationGate:
    """Return a ValidationGate that always reports success."""
    gate = MagicMock(spec=ValidationGate)
    gate.validate.return_value = ValidationResult(ok=True, errors=[])
    return gate


def _make_fix_loop_with_gate(gate: ValidationGate) -> FixLoop:
    """Create a FixLoop whose internal validation_gate is replaced by *gate*."""
    loop = FixLoop(llm_client=None)
    loop.validation_gate = gate
    return loop


# ---------------------------------------------------------------------------
# Property 15: Fix Loop Iteration Bounds
# ---------------------------------------------------------------------------

class TestFixLoopIterationBoundsProperty:
    """
    Property-based tests for Fix Loop Iteration Bounds.

    **Task 11.4: Write property tests for fix loop bounds**
    **Property 15: Fix Loop Iteration Bounds**
    **Validates: Requirements 4.5, 4.6**

    For any validation failure, the Fix_Loop SHALL:
    - Attempt automatic repair up to 3 iterations (Req 4.5)
    - Provide specific error categorization (Req 4.6)
    """

    # ------------------------------------------------------------------
    # Requirement 4.5 – Iteration limit of 3
    # ------------------------------------------------------------------

    @given(max_iterations_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_15_fix_loop_never_exceeds_max_iterations(self, max_iter):
        """
        **Property 15: Fix Loop Iteration Bounds – Never Exceeds Max**

        For any validation failure, the Fix_Loop SHALL never perform more
        iterations than the configured maximum (default 3).

        **Validates: Requirements 4.5**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            gate = _make_always_failing_gate()
            loop = _make_fix_loop_with_gate(gate)

            task = {"target": "backend"}
            result = loop.fix_and_validate(task, tmp, max_iterations=max_iter)

            assert result.iterations_used <= max_iter, (
                f"Fix loop used {result.iterations_used} iterations but max was {max_iter}"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_property_15_default_max_iterations_is_three(self):
        """
        **Property 15: Fix Loop Iteration Bounds – Default Max Is 3**

        The Fix_Loop SHALL use a default maximum of 3 iterations when no
        explicit limit is provided.

        **Validates: Requirements 4.5**
        """
        assert FixLoop.MAX_ITERATIONS == 3

    def test_property_15_fix_loop_stops_at_three_on_persistent_failure(self):
        """
        **Property 15: Fix Loop Iteration Bounds – Stops at 3 on Failure**

        For any validation failure that persists across all attempts, the
        Fix_Loop SHALL stop after exactly 3 iterations and return success=False.

        **Validates: Requirements 4.5**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            gate = _make_always_failing_gate()
            loop = _make_fix_loop_with_gate(gate)

            task = {"target": "backend"}
            result = loop.fix_and_validate(task, tmp)

            assert not result.success
            assert result.iterations_used == FixLoop.MAX_ITERATIONS
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_property_15_fix_loop_returns_zero_iterations_when_already_valid(self):
        """
        **Property 15: Fix Loop Iteration Bounds – Zero Iterations When Valid**

        When the initial validation already passes, the Fix_Loop SHALL return
        success=True with iterations_used=0 (no fix attempts needed).

        **Validates: Requirements 4.5**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            gate = _make_always_passing_gate()
            loop = _make_fix_loop_with_gate(gate)

            task = {"target": "backend"}
            result = loop.fix_and_validate(task, tmp)

            assert result.success
            assert result.iterations_used == 0
            assert result.attempts == []
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @given(max_iterations_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_15_fix_result_contains_attempt_records(self, max_iter):
        """
        **Property 15: Fix Loop Iteration Bounds – Attempt Records**

        For any fix loop run that performs at least one iteration, the
        FixResult SHALL contain attempt records for each iteration performed.

        **Validates: Requirements 4.5**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            gate = _make_always_failing_gate()
            loop = _make_fix_loop_with_gate(gate)

            task = {"target": "backend"}
            result = loop.fix_and_validate(task, tmp, max_iterations=max_iter)

            assert isinstance(result.attempts, list)
            assert len(result.attempts) == result.iterations_used
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @given(max_iterations_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_15_fix_result_has_final_errors_on_failure(self, max_iter):
        """
        **Property 15: Fix Loop Iteration Bounds – Final Errors on Failure**

        When the Fix_Loop exhausts all iterations without success, the
        FixResult SHALL contain the final validation errors.

        **Validates: Requirements 4.5**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            gate = _make_always_failing_gate()
            loop = _make_fix_loop_with_gate(gate)

            task = {"target": "backend"}
            result = loop.fix_and_validate(task, tmp, max_iterations=max_iter)

            assert not result.success
            assert isinstance(result.final_errors, list)
            assert len(result.final_errors) > 0, (
                "FixResult should contain final errors when fix loop fails"
            )
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Requirement 4.6 – Error categorization
    # ------------------------------------------------------------------

    @given(syntax_error_messages)
    @settings(deadline=None, max_examples=20)
    def test_property_15_syntax_errors_categorized_as_syntax(self, error_msg):
        """
        **Property 15: Fix Loop Iteration Bounds – Syntax Error Categorization**

        For any validation error containing syntax-related keywords, the
        Fix_Loop SHALL categorize it as ErrorCategory.SYNTAX.

        **Validates: Requirements 4.6**
        """
        loop = FixLoop(llm_client=None)
        category = loop._categorize_errors([error_msg])
        assert category == ErrorCategory.SYNTAX, (
            f"Expected SYNTAX category for error: {error_msg!r}, got: {category}"
        )

    @given(structure_error_messages)
    @settings(deadline=None, max_examples=20)
    def test_property_15_structure_errors_categorized_as_structure(self, error_msg):
        """
        **Property 15: Fix Loop Iteration Bounds – Structure Error Categorization**

        For any validation error containing structure-related keywords, the
        Fix_Loop SHALL categorize it as ErrorCategory.STRUCTURE.

        **Validates: Requirements 4.6**
        """
        loop = FixLoop(llm_client=None)
        category = loop._categorize_errors([error_msg])
        assert category == ErrorCategory.STRUCTURE, (
            f"Expected STRUCTURE category for error: {error_msg!r}, got: {category}"
        )

    @given(dependency_error_messages)
    @settings(deadline=None, max_examples=20)
    def test_property_15_dependency_errors_categorized_as_dependency(self, error_msg):
        """
        **Property 15: Fix Loop Iteration Bounds – Dependency Error Categorization**

        For any validation error containing dependency-related keywords, the
        Fix_Loop SHALL categorize it as ErrorCategory.DEPENDENCY.

        **Validates: Requirements 4.6**
        """
        loop = FixLoop(llm_client=None)
        category = loop._categorize_errors([error_msg])
        assert category == ErrorCategory.DEPENDENCY, (
            f"Expected DEPENDENCY category for error: {error_msg!r}, got: {category}"
        )

    @given(runtime_error_messages)
    @settings(deadline=None, max_examples=20)
    def test_property_15_runtime_errors_categorized_as_runtime(self, error_msg):
        """
        **Property 15: Fix Loop Iteration Bounds – Runtime Error Categorization**

        For any validation error containing runtime-related keywords, the
        Fix_Loop SHALL categorize it as ErrorCategory.RUNTIME.

        **Validates: Requirements 4.6**
        """
        loop = FixLoop(llm_client=None)
        category = loop._categorize_errors([error_msg])
        assert category == ErrorCategory.RUNTIME, (
            f"Expected RUNTIME category for error: {error_msg!r}, got: {category}"
        )

    def test_property_15_empty_error_list_categorized_as_unknown(self):
        """
        **Property 15: Fix Loop Iteration Bounds – Unknown Category for Empty List**

        When the error list is empty, the Fix_Loop SHALL return
        ErrorCategory.UNKNOWN.

        **Validates: Requirements 4.6**
        """
        loop = FixLoop(llm_client=None)
        category = loop._categorize_errors([])
        assert category == ErrorCategory.UNKNOWN

    @given(error_list_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_15_categorization_always_returns_valid_category(self, errors):
        """
        **Property 15: Fix Loop Iteration Bounds – Categorization Always Valid**

        For any list of error messages, the Fix_Loop SHALL return one of the
        defined ErrorCategory values (never raises, never returns None).

        **Validates: Requirements 4.6**
        """
        loop = FixLoop(llm_client=None)
        category = loop._categorize_errors(errors)

        assert category is not None
        assert isinstance(category, ErrorCategory)
        assert category in list(ErrorCategory)

    @given(max_iterations_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_15_each_attempt_records_error_category(self, max_iter):
        """
        **Property 15: Fix Loop Iteration Bounds – Attempt Records Category**

        For any fix loop run, each FixAttempt in the result SHALL record the
        error category that was diagnosed for that iteration.

        **Validates: Requirements 4.6**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            gate = _make_always_failing_gate()
            loop = _make_fix_loop_with_gate(gate)

            task = {"target": "backend"}
            result = loop.fix_and_validate(task, tmp, max_iterations=max_iter)

            for attempt in result.attempts:
                assert isinstance(attempt.category, ErrorCategory), (
                    f"Attempt {attempt.iteration} has invalid category: {attempt.category!r}"
                )
                assert attempt.category in list(ErrorCategory)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------------
    # Combined: iteration bounds + categorization together
    # ------------------------------------------------------------------

    @given(max_iterations_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_15_fix_result_summary_is_string(self, max_iter):
        """
        **Property 15: Fix Loop Iteration Bounds – Summary Is String**

        For any fix loop result, the summary property SHALL return a
        non-empty string describing the outcome.

        **Validates: Requirements 4.5, 4.6**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            gate = _make_always_failing_gate()
            loop = _make_fix_loop_with_gate(gate)

            task = {"target": "backend"}
            result = loop.fix_and_validate(task, tmp, max_iterations=max_iter)

            summary = result.summary
            assert isinstance(summary, str)
            assert len(summary) > 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_property_15_fix_result_dataclass_fields(self):
        """
        **Property 15: Fix Loop Iteration Bounds – FixResult Fields**

        The FixResult SHALL expose success, attempts, final_errors, and
        iterations_used fields with correct types.

        **Validates: Requirements 4.5, 4.6**
        """
        tmp = Path(tempfile.mkdtemp())
        try:
            gate = _make_always_failing_gate()
            loop = _make_fix_loop_with_gate(gate)

            task = {"target": "backend"}
            result = loop.fix_and_validate(task, tmp)

            assert isinstance(result.success, bool)
            assert isinstance(result.attempts, list)
            assert isinstance(result.final_errors, list)
            assert isinstance(result.iterations_used, int)
            assert result.iterations_used >= 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
