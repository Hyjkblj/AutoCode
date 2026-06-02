"""
Redis-based persistent outbox for reliable event delivery.

This module implements the outbox pattern using Redis for event persistence,
ensuring events are not lost during system failures or restarts.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

from jsonschema import ValidationError, validate


# JSON Schema for event validation
EVENT_SCHEMA = {
    "type": "object",
    "required": ["eventId", "eventVersion", "taskId", "assistant", "type", "timestamp", "seq", "payload"],
    "properties": {
        "eventId": {"type": "string", "pattern": "^evt_[a-f0-9]{32}$"},
        "eventVersion": {"type": "integer", "minimum": 1},
        "taskId": {"type": "string", "minLength": 1},
        "assistant": {"type": "string", "minLength": 1},
        "type": {"type": "string", "minLength": 1},
        "timestamp": {"type": "string", "format": "date-time"},
        "seq": {"type": "integer", "minimum": 0},
        "payload": {"type": "object"},
        "sessionId": {"type": "string"}
    },
    "additionalProperties": False
}


class RedisOutboxError(Exception):
    """Base exception for Redis outbox operations."""
    pass


class EventValidationError(RedisOutboxError):
    """Raised when event validation fails."""
    pass


class RedisOutbox:
    """
    Redis-based persistent outbox for reliable event delivery.
    
    This class implements the outbox pattern using Redis for event persistence.
    Events are stored in Redis before delivery attempts, ensuring they survive
    system restarts and failures.
    
    Features:
    - Event persistence to Redis before delivery
    - JSON schema validation for event serialization/deserialization
    - Atomic event storage with Redis transactions
    - Event recovery after system restart
    - Sequence number management per task
    """
    
    def __init__(
        self,
        *,
        backend: str | None = None,
        redis_url: str | None = None,
        namespace: str = "autocode:outbox",
        redis_client: Any | None = None,
        ttl_seconds: int = 86400,  # 24 hours default TTL
    ) -> None:
        """
        Initialize Redis outbox.
        
        Args:
            backend: Backend type ('redis' or 'memory' for testing)
            redis_url: Redis connection URL
            namespace: Redis key namespace for outbox data
            redis_client: Pre-configured Redis client (optional)
            ttl_seconds: TTL for outbox entries in seconds
        """
        self.backend = (backend or os.getenv("MVP_OUTBOX_BACKEND", "redis")).strip().lower() or "redis"
        self.redis_url = (redis_url or os.getenv("MVP_REDIS_URL", "redis://127.0.0.1:6379/0")).strip()
        self.namespace = namespace.strip() or "autocode:outbox"
        self.ttl_seconds = max(300, ttl_seconds)  # Minimum 5 minutes TTL
        
        self._redis = redis_client
        self._redis_enabled = False
        self._local_store: dict[str, list[dict[str, Any]]] = {}
        self._local_seq: dict[str, int] = {}
        self._local_lock = Lock()
        
        # Lua scripts for atomic operations
        self._store_script = None
        self._ack_script = None
        self._recover_script = None
        
        self._init_redis_if_needed()
    
    def store_event(self, task_id: str, event: dict[str, Any]) -> None:
        """
        Store an event in the outbox before delivery attempt.
        
        This method validates the event against the JSON schema and stores it
        atomically in Redis. The event is marked as pending delivery.
        
        Args:
            task_id: Task identifier
            event: Event data to store
            
        Raises:
            EventValidationError: If event validation fails
            RedisOutboxError: If storage operation fails
        """
        if not task_id or not task_id.strip():
            raise RedisOutboxError("task_id is required")
        
        # Validate event against schema
        try:
            validate(instance=event, schema=EVENT_SCHEMA)
        except ValidationError as e:
            raise EventValidationError(f"Event validation failed: {e.message}") from e
        
        task_id = task_id.strip()
        event_id = event.get("eventId", "")
        
        if not event_id:
            raise EventValidationError("Event must have eventId")
        
        # Store event with Redis transaction or local fallback
        if self._redis_enabled and self._redis is not None:
            try:
                self._store_event_redis(task_id, event)
            except Exception as e:
                raise RedisOutboxError(f"Failed to store event in Redis: {e}") from e
        else:
            self._store_event_local(task_id, event)
    
    def acknowledge_event(self, task_id: str, event_id: str) -> bool:
        """
        Acknowledge successful delivery of an event.
        
        This removes the event from the outbox, indicating it has been
        successfully delivered and acknowledged by the Control Plane.
        
        Args:
            task_id: Task identifier
            event_id: Event identifier to acknowledge
            
        Returns:
            True if event was found and acknowledged, False otherwise
        """
        if not task_id or not task_id.strip():
            return False
        if not event_id or not event_id.strip():
            return False
        
        task_id = task_id.strip()
        event_id = event_id.strip()
        
        if self._redis_enabled and self._redis is not None:
            try:
                return self._ack_event_redis(task_id, event_id)
            except Exception:
                # Fall back to local storage on Redis error
                pass
        
        return self._ack_event_local(task_id, event_id)
    
    def get_pending_events(self, task_id: str) -> list[dict[str, Any]]:
        """
        Get all pending events for a task.
        
        Returns events that have been stored but not yet acknowledged,
        ordered by sequence number.
        
        Args:
            task_id: Task identifier
            
        Returns:
            List of pending events, ordered by sequence number
        """
        if not task_id or not task_id.strip():
            return []
        
        task_id = task_id.strip()
        
        if self._redis_enabled and self._redis is not None:
            try:
                return self._get_pending_redis(task_id)
            except Exception:
                # Fall back to local storage on Redis error
                pass
        
        return self._get_pending_local(task_id)
    
    def get_all_pending_tasks(self) -> list[str]:
        """
        Get all task IDs that have pending events.
        
        This is used for recovery operations to find all tasks with
        undelivered events after a system restart.
        
        Returns:
            List of task IDs with pending events
        """
        if self._redis_enabled and self._redis is not None:
            try:
                return self._get_all_pending_tasks_redis()
            except Exception:
                # Fall back to local storage on Redis error
                pass
        
        return self._get_all_pending_tasks_local()
    
    def get_next_sequence(self, task_id: str) -> int:
        """
        Get the next sequence number for a task.
        
        Sequence numbers are used to maintain event ordering and
        detect gaps in event delivery.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Next sequence number for the task
        """
        if not task_id or not task_id.strip():
            return 0
        
        task_id = task_id.strip()
        
        if self._redis_enabled and self._redis is not None:
            try:
                return self._get_next_sequence_redis(task_id)
            except Exception:
                # Fall back to local storage on Redis error
                pass
        
        return self._get_next_sequence_local(task_id)
    
    def cleanup_task(self, task_id: str) -> None:
        """
        Clean up all outbox data for a completed task.
        
        This removes all pending events and sequence data for a task,
        typically called when a task is completed or cancelled.
        
        Args:
            task_id: Task identifier to clean up
        """
        if not task_id or not task_id.strip():
            return
        
        task_id = task_id.strip()
        
        if self._redis_enabled and self._redis is not None:
            try:
                self._cleanup_task_redis(task_id)
            except Exception:
                # Fall back to local storage on Redis error
                pass
        
        self._cleanup_task_local(task_id)
    
    def _init_redis_if_needed(self) -> None:
        """Initialize Redis connection and Lua scripts if needed."""
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
            # Lua script for atomic event storage
            self._store_script = self._redis.register_script("""
                local events_key = KEYS[1]
                local seq_key = KEYS[2]
                local event_data = ARGV[1]
                local ttl = tonumber(ARGV[2])
                
                -- Add event to list
                redis.call('RPUSH', events_key, event_data)
                redis.call('EXPIRE', events_key, ttl)
                
                -- Update sequence counter
                local seq = redis.call('INCR', seq_key)
                redis.call('EXPIRE', seq_key, ttl)
                
                return seq
            """)
            
            # Lua script for atomic event acknowledgment
            self._ack_script = self._redis.register_script("""
                local events_key = KEYS[1]
                local event_id = ARGV[1]
                
                local events = redis.call('LRANGE', events_key, 0, -1)
                local found = false
                local new_events = {}
                
                for i, event_data in ipairs(events) do
                    local event = cjson.decode(event_data)
                    if event.eventId ~= event_id then
                        table.insert(new_events, event_data)
                    else
                        found = true
                    end
                end
                
                if found then
                    redis.call('DEL', events_key)
                    if #new_events > 0 then
                        redis.call('RPUSH', events_key, unpack(new_events))
                        redis.call('EXPIRE', events_key, ARGV[2])
                    end
                    return 1
                else
                    return 0
                end
            """)
            
            self._redis_enabled = True
        except Exception:
            self._redis = None
            self._redis_enabled = False
    
    def _store_event_redis(self, task_id: str, event: dict[str, Any]) -> None:
        """Store event in Redis using atomic transaction."""
        events_key = f"{self.namespace}:events:{task_id}"
        seq_key = f"{self.namespace}:seq:{task_id}"
        event_data = json.dumps(event, separators=(",", ":"), sort_keys=True)
        
        if self._store_script:
            self._store_script(keys=[events_key, seq_key], args=[event_data, self.ttl_seconds])
        else:
            # Fallback without Lua script
            pipe = self._redis.pipeline()
            pipe.rpush(events_key, event_data)
            pipe.expire(events_key, self.ttl_seconds)
            pipe.incr(seq_key)
            pipe.expire(seq_key, self.ttl_seconds)
            pipe.execute()
    
    def _ack_event_redis(self, task_id: str, event_id: str) -> bool:
        """Acknowledge event in Redis using atomic transaction."""
        events_key = f"{self.namespace}:events:{task_id}"
        
        if self._ack_script:
            result = self._ack_script(keys=[events_key], args=[event_id, self.ttl_seconds])
            return bool(result)
        else:
            # Fallback without Lua script - less atomic but functional
            events = self._redis.lrange(events_key, 0, -1)
            found = False
            new_events = []
            
            for event_data in events:
                try:
                    event = json.loads(event_data)
                    if event.get("eventId") != event_id:
                        new_events.append(event_data)
                    else:
                        found = True
                except json.JSONDecodeError:
                    # Keep malformed events to avoid data loss
                    new_events.append(event_data)
            
            if found:
                pipe = self._redis.pipeline()
                pipe.delete(events_key)
                if new_events:
                    pipe.rpush(events_key, *new_events)
                    pipe.expire(events_key, self.ttl_seconds)
                pipe.execute()
                return True
            
            return False
    
    def _get_pending_redis(self, task_id: str) -> list[dict[str, Any]]:
        """Get pending events from Redis."""
        events_key = f"{self.namespace}:events:{task_id}"
        events_data = self._redis.lrange(events_key, 0, -1)
        
        events = []
        for event_data in events_data:
            try:
                event = json.loads(event_data)
                events.append(event)
            except json.JSONDecodeError:
                # Skip malformed events
                continue
        
        # Sort by sequence number
        events.sort(key=lambda e: e.get("seq", 0))
        return events
    
    def _get_all_pending_tasks_redis(self) -> list[str]:
        """Get all task IDs with pending events from Redis."""
        pattern = f"{self.namespace}:events:*"
        keys = self._redis.keys(pattern)
        
        task_ids = []
        prefix = f"{self.namespace}:events:"
        for key in keys:
            if key.startswith(prefix):
                task_id = key[len(prefix):]
                if task_id:
                    task_ids.append(task_id)
        
        return task_ids
    
    def _get_next_sequence_redis(self, task_id: str) -> int:
        """Get next sequence number from Redis."""
        seq_key = f"{self.namespace}:seq:{task_id}"
        seq = self._redis.get(seq_key)
        return int(seq) if seq is not None else 0
    
    def _cleanup_task_redis(self, task_id: str) -> None:
        """Clean up task data from Redis."""
        events_key = f"{self.namespace}:events:{task_id}"
        seq_key = f"{self.namespace}:seq:{task_id}"
        
        pipe = self._redis.pipeline()
        pipe.delete(events_key)
        pipe.delete(seq_key)
        pipe.execute()
    
    def _store_event_local(self, task_id: str, event: dict[str, Any]) -> None:
        """Store event in local memory (fallback)."""
        with self._local_lock:
            if task_id not in self._local_store:
                self._local_store[task_id] = []
            self._local_store[task_id].append(dict(event))
            
            # Update sequence counter
            self._local_seq[task_id] = self._local_seq.get(task_id, 0) + 1
    
    def _ack_event_local(self, task_id: str, event_id: str) -> bool:
        """Acknowledge event in local memory (fallback)."""
        with self._local_lock:
            events = self._local_store.get(task_id, [])
            original_count = len(events)
            
            self._local_store[task_id] = [
                event for event in events 
                if event.get("eventId") != event_id
            ]
            
            # Clean up empty task entries
            if not self._local_store[task_id]:
                self._local_store.pop(task_id, None)
            
            return len(self._local_store.get(task_id, [])) < original_count
    
    def _get_pending_local(self, task_id: str) -> list[dict[str, Any]]:
        """Get pending events from local memory (fallback)."""
        with self._local_lock:
            events = self._local_store.get(task_id, [])
            # Return copies to avoid external modification
            result = [dict(event) for event in events]
            # Sort by sequence number
            result.sort(key=lambda e: e.get("seq", 0))
            return result
    
    def _get_all_pending_tasks_local(self) -> list[str]:
        """Get all task IDs with pending events from local memory (fallback)."""
        with self._local_lock:
            return list(self._local_store.keys())
    
    def _get_next_sequence_local(self, task_id: str) -> int:
        """Get next sequence number from local memory (fallback)."""
        with self._local_lock:
            return self._local_seq.get(task_id, 0)
    
    def _cleanup_task_local(self, task_id: str) -> None:
        """Clean up task data from local memory (fallback)."""
        with self._local_lock:
            self._local_store.pop(task_id, None)
            self._local_seq.pop(task_id, None)