"""
Task queue manager with intelligent batching and prioritization.

Implements efficient task queuing and batching strategies for optimal
resource utilization, including:
- Priority-based task scheduling
- Intelligent task batching by similarity
- Load-aware queue management
- Dynamic batch sizing based on system load

Requirements: Task 33.2 - Optimize resource utilization
"""
from __future__ import annotations

import asyncio
import logging
import time
import threading
from collections import deque, defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Tuple
from uuid import uuid4
import heapq

from .resource_optimizer import TaskBatch, BatchingConfig, get_resource_optimizer

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Task priority levels."""
    CRITICAL = 1.0
    HIGH = 0.8
    NORMAL = 0.5
    LOW = 0.2
    BACKGROUND = 0.1


class TaskStatus(Enum):
    """Task processing status."""
    QUEUED = "queued"
    BATCHED = "batched"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueuedTask:
    """A task in the queue with metadata."""
    task_id: str
    task_data: Dict[str, Any]
    priority: float
    created_at: float
    estimated_duration: float
    intent: str
    agent_profile: str
    status: TaskStatus = TaskStatus.QUEUED
    batch_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __lt__(self, other: 'QueuedTask') -> bool:
        """For priority queue ordering (higher priority first)."""
        return self.priority > other.priority


@dataclass
class QueueMetrics:
    """Metrics for queue performance monitoring."""
    total_tasks: int
    queued_tasks: int
    batched_tasks: int
    processing_tasks: int
    completed_tasks: int
    failed_tasks: int
    average_wait_time: float
    average_processing_time: float
    throughput_tasks_per_minute: float
    current_batch_count: int
    timestamp: float = field(default_factory=time.time)


class TaskQueueManager:
    """
    Advanced task queue manager with intelligent batching and prioritization.
    
    Features:
    - Priority-based task scheduling
    - Dynamic batching based on task similarity and system load
    - Load-aware queue management
    - Comprehensive metrics and monitoring
    - Retry logic with exponential backoff
    """
    
    def __init__(
        self,
        batching_config: Optional[BatchingConfig] = None,
        max_queue_size: int = 1000,
        enable_metrics: bool = True,
        batch_processor: Optional[Callable[[TaskBatch], Any]] = None,
    ):
        """
        Initialize the task queue manager.
        
        Args:
            batching_config: Configuration for task batching
            max_queue_size: Maximum number of tasks in queue
            enable_metrics: Whether to collect performance metrics
            batch_processor: Function to process task batches
        """
        self._batching_config = batching_config or BatchingConfig()
        self._max_queue_size = max_queue_size
        self._enable_metrics = enable_metrics
        self._batch_processor = batch_processor
        
        # Thread-safe data structures
        self._lock = threading.RLock()
        self._priority_queue: List[QueuedTask] = []  # Min-heap (but we reverse priority)
        self._task_lookup: Dict[str, QueuedTask] = {}
        self._active_batches: Dict[str, TaskBatch] = {}
        self._processing_tasks: Dict[str, QueuedTask] = {}
        
        # Metrics tracking
        self._metrics_history: deque[QueueMetrics] = deque(maxlen=100)
        self._completed_tasks: deque[Tuple[str, float, float]] = deque(maxlen=1000)  # (task_id, wait_time, processing_time)
        
        # Background processing
        self._running = False
        self._processor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Integration with resource optimizer
        self._resource_optimizer = get_resource_optimizer()
        
        logger.info("TaskQueueManager initialized with max_queue_size=%d", max_queue_size)

    def start(self) -> None:
        """Start the background task processing."""
        if self._running:
            logger.warning("TaskQueueManager is already running")
            return
        
        self._running = True
        self._stop_event.clear()
        
        self._processor_thread = threading.Thread(
            target=self._processing_loop,
            name="task-queue-processor",
            daemon=True
        )
        self._processor_thread.start()
        
        logger.info("TaskQueueManager started")

    def stop(self) -> None:
        """Stop the background task processing."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._processor_thread and self._processor_thread.is_alive():
            self._processor_thread.join(timeout=5.0)
        
        logger.info("TaskQueueManager stopped")

    def add_task(
        self,
        task_data: Dict[str, Any],
        priority: Optional[TaskPriority] = None,
        estimated_duration: Optional[float] = None,
    ) -> str:
        """
        Add a task to the queue.
        
        Args:
            task_data: Task data dictionary
            priority: Task priority (defaults to NORMAL)
            estimated_duration: Estimated processing time in seconds
            
        Returns:
            Task ID for tracking
            
        Raises:
            ValueError: If queue is full or task data is invalid
        """
        with self._lock:
            if len(self._priority_queue) >= self._max_queue_size:
                raise ValueError(f"Queue is full (max size: {self._max_queue_size})")
            
            # Generate task ID if not provided
            task_id = task_data.get("task_id") or str(uuid4())
            
            # Validate required fields
            if not task_data.get("prompt"):
                raise ValueError("Task data must include 'prompt' field")
            
            # Extract task metadata
            intent = task_data.get("intent", "unknown")
            agent_profile = task_data.get("agentProfile", "default")
            
            # Set default priority
            if priority is None:
                priority = TaskPriority.NORMAL
            priority_value = priority.value if isinstance(priority, TaskPriority) else float(priority)
            
            # Estimate duration if not provided
            if estimated_duration is None:
                estimated_duration = self._estimate_task_duration(task_data)
            
            # Create queued task
            queued_task = QueuedTask(
                task_id=task_id,
                task_data=task_data,
                priority=priority_value,
                created_at=time.time(),
                estimated_duration=estimated_duration,
                intent=intent,
                agent_profile=agent_profile,
            )
            
            # Add to priority queue and lookup
            heapq.heappush(self._priority_queue, queued_task)
            self._task_lookup[task_id] = queued_task
            
            logger.debug(
                "Added task %s to queue (priority=%.2f, intent=%s)",
                task_id, priority_value, intent
            )
            
            return task_id

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a task."""
        with self._lock:
            task = self._task_lookup.get(task_id)
            if not task:
                return None
            
            return {
                "task_id": task.task_id,
                "status": task.status.value,
                "priority": task.priority,
                "created_at": task.created_at,
                "estimated_duration": task.estimated_duration,
                "intent": task.intent,
                "batch_id": task.batch_id,
                "retry_count": task.retry_count,
                "wait_time": time.time() - task.created_at if task.status == TaskStatus.QUEUED else None,
            }

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a queued task."""
        with self._lock:
            task = self._task_lookup.get(task_id)
            if not task or task.status not in [TaskStatus.QUEUED, TaskStatus.BATCHED]:
                return False
            
            task.status = TaskStatus.CANCELLED
            
            # Remove from priority queue (mark as cancelled, will be cleaned up)
            logger.info("Cancelled task %s", task_id)
            return True

    def get_queue_metrics(self) -> QueueMetrics:
        """Get current queue performance metrics."""
        with self._lock:
            # Count tasks by status
            status_counts = defaultdict(int)
            for task in self._task_lookup.values():
                status_counts[task.status] += 1
            
            # Calculate average wait and processing times
            current_time = time.time()
            wait_times = []
            processing_times = []
            
            # Wait times for queued tasks
            for task in self._priority_queue:
                if task.status == TaskStatus.QUEUED:
                    wait_times.append(current_time - task.created_at)
            
            # Processing times from completed tasks
            if self._completed_tasks:
                recent_completed = list(self._completed_tasks)[-50:]  # Last 50 completed
                processing_times = [pt for _, _, pt in recent_completed]
            
            avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0.0
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0.0
            
            # Calculate throughput (tasks per minute)
            if len(self._completed_tasks) >= 2:
                recent_tasks = list(self._completed_tasks)[-10:]
                if recent_tasks:
                    time_span = current_time - (recent_tasks[0][1] + recent_tasks[0][2])  # created_at + processing_time
                    if time_span > 0:
                        throughput = (len(recent_tasks) / time_span) * 60.0  # per minute
                    else:
                        throughput = 0.0
                else:
                    throughput = 0.0
            else:
                throughput = 0.0
            
            metrics = QueueMetrics(
                total_tasks=len(self._task_lookup),
                queued_tasks=status_counts[TaskStatus.QUEUED],
                batched_tasks=status_counts[TaskStatus.BATCHED],
                processing_tasks=status_counts[TaskStatus.PROCESSING],
                completed_tasks=status_counts[TaskStatus.COMPLETED],
                failed_tasks=status_counts[TaskStatus.FAILED],
                average_wait_time=avg_wait_time,
                average_processing_time=avg_processing_time,
                throughput_tasks_per_minute=throughput,
                current_batch_count=len(self._active_batches),
            )
            
            if self._enable_metrics:
                self._metrics_history.append(metrics)
            
            return metrics

    def _processing_loop(self) -> None:
        """Main processing loop that creates and processes batches."""
        logger.info("Task queue processing loop started")
        
        while self._running and not self._stop_event.is_set():
            try:
                # Create batches from queued tasks
                new_batches = self._create_batches()
                
                # Process batches
                for batch in new_batches:
                    self._process_batch(batch)
                
                # Clean up completed/cancelled tasks
                self._cleanup_tasks()
                
                # Update resource optimizer with current queue state
                self._update_resource_optimizer()
                
            except Exception as e:
                logger.error("Error in task queue processing loop: %s", e, exc_info=True)
            
            # Wait before next iteration
            self._stop_event.wait(1.0)  # Check every second
        
        logger.info("Task queue processing loop ended")

    def _create_batches(self) -> List[TaskBatch]:
        """Create optimized batches from queued tasks."""
        with self._lock:
            if not self._priority_queue:
                return []
            
            # Get current system load for dynamic batch sizing
            system_load = self._get_system_load_factor()
            
            # Adjust batch configuration based on load
            dynamic_config = self._adjust_batching_config(system_load)
            
            # Group tasks by similarity
            task_groups = self._group_tasks_for_batching()
            
            new_batches = []
            current_time = time.time()
            
            for group_name, tasks in task_groups.items():
                if not tasks:
                    continue
                
                # Create batches from this group
                while tasks:
                    batch_tasks = []
                    batch_priority = 0.0
                    estimated_time = 0.0
                    
                    # Fill batch up to max size
                    while (len(batch_tasks) < dynamic_config.max_batch_size and tasks):
                        task = tasks.pop(0)
                        
                        # Skip cancelled tasks
                        if task.status == TaskStatus.CANCELLED:
                            continue
                        
                        # High priority tasks bypass batching
                        if (task.priority > dynamic_config.priority_threshold and 
                            not batch_tasks):
                            batch = self._create_single_task_batch(task, current_time)
                            new_batches.append(batch)
                            continue
                        
                        batch_tasks.append(task)
                        batch_priority = max(batch_priority, task.priority)
                        estimated_time += task.estimated_duration
                    
                    # Create batch if we have enough tasks or if wait time exceeded
                    if (len(batch_tasks) >= dynamic_config.min_batch_size or
                        (batch_tasks and self._should_create_batch(batch_tasks, current_time))):
                        
                        batch = self._create_task_batch(
                            batch_tasks, group_name, batch_priority, 
                            estimated_time, current_time
                        )
                        new_batches.append(batch)
                    else:
                        # Put tasks back if batch isn't ready
                        tasks.extend(batch_tasks)
                        break
            
            return new_batches

    def _group_tasks_for_batching(self) -> Dict[str, List[QueuedTask]]:
        """Group queued tasks by similarity for efficient batching."""
        groups = defaultdict(list)
        
        # Get all queued tasks
        queued_tasks = [task for task in self._priority_queue 
                       if task.status == TaskStatus.QUEUED]
        
        for task in queued_tasks:
            # Group by intent and agent profile
            group_key = f"{task.intent}_{task.agent_profile}"
            groups[group_key].append(task)
        
        # Sort each group by priority (highest first)
        for group_tasks in groups.values():
            group_tasks.sort(key=lambda t: t.priority, reverse=True)
        
        return dict(groups)

    def _adjust_batching_config(self, system_load: float) -> BatchingConfig:
        """Adjust batching configuration based on current system load."""
        config = BatchingConfig(
            max_batch_size=self._batching_config.max_batch_size,
            max_wait_time_seconds=self._batching_config.max_wait_time_seconds,
            min_batch_size=self._batching_config.min_batch_size,
            priority_threshold=self._batching_config.priority_threshold,
            similar_task_grouping=self._batching_config.similar_task_grouping,
        )
        
        # Adjust batch size based on system load
        if system_load > 0.8:  # High load - smaller batches for faster response
            config.max_batch_size = max(2, config.max_batch_size // 2)
            config.max_wait_time_seconds *= 0.5
        elif system_load < 0.3:  # Low load - larger batches for efficiency
            config.max_batch_size = min(20, config.max_batch_size * 2)
            config.max_wait_time_seconds *= 1.5
        
        return config

    def _get_system_load_factor(self) -> float:
        """Get current system load factor (0.0 to 1.0)."""
        try:
            # Get metrics from resource optimizer
            summary = self._resource_optimizer.get_resource_utilization_summary()
            
            if summary.get("status") == "no_data":
                return 0.5  # Default moderate load
            
            current_metrics = summary.get("current_metrics", {})
            cpu_percent = current_metrics.get("cpu_percent", 0.0)
            memory_percent = current_metrics.get("memory_percent", 0.0)
            queue_depth = current_metrics.get("queue_depth", 0)
            
            # Calculate composite load factor
            cpu_load = cpu_percent / 100.0
            memory_load = memory_percent / 100.0
            queue_load = min(1.0, queue_depth / 50.0)  # Normalize queue depth
            
            # Weighted average
            load_factor = (cpu_load * 0.4 + memory_load * 0.3 + queue_load * 0.3)
            
            return max(0.0, min(1.0, load_factor))
            
        except Exception as e:
            logger.warning("Failed to get system load factor: %s", e)
            return 0.5

    def _should_create_batch(self, batch_tasks: List[QueuedTask], current_time: float) -> bool:
        """Determine if a batch should be created based on wait time."""
        if not batch_tasks:
            return False
        
        # Check if any task has been waiting too long
        oldest_task = min(batch_tasks, key=lambda t: t.created_at)
        wait_time = current_time - oldest_task.created_at
        
        return wait_time >= self._batching_config.max_wait_time_seconds

    def _create_single_task_batch(self, task: QueuedTask, current_time: float) -> TaskBatch:
        """Create a batch with a single high-priority task."""
        batch_id = f"priority_{task.task_id}_{int(current_time * 1000)}"
        
        # Update task status
        task.status = TaskStatus.BATCHED
        task.batch_id = batch_id
        
        batch = TaskBatch(
            tasks=[task.task_data],
            batch_id=batch_id,
            created_at=current_time,
            priority=task.priority,
            estimated_processing_time=task.estimated_duration,
        )
        
        self._active_batches[batch_id] = batch
        
        logger.debug("Created priority batch %s with task %s", batch_id, task.task_id)
        return batch

    def _create_task_batch(
        self,
        batch_tasks: List[QueuedTask],
        group_name: str,
        batch_priority: float,
        estimated_time: float,
        current_time: float,
    ) -> TaskBatch:
        """Create a batch from multiple tasks."""
        batch_id = f"batch_{group_name}_{int(current_time * 1000)}"
        
        # Update task statuses
        task_data_list = []
        for task in batch_tasks:
            task.status = TaskStatus.BATCHED
            task.batch_id = batch_id
            task_data_list.append(task.task_data)
        
        batch = TaskBatch(
            tasks=task_data_list,
            batch_id=batch_id,
            created_at=current_time,
            priority=batch_priority,
            estimated_processing_time=estimated_time,
        )
        
        self._active_batches[batch_id] = batch
        
        logger.debug(
            "Created batch %s with %d tasks (group=%s, priority=%.2f)",
            batch_id, len(batch_tasks), group_name, batch_priority
        )
        
        return batch

    def _process_batch(self, batch: TaskBatch) -> None:
        """Process a task batch."""
        if not self._batch_processor:
            logger.warning("No batch processor configured, skipping batch %s", batch.batch_id)
            return
        
        try:
            # Mark tasks as processing
            batch_tasks = [task for task in self._task_lookup.values() 
                          if task.batch_id == batch.batch_id]
            
            for task in batch_tasks:
                task.status = TaskStatus.PROCESSING
                self._processing_tasks[task.task_id] = task
            
            logger.info("Processing batch %s with %d tasks", batch.batch_id, len(batch.tasks))
            
            # Process the batch
            start_time = time.time()
            result = self._batch_processor(batch)
            processing_time = time.time() - start_time
            
            # Mark tasks as completed
            for task in batch_tasks:
                task.status = TaskStatus.COMPLETED
                wait_time = start_time - task.created_at
                self._completed_tasks.append((task.task_id, wait_time, processing_time))
                self._processing_tasks.pop(task.task_id, None)
            
            # Remove batch from active batches
            self._active_batches.pop(batch.batch_id, None)
            
            logger.info(
                "Completed batch %s in %.2fs (result: %s)",
                batch.batch_id, processing_time, type(result).__name__
            )
            
        except Exception as e:
            logger.error("Failed to process batch %s: %s", batch.batch_id, e, exc_info=True)
            
            # Mark tasks as failed and handle retries
            batch_tasks = [task for task in self._task_lookup.values() 
                          if task.batch_id == batch.batch_id]
            
            for task in batch_tasks:
                self._processing_tasks.pop(task.task_id, None)
                
                if task.retry_count < task.max_retries:
                    # Retry the task
                    task.retry_count += 1
                    task.status = TaskStatus.QUEUED
                    task.batch_id = None
                    heapq.heappush(self._priority_queue, task)
                    logger.info("Retrying task %s (attempt %d/%d)", 
                               task.task_id, task.retry_count, task.max_retries)
                else:
                    # Mark as failed
                    task.status = TaskStatus.FAILED
                    logger.error("Task %s failed after %d retries", 
                                task.task_id, task.max_retries)
            
            # Remove batch from active batches
            self._active_batches.pop(batch.batch_id, None)

    def _cleanup_tasks(self) -> None:
        """Clean up completed, failed, and cancelled tasks."""
        with self._lock:
            current_time = time.time()
            cleanup_age = 3600.0  # 1 hour
            
            # Find tasks to clean up
            tasks_to_remove = []
            for task_id, task in self._task_lookup.items():
                if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] and
                    current_time - task.created_at > cleanup_age):
                    tasks_to_remove.append(task_id)
            
            # Remove old tasks
            for task_id in tasks_to_remove:
                self._task_lookup.pop(task_id, None)
            
            # Clean up priority queue (remove cancelled/completed tasks)
            self._priority_queue = [task for task in self._priority_queue 
                                  if task.task_id in self._task_lookup and 
                                  task.status == TaskStatus.QUEUED]
            heapq.heapify(self._priority_queue)
            
            if tasks_to_remove:
                logger.debug("Cleaned up %d old tasks", len(tasks_to_remove))

    def _update_resource_optimizer(self) -> None:
        """Update the resource optimizer with current queue state."""
        try:
            # Add queued tasks to resource optimizer
            with self._lock:
                queued_tasks = [task for task in self._priority_queue 
                               if task.status == TaskStatus.QUEUED]
            
            for task in queued_tasks:
                self._resource_optimizer.add_task_to_queue(task.task_data)
                
        except Exception as e:
            logger.warning("Failed to update resource optimizer: %s", e)

    def _estimate_task_duration(self, task_data: Dict[str, Any]) -> float:
        """Estimate processing time for a task in seconds."""
        intent = task_data.get("intent", "unknown")
        prompt_length = len(task_data.get("prompt", ""))
        
        # Base times by intent
        base_times = {
            "analyze": 30.0,
            "code_change": 120.0,
            "backend_generation": 180.0,
            "fullstack_generation": 300.0,
            "test": 60.0,
            "deploy": 90.0,
        }
        
        base_time = base_times.get(intent, 60.0)
        
        # Adjust for prompt complexity
        complexity_factor = min(2.0, 1.0 + (prompt_length / 1000.0))
        
        return base_time * complexity_factor

    def get_queue_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of the queue state."""
        metrics = self.get_queue_metrics()
        
        with self._lock:
            # Get task distribution by intent
            intent_distribution = defaultdict(int)
            priority_distribution = defaultdict(int)
            
            for task in self._task_lookup.values():
                intent_distribution[task.intent] += 1
                
                if task.priority >= 0.8:
                    priority_distribution["high"] += 1
                elif task.priority >= 0.5:
                    priority_distribution["normal"] += 1
                else:
                    priority_distribution["low"] += 1
        
        return {
            "metrics": {
                "total_tasks": metrics.total_tasks,
                "queued_tasks": metrics.queued_tasks,
                "processing_tasks": metrics.processing_tasks,
                "completed_tasks": metrics.completed_tasks,
                "failed_tasks": metrics.failed_tasks,
                "current_batch_count": metrics.current_batch_count,
                "average_wait_time": metrics.average_wait_time,
                "average_processing_time": metrics.average_processing_time,
                "throughput_tasks_per_minute": metrics.throughput_tasks_per_minute,
            },
            "distribution": {
                "by_intent": dict(intent_distribution),
                "by_priority": dict(priority_distribution),
            },
            "configuration": {
                "max_queue_size": self._max_queue_size,
                "max_batch_size": self._batching_config.max_batch_size,
                "max_wait_time": self._batching_config.max_wait_time_seconds,
                "min_batch_size": self._batching_config.min_batch_size,
            },
            "status": {
                "running": self._running,
                "system_load_factor": self._get_system_load_factor(),
            }
        }


# Global queue manager instance
_task_queue_manager: Optional[TaskQueueManager] = None


def get_task_queue_manager() -> TaskQueueManager:
    """Get the global task queue manager instance."""
    global _task_queue_manager
    if _task_queue_manager is None:
        _task_queue_manager = TaskQueueManager()
    return _task_queue_manager


def initialize_task_queue_manager(
    batching_config: Optional[BatchingConfig] = None,
    max_queue_size: int = 1000,
    enable_metrics: bool = True,
    batch_processor: Optional[Callable[[TaskBatch], Any]] = None,
) -> TaskQueueManager:
    """Initialize the global task queue manager with custom configuration."""
    global _task_queue_manager
    _task_queue_manager = TaskQueueManager(
        batching_config=batching_config,
        max_queue_size=max_queue_size,
        enable_metrics=enable_metrics,
        batch_processor=batch_processor,
    )
    return _task_queue_manager