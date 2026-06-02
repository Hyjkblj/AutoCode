"""
Integration layer for resource optimization components.

Connects the resource optimizer, monitor, and task queue manager with the
existing orchestrator and agent system to provide seamless resource optimization.

This module provides:
- Integration with the existing orchestrator
- Automatic resource monitoring startup
- Cost tracking integration with LLM clients
- Scaling recommendation handling
- Performance metrics collection

Requirements: Task 33.2 - Optimize resource utilization
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass

from .resource_optimizer import (
    ResourceOptimizer, 
    ResourceMetrics, 
    CostMetrics,
    ScalingRecommendation,
    get_resource_optimizer,
    initialize_resource_optimizer,
)
from .resource_monitor import (
    ResourceMonitor,
    MonitoringConfig,
    get_resource_monitor,
    initialize_resource_monitor,
    start_resource_monitoring,
    stop_resource_monitoring,
)
from .task_queue_manager import (
    TaskQueueManager,
    TaskPriority,
    BatchingConfig,
    get_task_queue_manager,
    initialize_task_queue_manager,
)

logger = logging.getLogger(__name__)


@dataclass
class ResourceOptimizationConfig:
    """Configuration for the complete resource optimization system."""
    # Resource monitoring
    monitoring_enabled: bool = True
    monitoring_interval_seconds: float = 30.0
    
    # Cost tracking
    cost_tracking_enabled: bool = True
    llm_token_cost_per_1k: float = 0.002
    compute_cost_per_hour: float = 0.10
    
    # Task batching
    batching_enabled: bool = True
    max_batch_size: int = 10
    max_wait_time_seconds: float = 5.0
    min_batch_size: int = 2
    
    # Scaling thresholds
    cpu_scale_up_threshold: float = 80.0
    cpu_scale_down_threshold: float = 30.0
    memory_scale_up_threshold: float = 85.0
    memory_scale_down_threshold: float = 40.0
    queue_scale_up_threshold: int = 20
    queue_scale_down_threshold: int = 5
    
    # Alert thresholds
    cpu_alert_threshold: float = 90.0
    memory_alert_threshold: float = 95.0
    queue_alert_threshold: int = 50


class ResourceOptimizationManager:
    """
    Main manager for the complete resource optimization system.
    
    Coordinates between the optimizer, monitor, and task queue manager
    to provide comprehensive resource optimization capabilities.
    """
    
    def __init__(self, config: Optional[ResourceOptimizationConfig] = None):
        """Initialize the resource optimization manager."""
        self._config = config or ResourceOptimizationConfig()
        
        # Initialize components
        self._optimizer: Optional[ResourceOptimizer] = None
        self._monitor: Optional[ResourceMonitor] = None
        self._queue_manager: Optional[TaskQueueManager] = None
        
        # Callbacks and handlers
        self._scaling_handlers: List[Callable[[List[ScalingRecommendation]], None]] = []
        self._alert_handlers: List[Callable[[str, Dict[str, Any]], None]] = []
        self._cost_handlers: List[Callable[[List[str]], None]] = []
        
        # State tracking
        self._initialized = False
        self._running = False
        
        logger.info("ResourceOptimizationManager created")

    def initialize(self) -> None:
        """Initialize all resource optimization components."""
        if self._initialized:
            logger.warning("ResourceOptimizationManager already initialized")
            return
        
        try:
            # Initialize resource optimizer
            scaling_thresholds = {
                "cpu": (self._config.cpu_scale_down_threshold, self._config.cpu_scale_up_threshold),
                "memory": (self._config.memory_scale_down_threshold, self._config.memory_scale_up_threshold),
                "queue_depth": (self._config.queue_scale_down_threshold, self._config.queue_scale_up_threshold),
                "connections": (10, 45),  # Default connection thresholds
            }
            
            self._optimizer = initialize_resource_optimizer(
                scaling_thresholds=scaling_thresholds,
                cost_tracking_enabled=self._config.cost_tracking_enabled,
            )
            
            # Initialize resource monitor
            if self._config.monitoring_enabled:
                monitoring_config = MonitoringConfig(
                    collection_interval_seconds=self._config.monitoring_interval_seconds,
                    enable_cost_tracking=self._config.cost_tracking_enabled,
                    alert_thresholds={
                        "cpu_percent": self._config.cpu_alert_threshold,
                        "memory_percent": self._config.memory_alert_threshold,
                        "queue_depth": self._config.queue_alert_threshold,
                    }
                )
                
                self._monitor = initialize_resource_monitor(
                    config=monitoring_config,
                    optimizer=self._optimizer,
                    alert_callback=self._handle_alert,
                )
            
            # Initialize task queue manager
            if self._config.batching_enabled:
                batching_config = BatchingConfig(
                    max_batch_size=self._config.max_batch_size,
                    max_wait_time_seconds=self._config.max_wait_time_seconds,
                    min_batch_size=self._config.min_batch_size,
                )
                
                self._queue_manager = initialize_task_queue_manager(
                    batching_config=batching_config,
                    batch_processor=self._process_task_batch,
                )
            
            self._initialized = True
            logger.info("ResourceOptimizationManager initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize ResourceOptimizationManager: %s", e, exc_info=True)
            raise

    def start(self) -> None:
        """Start all resource optimization services."""
        if not self._initialized:
            self.initialize()
        
        if self._running:
            logger.warning("ResourceOptimizationManager already running")
            return
        
        try:
            # Start resource monitoring
            if self._monitor:
                self._monitor.start()
            
            # Start task queue processing
            if self._queue_manager:
                self._queue_manager.start()
            
            self._running = True
            logger.info("ResourceOptimizationManager started")
            
        except Exception as e:
            logger.error("Failed to start ResourceOptimizationManager: %s", e, exc_info=True)
            raise

    def stop(self) -> None:
        """Stop all resource optimization services."""
        if not self._running:
            return
        
        try:
            # Stop resource monitoring
            if self._monitor:
                self._monitor.stop()
            
            # Stop task queue processing
            if self._queue_manager:
                self._queue_manager.stop()
            
            self._running = False
            logger.info("ResourceOptimizationManager stopped")
            
        except Exception as e:
            logger.error("Error stopping ResourceOptimizationManager: %s", e, exc_info=True)

    def add_task(
        self,
        task_data: Dict[str, Any],
        priority: Optional[TaskPriority] = None,
    ) -> str:
        """Add a task to the optimized queue."""
        if not self._queue_manager:
            raise RuntimeError("Task queue manager not initialized")
        
        return self._queue_manager.add_task(task_data, priority)

    def get_scaling_recommendations(self) -> List[ScalingRecommendation]:
        """Get current scaling recommendations."""
        if not self._optimizer:
            return []
        
        recommendations = self._optimizer.get_scaling_recommendations()
        
        # Notify handlers
        if recommendations and self._scaling_handlers:
            for handler in self._scaling_handlers:
                try:
                    handler(recommendations)
                except Exception as e:
                    logger.error("Error in scaling handler: %s", e)
        
        return recommendations

    def get_cost_optimization_recommendations(self) -> List[str]:
        """Get current cost optimization recommendations."""
        if not self._optimizer:
            return []
        
        recommendations = self._optimizer.get_cost_optimization_recommendations()
        
        # Notify handlers
        if recommendations and self._cost_handlers:
            for handler in self._cost_handlers:
                try:
                    handler(recommendations)
                except Exception as e:
                    logger.error("Error in cost handler: %s", e)
        
        return recommendations

    def record_llm_usage(self, token_count: int, cost_usd: Optional[float] = None) -> None:
        """Record LLM usage for cost tracking."""
        if self._monitor:
            self._monitor.record_llm_usage(token_count)
        
        # Calculate cost if not provided
        if cost_usd is None:
            cost_usd = (token_count / 1000.0) * self._config.llm_token_cost_per_1k
        
        logger.debug("Recorded LLM usage: %d tokens, $%.4f", token_count, cost_usd)

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status including all optimization metrics."""
        status = {
            "initialized": self._initialized,
            "running": self._running,
            "timestamp": time.time(),
        }
        
        # Resource utilization
        if self._optimizer:
            status["resource_utilization"] = self._optimizer.get_resource_utilization_summary()
        
        # Queue status
        if self._queue_manager:
            status["queue_status"] = self._queue_manager.get_queue_summary()
        
        # Monitoring status
        if self._monitor:
            status["monitoring_status"] = self._monitor.get_monitoring_status()
        
        # Current recommendations
        status["scaling_recommendations"] = self.get_scaling_recommendations()
        status["cost_recommendations"] = self.get_cost_optimization_recommendations()
        
        return status

    def add_scaling_handler(self, handler: Callable[[List[ScalingRecommendation]], None]) -> None:
        """Add a handler for scaling recommendations."""
        self._scaling_handlers.append(handler)

    def add_alert_handler(self, handler: Callable[[str, Dict[str, Any]], None]) -> None:
        """Add a handler for resource alerts."""
        self._alert_handlers.append(handler)

    def add_cost_handler(self, handler: Callable[[List[str]], None]) -> None:
        """Add a handler for cost optimization recommendations."""
        self._cost_handlers.append(handler)

    def _handle_alert(self, alert_type: str, alert_data: Dict[str, Any]) -> None:
        """Handle resource alerts from the monitor."""
        logger.warning("Resource alert: %s - %s", alert_type, alert_data.get("message", ""))
        
        # Notify handlers
        for handler in self._alert_handlers:
            try:
                handler(alert_type, alert_data)
            except Exception as e:
                logger.error("Error in alert handler: %s", e)

    def _process_task_batch(self, batch) -> Any:
        """Process a task batch (placeholder for integration with orchestrator)."""
        # This would integrate with the existing orchestrator
        # For now, just log the batch processing
        logger.info("Processing task batch %s with %d tasks", batch.batch_id, len(batch.tasks))
        
        # Simulate processing time
        time.sleep(0.1)
        
        return {"batch_id": batch.batch_id, "status": "completed", "task_count": len(batch.tasks)}


