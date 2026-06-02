"""
Resource utilization optimizer for the Python Agent.

Implements dynamic resource scaling based on load, cost monitoring and optimization
recommendations, and efficient task queuing and batching strategies.

This module provides:
- Dynamic scaling based on system load and queue depth
- Cost monitoring with optimization recommendations
- Intelligent task batching and queuing strategies
- Resource utilization tracking and alerting

Requirements: Task 33.2 - Optimize resource utilization
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Dict, List, Optional, Tuple, Any
from collections import deque, defaultdict
import statistics

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of resources that can be optimized."""
    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"
    LLM_TOKENS = "llm_tokens"
    REDIS_CONNECTIONS = "redis_connections"
    DATABASE_CONNECTIONS = "database_connections"


class ScalingAction(Enum):
    """Actions that can be taken for resource scaling."""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    MAINTAIN = "maintain"


@dataclass
class ResourceMetrics:
    """Current resource utilization metrics."""
    cpu_percent: float
    memory_percent: float
    network_io_mbps: float
    active_connections: int
    queue_depth: int
    pending_tasks: int
    llm_tokens_per_minute: int
    timestamp: float = field(default_factory=time.time)


@dataclass
class ScalingRecommendation:
    """Recommendation for resource scaling."""
    resource_type: ResourceType
    action: ScalingAction
    current_value: float
    recommended_value: float
    reason: str
    confidence: float  # 0.0 to 1.0
    estimated_cost_impact: float  # Positive = cost increase, negative = savings


@dataclass
class CostMetrics:
    """Cost tracking metrics."""
    llm_api_cost_usd: float
    compute_cost_usd: float
    storage_cost_usd: float
    network_cost_usd: float
    total_cost_usd: float
    cost_per_task: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class BatchingConfig:
    """Configuration for task batching."""
    max_batch_size: int = 10
    max_wait_time_seconds: float = 5.0
    min_batch_size: int = 2
    priority_threshold: float = 0.8  # High priority tasks bypass batching
    similar_task_grouping: bool = True


@dataclass
class TaskBatch:
    """A batch of tasks to be processed together."""
    tasks: List[Dict[str, Any]]
    batch_id: str
    created_at: float
    priority: float
    estimated_processing_time: float


