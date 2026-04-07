from __future__ import annotations

import json
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

