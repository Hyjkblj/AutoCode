"""
Enhanced Agent Runner with Event Recovery Service integration.

This module extends the base AgentRunner to include automatic event recovery
on startup, implementing Requirements 2.3 and 2.6 for reliable event delivery
across Python Agent restarts.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from agents.base_agent import BaseAgent
from client.control_plane_client import ControlPlaneClient
from outbox.redis_outbox import RedisOutbox
from outbox.recovery_service import EventRecoveryService, RecoveryConfig, create_recovery_service
from runner import RunnerConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EnhancedRunnerConfig(RunnerConfig):
    """Extended runner configuration with recovery service settings."""
    
    # Recovery service configuration
    recovery_enabled: bool = True
    recovery_startup_delay_seconds: float = 2.0
    recovery_max_retry_attempts: int = 3
    recovery_retry_backoff_seconds: float = 1.0
    recovery_batch_size: int = 10
    recovery_timeout_seconds: float = 300.0
    recovery_sequence_gap_detection: bool = True
    
    # Outbox configuration
    outbox_backend: str = "redis"
    outbox_redis_url: str = "redis://127.0.0.1:6379/0"
    outbox_namespace: str = "autocode:outbox"
    outbox_ttl_seconds: int = 86400  # 24 hours


class EnhancedAgentRunner:
    """
    Enhanced Agent Runner with integrated event recovery service.
    
    This runner extends the base functionality to include:
    - Automatic event recovery on startup
    - Integration with Redis-based persistent outbox
    - Comprehensive logging and metrics for recovery operations
    - Graceful shutdown with recovery service cleanup
    """
    
    def __init__(
        self, 
        client: ControlPlaneClient, 
        config: EnhancedRunnerConfig, 
        agent: BaseAgent,
        outbox: RedisOutbox | None = None,
        recovery_service: EventRecoveryService | None = None,
    ) -> None:
        """
        Initialize enhanced agent runner.
        
        Args:
            client: Control plane client for communication
            config: Enhanced runner configuration
            agent: Base agent for task handling
            outbox: Optional Redis outbox (creates default if None)
            recovery_service: Optional recovery service (creates default if None)
        """
        self.client = client
        self.config = config
        self.agent = agent
        self._registered = False
        self._last_heartbeat_ms = 0
        
        # Initialize outbox
        self.outbox = outbox or self._create_outbox()
        
        # Initialize recovery service
        self.recovery_service = recovery_service or self._create_recovery_service()
        
        # Track startup state
        self._startup_recovery_completed = False
        self._shutdown_requested = False
        
        log.info(
            "Enhanced agent runner initialized",
            extra={
                "recoveryEnabled": self.config.recovery_enabled,
                "outboxBackend": self.config.outbox_backend,
                "outboxNamespace": self.config.outbox_namespace,
            }
        )
    
    def run_forever(self) -> None:
        """
        Run the agent forever with integrated recovery service.
        
        This method performs startup recovery before beginning the main
        polling loop, ensuring any pending events from previous runs
        are recovered and delivered.
        """
        log.info(
            "Enhanced agent runner starting",
            extra={
                "baseUrl": self.config.base_url,
                "pollIntervalMs": self.config.poll_interval_ms,
                "recoveryEnabled": self.config.recovery_enabled,
            }
        )
        
        try:
            # Perform startup recovery
            self._perform_startup_recovery()
            
            # Start main polling loop
            log.info("Starting main polling loop")
            while not self._shutdown_requested:
                try:
                    handled = self.tick()
                except Exception as exc:  # noqa: BLE001
                    log.warning("tick error (will retry): %s", exc)
                    self._registered = False
                    time.sleep(self.config.poll_interval_ms / 1000.0)
                    continue
                
                if not handled:
                    time.sleep(self.config.poll_interval_ms / 1000.0)
                    
        except KeyboardInterrupt:
            log.info("Shutdown requested via keyboard interrupt")
        except Exception as exc:
            log.error("Unexpected error in main loop", exc_info=True)
            raise
        finally:
            self._perform_shutdown()
    
    def tick(self, now_ms: Optional[int] = None) -> bool:
        """
        Perform one polling tick.
        
        Args:
            now_ms: Current time in milliseconds (uses current time if None)
            
        Returns:
            True if a task was handled, False otherwise
        """
        now = now_ms if now_ms is not None else int(time.time() * 1000)
        self._ensure_registered(now)
        self._maybe_heartbeat(now)
        
        task = self.client.poll_next_task(self.config.node_id, profile=self.config.agent_profile)
        if not task:
            return False
        
        # Handle task with enhanced agent (if available) or base agent
        if hasattr(self.agent, 'handle_task_with_outbox'):
            self.agent.handle_task_with_outbox(task, self.client, self.outbox)
        else:
            self.agent.handle_task(task, self.client)
        
        return True
    
    def shutdown(self, timeout_seconds: float = 30.0) -> bool:
        """
        Request graceful shutdown of the runner.
        
        Args:
            timeout_seconds: Maximum time to wait for shutdown
            
        Returns:
            True if shutdown completed gracefully
        """
        log.info("Shutdown requested")
        self._shutdown_requested = True
        
        # Give main loop time to exit gracefully
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if not hasattr(self, '_main_loop_active') or not self._main_loop_active:
                break
            time.sleep(0.1)
        
        return self._perform_shutdown()
    
    def get_recovery_stats(self) -> dict[str, any]:
        """
        Get recovery service statistics.
        
        Returns:
            Dictionary containing recovery statistics and metrics
        """
        if not self.recovery_service:
            return {"recoveryEnabled": False}
        
        return {
            "recoveryEnabled": self.config.recovery_enabled,
            "startupRecoveryCompleted": self._startup_recovery_completed,
            "lastRecoveryStats": self.recovery_service.get_recovery_stats(),
            "serviceMetrics": self.recovery_service.get_service_metrics(),
        }
    
    def _create_outbox(self) -> RedisOutbox:
        """Create Redis outbox with configuration."""
        return RedisOutbox(
            backend=self.config.outbox_backend,
            redis_url=self.config.outbox_redis_url,
            namespace=self.config.outbox_namespace,
            ttl_seconds=self.config.outbox_ttl_seconds,
        )
    
    def _create_recovery_service(self) -> EventRecoveryService:
        """Create recovery service with configuration."""
        recovery_config = RecoveryConfig(
            enabled=self.config.recovery_enabled,
            startup_delay_seconds=self.config.recovery_startup_delay_seconds,
            max_retry_attempts=self.config.recovery_max_retry_attempts,
            retry_backoff_seconds=self.config.recovery_retry_backoff_seconds,
            batch_size=self.config.recovery_batch_size,
            recovery_timeout_seconds=self.config.recovery_timeout_seconds,
            sequence_gap_detection=self.config.recovery_sequence_gap_detection,
        )
        
        return create_recovery_service(
            outbox=self.outbox,
            client=self.client,
            config=recovery_config,
        )
    
    def _perform_startup_recovery(self) -> None:
        """
        Perform event recovery on startup.
        
        This implements Requirement 2.3: "WHEN the Python_Agent restarts, 
        THE Event_Outbox SHALL recover and redeliver unacknowledged events"
        """
        if not self.config.recovery_enabled:
            log.info("Event recovery disabled by configuration")
            self._startup_recovery_completed = True
            return
        
        log.info("Starting startup event recovery")
        recovery_start = time.time()
        
        try:
            # Perform immediate recovery (synchronous)
            stats = self.recovery_service.recover_events_now()
            
            recovery_duration = time.time() - recovery_start
            
            log.info(
                "Startup event recovery completed",
                extra={
                    "durationSeconds": round(recovery_duration, 3),
                    "tasksScanned": stats.total_tasks_scanned,
                    "eventsFound": stats.total_events_found,
                    "successfulDeliveries": stats.successful_deliveries,
                    "failedDeliveries": stats.failed_deliveries,
                    "sequenceGapsResolved": stats.sequence_gaps_resolved,
                }
            )
            
            # Log warnings for any issues
            if stats.failed_deliveries > 0:
                log.warning(
                    f"Some events failed recovery and remain in outbox: {stats.failed_deliveries} failed"
                )
            
            if stats.sequence_gaps_detected > 0:
                log.warning(
                    f"Sequence gaps detected during recovery: {stats.sequence_gaps_detected} gaps"
                )
            
        except Exception as exc:
            log.error(
                "Startup event recovery failed",
                extra={"error": str(exc)},
                exc_info=True
            )
            # Continue startup even if recovery fails
        finally:
            self._startup_recovery_completed = True
    
    def _perform_shutdown(self) -> bool:
        """
        Perform graceful shutdown cleanup.
        
        Returns:
            True if shutdown completed successfully
        """
        log.info("Performing graceful shutdown")
        success = True
        
        try:
            # Stop recovery service if running
            if self.recovery_service:
                stopped = self.recovery_service.stop_recovery_service(timeout_seconds=10.0)
                if not stopped:
                    log.warning("Recovery service did not stop gracefully")
                    success = False
                else:
                    log.info("Recovery service stopped successfully")
            
            # Log final statistics
            if self.recovery_service:
                final_stats = self.get_recovery_stats()
                log.info("Final recovery statistics", extra=final_stats)
            
        except Exception as exc:
            log.error("Error during shutdown", exc_info=True)
            success = False
        
        log.info("Graceful shutdown completed" if success else "Shutdown completed with errors")
        return success
    
    def _ensure_registered(self, now_ms: int) -> None:
        """Ensure agent is registered with control plane."""
        if self._registered:
            return
        
        self.client.register(self.config.node_id, capabilities=self.config.capabilities)
        self._registered = True
        self._last_heartbeat_ms = now_ms
        
        log.info(
            "Registered node to control plane",
            extra={
                "nodeId": self.config.node_id,
                "baseUrl": self.config.base_url,
                "capabilities": self.config.capabilities,
            }
        )
    
    def _maybe_heartbeat(self, now_ms: int) -> None:
        """Send heartbeat if needed."""
        if now_ms - self._last_heartbeat_ms < self.config.heartbeat_interval_ms:
            return
        
        self.client.heartbeat(self.config.node_id)
        self._last_heartbeat_ms = now_ms
        log.debug("Heartbeat sent")


def create_enhanced_runner(
    client: ControlPlaneClient,
    config: EnhancedRunnerConfig,
    agent: BaseAgent,
) -> EnhancedAgentRunner:
    """
    Factory function to create an enhanced agent runner.
    
    Args:
        client: Control plane client
        config: Enhanced runner configuration
        agent: Base agent for task handling
        
    Returns:
        Configured EnhancedAgentRunner instance
    """
    return EnhancedAgentRunner(
        client=client,
        config=config,
        agent=agent,
    )


# Example usage and integration
if __name__ == "__main__":
    import os
    from pathlib import Path
    from orchestrator.agent_orchestrator import AgentOrchestrator
    
    # Load environment variables
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    
    # Create enhanced configuration
    config = EnhancedRunnerConfig(
        base_url=os.getenv("MVP_BASE_URL", "http://localhost:8058").strip(),
        node_id=os.getenv("MVP_NODE_ID", "ai-node-local-1").strip(),
        agent_token=os.getenv("MVP_AGENT_TOKEN", "agent-dev-token").strip(),
        agent_profile=os.getenv("MVP_AGENT_PROFILE", "ai-agent").strip().lower(),
        poll_interval_ms=int(os.getenv("MVP_POLL_INTERVAL_MS", "1500")),
        heartbeat_interval_ms=int(os.getenv("MVP_HEARTBEAT_INTERVAL_MS", "10000")),
        agent_version=os.getenv("MVP_AGENT_VERSION", "0.1.0").strip(),
        capabilities=os.getenv("MVP_AGENT_CAPABILITIES", "ai-agent,events,approval").strip(),
        
        # Recovery configuration
        recovery_enabled=os.getenv("MVP_RECOVERY_ENABLED", "true").lower() == "true",
        recovery_startup_delay_seconds=float(os.getenv("MVP_RECOVERY_STARTUP_DELAY", "2.0")),
        recovery_max_retry_attempts=int(os.getenv("MVP_RECOVERY_MAX_RETRIES", "3")),
        recovery_batch_size=int(os.getenv("MVP_RECOVERY_BATCH_SIZE", "10")),
        
        # Outbox configuration
        outbox_backend=os.getenv("MVP_OUTBOX_BACKEND", "redis").strip(),
        outbox_redis_url=os.getenv("MVP_REDIS_URL", "redis://127.0.0.1:6379/0").strip(),
        outbox_namespace=os.getenv("MVP_OUTBOX_NAMESPACE", "autocode:outbox").strip(),
    )
    
    # Create client and agent
    client = ControlPlaneClient(
        base_url=config.base_url,
        agent_token=config.agent_token,
        agent_version=config.agent_version,
    )
    
    agent = AgentOrchestrator()
    
    # Create and run enhanced runner
    runner = create_enhanced_runner(client=client, config=config, agent=agent)
    
    try:
        runner.run_forever()
    except KeyboardInterrupt:
        log.info("Shutdown requested")
        runner.shutdown()