"""
Plugin resource limits and isolation mechanisms.

Validates: Requirements 13.1 (Security Policy Enforcement)
"""
from __future__ import annotations

import os
import signal
import threading
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

# Resource module is Unix-only, make it optional
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False

T = TypeVar("T")


@dataclass(frozen=True)
class ResourceLimits:
    """Resource limits for plugin execution."""
    
    max_memory_mb: int = 512
    max_cpu_time_seconds: int = 30
    max_wall_time_seconds: int = 60
    max_file_descriptors: int = 100
    max_processes: int = 10
    
    @classmethod
    def from_env(cls) -> ResourceLimits:
        """Load resource limits from environment variables."""
        return cls(
            max_memory_mb=_parse_int_env("MVP_PLUGIN_MAX_MEMORY_MB", 512),
            max_cpu_time_seconds=_parse_int_env("MVP_PLUGIN_MAX_CPU_TIME_SECONDS", 30),
            max_wall_time_seconds=_parse_int_env("MVP_PLUGIN_MAX_WALL_TIME_SECONDS", 60),
            max_file_descriptors=_parse_int_env("MVP_PLUGIN_MAX_FILE_DESCRIPTORS", 100),
            max_processes=_parse_int_env("MVP_PLUGIN_MAX_PROCESSES", 10),
        )


class ResourceLimitExceeded(Exception):
    """Raised when a plugin exceeds its resource limits."""
    pass


class PluginIsolationManager:
    """Manages plugin execution isolation and resource limits."""
    
    def __init__(self, limits: ResourceLimits | None = None) -> None:
        self.limits = limits or ResourceLimits.from_env()
    
    def execute_with_limits(
        self,
        plugin_id: str,
        operation: Callable[[], T],
        timeout_seconds: int | None = None,
    ) -> T:
        """
        Execute a plugin operation with resource limits and isolation.
        
        Args:
            plugin_id: Unique identifier for the plugin
            operation: The operation to execute
            timeout_seconds: Override wall time limit for this operation
            
        Returns:
            The result of the operation
            
        Raises:
            ResourceLimitExceeded: If resource limits are exceeded
            TimeoutError: If wall time limit is exceeded
        """
        wall_time_limit = timeout_seconds or self.limits.max_wall_time_seconds
        
        # Use threading with timeout for wall time enforcement
        result_container: list[Any] = []
        error_container: list[Exception] = []
        
        def wrapped_operation():
            try:
                # Apply resource limits in the execution thread
                self._apply_resource_limits()
                result = operation()
                result_container.append(result)
            except Exception as e:
                error_container.append(e)
        
        thread = threading.Thread(target=wrapped_operation, name=f"plugin-{plugin_id}")
        thread.daemon = True
        thread.start()
        thread.join(timeout=wall_time_limit)
        
        if thread.is_alive():
            # Thread is still running after timeout
            raise TimeoutError(
                f"Plugin {plugin_id} exceeded wall time limit of {wall_time_limit}s"
            )
        
        if error_container:
            raise error_container[0]
        
        if not result_container:
            raise RuntimeError(f"Plugin {plugin_id} completed without result")
        
        return result_container[0]
    
    def _apply_resource_limits(self) -> None:
        """Apply resource limits to the current process/thread."""
        if not HAS_RESOURCE:
            # Resource limits not supported on this platform (e.g., Windows)
            return
        
        try:
            # Memory limit (virtual memory)
            memory_bytes = self.limits.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            
            # CPU time limit
            cpu_time = self.limits.max_cpu_time_seconds
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_time, cpu_time))
            
            # File descriptor limit
            fd_limit = self.limits.max_file_descriptors
            resource.setrlimit(resource.RLIMIT_NOFILE, (fd_limit, fd_limit))
            
            # Process limit
            proc_limit = self.limits.max_processes
            resource.setrlimit(resource.RLIMIT_NPROC, (proc_limit, proc_limit))
            
        except (ValueError, OSError) as e:
            # Resource limits may not be supported on all platforms
            # Log but don't fail - this is a best-effort security measure
            pass
    
    def get_resource_usage(self) -> dict[str, Any]:
        """Get current resource usage statistics."""
        if not HAS_RESOURCE:
            # Return empty usage on platforms without resource module
            return {
                "user_cpu_time_seconds": 0.0,
                "system_cpu_time_seconds": 0.0,
                "max_memory_kb": 0,
                "platform": "resource_module_unavailable",
            }
        
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return {
            "user_cpu_time_seconds": usage.ru_utime,
            "system_cpu_time_seconds": usage.ru_stime,
            "max_memory_kb": usage.ru_maxrss,
            "page_faults": usage.ru_majflt,
            "block_io_operations": usage.ru_inblock + usage.ru_oublock,
            "voluntary_context_switches": usage.ru_nvcsw,
            "involuntary_context_switches": usage.ru_nivcsw,
        }


def _parse_int_env(key: str, default: int) -> int:
    """Parse integer from environment variable with fallback."""
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default
