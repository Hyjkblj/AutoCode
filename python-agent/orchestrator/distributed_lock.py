from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from time import sleep
from time import time
from uuid import uuid4


_LOCAL_LOCK = threading.Lock()
_LOCAL_LEASES: dict[str, tuple[str, float]] = {}


@dataclass
class TaskLease:
    owner: "DistributedTaskLock"
    key: str
    token: str
    acquired: bool
    _renew_stop: threading.Event | None = None
    _renew_thread: threading.Thread | None = None

    def start_renewal(self) -> None:
        if not self.acquired or self._renew_stop is not None:
            return
        stop = threading.Event()
        self._renew_stop = stop

        def _runner() -> None:
            while not stop.wait(self.owner.renew_interval_seconds):
                try:
                    self.owner.renew(self.key, self.token)
                except Exception:
                    return

        thread = threading.Thread(target=_runner, name=f"task-lease-renew-{self.key}", daemon=True)
        thread.start()
        self._renew_thread = thread

    def release(self) -> None:
        if self._renew_stop is not None:
            self._renew_stop.set()
        if self.acquired:
            self.owner.release(self.key, self.token)
            self.acquired = False


class DistributedTaskLock:
    def __init__(
        self,
        *,
        backend: str | None = None,
        redis_url: str | None = None,
        namespace: str = "autocode:tasklock",
        lease_seconds: int = 60,
        renew_interval_seconds: int = 20,
        redis_client: object | None = None,
    ) -> None:
        self.backend = (backend or os.getenv("MVP_DISTRIBUTED_LOCK_BACKEND", "memory")).strip().lower() or "memory"
        self.redis_url = (redis_url or os.getenv("MVP_REDIS_URL", "redis://127.0.0.1:6379/0")).strip()
        self.namespace = namespace.strip() or "autocode:tasklock"
        self.lease_seconds = max(5, int(lease_seconds))
        self.renew_interval_seconds = max(2, min(int(renew_interval_seconds), self.lease_seconds - 1))
        self._redis = redis_client
        self._redis_enabled = False
        self._renew_script = None
        self._release_script = None
        self._init_redis_if_needed()

    def acquire(self, task_id: str) -> TaskLease:
        normalized = self._key(task_id)
        token = uuid4().hex
        acquired = self._acquire_redis(normalized, token) if self._redis_enabled else self._acquire_local(normalized, token)
        lease = TaskLease(owner=self, key=normalized, token=token, acquired=acquired)
        if acquired:
            lease.start_renewal()
        return lease

    def renew(self, key: str, token: str) -> bool:
        if self._redis_enabled:
            return self._renew_redis(key, token)
        return self._renew_local(key, token)

    def release(self, key: str, token: str) -> bool:
        if self._redis_enabled:
            return self._release_redis(key, token)
        return self._release_local(key, token)

    def _key(self, task_id: str) -> str:
        normalized = str(task_id or "").strip()
        return f"{self.namespace}:{normalized}"

    def _acquire_local(self, key: str, token: str) -> bool:
        now = time()
        expires_at = now + self.lease_seconds
        with _LOCAL_LOCK:
            current = _LOCAL_LEASES.get(key)
            if current is not None and current[1] > now:
                return False
            _LOCAL_LEASES[key] = (token, expires_at)
            return True

    def _renew_local(self, key: str, token: str) -> bool:
        with _LOCAL_LOCK:
            current = _LOCAL_LEASES.get(key)
            if current is None or current[0] != token:
                return False
            _LOCAL_LEASES[key] = (token, time() + self.lease_seconds)
            return True

    def _release_local(self, key: str, token: str) -> bool:
        with _LOCAL_LOCK:
            current = _LOCAL_LEASES.get(key)
            if current is None or current[0] != token:
                return False
            _LOCAL_LEASES.pop(key, None)
            return True

    def _init_redis_if_needed(self) -> None:
        if self.backend != "redis":
            self._redis_enabled = False
            return
        if self._redis is None:
            try:
                import redis  # type: ignore

                self._redis = redis.from_url(self.redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None
                self._redis_enabled = False
                return
        try:
            self._renew_script = self._redis.register_script(
                "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end"
            )
            self._release_script = self._redis.register_script(
                "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
            )
            self._redis_enabled = True
        except Exception:
            self._redis = None
            self._redis_enabled = False

    def _acquire_redis(self, key: str, token: str) -> bool:
        try:
            return bool(self._redis.set(key, token, nx=True, ex=self.lease_seconds))
        except Exception:
            self._redis_enabled = False
            return self._acquire_local(key, token)

    def _renew_redis(self, key: str, token: str) -> bool:
        try:
            return bool(self._renew_script(keys=[key], args=[token, self.lease_seconds]))
        except Exception:
            return False

    def _release_redis(self, key: str, token: str) -> bool:
        try:
            return bool(self._release_script(keys=[key], args=[token]))
        except Exception:
            return False
