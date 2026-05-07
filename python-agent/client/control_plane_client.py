from __future__ import annotations

import json
import logging
import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse, request
from urllib.error import HTTPError
from uuid import uuid4

from utils.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from utils.observability import TaskObservability

# ACK error codes — must stay in sync with shared-protocol AckErrorCode enum.
# Non-retryable errors: agent should NOT re-attempt delivery.
NON_RETRYABLE_ACK_ERRORS: frozenset[str] = frozenset({
    "INVALID_NODE_ID",
    "NODE_NOT_REGISTERED",
    "MISSING_EVENT_ID",
    "TASK_NOT_FOUND",
    "ACCESS_DENIED",
    "INVALID_EVENT",
    "ILLEGAL_STATE_TRANSITION",
})



class ControlPlaneRequestError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool, status_code: int | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


@dataclass(frozen=True)
class PublishEventResult:
    response: dict[str, Any] | None
    attempts: int
    total_delay_seconds: float = 0.0
    circuit_breaker_triggered: bool = False
    final_error: Exception | None = None
    ack_response: dict[str, Any] | None = None  # ACK response data (seq, accepted, duplicate, errorCode)


class ControlPlaneClient:
    def __init__(self, base_url: str, agent_token: str, agent_version: str = "0.1.0", timeout_seconds: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_token = agent_token
        self.agent_version = agent_version.strip() or "0.1.0"
        self.timeout_seconds = timeout_seconds if timeout_seconds > 0 else 15
        self.user_agent = f"AutoCode-Python-Agent/{self.agent_version}"
        self._jwt_token: str | None = None
        self._jwt_expires_at: float = 0.0

        # Initialize circuit breaker for event delivery
        self._event_circuit_breaker = CircuitBreaker(
            name="control_plane_events",
            failure_threshold=3,
            recovery_timeout_seconds=60.0
        )
        
        # Initialize logger for structured logging
        self._logger = logging.getLogger(f"{__name__}.ControlPlaneClient")
        
        # Metrics tracking
        self._event_delivery_metrics = {
            "total_attempts": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "circuit_breaker_opens": 0,
            "retry_exhausted": 0
        }

    def register(self, node_id: str, capabilities: str | None = None) -> dict[str, Any] | None:
        body: dict[str, Any] = {
            "nodeId": node_id,
            "version": self.agent_version,
        }
        if capabilities and capabilities.strip():
            body["capabilities"] = capabilities.strip()
        return self._post_json("/api/v1/agent/register", body)

    def heartbeat(self, node_id: str) -> dict[str, Any] | None:
        return self._post_json("/api/v1/agent/heartbeat", {"nodeId": node_id})

    def poll_next_task(self, node_id: str, profile: str = "ai-agent") -> dict[str, Any] | None:
        query = {"nodeId": node_id, "profile": profile}
        data = self._request_json("GET", "/api/v1/agent/tasks/next", query=query)
        return _extract_payload(data) if data is not None else None

    def publish_event(self, task_id: str, event: dict[str, Any]) -> dict[str, Any] | None:
        """
        Publish event to Control Plane and return the ACK payload.
        
        The Control Plane responds with the standard ApiResponse envelope and this
        client unwraps it before returning:
        {
            "seq": 123,
            "accepted": true,
            "duplicate": false,
            "errorCode": null
        }
        
        Args:
            task_id: Task identifier
            event: Event data to publish
            
        Returns:
            ACK payload from Control Plane, or None if no response
        """
        safe_task_id = parse.quote(task_id, safe="")
        return self._post_json(f"/api/v1/agent/tasks/{safe_task_id}/events", {"event": event})

    def publish_event_with_retry(
        self,
        task_id: str,
        event: dict[str, Any],
        *,
        max_attempts: int = 5,
        initial_backoff_seconds: float = 1.0,
        observability: TaskObservability | None = None,
    ) -> dict[str, Any] | None:
        """
        Publish event with retry logic - convenience method that returns only the response.
        
        Args:
            task_id: Task identifier
            event: Event data to publish
            max_attempts: Maximum retry attempts (default 5)
            initial_backoff_seconds: Initial backoff delay (default 1s)
            observability: Optional observability context
            
        Returns:
            Response from successful delivery, or None if all attempts failed
        """
        result = self.publish_event_with_retry_result(
            task_id,
            event,
            max_attempts=max_attempts,
            initial_backoff_seconds=initial_backoff_seconds,
            observability=observability,
        )
        return result.response

    def publish_event_with_retry_result(
        self,
        task_id: str,
        event: dict[str, Any],
        *,
        max_attempts: int = 5,
        initial_backoff_seconds: float = 1.0,
        observability: TaskObservability | None = None,
    ) -> PublishEventResult:
        """
        Publish event with exponential backoff retry logic and circuit breaker integration.
        
        Implements Requirement 2.2: "WHEN the Control_Plane is unavailable, THE Python_Agent 
        SHALL retry event delivery with exponential backoff up to 5 attempts"
        
        Args:
            task_id: Task identifier
            event: Event data to publish
            max_attempts: Maximum retry attempts (default 5 per requirement)
            initial_backoff_seconds: Initial backoff delay (default 1s)
            observability: Optional observability context for structured logging
            
        Returns:
            PublishEventResult with delivery status and metrics
        """
        attempts = max(1, min(int(max_attempts), 5))  # Enforce requirement limit
        backoff = max(1.0, float(initial_backoff_seconds))  # Start at 1s per requirement
        total_delay = 0.0
        circuit_breaker_triggered = False
        final_error = None
        
        # Structured logging context
        log_context = {
            "taskId": task_id,
            "eventType": event.get("type", "unknown"),
            "maxAttempts": attempts,
            "initialBackoff": backoff
        }
        
        if observability:
            log_context.update({
                "traceId": observability.trace_id,
                "runId": observability.run_id
            })
        
        self._logger.info("Starting event delivery with retry", extra=log_context)
        
        for attempt in range(1, attempts + 1):
            attempt_start = time.time()
            
            # Calculate exponential backoff: 1s, 2s, 4s, 8s, 16s
            if attempt > 1:
                delay = backoff * (2 ** (attempt - 2))  # 1s, 2s, 4s, 8s, 16s
                total_delay += delay
                
                self._logger.info(
                    f"Retrying event delivery after backoff (attempt {attempt}/{attempts})",
                    extra={**log_context, "attempt": attempt, "backoffSeconds": delay}
                )
                time.sleep(delay)
            
            try:
                # Track metrics
                self._event_delivery_metrics["total_attempts"] += 1
                
                # Check circuit breaker state before attempting
                try:
                    # Use circuit breaker for event delivery
                    def publish_operation():
                        return self.publish_event(task_id, event)
                    
                    response = self._event_circuit_breaker.call(publish_operation)
                    
                    # Extract and validate ACK response
                    ack_response = self.extract_ack_response(response)
                    if ack_response is None:
                        # Invalid ACK response format - treat as error
                        raise ControlPlaneRequestError(
                            "Invalid ACK response format from Control Plane",
                            retryable=True
                        )
                    
                    # Log ACK response details
                    self._logger.info(
                        "Received ACK response",
                        extra={
                            **log_context,
                            "attempt": attempt,
                            "ackSeq": ack_response["seq"],
                            "ackAccepted": ack_response["accepted"],
                            "ackDuplicate": ack_response["duplicate"],
                            "ackErrorCode": ack_response["errorCode"]
                        }
                    )
                    
                    # Check if event was accepted
                    if not ack_response["accepted"]:
                        error_code = ack_response.get("errorCode", "UNKNOWN_ERROR")
                        
                        # Determine if error is retryable (synced with AckErrorCode enum)
                        retryable = error_code not in NON_RETRYABLE_ACK_ERRORS
                        
                        raise ControlPlaneRequestError(
                            f"Event not accepted by Control Plane: {error_code}",
                            retryable=retryable
                        )
                    
                    # Event was accepted - check for duplicate
                    if ack_response["duplicate"]:
                        self._logger.info(
                            "Event was duplicate but acknowledged",
                            extra={
                                **log_context,
                                "attempt": attempt,
                                "ackSeq": ack_response["seq"]
                            }
                        )
                    
                except CircuitBreakerOpenError as exc:
                    circuit_breaker_triggered = True
                    final_error = exc
                    self._event_delivery_metrics["circuit_breaker_opens"] += 1
                    
                    self._logger.warning(
                        "Circuit breaker open - event delivery blocked",
                        extra={
                            **log_context,
                            "attempt": attempt,
                            "circuitBreakerState": self._event_circuit_breaker.state()
                        }
                    )
                    
                    # Don't retry when circuit breaker is open
                    break
                
                # Success - record metrics and log
                self._event_delivery_metrics["successful_deliveries"] += 1
                attempt_duration = time.time() - attempt_start
                
                self._logger.info(
                    "Event delivery successful",
                    extra={
                        **log_context,
                        "attempt": attempt,
                        "durationSeconds": round(attempt_duration, 3),
                        "totalDelaySeconds": round(total_delay, 3)
                    }
                )
                
                # Record observability metrics
                if observability:
                    observability.record_event_publish(
                        event.get("type", "unknown"),
                        attempts=attempt
                    )
                    observability.record_metric(
                        "event_delivery_success_total",
                        1,
                        unit="count",
                        attempts=str(attempt)
                    )
                
                return PublishEventResult(
                    response=response,
                    attempts=attempt,
                    total_delay_seconds=total_delay,
                    circuit_breaker_triggered=circuit_breaker_triggered,
                    final_error=None,
                    ack_response=ack_response
                )
                
            except Exception as exc:
                final_error = exc
                attempt_duration = time.time() - attempt_start
                retryable = isinstance(exc, ControlPlaneRequestError) and exc.retryable
                
                self._logger.warning(
                    f"Event delivery failed (attempt {attempt}/{attempts})",
                    extra={
                        **log_context,
                        "attempt": attempt,
                        "error": str(exc),
                        "retryable": retryable,
                        "durationSeconds": round(attempt_duration, 3)
                    }
                )
                
                # For non-retryable errors, return result immediately
                if not retryable:
                    self._event_delivery_metrics["failed_deliveries"] += 1
                    
                    self._logger.error(
                        "Event delivery failed with non-retryable error",
                        extra={
                            **log_context,
                            "attempt": attempt,
                            "error": str(exc),
                            "totalDelaySeconds": round(total_delay, 3)
                        }
                    )
                    
                    # Record observability metrics for non-retryable failure
                    if observability:
                        observability.record_metric(
                            "event_delivery_failure_total",
                            1,
                            unit="count",
                            attempts=str(attempt),
                            errorType="non_retryable"
                        )
                    
                    return PublishEventResult(
                        response=None,
                        attempts=attempt,
                        total_delay_seconds=total_delay,
                        circuit_breaker_triggered=circuit_breaker_triggered,
                        final_error=exc,
                        ack_response=None
                    )
                
                # If this is the last attempt, break out of loop
                if attempt >= attempts:
                    break
        
        # All attempts failed
        self._event_delivery_metrics["failed_deliveries"] += 1
        if not circuit_breaker_triggered:
            self._event_delivery_metrics["retry_exhausted"] += 1
        
        self._logger.error(
            "Event delivery failed after all retry attempts",
            extra={
                **log_context,
                "totalAttempts": attempts,
                "totalDelaySeconds": round(total_delay, 3),
                "circuitBreakerTriggered": circuit_breaker_triggered,
                "finalError": str(final_error) if final_error else None
            }
        )
        
        # Record observability metrics for failure
        if observability:
            observability.record_metric(
                "event_delivery_failure_total",
                1,
                unit="count",
                attempts=str(attempts),
                circuitBreakerTriggered=str(circuit_breaker_triggered)
            )
        
        return PublishEventResult(
            response=None,
            attempts=attempts,
            total_delay_seconds=total_delay,
            circuit_breaker_triggered=circuit_breaker_triggered,
            final_error=final_error,
            ack_response=None
        )

    def get_event_delivery_metrics(self) -> dict[str, Any]:
        """
        Get event delivery metrics for monitoring and observability.
        
        Returns:
            Dictionary containing delivery success/failure rates and circuit breaker stats
        """
        total = self._event_delivery_metrics["total_attempts"]
        success_rate = (
            self._event_delivery_metrics["successful_deliveries"] / total * 100
            if total > 0 else 0.0
        )
        failure_rate = (
            self._event_delivery_metrics["failed_deliveries"] / total * 100
            if total > 0 else 0.0
        )
        
        return {
            "totalAttempts": total,
            "successfulDeliveries": self._event_delivery_metrics["successful_deliveries"],
            "failedDeliveries": self._event_delivery_metrics["failed_deliveries"],
            "successRate": round(success_rate, 2),
            "failureRate": round(failure_rate, 2),
            "circuitBreakerOpens": self._event_delivery_metrics["circuit_breaker_opens"],
            "retryExhausted": self._event_delivery_metrics["retry_exhausted"],
            "circuitBreakerState": self._event_circuit_breaker.state()
        }

    def extract_ack_response(self, response: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        Extract ACK response data from Control Plane response.
        
        Expected response format after ApiResponse unwrapping:
        {
            "seq": 123,
            "accepted": true,
            "duplicate": false,
            "errorCode": null
        }
        
        Args:
            response: Full response from Control Plane
            
        Returns:
            ACK response data with seq, accepted, duplicate, errorCode fields, or None if invalid
        """
        if not response or not isinstance(response, dict):
            return None
            
        # Validate required ACK fields
        required_fields = ["seq", "accepted", "duplicate", "errorCode"]
        if not all(field in response for field in required_fields):
            return None
            
        # Validate field types
        if not isinstance(response.get("seq"), int):
            return None
        if response["seq"] < 0:
            return None
        if not isinstance(response.get("accepted"), bool):
            return None
        if not isinstance(response.get("duplicate"), bool):
            return None
            
        # errorCode can be string or None
        error_code = response.get("errorCode")
        if error_code is not None and not isinstance(error_code, str):
            return None
            
        return {
            "seq": response["seq"],
            "accepted": response["accepted"],
            "duplicate": response["duplicate"],
            "errorCode": error_code
        }

    def validate_ack_response(self, ack_response: dict[str, Any], expected_seq: int | None = None) -> bool:
        """
        Validate ACK response structure and optionally check sequence number.
        
        Args:
            ack_response: ACK response data from extract_ack_response
            expected_seq: Optional expected sequence number to validate
            
        Returns:
            True if ACK response is valid, False otherwise
        """
        if not ack_response or not isinstance(ack_response, dict):
            return False
            
        # Check required fields exist and have correct types
        required_fields = {
            "seq": int,
            "accepted": bool,
            "duplicate": bool
        }
        
        for field, expected_type in required_fields.items():
            if field not in ack_response:
                return False
            if not isinstance(ack_response[field], expected_type):
                return False
                
        # Validate sequence number constraints (minimum: 0 per schema)
        seq = ack_response["seq"]
        if seq < 0:
            return False
                
        # Validate sequence number if provided
        if expected_seq is not None:
            if seq != expected_seq:
                return False
                
        # errorCode should be string or None
        error_code = ack_response.get("errorCode")
        if error_code is not None and not isinstance(error_code, str):
            return False
            
        return True
    
    def publish_event_with_ack(
        self,
        task_id: str,
        event: dict[str, Any],
        *,
        max_attempts: int = 5,
        initial_backoff_seconds: float = 1.0,
        observability: TaskObservability | None = None,
    ) -> dict[str, Any] | None:
        """
        Publish event with retry logic and return only the ACK response data.
        
        Args:
            task_id: Task identifier
            event: Event data to publish
            max_attempts: Maximum retry attempts (default 5)
            initial_backoff_seconds: Initial backoff delay (default 1s)
            observability: Optional observability context
            
        Returns:
            ACK response data with seq, accepted, duplicate, errorCode fields, or None if failed
            
        Raises:
            ControlPlaneRequestError: If event delivery fails with non-retryable error or after all retries
        """
        result = self.publish_event_with_retry_result(
            task_id,
            event,
            max_attempts=max_attempts,
            initial_backoff_seconds=initial_backoff_seconds,
            observability=observability,
        )
        
        # If there was a final error, raise it
        if result.final_error is not None:
            raise result.final_error
            
        return result.ack_response

    def reset_metrics(self) -> None:
        """Reset event delivery metrics - useful for testing."""
        self._event_delivery_metrics = {
            "total_attempts": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "circuit_breaker_opens": 0,
            "retry_exhausted": 0
        }

    def upload_artifact(
        self,
        task_id: str,
        file_path: str,
        *,
        name: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any] | None:
        source = Path(file_path).resolve(strict=False)
        if not source.exists() or not source.is_file():
            raise RuntimeError(f"artifact file not found: {source}")

        file_name = source.name
        artifact_name = (name or file_name).strip() or file_name
        mime = (content_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream").strip()

        safe_task_id = parse.quote(task_id, safe="")
        url = _build_url(self.base_url, f"/api/v1/tasks/{safe_task_id}/artifacts", None)

        with source.open("rb") as fh:
            file_bytes = fh.read()

        boundary = "----AutoCodeBoundary" + uuid4().hex
        data = _build_multipart_payload(
            boundary=boundary,
            fields={"name": artifact_name},
            files={"file": (file_name, file_bytes, mime)},
        )
        headers = {
            **self._get_auth_header(),
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        req = request.Request(url=url, data=data, method="POST", headers=headers)
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:  # noqa: S310
                status = getattr(resp, "status", None) or resp.getcode()
                if status == 204:
                    return None
                raw = resp.read().decode("utf-8").strip()
                if not raw:
                    return {}
                decoded = json.loads(raw)
                if not isinstance(decoded, dict):
                    raise RuntimeError(f"invalid json response from {url}: expected object")
                if decoded.get("ok") is False:
                    raise ControlPlaneRequestError(
                        str(decoded.get("error") or "artifact upload failed"),
                        retryable=False,
                        status_code=status,
                    )
                return _extract_payload(decoded)
        except HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace").strip()
            raise ControlPlaneRequestError(
                f"POST /api/v1/tasks/{safe_task_id}/artifacts failed: {exc.code} {message}",
                retryable=_is_retryable_http_status(exc.code),
                status_code=exc.code,
            ) from exc

    def _obtain_jwt(self) -> str | None:
        """Request a short-lived JWT from the control plane using the static agent token."""
        url = f"{self.base_url}/api/v1/auth/agent/token"
        body = json.dumps({"agentToken": self.agent_token}).encode("utf-8")
        req = request.Request(
            url=url,
            method="POST",
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "User-Agent": self.user_agent,
            },
        )
        try:
            with request.urlopen(req, timeout=5) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8").strip()
                if not raw:
                    return None
                data = json.loads(raw)
                payload = data.get("payload", data)
                jwt = payload.get("accessToken")
                expires_in = int(payload.get("expiresInSeconds", 900))
                if jwt:
                    self._jwt_token = jwt
                    self._jwt_expires_at = time.time() + expires_in - 30  # 30s safety margin
                return jwt
        except Exception:
            return None

    def _get_auth_header(self) -> dict[str, str]:
        """Return auth header, preferring JWT over static token."""
        now = time.time()
        if self._jwt_token and now < self._jwt_expires_at:
            return {"Authorization": f"Bearer {self._jwt_token}"}
        # Try to refresh JWT (non-blocking: fall back to static token on failure)
        jwt = self._obtain_jwt()
        if jwt:
            return {"Authorization": f"Bearer {jwt}"}
        return {"X-Agent-Token": self.agent_token}

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any] | None:
        data = self._request_json("POST", path, body=body)
        return _extract_payload(data) if data is not None else None

    def _request_json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        query: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        url = _build_url(self.base_url, path, query)
        data_bytes = None
        headers = {
            **self._get_auth_header(),
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if body is not None:
            data_bytes = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        req = request.Request(url=url, data=data_bytes, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:  # noqa: S310
                status = getattr(resp, "status", None) or resp.getcode()
                if status == 204:
                    return None
                raw = resp.read().decode("utf-8").strip()
                if not raw:
                    return {}
                decoded = json.loads(raw)
                if not isinstance(decoded, dict):
                    raise ControlPlaneRequestError(
                        f"invalid json response from {url}: expected object",
                        retryable=False,
                        status_code=status,
                    )
                if decoded.get("ok") is False:
                    raise ControlPlaneRequestError(
                        str(decoded.get("error") or f"{method} {path} failed"),
                        retryable=False,
                        status_code=status,
                    )
                return decoded
        except HTTPError as exc:
            if exc.code == 204:
                return None
            message = exc.read().decode("utf-8", errors="replace").strip()
            raise ControlPlaneRequestError(
                f"{method} {path} failed: {exc.code} {message}",
                retryable=_is_retryable_http_status(exc.code),
                status_code=exc.code,
            ) from exc
        except (urllib_error.URLError, TimeoutError) as exc:
            raise ControlPlaneRequestError(
                f"{method} {path} failed: {exc}",
                retryable=True,
            ) from exc


def _build_url(base_url: str, path: str, query: dict[str, str] | None) -> str:
    url = f"{base_url}{path}"
    if not query:
        return url
    return f"{url}?{parse.urlencode(query)}"


def _extract_payload(decoded: dict[str, Any]) -> dict[str, Any]:
    payload = decoded.get("payload")
    if isinstance(payload, dict):
        return payload
    return decoded


def _build_multipart_payload(
    *,
    boundary: str,
    fields: dict[str, str],
    files: dict[str, tuple[str, bytes, str]],
) -> bytes:
    chunks: list[bytes] = []
    separator = f"--{boundary}\r\n".encode("utf-8")
    for key, value in fields.items():
        chunks.append(separator)
        chunks.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        chunks.append(value.encode("utf-8"))
        chunks.append(b"\r\n")

    for field_name, (filename, content, content_type) in files.items():
        chunks.append(separator)
        chunks.append(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        chunks.append(content)
        chunks.append(b"\r\n")

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)


def _is_retryable_http_status(status_code: int | None) -> bool:
    if status_code is None:
        return True
    if status_code >= 500:
        return True
    return status_code in {408, 425, 429}

