from __future__ import annotations

import mimetypes
import json
from pathlib import Path
from uuid import uuid4
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError


class ControlPlaneClient:
    def __init__(self, base_url: str, agent_token: str, agent_version: str = "0.1.0", timeout_seconds: int = 15) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_token = agent_token
        self.agent_version = agent_version.strip() or "0.1.0"
        self.timeout_seconds = timeout_seconds if timeout_seconds > 0 else 15
        self.user_agent = f"AutoCode-Python-Agent/{self.agent_version}"

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
        safe_task_id = parse.quote(task_id, safe="")
        return self._post_json(f"/api/v1/agent/tasks/{safe_task_id}/events", {"event": event})

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
            "X-Agent-Token": self.agent_token,
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
                    raise RuntimeError(str(decoded.get("error") or "artifact upload failed"))
                return _extract_payload(decoded)
        except HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"POST /api/v1/tasks/{safe_task_id}/artifacts failed: {exc.code} {message}") from exc

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
            "X-Agent-Token": self.agent_token,
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
                    raise RuntimeError(f"invalid json response from {url}: expected object")
                if decoded.get("ok") is False:
                    raise RuntimeError(str(decoded.get("error") or f"{method} {path} failed"))
                return decoded
        except HTTPError as exc:
            if exc.code == 204:
                return None
            message = exc.read().decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"{method} {path} failed: {exc.code} {message}") from exc


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

