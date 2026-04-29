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
