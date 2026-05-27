from __future__ import annotations

import json
import os
from datetime import datetime
from datetime import timezone
from threading import Lock
from typing import Any


_LOCAL_STORE: dict[str, list[str]] = {}
_LOCAL_LOCK = Lock()


class RedisMemory:
    def __init__(
        self,
        *,
        backend: str | None = None,
        redis_url: str | None = None,
        namespace: str = "autocode:memory",
        max_entries: int = 50,
        redis_client: Any | None = None,
    ) -> None:
        self.backend = (backend or os.getenv("MVP_MEMORY_BACKEND", "redis")).strip().lower() or "redis"
        self.redis_url = (redis_url or os.getenv("MVP_REDIS_URL", "redis://127.0.0.1:6379/0")).strip()
        self.namespace = namespace.strip() or "autocode:memory"
        self.max_entries = max(1, max_entries)
        self._redis = redis_client
        self._redis_enabled = False
        self._init_redis_if_needed()

    def project_key_for_task(self, task: dict[str, Any]) -> str:
        for key in ("projectId", "project", "workspacePath", "workspaceRef", "sessionId", "sessionKey"):
            value = task.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return _normalize_project_key(text)
        return "default"

    def recent(self, project_key: str, limit: int = 5) -> list[dict[str, Any]]:
        bounded_limit = max(1, limit)
        key = self._key(project_key)
        raw_items: list[str] = []

        if self._redis_enabled and self._redis is not None:
            try:
                values = self._redis.lrange(key, -bounded_limit, -1)
                for item in values:
                    if isinstance(item, bytes):
                        raw_items.append(item.decode("utf-8", errors="replace"))
                    else:
                        raw_items.append(str(item))
            except Exception:  # noqa: BLE001
                raw_items = []
        else:
            with _LOCAL_LOCK:
                values = _LOCAL_STORE.get(key, [])
                raw_items = list(values[-bounded_limit:])

        decoded: list[dict[str, Any]] = []
        for raw in raw_items:
            try:
                item = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                decoded.append(item)
        return decoded

    def append(self, project_key: str, record: dict[str, Any]) -> None:
        payload = dict(record)
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        key = self._key(project_key)

        if self._redis_enabled and self._redis is not None:
            try:
                self._redis.rpush(key, encoded)
                self._redis.ltrim(key, -self.max_entries, -1)
                return
            except Exception:  # noqa: BLE001
                # Fall through to local memory fallback.
                pass

        with _LOCAL_LOCK:
            bucket = _LOCAL_STORE.setdefault(key, [])
            bucket.append(encoded)
            if len(bucket) > self.max_entries:
                del bucket[: len(bucket) - self.max_entries]

    def _init_redis_if_needed(self) -> None:
        if self.backend != "redis":
            self._redis_enabled = False
            return
        if self._redis is not None:
            self._redis_enabled = True
            return
        try:
            import redis  # type: ignore

            client = redis.from_url(self.redis_url, decode_responses=False)
            client.ping()
            self._redis = client
            self._redis_enabled = True
        except Exception:  # noqa: BLE001
            self._redis = None
            self._redis_enabled = False

    def store_code_knowledge(self, project_key: str, knowledge: dict) -> None:
        key = f"{self.namespace}:{project_key}:knowledge"
        if self._redis:
            import json
            self._redis.hset(key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in knowledge.items()})

    def get_code_knowledge(self, project_key: str) -> dict:
        key = f"{self.namespace}:{project_key}:knowledge"
        if self._redis:
            raw = self._redis.hgetall(key)
            return {k.decode(): v.decode() for k, v in raw.items()} if raw else {}
        return {}

    def store_file_summary(self, project_key: str, file_path: str, summary: str) -> None:
        key = f"{self.namespace}:{project_key}:file_summaries"
        if self._redis:
            self._redis.hset(key, file_path, summary)

    def get_file_summaries(self, project_key: str) -> dict[str, str]:
        key = f"{self.namespace}:{project_key}:file_summaries"
        if self._redis:
            raw = self._redis.hgetall(key)
            return {k.decode(): v.decode() for k, v in raw.items()}
        return {}

    def store_error_pattern(self, project_key: str, error: str, fix: str) -> None:
        import hashlib
        error_hash = hashlib.md5(error.encode()).hexdigest()[:12]
        key = f"{self.namespace}:{project_key}:error_fixes"
        if self._redis:
            self._redis.hset(key, error_hash, f"{error}\n---\n{fix}")

    def get_error_fixes(self, project_key: str, error: str) -> list[str]:
        key = f"{self.namespace}:{project_key}:error_fixes"
        if self._redis:
            import hashlib
            error_hash = hashlib.md5(error.encode()).hexdigest()[:12]
            raw = self._redis.hget(key, error_hash)
            if raw:
                return [raw.decode().split("\n---\n", 1)[-1]]
        return []

    def _key(self, project_key: str) -> str:
        normalized = _normalize_project_key(project_key)
        return f"{self.namespace}:{normalized}"


def _normalize_project_key(raw: str) -> str:
    key = raw.strip().lower()
    if not key:
        return "default"
    normalized = key.replace("\\", "/")
    normalized = normalized.replace(":", "_")
    normalized = normalized.replace(" ", "_")
    return normalized