# Global manager instance
_resource_optimization_manager: Optional[ResourceOptimizationManager] = None


def get_resource_optimization_manager() -> ResourceOptimizationManager:
    """Get the global resource optimization manager instance."""
    global _resource_optimization_manager
    if _resource_optimization_manager is None:
        _resource_optimization_manager = ResourceOptimizationManager()
    return _resource_optimization_manager


def initialize_resource_optimization(
    config: Optional[ResourceOptimizationConfig] = None
) -> ResourceOptimizationManager:
    """Initialize the global resource optimization system."""
    global _resource_optimization_manager
    _resource_optimization_manager = ResourceOptimizationManager(config)
    _resource_optimization_manager.initialize()
    return _resource_optimization_manager


def start_resource_optimization() -> None:
    """Start the global resource optimization system."""
    manager = get_resource_optimization_manager()
    manager.start()


def stop_resource_optimization() -> None:
    """Stop the global resource optimization system."""
    global _resource_optimization_manager
    if _resource_optimization_manager:
        _resource_optimization_manager.stop()


# Convenience functions for common operations
def add_optimized_task(
    task_data: Dict[str, Any],
    priority: Optional[TaskPriority] = None,
) -> str:
    """Add a task to the optimized queue."""
    manager = get_resource_optimization_manager()
    return manager.add_task(task_data, priority)


def record_llm_usage(token_count: int, cost_usd: Optional[float] = None) -> None:
    """Record LLM usage for cost tracking."""
    manager = get_resource_optimization_manager()
    manager.record_llm_usage(token_count, cost_usd)


def get_optimization_status() -> Dict[str, Any]:
    """Get current optimization system status."""
    manager = get_resource_optimization_manager()
    return manager.get_system_status()


def get_scaling_recommendations() -> List[ScalingRecommendation]:
    """Get current scaling recommendations."""
    manager = get_resource_optimization_manager()
    return manager.get_scaling_recommendations()


def get_cost_recommendations() -> List[str]:
    """Get current cost optimization recommendations."""
    manager = get_resource_optimization_manager()
    return manager.get_cost_optimization_recommendations()