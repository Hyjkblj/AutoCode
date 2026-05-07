from __future__ import annotations


class AgentError(RuntimeError):
    def __init__(
        self,
        reason: str,
        detail: str | None = None,
        *,
        error_code: str | None = None,
        retryable: bool = False,
    ) -> None:
        self.reason = (reason or "agent_error").strip() or "agent_error"
        self.detail = (detail or "").strip()
        self.error_code = (error_code or "").strip()
        self.retryable = bool(retryable)
        message = self.detail or self.reason
        super().__init__(message)


class LLMError(AgentError):
    def __init__(self, detail: str, *, retryable: bool = False) -> None:
        super().__init__("llm_error", detail, error_code="LLM_ERROR", retryable=retryable)


class SandboxError(AgentError):
    def __init__(self, detail: str, *, retryable: bool = False) -> None:
        super().__init__("sandbox_error", detail, error_code="SANDBOX_ERROR", retryable=retryable)


class ValidationError(AgentError):
    def __init__(self, detail: str) -> None:
        super().__init__("validation_error", detail, error_code="VALIDATION_ERROR", retryable=False)


class ProtocolError(AgentError):
    def __init__(self, detail: str, *, retryable: bool = True) -> None:
        super().__init__("protocol_error", detail, error_code="PROTOCOL_ERROR", retryable=retryable)


class PluginError(AgentError):
    def __init__(self, detail: str, *, retryable: bool = False) -> None:
        super().__init__("plugin_error", detail, error_code="PLUGIN_ERROR", retryable=retryable)


def categorize_exception(exc: Exception) -> type[AgentError] | None:
    """Map a raw exception to the matching AgentError subclass, or None."""
    if isinstance(exc, AgentError):
        return type(exc)
    name = type(exc).__name__.lower()
    if "llm" in name or "openai" in name or "anthropic" in name:
        return LLMError
    if "sandbox" in name or "container" in name or "docker" in name:
        return SandboxError
    if "validation" in name or "value" in name or "type" in name:
        return ValidationError
    if "protocol" in name or "http" in name or "connection" in name:
        return ProtocolError
    if "plugin" in name:
        return PluginError
    return None
