"""
Resource monitoring service for the Python Agent.

Collects system resource metrics, integrates with the resource optimizer,
and provides real-time monitoring capabilities for dynamic scaling decisions.

This service runs as a background thread and continuously monitors:
- CPU and memory utilization
- Network I/O
- Database and Redis connection pools
- Task queue depths
- LLM token usage

Requirements: Task 33.2 - Optimize resource utilization
"""
from __future__ import annotations

import asyncio
import logging
import os
import psutil
import threading
import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass

from .resource_optimizer import (
    ResourceOptimizer, 
    ResourceMetrics, 
    CostMetrics,
    get_resource_optimizer
)

logger = logging.getLogger(__name__)


@dataclass
class MonitoringConfig:
    """Configuration for resource monitoring."""
    collection_interval_seconds: float = 30.0
    cpu_collection_interval: float = 1.0  # For CPU percentage calculation
    enable_network_monitoring: bool = True
    enable_process_monitoring: bool = True
    enable_cost_tracking: bool = True
    alert_thresholds: Dict[str, float] = None
    
    def __post_init__(self):
        if self.alert_thresholds is None:
            self.alert_thresholds = {
                "cpu_percent": 90.0,
                "memory_percent": 95.0,
                "disk_percent": 90.0,
                "queue_depth": 50,
            }