class ResourceOptimizer:
    """
    Main resource optimization engine.
    
    Monitors system resources, provides scaling recommendations,
    tracks costs, and manages efficient task batching.
    """
    
    def __init__(
        self,
        scaling_thresholds: Optional[Dict[str, Tuple[float, float]]] = None,
        cost_tracking_enabled: bool = True,
        batching_config: Optional[BatchingConfig] = None,
    ):
        """
        Initialize the resource optimizer.
        
        Args:
            scaling_thresholds: Dict mapping resource types to (scale_down_threshold, scale_up_threshold)
            cost_tracking_enabled: Whether to track and optimize costs
            batching_config: Configuration for task batching
        """
        self._lock = Lock()
        self._metrics_history: deque[ResourceMetrics] = deque(maxlen=100)
        self._cost_history: deque[CostMetrics] = deque(maxlen=100)
        self._pending_batches: List[TaskBatch] = []
        self._task_queue: deque[Dict[str, Any]] = deque()
        
        # Default scaling thresholds (scale_down, scale_up)
        self._scaling_thresholds = scaling_thresholds or {
            "cpu": (30.0, 80.0),
            "memory": (40.0, 85.0),
            "queue_depth": (5, 20),
            "connections": (10, 45),
        }
        
        self._cost_tracking_enabled = cost_tracking_enabled
        self._batching_config = batching_config or BatchingConfig()
        
        # Cost tracking
        self._llm_token_cost_per_1k = 0.002  # $0.002 per 1K tokens (example rate)
        self._compute_cost_per_hour = 0.10   # $0.10 per hour (example rate)
        
        logger.info("ResourceOptimizer initialized with cost_tracking=%s", cost_tracking_enabled)

    def record_metrics(self, metrics: ResourceMetrics) -> None:
        """Record current resource metrics."""
        with self._lock:
            self._metrics_history.append(metrics)
            logger.debug(
                "Recorded metrics: CPU=%.1f%%, Memory=%.1f%%, Queue=%d",
                metrics.cpu_percent, metrics.memory_percent, metrics.queue_depth
            )

    def get_scaling_recommendations(self) -> List[ScalingRecommendation]:
        """
        Analyze current metrics and provide scaling recommendations.
        
        Returns:
            List of scaling recommendations with confidence scores
        """
        with self._lock:
            if not self._metrics_history:
                return []
            
            current = self._metrics_history[-1]
            recent_metrics = list(self._metrics_history)[-10:]  # Last 10 samples
            
        recommendations = []
        
        # CPU scaling recommendation
        cpu_recommendation = self._analyze_cpu_scaling(current, recent_metrics)
        if cpu_recommendation:
            recommendations.append(cpu_recommendation)
        
        # Memory scaling recommendation
        memory_recommendation = self._analyze_memory_scaling(current, recent_metrics)
        if memory_recommendation:
            recommendations.append(memory_recommendation)
        
        # Queue depth scaling recommendation
        queue_recommendation = self._analyze_queue_scaling(current, recent_metrics)
        if queue_recommendation:
            recommendations.append(queue_recommendation)
        
        # Connection pool scaling recommendation
        connection_recommendation = self._analyze_connection_scaling(current, recent_metrics)
        if connection_recommendation:
            recommendations.append(connection_recommendation)
        
        return recommendations

    def _analyze_cpu_scaling(
        self, 
        current: ResourceMetrics, 
        recent_metrics: List[ResourceMetrics]
    ) -> Optional[ScalingRecommendation]:
        """Analyze CPU utilization and recommend scaling."""
        cpu_values = [m.cpu_percent for m in recent_metrics]
        avg_cpu = statistics.mean(cpu_values)
        cpu_trend = self._calculate_trend(cpu_values)
        
        scale_down_threshold, scale_up_threshold = self._scaling_thresholds["cpu"]
        
        if avg_cpu > scale_up_threshold and cpu_trend > 0:
            return ScalingRecommendation(
                resource_type=ResourceType.CPU,
                action=ScalingAction.SCALE_UP,
                current_value=avg_cpu,
                recommended_value=min(100.0, avg_cpu * 1.5),
                reason=f"CPU utilization {avg_cpu:.1f}% exceeds threshold {scale_up_threshold}% with upward trend",
                confidence=min(1.0, (avg_cpu - scale_up_threshold) / 20.0),
                estimated_cost_impact=self._compute_cost_per_hour * 0.5  # 50% increase
            )
        elif avg_cpu < scale_down_threshold and cpu_trend < 0:
            return ScalingRecommendation(
                resource_type=ResourceType.CPU,
                action=ScalingAction.SCALE_DOWN,
                current_value=avg_cpu,
                recommended_value=max(10.0, avg_cpu * 0.7),
                reason=f"CPU utilization {avg_cpu:.1f}% below threshold {scale_down_threshold}% with downward trend",
                confidence=min(1.0, (scale_down_threshold - avg_cpu) / 20.0),
                estimated_cost_impact=-self._compute_cost_per_hour * 0.3  # 30% savings
            )
        
        return None

    def _analyze_memory_scaling(
        self, 
        current: ResourceMetrics, 
        recent_metrics: List[ResourceMetrics]
    ) -> Optional[ScalingRecommendation]:
        """Analyze memory utilization and recommend scaling."""
        memory_values = [m.memory_percent for m in recent_metrics]
        avg_memory = statistics.mean(memory_values)
        memory_trend = self._calculate_trend(memory_values)
        
        scale_down_threshold, scale_up_threshold = self._scaling_thresholds["memory"]
        
        if avg_memory > scale_up_threshold:
            return ScalingRecommendation(
                resource_type=ResourceType.MEMORY,
                action=ScalingAction.SCALE_UP,
                current_value=avg_memory,
                recommended_value=min(100.0, avg_memory * 1.3),
                reason=f"Memory utilization {avg_memory:.1f}% exceeds threshold {scale_up_threshold}%",
                confidence=min(1.0, (avg_memory - scale_up_threshold) / 15.0),
                estimated_cost_impact=self._compute_cost_per_hour * 0.4  # 40% increase
            )
        elif avg_memory < scale_down_threshold and memory_trend < 0:
            return ScalingRecommendation(
                resource_type=ResourceType.MEMORY,
                action=ScalingAction.SCALE_DOWN,
                current_value=avg_memory,
                recommended_value=max(20.0, avg_memory * 0.8),
                reason=f"Memory utilization {avg_memory:.1f}% below threshold {scale_down_threshold}%",
                confidence=min(1.0, (scale_down_threshold - avg_memory) / 15.0),
                estimated_cost_impact=-self._compute_cost_per_hour * 0.2  # 20% savings
            )
        
        return None

    def _analyze_queue_scaling(
        self, 
        current: ResourceMetrics, 
        recent_metrics: List[ResourceMetrics]
    ) -> Optional[ScalingRecommendation]:
        """Analyze task queue depth and recommend scaling."""
        queue_values = [m.queue_depth for m in recent_metrics]
        avg_queue = statistics.mean(queue_values)
        queue_trend = self._calculate_trend(queue_values)
        
        scale_down_threshold, scale_up_threshold = self._scaling_thresholds["queue_depth"]
        
        if avg_queue > scale_up_threshold and queue_trend > 0:
            return ScalingRecommendation(
                resource_type=ResourceType.CPU,  # More workers needed
                action=ScalingAction.SCALE_UP,
                current_value=avg_queue,
                recommended_value=scale_up_threshold * 0.7,  # Target queue depth
                reason=f"Queue depth {avg_queue:.1f} exceeds threshold {scale_up_threshold} with growing trend",
                confidence=min(1.0, (avg_queue - scale_up_threshold) / 10.0),
                estimated_cost_impact=self._compute_cost_per_hour * 0.6  # 60% increase for more workers
            )
        
        return None

    def _analyze_connection_scaling(
        self, 
        current: ResourceMetrics, 
        recent_metrics: List[ResourceMetrics]
    ) -> Optional[ScalingRecommendation]:
        """Analyze connection pool utilization and recommend scaling."""
        connection_values = [m.active_connections for m in recent_metrics]
        avg_connections = statistics.mean(connection_values)
        
        scale_down_threshold, scale_up_threshold = self._scaling_thresholds["connections"]
        
        if avg_connections > scale_up_threshold:
            return ScalingRecommendation(
                resource_type=ResourceType.DATABASE_CONNECTIONS,
                action=ScalingAction.SCALE_UP,
                current_value=avg_connections,
                recommended_value=min(100, avg_connections * 1.2),
                reason=f"Active connections {avg_connections:.1f} exceeds threshold {scale_up_threshold}",
                confidence=min(1.0, (avg_connections - scale_up_threshold) / 10.0),
                estimated_cost_impact=0.05  # Small cost increase for connection pool
            )
        elif avg_connections < scale_down_threshold:
            return ScalingRecommendation(
                resource_type=ResourceType.DATABASE_CONNECTIONS,
                action=ScalingAction.SCALE_DOWN,
                current_value=avg_connections,
                recommended_value=max(5, avg_connections * 0.8),
                reason=f"Active connections {avg_connections:.1f} below threshold {scale_down_threshold}",
                confidence=min(1.0, (scale_down_threshold - avg_connections) / 10.0),
                estimated_cost_impact=-0.02  # Small cost savings
            )
        
        return None

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend direction (-1 to 1) for a series of values."""
        if len(values) < 2:
            return 0.0
        
        # Simple linear trend calculation
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        if n * x2_sum - x_sum * x_sum == 0:
            return 0.0
        
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        
        # Normalize slope to [-1, 1] range
        max_value = max(values) if values else 1.0
        return max(-1.0, min(1.0, slope / max_value))

    def track_cost(self, cost_metrics: CostMetrics) -> None:
        """Track cost metrics for optimization analysis."""
        if not self._cost_tracking_enabled:
            return
        
        with self._lock:
            self._cost_history.append(cost_metrics)
            logger.debug(
                "Tracked costs: Total=$%.4f, Per-task=$%.4f",
                cost_metrics.total_cost_usd, cost_metrics.cost_per_task
            )

    def get_cost_optimization_recommendations(self) -> List[str]:
        """
        Analyze cost trends and provide optimization recommendations.
        
        Returns:
            List of human-readable cost optimization recommendations
        """
        if not self._cost_tracking_enabled or not self._cost_history:
            return []
        
        recommendations = []
        recent_costs = list(self._cost_history)[-10:]  # Last 10 cost samples
        
        # Analyze LLM token costs
        llm_costs = [c.llm_api_cost_usd for c in recent_costs]
        if llm_costs:
            avg_llm_cost = statistics.mean(llm_costs)
            total_cost = recent_costs[-1].total_cost_usd
            llm_percentage = (avg_llm_cost / total_cost) * 100 if total_cost > 0 else 0
            
            if llm_percentage > 60:
                recommendations.append(
                    f"LLM costs represent {llm_percentage:.1f}% of total costs. "
                    "Consider implementing more aggressive caching, using smaller models "
                    "for simple tasks, or batching similar requests."
                )
        
        # Analyze cost per task trend
        cost_per_task_values = [c.cost_per_task for c in recent_costs]
        if len(cost_per_task_values) >= 5:
            trend = self._calculate_trend(cost_per_task_values)
            if trend > 0.15:  # Significant upward trend (lowered from 0.3 for more realistic detection)
                recommendations.append(
                    f"Cost per task is trending upward (trend: {trend:.2f}). "
                    "Review recent changes and consider optimizing resource allocation."
                )
        
        # Check for cost spikes
        if len(recent_costs) >= 2:
            current_cost = recent_costs[-1].total_cost_usd
            previous_cost = recent_costs[-2].total_cost_usd
            if previous_cost > 0 and (current_cost / previous_cost) > 1.5:
                recommendations.append(
                    f"Cost spike detected: {((current_cost / previous_cost - 1) * 100):.1f}% increase. "
                    "Investigate recent system changes or unusual load patterns."
                )
        
        return recommendations

    def add_task_to_queue(self, task: Dict[str, Any]) -> None:
        """Add a task to the optimization queue."""
        with self._lock:
            self._task_queue.append(task)
            logger.debug("Added task to queue: %s", task.get("task_id", "unknown"))

    def get_optimized_batches(self) -> List[TaskBatch]:
        """
        Create optimized task batches based on current queue and configuration.
        
        Returns:
            List of optimized task batches ready for processing
        """
        with self._lock:
            if not self._task_queue:
                return []
            
            # Process pending tasks into batches
            ready_batches = []
            current_time = time.time()
            
            # Group tasks by similarity if enabled
            if self._batching_config.similar_task_grouping:
                task_groups = self._group_similar_tasks(list(self._task_queue))
            else:
                task_groups = {"default": list(self._task_queue)}
            
            for group_name, tasks in task_groups.items():
                if not tasks:
                    continue
                
                # Create batches from this group
                while tasks:
                    batch_tasks = []
                    batch_priority = 0.0
                    estimated_time = 0.0
                    
                    # Fill batch up to max size or until we run out of tasks
                    while (len(batch_tasks) < self._batching_config.max_batch_size and 
                           tasks):
                        task = tasks.pop(0)
                        task_priority = task.get("priority", 0.5)
                        
                        # High priority tasks bypass batching
                        if (task_priority > self._batching_config.priority_threshold and 
                            not batch_tasks):
                            ready_batches.append(TaskBatch(
                                tasks=[task],
                                batch_id=f"priority_{int(current_time * 1000)}",
                                created_at=current_time,
                                priority=task_priority,
                                estimated_processing_time=self._estimate_task_time(task)
                            ))
                            continue
                        
                        batch_tasks.append(task)
                        batch_priority = max(batch_priority, task_priority)
                        estimated_time += self._estimate_task_time(task)
                    
                    # Create batch if we have enough tasks or if wait time exceeded
                    if (len(batch_tasks) >= self._batching_config.min_batch_size or
                        (batch_tasks and self._should_flush_batch(current_time))):
                        ready_batches.append(TaskBatch(
                            tasks=batch_tasks,
                            batch_id=f"batch_{group_name}_{int(current_time * 1000)}",
                            created_at=current_time,
                            priority=batch_priority,
                            estimated_processing_time=estimated_time
                        ))
                    else:
                        # Put tasks back if batch isn't ready
                        tasks.extend(batch_tasks)
                        break
            
            # Clear processed tasks from queue
            self._task_queue.clear()
            
            return ready_batches

    def _group_similar_tasks(self, tasks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group tasks by similarity for more efficient batching."""
        groups = defaultdict(list)
        
        for task in tasks:
            # Group by intent and agent profile
            intent = task.get("intent", "unknown")
            agent_profile = task.get("agentProfile", "default")
            group_key = f"{intent}_{agent_profile}"
            groups[group_key].append(task)
        
        return dict(groups)

    def _estimate_task_time(self, task: Dict[str, Any]) -> float:
        """Estimate processing time for a task in seconds."""
        # Simple heuristic based on task type and complexity
        intent = task.get("intent", "unknown")
        prompt_length = len(task.get("prompt", ""))
        
        base_times = {
            "analyze": 30.0,
            "code_change": 120.0,
            "backend_generation": 180.0,
            "test": 60.0,
            "deploy": 90.0,
        }
        
        base_time = base_times.get(intent, 60.0)
        
        # Adjust for prompt complexity
        complexity_factor = min(2.0, 1.0 + (prompt_length / 1000.0))
        
        return base_time * complexity_factor

    def _should_flush_batch(self, current_time: float) -> bool:
        """Determine if a batch should be flushed based on wait time."""
        if not self._pending_batches:
            return False
        
        oldest_batch = min(self._pending_batches, key=lambda b: b.created_at)
        wait_time = current_time - oldest_batch.created_at
        
        return wait_time >= self._batching_config.max_wait_time_seconds

    def get_resource_utilization_summary(self) -> Dict[str, Any]:
        """Get a summary of current resource utilization."""
        with self._lock:
            if not self._metrics_history:
                return {"status": "no_data"}
            
            current = self._metrics_history[-1]
            recent_metrics = list(self._metrics_history)[-10:]
            
        return {
            "timestamp": current.timestamp,
            "current_metrics": {
                "cpu_percent": current.cpu_percent,
                "memory_percent": current.memory_percent,
                "network_io_mbps": current.network_io_mbps,
                "active_connections": current.active_connections,
                "queue_depth": current.queue_depth,
                "pending_tasks": current.pending_tasks,
            },
            "averages_last_10": {
                "cpu_percent": statistics.mean([m.cpu_percent for m in recent_metrics]),
                "memory_percent": statistics.mean([m.memory_percent for m in recent_metrics]),
                "queue_depth": statistics.mean([m.queue_depth for m in recent_metrics]),
            },
            "trends": {
                "cpu_trend": self._calculate_trend([m.cpu_percent for m in recent_metrics]),
                "memory_trend": self._calculate_trend([m.memory_percent for m in recent_metrics]),
                "queue_trend": self._calculate_trend([m.queue_depth for m in recent_metrics]),
            },
            "queue_status": {
                "pending_tasks": len(self._task_queue),
                "pending_batches": len(self._pending_batches),
            }
        }


# Singleton instance for global access
_resource_optimizer: Optional[ResourceOptimizer] = None


def get_resource_optimizer() -> ResourceOptimizer:
    """Get the global resource optimizer instance."""
    global _resource_optimizer
    if _resource_optimizer is None:
        _resource_optimizer = ResourceOptimizer()
    return _resource_optimizer


def initialize_resource_optimizer(
    scaling_thresholds: Optional[Dict[str, Tuple[float, float]]] = None,
    cost_tracking_enabled: bool = True,
    batching_config: Optional[BatchingConfig] = None,
) -> ResourceOptimizer:
    """Initialize the global resource optimizer with custom configuration."""
    global _resource_optimizer
    _resource_optimizer = ResourceOptimizer(
        scaling_thresholds=scaling_thresholds,
        cost_tracking_enabled=cost_tracking_enabled,
        batching_config=batching_config,
    )
    return _resource_optimizer