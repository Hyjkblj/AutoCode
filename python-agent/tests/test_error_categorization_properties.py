"""
Property-based tests for error categorization.

Task 15.4: Write property tests for error categorization
Property 57: Error Categorization
Validates: Requirements 15.1

These tests validate that "For any system error, it SHALL be categorized into
distinct types (LLMError, SandboxError, ValidationError, ProtocolError, PluginError)."
"""

from __future__ import annotations

from typing import Type

import pytest
from hypothesis import given, settings, strategies as st

from utils.errors import (
    AgentError,
    ALL_ERROR_TYPES,
    ERROR_CODE_REGISTRY,
    ERROR_TYPE_MAP,
    LLMError,
    NON_RETRYABLE_ERROR_CODES,
    PluginError,
    ProtocolError,
    RETRYABLE_ERROR_CODES,
    SandboxError,
    ValidationError,
    categorize_exception,
    get_error_description,
    is_retryable,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Strategy for arbitrary non-empty detail strings
detail_strategy = st.text(min_size=1, max_size=200).filter(lambda s: s.strip())

# Strategy for known error codes
known_error_code_strategy = st.sampled_from(list(ERROR_CODE_REGISTRY.keys()))

# Strategy for LLM-specific error codes
llm_error_code_strategy = st.sampled_from([
    "LLM_ERROR",
    "LLM_TIMEOUT",
    "LLM_RATE_LIMIT",
    "LLM_CONTEXT_OVERFLOW",
    "LLM_INVALID_RESPONSE",
])

# Strategy for Sandbox-specific error codes
sandbox_error_code_strategy = st.sampled_from([
    "SANDBOX_ERROR",
    "SANDBOX_TIMEOUT",
    "SANDBOX_SECURITY_VIOLATION",
    "SANDBOX_RESOURCE_LIMIT",
    "SANDBOX_UNAVAILABLE",
])

# Strategy for Validation-specific error codes
validation_error_code_strategy = st.sampled_from([
    "VALIDATION_ERROR",
    "VALIDATION_SYNTAX",
    "VALIDATION_STRUCTURE",
    "VALIDATION_DEPENDENCY",
    "VALIDATION_RUNTIME",
])

# Strategy for Protocol-specific error codes
protocol_error_code_strategy = st.sampled_from([
    "PROTOCOL_ERROR",
    "PROTOCOL_ACK_TIMEOUT",
    "PROTOCOL_INVALID_ACK",
    "PROTOCOL_SEQUENCE_GAP",
    "PROTOCOL_DUPLICATE_EVENT",
])

# Strategy for Plugin-specific error codes
plugin_error_code_strategy = st.sampled_from([
    "PLUGIN_ERROR",
    "PLUGIN_NOT_FOUND",
    "PLUGIN_LOAD_FAILED",
    "PLUGIN_EXECUTION_FAILED",
    "PLUGIN_SECURITY_VIOLATION",
])

# Strategy for all five concrete error type classes
error_class_strategy = st.sampled_from([
    LLMError,
    SandboxError,
    ValidationError,
    ProtocolError,
    PluginError,
])


# ---------------------------------------------------------------------------
# Property 57: Error Categorization
# ---------------------------------------------------------------------------

class TestErrorCategorizationProperty:
    """
    Property-based tests for Error Categorization.

    **Task 15.4: Write property tests for error categorization**
    **Property 57: Error Categorization**
    **Validates: Requirements 15.1**

    For any system error, it SHALL be categorized into distinct types:
    LLMError, SandboxError, ValidationError, ProtocolError, PluginError.
    """

    # ------------------------------------------------------------------
    # 1. ALL_ERROR_TYPES contains exactly the five required types
    # ------------------------------------------------------------------

    def test_property_57_all_error_types_contains_five_distinct_types(self):
        """
        **Property 57: Error Categorization – Five Distinct Types**

        The system SHALL define exactly five distinct error types:
        LLMError, SandboxError, ValidationError, ProtocolError, PluginError.

        **Validates: Requirements 15.1**
        """
        assert len(ALL_ERROR_TYPES) == 5
        assert LLMError in ALL_ERROR_TYPES
        assert SandboxError in ALL_ERROR_TYPES
        assert ValidationError in ALL_ERROR_TYPES
        assert ProtocolError in ALL_ERROR_TYPES
        assert PluginError in ALL_ERROR_TYPES

    def test_property_57_all_error_types_are_distinct(self):
        """
        **Property 57: Error Categorization – Types Are Distinct**

        Each error type SHALL be a distinct class (no duplicates).

        **Validates: Requirements 15.1**
        """
        assert len(set(ALL_ERROR_TYPES)) == len(ALL_ERROR_TYPES)

    def test_property_57_all_error_types_are_subclasses_of_agent_error(self):
        """
        **Property 57: Error Categorization – All Types Inherit AgentError**

        Each error type SHALL be a subclass of AgentError to ensure
        consistent error handling.

        **Validates: Requirements 15.1**
        """
        for error_type in ALL_ERROR_TYPES:
            assert issubclass(error_type, AgentError), (
                f"{error_type.__name__} is not a subclass of AgentError"
            )

    # ------------------------------------------------------------------
    # 2. Each error type can be instantiated and is an instance of itself
    # ------------------------------------------------------------------

    @given(detail_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_57_llm_error_is_instance_of_llm_error(self, detail):
        """
        **Property 57: Error Categorization – LLMError Instance**

        For any detail string, LLMError SHALL be an instance of LLMError
        and AgentError, but NOT of SandboxError, ValidationError,
        ProtocolError, or PluginError.

        **Validates: Requirements 15.1**
        """
        exc = LLMError(detail)
        assert isinstance(exc, LLMError)
        assert isinstance(exc, AgentError)
        assert not isinstance(exc, SandboxError)
        assert not isinstance(exc, ValidationError)
        assert not isinstance(exc, ProtocolError)
        assert not isinstance(exc, PluginError)

    @given(detail_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_57_sandbox_error_is_instance_of_sandbox_error(self, detail):
        """
        **Property 57: Error Categorization – SandboxError Instance**

        For any detail string, SandboxError SHALL be an instance of SandboxError
        and AgentError, but NOT of LLMError, ValidationError, ProtocolError,
        or PluginError.

        **Validates: Requirements 15.1**
        """
        exc = SandboxError(detail)
        assert isinstance(exc, SandboxError)
        assert isinstance(exc, AgentError)
        assert not isinstance(exc, LLMError)
        assert not isinstance(exc, ValidationError)
        assert not isinstance(exc, ProtocolError)
        assert not isinstance(exc, PluginError)

    @given(detail_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_57_validation_error_is_instance_of_validation_error(self, detail):
        """
        **Property 57: Error Categorization – ValidationError Instance**

        For any detail string, ValidationError SHALL be an instance of
        ValidationError and AgentError, but NOT of LLMError, SandboxError,
        ProtocolError, or PluginError.

        **Validates: Requirements 15.1**
        """
        exc = ValidationError(detail)
        assert isinstance(exc, ValidationError)
        assert isinstance(exc, AgentError)
        assert not isinstance(exc, LLMError)
        assert not isinstance(exc, SandboxError)
        assert not isinstance(exc, ProtocolError)
        assert not isinstance(exc, PluginError)

    @given(detail_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_57_protocol_error_is_instance_of_protocol_error(self, detail):
        """
        **Property 57: Error Categorization – ProtocolError Instance**

        For any detail string, ProtocolError SHALL be an instance of
        ProtocolError and AgentError, but NOT of LLMError, SandboxError,
        ValidationError, or PluginError.

        **Validates: Requirements 15.1**
        """
        exc = ProtocolError(detail)
        assert isinstance(exc, ProtocolError)
        assert isinstance(exc, AgentError)
        assert not isinstance(exc, LLMError)
        assert not isinstance(exc, SandboxError)
        assert not isinstance(exc, ValidationError)
        assert not isinstance(exc, PluginError)

    @given(detail_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_57_plugin_error_is_instance_of_plugin_error(self, detail):
        """
        **Property 57: Error Categorization – PluginError Instance**

        For any detail string, PluginError SHALL be an instance of
        PluginError and AgentError, but NOT of LLMError, SandboxError,
        ValidationError, or ProtocolError.

        **Validates: Requirements 15.1**
        """
        exc = PluginError(detail)
        assert isinstance(exc, PluginError)
        assert isinstance(exc, AgentError)
        assert not isinstance(exc, LLMError)
        assert not isinstance(exc, SandboxError)
        assert not isinstance(exc, ValidationError)
        assert not isinstance(exc, ProtocolError)

    # ------------------------------------------------------------------
    # 3. categorize_exception maps each type to itself
    # ------------------------------------------------------------------

    @given(detail_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_categorize_llm_error_returns_llm_error_class(self, detail):
        """
        **Property 57: Error Categorization – categorize_exception for LLMError**

        categorize_exception SHALL return LLMError for any LLMError instance.

        **Validates: Requirements 15.1**
        """
        exc = LLMError(detail)
        result = categorize_exception(exc)
        assert result is LLMError

    @given(detail_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_categorize_sandbox_error_returns_sandbox_error_class(self, detail):
        """
        **Property 57: Error Categorization – categorize_exception for SandboxError**

        categorize_exception SHALL return SandboxError for any SandboxError instance.

        **Validates: Requirements 15.1**
        """
        exc = SandboxError(detail)
        result = categorize_exception(exc)
        assert result is SandboxError

    @given(detail_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_categorize_validation_error_returns_validation_error_class(self, detail):
        """
        **Property 57: Error Categorization – categorize_exception for ValidationError**

        categorize_exception SHALL return ValidationError for any ValidationError instance.

        **Validates: Requirements 15.1**
        """
        exc = ValidationError(detail)
        result = categorize_exception(exc)
        assert result is ValidationError

    @given(detail_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_categorize_protocol_error_returns_protocol_error_class(self, detail):
        """
        **Property 57: Error Categorization – categorize_exception for ProtocolError**

        categorize_exception SHALL return ProtocolError for any ProtocolError instance.

        **Validates: Requirements 15.1**
        """
        exc = ProtocolError(detail)
        result = categorize_exception(exc)
        assert result is ProtocolError

    @given(detail_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_categorize_plugin_error_returns_plugin_error_class(self, detail):
        """
        **Property 57: Error Categorization – categorize_exception for PluginError**

        categorize_exception SHALL return PluginError for any PluginError instance.

        **Validates: Requirements 15.1**
        """
        exc = PluginError(detail)
        result = categorize_exception(exc)
        assert result is PluginError

    def test_property_57_categorize_non_agent_exception_returns_none(self):
        """
        **Property 57: Error Categorization – Non-AgentError Returns None**

        categorize_exception SHALL return None for exceptions that are not
        AgentError subclasses.

        **Validates: Requirements 15.1**
        """
        assert categorize_exception(ValueError("oops")) is None
        assert categorize_exception(RuntimeError("fail")) is None
        assert categorize_exception(Exception("generic")) is None

    # ------------------------------------------------------------------
    # 4. Each error type has a distinct default error code
    # ------------------------------------------------------------------

    def test_property_57_each_error_type_has_distinct_default_error_code(self):
        """
        **Property 57: Error Categorization – Distinct Default Error Codes**

        Each of the five error types SHALL have a distinct DEFAULT_ERROR_CODE,
        ensuring unambiguous categorization.

        **Validates: Requirements 15.1**
        """
        codes = [t.DEFAULT_ERROR_CODE for t in ALL_ERROR_TYPES]
        assert len(set(codes)) == len(codes), (
            f"Duplicate default error codes found: {codes}"
        )

    @given(detail_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_error_type_preserves_error_code(self, detail):
        """
        **Property 57: Error Categorization – Error Code Preserved**

        For any error instance, the error_code attribute SHALL match the
        class's DEFAULT_ERROR_CODE when no explicit code is provided.

        **Validates: Requirements 15.1**
        """
        for error_class in ALL_ERROR_TYPES:
            exc = error_class(detail)
            assert exc.error_code == error_class.DEFAULT_ERROR_CODE, (
                f"{error_class.__name__} error_code {exc.error_code!r} "
                f"!= DEFAULT_ERROR_CODE {error_class.DEFAULT_ERROR_CODE!r}"
            )

    # ------------------------------------------------------------------
    # 5. Error type map covers all five types
    # ------------------------------------------------------------------

    def test_property_57_error_type_map_covers_all_five_types(self):
        """
        **Property 57: Error Categorization – ERROR_TYPE_MAP Coverage**

        ERROR_TYPE_MAP SHALL contain entries for all five error types,
        enabling lookup by name.

        **Validates: Requirements 15.1**
        """
        required_names = {"LLMError", "SandboxError", "ValidationError", "ProtocolError", "PluginError"}
        assert required_names.issubset(set(ERROR_TYPE_MAP.keys())), (
            f"Missing error types in ERROR_TYPE_MAP: {required_names - set(ERROR_TYPE_MAP.keys())}"
        )

    @given(error_class_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_error_type_map_lookup_returns_correct_class(self, error_class):
        """
        **Property 57: Error Categorization – ERROR_TYPE_MAP Lookup**

        For any of the five error types, looking up its name in ERROR_TYPE_MAP
        SHALL return the same class.

        **Validates: Requirements 15.1**
        """
        name = error_class.__name__
        assert ERROR_TYPE_MAP[name] is error_class

    # ------------------------------------------------------------------
    # 6. Error codes in registry have human-readable descriptions
    # ------------------------------------------------------------------

    @given(known_error_code_strategy)
    @settings(deadline=None, max_examples=30)
    def test_property_57_all_error_codes_have_non_empty_descriptions(self, error_code):
        """
        **Property 57: Error Categorization – Non-Empty Descriptions**

        For any registered error code, get_error_description SHALL return
        a non-empty human-readable string.

        **Validates: Requirements 15.1, 15.2**
        """
        description = get_error_description(error_code)
        assert isinstance(description, str)
        assert len(description.strip()) > 0, (
            f"Empty description for error code: {error_code!r}"
        )

    @given(detail_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_error_instance_description_is_non_empty(self, detail):
        """
        **Property 57: Error Categorization – Instance Description Non-Empty**

        For any error instance, the description property SHALL return a
        non-empty string.

        **Validates: Requirements 15.1, 15.2**
        """
        for error_class in ALL_ERROR_TYPES:
            exc = error_class(detail)
            assert isinstance(exc.description, str)
            assert len(exc.description.strip()) > 0

    # ------------------------------------------------------------------
    # 7. Retryable vs non-retryable classification
    # ------------------------------------------------------------------

    def test_property_57_retryable_and_non_retryable_sets_are_disjoint(self):
        """
        **Property 57: Error Categorization – Retryable/Non-Retryable Disjoint**

        The RETRYABLE_ERROR_CODES and NON_RETRYABLE_ERROR_CODES sets SHALL
        be disjoint (no code can be both retryable and non-retryable).

        **Validates: Requirements 15.1, 15.4**
        """
        overlap = RETRYABLE_ERROR_CODES & NON_RETRYABLE_ERROR_CODES
        assert len(overlap) == 0, (
            f"Error codes appear in both retryable and non-retryable sets: {overlap}"
        )

    @given(st.sampled_from(sorted(RETRYABLE_ERROR_CODES)))
    @settings(deadline=None, max_examples=20)
    def test_property_57_retryable_codes_return_true(self, error_code):
        """
        **Property 57: Error Categorization – Retryable Codes Return True**

        For any error code in RETRYABLE_ERROR_CODES, is_retryable SHALL
        return True.

        **Validates: Requirements 15.4**
        """
        assert is_retryable(error_code) is True

    @given(st.sampled_from(sorted(NON_RETRYABLE_ERROR_CODES)))
    @settings(deadline=None, max_examples=20)
    def test_property_57_non_retryable_codes_return_false(self, error_code):
        """
        **Property 57: Error Categorization – Non-Retryable Codes Return False**

        For any error code in NON_RETRYABLE_ERROR_CODES, is_retryable SHALL
        return False.

        **Validates: Requirements 15.4**
        """
        assert is_retryable(error_code) is False

    @given(detail_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_validation_error_is_not_retryable_by_default(self, detail):
        """
        **Property 57: Error Categorization – ValidationError Not Retryable**

        ValidationError SHALL be non-retryable by default, since validation
        failures require code changes, not retries.

        **Validates: Requirements 15.4**
        """
        exc = ValidationError(detail)
        assert exc.retryable is False

    @given(detail_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_error_to_dict_contains_required_fields(self, detail):
        """
        **Property 57: Error Categorization – to_dict Contains Required Fields**

        For any error instance, to_dict SHALL return a dict containing
        errorType, reason, detail, errorCode, description, and retryable.

        **Validates: Requirements 15.1, 15.2**
        """
        required_fields = {"errorType", "reason", "detail", "errorCode", "description", "retryable"}
        for error_class in ALL_ERROR_TYPES:
            exc = error_class(detail)
            d = exc.to_dict()
            assert isinstance(d, dict)
            missing = required_fields - set(d.keys())
            assert not missing, (
                f"{error_class.__name__}.to_dict() missing fields: {missing}"
            )
            assert d["errorType"] == error_class.__name__
            assert isinstance(d["retryable"], bool)

    # ------------------------------------------------------------------
    # 8. Custom error codes can be passed to each type
    # ------------------------------------------------------------------

    @given(detail_strategy, llm_error_code_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_llm_error_accepts_specific_error_codes(self, detail, error_code):
        """
        **Property 57: Error Categorization – LLMError Specific Codes**

        LLMError SHALL accept any LLM-specific error code and preserve it.

        **Validates: Requirements 15.1**
        """
        exc = LLMError(detail, error_code=error_code)
        assert exc.error_code == error_code

    @given(detail_strategy, sandbox_error_code_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_sandbox_error_accepts_specific_error_codes(self, detail, error_code):
        """
        **Property 57: Error Categorization – SandboxError Specific Codes**

        SandboxError SHALL accept any Sandbox-specific error code and preserve it.

        **Validates: Requirements 15.1**
        """
        exc = SandboxError(detail, error_code=error_code)
        assert exc.error_code == error_code

    @given(detail_strategy, protocol_error_code_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_protocol_error_accepts_specific_error_codes(self, detail, error_code):
        """
        **Property 57: Error Categorization – ProtocolError Specific Codes**

        ProtocolError SHALL accept any Protocol-specific error code and preserve it.

        **Validates: Requirements 15.1**
        """
        exc = ProtocolError(detail, error_code=error_code)
        assert exc.error_code == error_code

    @given(detail_strategy, plugin_error_code_strategy)
    @settings(deadline=None, max_examples=20)
    def test_property_57_plugin_error_accepts_specific_error_codes(self, detail, error_code):
        """
        **Property 57: Error Categorization – PluginError Specific Codes**

        PluginError SHALL accept any Plugin-specific error code and preserve it.

        **Validates: Requirements 15.1**
        """
        exc = PluginError(detail, error_code=error_code)
        assert exc.error_code == error_code
