"""
Cache configuration for the Python Agent.

Defines TTL settings for different data types to support a 95% Redis cache
hit rate for frequently accessed data.

Requirements: 12.4
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# TTL constants (seconds)
# ---------------------------------------------------------------------------

#: Cache TTL for task data (5 minutes).
TASK_CACHE_TTL: int = 300

#: Cache TTL for event data (1 minute).
EVENT_CACHE_TTL: int = 60

#: Cache TTL for artifact metadata (1 hour).
ARTIFACT_CACHE_TTL: int = 3600

#: Cache TTL for LLM responses (24 hours).
LLM_RESPONSE_CACHE_TTL: int = 86400


# ---------------------------------------------------------------------------
# Redis connection pool defaults
# ---------------------------------------------------------------------------

#: Maximum number of connections in the Redis connection pool.
REDIS_MAX_CONNECTIONS: int = 50

#: Socket connect timeout in seconds.
REDIS_SOCKET_CONNECT_TIMEOUT: int = 5

#: Socket read/write timeout in seconds.
REDIS_SOCKET_TIMEOUT: int = 5

#: Whether to retry on connection errors.
REDIS_RETRY_ON_TIMEOUT: bool = True

#: Maximum number of retry attempts on transient errors.
REDIS_MAX_RETRIES: int = 3


# ---------------------------------------------------------------------------
# Cache configuration dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CacheConfig:
    """
    Immutable cache configuration with TTL settings for each data type.

    All TTL values are in seconds.  The defaults are tuned to achieve a
    95% cache hit rate for frequently accessed data (Requirement 12.4).

    Requirements: 12.4
    """

    #: TTL for task data.
    task_ttl: int = TASK_CACHE_TTL

    #: TTL for event data.
    event_ttl: int = EVENT_CACHE_TTL

    #: TTL for artifact metadata.
    artifact_ttl: int = ARTIFACT_CACHE_TTL

    #: TTL for LLM response data.
    llm_response_ttl: int = LLM_RESPONSE_CACHE_TTL

    #: Maximum Redis connection pool size.
    redis_max_connections: int = REDIS_MAX_CONNECTIONS

    #: Redis socket connect timeout (seconds).
    redis_socket_connect_timeout: int = REDIS_SOCKET_CONNECT_TIMEOUT

    #: Redis socket read/write timeout (seconds).
    redis_socket_timeout: int = REDIS_SOCKET_TIMEOUT

    #: Whether to retry on Redis timeout errors.
    redis_retry_on_timeout: bool = REDIS_RETRY_ON_TIMEOUT

    #: Maximum retry attempts for transient Redis errors.
    redis_max_retries: int = REDIS_MAX_RETRIES

    def __post_init__(self) -> None:
        for attr, value in [
            ("task_ttl", self.task_ttl),
            ("event_ttl", self.event_ttl),
            ("artifact_ttl", self.artifact_ttl),
            ("llm_response_ttl", self.llm_response_ttl),
        ]:
            if value <= 0:
                raise ValueError(f"{attr} must be positive, got {value}")
        if self.redis_max_connections <= 0:
            raise ValueError(
                f"redis_max_connections must be positive, got {self.redis_max_connections}"
            )

    def get_ttl(self, data_type: str) -> int:
        """
        Return the TTL in seconds for the given data type.

        :param data_type: One of 'task', 'event', 'artifact', 'llm_response'.
        :returns: TTL in seconds.
        :raises ValueError: If the data type is not recognised.
        """
        mapping: dict[str, int] = {
            "task": self.task_ttl,
            "event": self.event_ttl,
            "artifact": self.artifact_ttl,
            "llm_response": self.llm_response_ttl,
        }
        key = (data_type or "").strip().lower()
        if key not in mapping:
            raise ValueError(
                f"Unknown data type '{data_type}'. Valid types: {sorted(mapping.keys())}"
            )
        return mapping[key]

    def redis_connection_kwargs(self) -> dict:
        """
        Return a dict of kwargs suitable for passing to a Redis connection pool.

        Example::

            import redis
            pool = redis.ConnectionPool(**cache_config.redis_connection_kwargs())
            client = redis.Redis(connection_pool=pool)
        """
        return {
            "max_connections": self.redis_max_connections,
            "socket_connect_timeout": self.redis_socket_connect_timeout,
            "socket_timeout": self.redis_socket_timeout,
            "retry_on_timeout": self.redis_retry_on_timeout,
        }


# ---------------------------------------------------------------------------
# Default configuration instance
# ---------------------------------------------------------------------------

DEFAULT_CACHE_CONFIG = CacheConfig()