class ResourceMonitor:
    """
    Background service for monitoring system resources.
    
    Collects metrics and feeds them to the ResourceOptimizer for
    scaling decisions and cost optimization.
    """
    
    def __init__(
        self,
        config: Optional[MonitoringConfig] = None,
        optimizer: Optional[ResourceOptimizer] = None,
        alert_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        """
        Initialize the resource monitor.
        
        Args:
            config: Monitoring configuration
            optimizer: Resource optimizer instance (uses global if None)
            alert_callback: Function to call when alerts are triggered
        """
        self._config = config or MonitoringConfig()
        self._optimizer = optimizer or get_resource_optimizer()
        self._alert_callback = alert_callback
        
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Metrics tracking
        self._last_network_io: Optional[Dict[str, int]] = None
        self._last_network_time: Optional[float] = None
        self._process = psutil.Process()
        
        # Cost tracking
        self._llm_token_count = 0
        self._llm_api_calls = 0
        self._start_time = time.time()
        
        logger.info("ResourceMonitor initialized with interval=%.1fs", 
                   self._config.collection_interval_seconds)

    def start(self) -> None:
        """Start the resource monitoring service."""
        if self._running:
            logger.warning("ResourceMonitor is already running")
            return
        
        self._running = True
        self._stop_event.clear()
        
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="resource-monitor",
            daemon=True
        )
        self._monitor_thread.start()
        
        logger.info("ResourceMonitor started")

    def stop(self) -> None:
        """Stop the resource monitoring service."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)
        
        logger.info("ResourceMonitor stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop that runs in a background thread."""
        logger.info("Resource monitoring loop started")
        
        while self._running and not self._stop_event.is_set():
            try:
                # Collect current metrics
                metrics = self._collect_metrics()
                
                # Send to optimizer
                self._optimizer.record_metrics(metrics)
                
                # Check for alerts
                self._check_alerts(metrics)
                
                # Collect and track costs if enabled
                if self._config.enable_cost_tracking:
                    cost_metrics = self._collect_cost_metrics()
                    self._optimizer.track_cost(cost_metrics)
                
            except Exception as e:
                logger.error("Error in resource monitoring loop: %s", e, exc_info=True)
            
            # Wait for next collection interval
            self._stop_event.wait(self._config.collection_interval_seconds)
        
        logger.info("Resource monitoring loop ended")

    def _collect_metrics(self) -> ResourceMetrics:
        """Collect current system resource metrics."""
        # CPU utilization (averaged over collection interval)
        cpu_percent = psutil.cpu_percent(interval=self._config.cpu_collection_interval)
        
        # Memory utilization
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Network I/O rate
        network_io_mbps = self._calculate_network_io_rate()
        
        # Process-specific metrics
        active_connections = self._get_active_connections()
        
        # Queue metrics (from optimizer or external source)
        queue_depth, pending_tasks = self._get_queue_metrics()
        
        # LLM token usage
        llm_tokens_per_minute = self._calculate_llm_token_rate()
        
        return ResourceMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            network_io_mbps=network_io_mbps,
            active_connections=active_connections,
            queue_depth=queue_depth,
            pending_tasks=pending_tasks,
            llm_tokens_per_minute=llm_tokens_per_minute,
        )

    def _calculate_network_io_rate(self) -> float:
        """Calculate network I/O rate in MB/s."""
        if not self._config.enable_network_monitoring:
            return 0.0
        
        try:
            current_io = psutil.net_io_counters()
            current_time = time.time()
            
            if self._last_network_io is None or self._last_network_time is None:
                self._last_network_io = {
                    'bytes_sent': current_io.bytes_sent,
                    'bytes_recv': current_io.bytes_recv,
                }
                self._last_network_time = current_time
                return 0.0
            
            # Calculate rate
            time_delta = current_time - self._last_network_time
            if time_delta <= 0:
                return 0.0
            
            bytes_sent_delta = current_io.bytes_sent - self._last_network_io['bytes_sent']
            bytes_recv_delta = current_io.bytes_recv - self._last_network_io['bytes_recv']
            total_bytes_delta = bytes_sent_delta + bytes_recv_delta
            
            # Convert to MB/s
            mbps = (total_bytes_delta / time_delta) / (1024 * 1024)
            
            # Update last values
            self._last_network_io = {
                'bytes_sent': current_io.bytes_sent,
                'bytes_recv': current_io.bytes_recv,
            }
            self._last_network_time = current_time
            
            return max(0.0, mbps)
            
        except Exception as e:
            logger.warning("Failed to calculate network I/O rate: %s", e)
            return 0.0

    def _get_active_connections(self) -> int:
        """Get the number of active network connections."""
        try:
            if not self._config.enable_process_monitoring:
                return 0
            
            connections = self._process.connections()
            # Count established connections
            active_count = sum(1 for conn in connections 
                             if conn.status == psutil.CONN_ESTABLISHED)
            return active_count
            
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.warning("Failed to get active connections: %s", e)
            return 0

    def _get_queue_metrics(self) -> tuple[int, int]:
        """Get current queue depth and pending tasks."""
        try:
            # Get metrics from the optimizer's internal state
            summary = self._optimizer.get_resource_utilization_summary()
            
            if summary.get("status") == "no_data":
                return 0, 0
            
            queue_status = summary.get("queue_status", {})
            queue_depth = queue_status.get("pending_tasks", 0)
            pending_batches = queue_status.get("pending_batches", 0)
            
            # Estimate total pending tasks
            pending_tasks = queue_depth + (pending_batches * 5)  # Assume 5 tasks per batch
            
            return queue_depth, pending_tasks
            
        except Exception as e:
            logger.warning("Failed to get queue metrics: %s", e)
            return 0, 0

    def _calculate_llm_token_rate(self) -> int:
        """Calculate LLM token usage rate per minute."""
        try:
            current_time = time.time()
            elapsed_minutes = (current_time - self._start_time) / 60.0
            
            if elapsed_minutes <= 0:
                return 0
            
            return int(self._llm_token_count / elapsed_minutes)
            
        except Exception as e:
            logger.warning("Failed to calculate LLM token rate: %s", e)
            return 0

    def _collect_cost_metrics(self) -> CostMetrics:
        """Collect current cost metrics."""
        current_time = time.time()
        elapsed_hours = (current_time - self._start_time) / 3600.0
        
        # Calculate costs based on usage
        llm_api_cost = (self._llm_token_count / 1000.0) * 0.002  # $0.002 per 1K tokens
        compute_cost = elapsed_hours * 0.10  # $0.10 per hour
        storage_cost = 0.01  # Fixed small storage cost
        network_cost = 0.005  # Fixed small network cost
        
        total_cost = llm_api_cost + compute_cost + storage_cost + network_cost
        
        # Calculate cost per task (rough estimate)
        estimated_tasks = max(1, self._llm_api_calls)  # Avoid division by zero
        cost_per_task = total_cost / estimated_tasks
        
        return CostMetrics(
            llm_api_cost_usd=llm_api_cost,
            compute_cost_usd=compute_cost,
            storage_cost_usd=storage_cost,
            network_cost_usd=network_cost,
            total_cost_usd=total_cost,
            cost_per_task=cost_per_task,
        )

    def _check_alerts(self, metrics: ResourceMetrics) -> None:
        """Check if any metrics exceed alert thresholds."""
        alerts = []
        
        thresholds = self._config.alert_thresholds
        
        if metrics.cpu_percent > thresholds.get("cpu_percent", 90.0):
            alerts.append({
                "type": "cpu_high",
                "message": f"CPU utilization {metrics.cpu_percent:.1f}% exceeds threshold",
                "value": metrics.cpu_percent,
                "threshold": thresholds["cpu_percent"],
            })
        
        if metrics.memory_percent > thresholds.get("memory_percent", 95.0):
            alerts.append({
                "type": "memory_high",
                "message": f"Memory utilization {metrics.memory_percent:.1f}% exceeds threshold",
                "value": metrics.memory_percent,
                "threshold": thresholds["memory_percent"],
            })
        
        if metrics.queue_depth > thresholds.get("queue_depth", 50):
            alerts.append({
                "type": "queue_high",
                "message": f"Queue depth {metrics.queue_depth} exceeds threshold",
                "value": metrics.queue_depth,
                "threshold": thresholds["queue_depth"],
            })
        
        # Trigger alert callback for each alert
        for alert in alerts:
            if self._alert_callback:
                try:
                    self._alert_callback(alert["type"], alert)
                except Exception as e:
                    logger.error("Error in alert callback: %s", e)
            else:
                logger.warning("ALERT: %s", alert["message"])

    def record_llm_usage(self, token_count: int) -> None:
        """Record LLM token usage for cost tracking."""
        self._llm_token_count += token_count
        self._llm_api_calls += 1
        
        logger.debug("Recorded LLM usage: %d tokens (total: %d)", 
                    token_count, self._llm_token_count)

    def get_current_metrics(self) -> Optional[ResourceMetrics]:
        """Get the most recent metrics without waiting for the next collection."""
        try:
            return self._collect_metrics()
        except Exception as e:
            logger.error("Failed to collect current metrics: %s", e)
            return None

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get the current status of the monitoring service."""
        return {
            "running": self._running,
            "collection_interval": self._config.collection_interval_seconds,
            "uptime_seconds": time.time() - self._start_time,
            "total_llm_tokens": self._llm_token_count,
            "total_llm_calls": self._llm_api_calls,
            "config": {
                "enable_network_monitoring": self._config.enable_network_monitoring,
                "enable_process_monitoring": self._config.enable_process_monitoring,
                "enable_cost_tracking": self._config.enable_cost_tracking,
            }
        }


# Global monitor instance
_resource_monitor: Optional[ResourceMonitor] = None


def get_resource_monitor() -> ResourceMonitor:
    """Get the global resource monitor instance."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor


def initialize_resource_monitor(
    config: Optional[MonitoringConfig] = None,
    optimizer: Optional[ResourceOptimizer] = None,
    alert_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> ResourceMonitor:
    """Initialize the global resource monitor with custom configuration."""
    global _resource_monitor
    _resource_monitor = ResourceMonitor(
        config=config,
        optimizer=optimizer,
        alert_callback=alert_callback,
    )
    return _resource_monitor


def start_resource_monitoring() -> None:
    """Start the global resource monitoring service."""
    monitor = get_resource_monitor()
    monitor.start()


def stop_resource_monitoring() -> None:
    """Stop the global resource monitoring service."""
    global _resource_monitor
    if _resource_monitor:
        _resource_monitor.stop()