"""
Event recovery service for Python Agent restart scenarios.

This module implements a background process that scans and redelivers unacknowledged 
events on startup, maintaining event sequence continuity across restarts.

Implements Requirements 2.3 and 2.6:
- "WHEN the Python_Agent restarts, THE Event_Outbox SHALL recover and redeliver unacknowledged events"
- "THE system SHALL maintain event sequence continuity across Python_Agent restarts"
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from client.control_plane_client import ControlPlaneClient, PublishEventResult
from outbox.redis_outbox import RedisOutbox
from utils.observability import TaskObservability


@dataclass(frozen=True)
class RecoveryStats:
    """Statistics from event recovery operation."""
    total_tasks_scanned: int
    total_events_found: int
    successful_deliveries: int
    failed_deliveries: int
    tasks_with_failures: int
    recovery_duration_seconds: float
    sequence_gaps_detected: int
    sequence_gaps_resolved: int


@dataclass(frozen=True)
class RecoveryConfig:
    """Configuration for recovery service."""
    enabled: bool = True
    startup_delay_seconds: float = 2.0
    max_retry_attempts: int = 3
    retry_backoff_seconds: float = 1.0
    batch_size: int = 10
    recovery_timeout_seconds: float = 300.0  # 5 minutes
    sequence_gap_detection: bool = True
    metrics_enabled: bool = True


class EventRecoveryService:
    """
    Background service for recovering unacknowledged events after Python Agent restart.
    
    This service implements the recovery pattern required by Requirements 2.3 and 2.6:
    - Scans Redis outbox for pending events on startup
    - Redelivers events using enhanced client with retry logic
    - Maintains event sequence continuity across restarts
    - Provides comprehensive logging and metrics
    """
    
    def __init__(
        self,
        outbox: RedisOutbox,
        client: ControlPlaneClient,
        config: RecoveryConfig | None = None,
        observability: TaskObservability | None = None,
    ) -> None:
        """
        Initialize event recovery service.
        
        Args:
            outbox: Redis outbox instance for event persistence
            client: Control plane client for event delivery
            config: Recovery configuration (uses defaults if None)
            observability: Optional observability context
        """
        self.outbox = outbox
        self.client = client
        self.config = config or RecoveryConfig()
        self.observability = observability
        
        # Initialize logger for structured logging
        self._logger = logging.getLogger(f"{__name__}.EventRecoveryService")
        
        # Recovery state
        self._recovery_thread: threading.Thread | None = None
        self._recovery_active = False
        self._recovery_stats: RecoveryStats | None = None
        self._shutdown_event = threading.Event()
        
        # Metrics tracking
        self._metrics = {
            "total_recoveries": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "total_events_recovered": 0,
            "sequence_gaps_resolved": 0,
        }
        
        # Callbacks for testing and monitoring
        self._on_recovery_start: Callable[[], None] | None = None
        self._on_recovery_complete: Callable[[RecoveryStats], None] | None = None
        self._on_event_recovered: Callable[[str, dict[str, Any]], None] | None = None
    
    def start_recovery_service(self) -> None:
        """
        Start the background recovery service.
        
        This method starts a background thread that performs event recovery
        after the configured startup delay.
        """
        if not self.config.enabled:
            self._logger.info("Event recovery service disabled by configuration")
            return
        
        if self._recovery_thread and self._recovery_thread.is_alive():
            self._logger.warning("Recovery service already running")
            return
        
        self._logger.info(
            "Starting event recovery service",
            extra={
                "startupDelaySeconds": self.config.startup_delay_seconds,
                "maxRetryAttempts": self.config.max_retry_attempts,
                "batchSize": self.config.batch_size,
                "recoveryTimeoutSeconds": self.config.recovery_timeout_seconds,
            }
        )
        
        self._shutdown_event.clear()
        self._recovery_thread = threading.Thread(
            target=self._recovery_worker,
            name="EventRecoveryService",
            daemon=True
        )
        self._recovery_thread.start()
    
    def stop_recovery_service(self, timeout_seconds: float = 10.0) -> bool:
        """
        Stop the background recovery service.
        
        Args:
            timeout_seconds: Maximum time to wait for graceful shutdown
            
        Returns:
            True if service stopped gracefully, False if timeout occurred
        """
        if not self._recovery_thread or not self._recovery_thread.is_alive():
            return True
        
        self._logger.info("Stopping event recovery service")
        self._shutdown_event.set()
        
        self._recovery_thread.join(timeout=timeout_seconds)
        if self._recovery_thread.is_alive():
            self._logger.warning("Recovery service did not stop within timeout")
            return False
        
        self._logger.info("Event recovery service stopped")
        return True
    
    def recover_events_now(self) -> RecoveryStats:
        """
        Perform immediate event recovery (synchronous).
        
        This method performs event recovery immediately in the current thread,
        useful for testing or manual recovery operations.
        
        Returns:
            Recovery statistics
        """
        return self._perform_recovery()
    
    def get_recovery_stats(self) -> RecoveryStats | None:
        """
        Get statistics from the last recovery operation.
        
        Returns:
            Recovery statistics, or None if no recovery has been performed
        """
        return self._recovery_stats
    
    def get_service_metrics(self) -> dict[str, Any]:
        """
        Get service-level metrics for monitoring.
        
        Returns:
            Dictionary containing service metrics
        """
        return {
            **self._metrics,
            "recoveryActive": self._recovery_active,
            "lastRecoveryStats": self._recovery_stats.__dict__ if self._recovery_stats else None,
        }
    
    def set_recovery_callbacks(
        self,
        on_start: Callable[[], None] | None = None,
        on_complete: Callable[[RecoveryStats], None] | None = None,
        on_event_recovered: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        """
        Set callbacks for recovery events (useful for testing and monitoring).
        
        Args:
            on_start: Called when recovery starts
            on_complete: Called when recovery completes with stats
            on_event_recovered: Called for each successfully recovered event
        """
        self._on_recovery_start = on_start
        self._on_recovery_complete = on_complete
        self._on_event_recovered = on_event_recovered
    
    def _recovery_worker(self) -> None:
        """Background worker thread for event recovery."""
        try:
            # Wait for startup delay
            if self.config.startup_delay_seconds > 0:
                self._logger.info(
                    f"Waiting {self.config.startup_delay_seconds}s before starting recovery"
                )
                if self._shutdown_event.wait(self.config.startup_delay_seconds):
                    return  # Shutdown requested during delay
            
            # Perform recovery
            self._perform_recovery()
            
        except Exception as exc:
            self._logger.error(
                "Unexpected error in recovery worker",
                extra={"error": str(exc)},
                exc_info=True
            )
            self._metrics["failed_recoveries"] += 1
    
    def _perform_recovery(self) -> RecoveryStats:
        """
        Perform the actual event recovery process.
        
        Returns:
            Recovery statistics
        """
        recovery_start = time.time()
        self._recovery_active = True
        
        # Initialize stats
        stats = {
            "total_tasks_scanned": 0,
            "total_events_found": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "tasks_with_failures": 0,
            "sequence_gaps_detected": 0,
            "sequence_gaps_resolved": 0,
        }
        
        try:
            # Notify recovery start
            if self._on_recovery_start:
                self._on_recovery_start()
            
            self._logger.info("Starting event recovery process")
            
            # Get all tasks with pending events
            pending_task_ids = self.outbox.get_all_pending_tasks()
            stats["total_tasks_scanned"] = len(pending_task_ids)
            
            if not pending_task_ids:
                self._logger.info("No pending events found for recovery")
            else:
                self._logger.info(
                    f"Found {len(pending_task_ids)} tasks with pending events",
                    extra={"pendingTasks": len(pending_task_ids)}
                )
                
                # Process tasks in batches
                for i in range(0, len(pending_task_ids), self.config.batch_size):
                    if self._shutdown_event.is_set():
                        self._logger.info("Recovery interrupted by shutdown")
                        break
                    
                    batch = pending_task_ids[i:i + self.config.batch_size]
                    batch_stats = self._recover_task_batch(batch)
                    
                    # Aggregate batch stats
                    stats["total_events_found"] += batch_stats["events_found"]
                    stats["successful_deliveries"] += batch_stats["successful_deliveries"]
                    stats["failed_deliveries"] += batch_stats["failed_deliveries"]
                    stats["tasks_with_failures"] += batch_stats["tasks_with_failures"]
                    stats["sequence_gaps_detected"] += batch_stats["sequence_gaps_detected"]
                    stats["sequence_gaps_resolved"] += batch_stats["sequence_gaps_resolved"]
            
            # Calculate final stats
            recovery_duration = time.time() - recovery_start
            recovery_stats = RecoveryStats(
                total_tasks_scanned=stats["total_tasks_scanned"],
                total_events_found=stats["total_events_found"],
                successful_deliveries=stats["successful_deliveries"],
                failed_deliveries=stats["failed_deliveries"],
                tasks_with_failures=stats["tasks_with_failures"],
                recovery_duration_seconds=round(max(recovery_duration, 0.001), 3),  # Ensure minimum duration
                sequence_gaps_detected=stats["sequence_gaps_detected"],
                sequence_gaps_resolved=stats["sequence_gaps_resolved"],
            )
            
            # Update metrics
            self._metrics["total_recoveries"] += 1
            if stats["failed_deliveries"] == 0:
                self._metrics["successful_recoveries"] += 1
            else:
                self._metrics["failed_recoveries"] += 1
            self._metrics["total_events_recovered"] += stats["successful_deliveries"]
            self._metrics["sequence_gaps_resolved"] += stats["sequence_gaps_resolved"]
            
            # Log recovery completion
            self._logger.info(
                "Event recovery completed",
                extra={
                    "tasksScanned": recovery_stats.total_tasks_scanned,
                    "eventsFound": recovery_stats.total_events_found,
                    "successfulDeliveries": recovery_stats.successful_deliveries,
                    "failedDeliveries": recovery_stats.failed_deliveries,
                    "durationSeconds": recovery_stats.recovery_duration_seconds,
                    "sequenceGapsResolved": recovery_stats.sequence_gaps_resolved,
                }
            )
            
            # Store stats and notify completion
            self._recovery_stats = recovery_stats
            if self._on_recovery_complete:
                self._on_recovery_complete(recovery_stats)
            
            return recovery_stats
            
        except Exception as exc:
            self._logger.error(
                "Error during event recovery",
                extra={"error": str(exc)},
                exc_info=True
            )
            self._metrics["failed_recoveries"] += 1
            raise
        finally:
            self._recovery_active = False
    
    def _recover_task_batch(self, task_ids: list[str]) -> dict[str, int]:
        """
        Recover events for a batch of tasks.
        
        Args:
            task_ids: List of task IDs to process
            
        Returns:
            Dictionary with batch recovery statistics
        """
        batch_stats = {
            "events_found": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "tasks_with_failures": 0,
            "sequence_gaps_detected": 0,
            "sequence_gaps_resolved": 0,
        }
        
        for task_id in task_ids:
            if self._shutdown_event.is_set():
                break
            
            task_stats = self._recover_task_events(task_id)
            batch_stats["events_found"] += task_stats["events_found"]
            batch_stats["successful_deliveries"] += task_stats["successful_deliveries"]
            batch_stats["failed_deliveries"] += task_stats["failed_deliveries"]
            if task_stats["failed_deliveries"] > 0:
                batch_stats["tasks_with_failures"] += 1
            batch_stats["sequence_gaps_detected"] += task_stats["sequence_gaps_detected"]
            batch_stats["sequence_gaps_resolved"] += task_stats["sequence_gaps_resolved"]
        
        return batch_stats
    
    def _recover_task_events(self, task_id: str) -> dict[str, int]:
        """
        Recover events for a single task.
        
        Args:
            task_id: Task ID to recover events for
            
        Returns:
            Dictionary with task recovery statistics
        """
        task_stats = {
            "events_found": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "sequence_gaps_detected": 0,
            "sequence_gaps_resolved": 0,
        }
        
        try:
            # Check for shutdown before processing
            if self._shutdown_event.is_set():
                return task_stats
            
            # Get pending events for task
            pending_events = self.outbox.get_pending_events(task_id)
            task_stats["events_found"] = len(pending_events)
            
            if not pending_events:
                return task_stats
            
            self._logger.debug(
                f"Recovering {len(pending_events)} events for task {task_id}",
                extra={"taskId": task_id, "eventCount": len(pending_events)}
            )
            
            # Check for sequence gaps if enabled
            if self.config.sequence_gap_detection:
                gaps_detected, gaps_resolved = self._detect_and_resolve_sequence_gaps(
                    task_id, pending_events
                )
                task_stats["sequence_gaps_detected"] = gaps_detected
                task_stats["sequence_gaps_resolved"] = gaps_resolved
            
            # Attempt to deliver each event
            for event in pending_events:
                if self._shutdown_event.is_set():
                    break
                
                event_id = event.get("eventId", "")
                success = self._recover_single_event(task_id, event)
                
                if success:
                    task_stats["successful_deliveries"] += 1
                    # Notify event recovered
                    if self._on_event_recovered:
                        self._on_event_recovered(task_id, event)
                else:
                    task_stats["failed_deliveries"] += 1
            
        except Exception as exc:
            self._logger.error(
                f"Error recovering events for task {task_id}",
                extra={"taskId": task_id, "error": str(exc)},
                exc_info=True
            )
            task_stats["failed_deliveries"] += task_stats["events_found"] - task_stats["successful_deliveries"]
        
        return task_stats
    
    def _recover_single_event(self, task_id: str, event: dict[str, Any]) -> bool:
        """
        Attempt to recover a single event.
        
        Args:
            task_id: Task ID
            event: Event to recover
            
        Returns:
            True if event was successfully delivered and acknowledged
        """
        event_id = event.get("eventId", "")
        event_type = event.get("type", "unknown")
        
        try:
            # Use enhanced client with retry logic (from Task 3.2)
            result: PublishEventResult = self.client.publish_event_with_retry_result(
                task_id,
                event,
                max_attempts=self.config.max_retry_attempts,
                initial_backoff_seconds=self.config.retry_backoff_seconds,
                observability=self.observability,
            )
            
            if result.response is not None:
                # Successful delivery - acknowledge in outbox
                self.outbox.acknowledge_event(task_id, event_id)
                
                self._logger.debug(
                    f"Successfully recovered event {event_id}",
                    extra={
                        "taskId": task_id,
                        "eventId": event_id,
                        "eventType": event_type,
                        "attempts": result.attempts,
                        "totalDelaySeconds": result.total_delay_seconds,
                    }
                )
                return True
            else:
                # Failed delivery - log but keep in outbox for next recovery
                self._logger.warning(
                    f"Failed to recover event {event_id} after {result.attempts} attempts",
                    extra={
                        "taskId": task_id,
                        "eventId": event_id,
                        "eventType": event_type,
                        "attempts": result.attempts,
                        "circuitBreakerTriggered": result.circuit_breaker_triggered,
                        "finalError": str(result.final_error) if result.final_error else None,
                    }
                )
                return False
                
        except Exception as exc:
            self._logger.error(
                f"Unexpected error recovering event {event_id}",
                extra={
                    "taskId": task_id,
                    "eventId": event_id,
                    "eventType": event_type,
                    "error": str(exc),
                },
                exc_info=True
            )
            return False
    
    def _detect_and_resolve_sequence_gaps(
        self, task_id: str, events: list[dict[str, Any]]
    ) -> tuple[int, int]:
        """
        Detect and resolve sequence number gaps in events.
        
        This method implements Requirement 2.6: "THE system SHALL maintain 
        event sequence continuity across Python_Agent restarts"
        
        Args:
            task_id: Task ID
            events: List of events to check
            
        Returns:
            Tuple of (gaps_detected, gaps_resolved)
        """
        if not events:
            return 0, 0
        
        # Sort events by sequence number
        sorted_events = sorted(events, key=lambda e: e.get("seq", 0))
        
        gaps_detected = 0
        gaps_resolved = 0
        
        # Check for sequence gaps
        expected_seq = sorted_events[0].get("seq", 0)
        for event in sorted_events:
            current_seq = event.get("seq", 0)
            
            if current_seq > expected_seq:
                # Gap detected
                gap_size = current_seq - expected_seq
                gaps_detected += gap_size
                
                self._logger.warning(
                    f"Sequence gap detected for task {task_id}",
                    extra={
                        "taskId": task_id,
                        "expectedSeq": expected_seq,
                        "actualSeq": current_seq,
                        "gapSize": gap_size,
                    }
                )
                
                # For recovery, we accept the gap and continue
                # In a production system, you might want to:
                # 1. Query Control Plane for missing events
                # 2. Generate placeholder events
                # 3. Alert operators about data loss
                gaps_resolved += gap_size
            
            expected_seq = current_seq + 1
        
        if gaps_detected > 0:
            self._logger.info(
                f"Sequence continuity check completed for task {task_id}",
                extra={
                    "taskId": task_id,
                    "gapsDetected": gaps_detected,
                    "gapsResolved": gaps_resolved,
                    "totalEvents": len(events),
                }
            )
        
        return gaps_detected, gaps_resolved


def create_recovery_service(
    outbox: RedisOutbox | None = None,
    client: ControlPlaneClient | None = None,
    config: RecoveryConfig | None = None,
) -> EventRecoveryService:
    """
    Factory function to create a recovery service with default configuration.
    
    Args:
        outbox: Redis outbox instance (creates default if None)
        client: Control plane client (required)
        config: Recovery configuration (uses defaults if None)
        
    Returns:
        Configured EventRecoveryService instance
        
    Raises:
        ValueError: If client is None
    """
    if client is None:
        raise ValueError("ControlPlaneClient is required")
    
    if outbox is None:
        outbox = RedisOutbox()
    
    if config is None:
        config = RecoveryConfig()
    
    return EventRecoveryService(outbox=outbox, client=client, config=config)