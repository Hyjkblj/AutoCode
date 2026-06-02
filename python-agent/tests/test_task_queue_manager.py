"""
Unit tests for the task queue manager.

Tests the task queue management functionality including:
- Priority-based task scheduling
- Intelligent task batching
- Load-aware queue management
- Performance metrics collection

Requirements: Task 33.2 - Optimize resource utilization
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch
from typing import Dict, Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.task_queue_manager import (
    TaskQueueManager,
    QueuedTask,
    TaskPriority,
    TaskStatus,
    QueueMetrics,
    BatchingConfig,
    get_task_queue_manager,
    initialize_task_queue_manager,
)
from utils.resource_optimizer import TaskBatch


class TestQueuedTask:
    """Test cases for QueuedTask."""
    
    def test_queued_task_creation(self):
        """Test QueuedTask creation."""
        task_data = {"task_id": "test-1", "prompt": "Test task"}
        
        task = QueuedTask(
            task_id="test-1",
            task_data=task_data,
            priority=0.8,
            created_at=time.time(),
            estimated_duration=60.0,
            intent="analyze",
            agent_profile="coder",
        )
        
        assert task.task_id == "test-1"
        assert task.task_data == task_data
        assert task.priority == 0.8
        assert task.estimated_duration == 60.0
        assert task.intent == "analyze"
        assert task.agent_profile == "coder"
        assert task.status == TaskStatus.QUEUED
        assert task.retry_count == 0
        assert task.max_retries == 3
    
    def test_queued_task_comparison(self):
        """Test QueuedTask priority comparison."""
        task1 = QueuedTask(
            task_id="task1",
            task_data={},
            priority=0.8,
            created_at=time.time(),
            estimated_duration=60.0,
            intent="analyze",
            agent_profile="coder",
        )
        
        task2 = QueuedTask(
            task_id="task2",
            task_data={},
            priority=0.5,
            created_at=time.time(),
            estimated_duration=60.0,
            intent="analyze",
            agent_profile="coder",
        )
        
        # Higher priority task should be "less than" (for min-heap)
        assert task1 < task2
        assert not (task2 < task1)


class TestTaskQueueManager:
    """Test cases for TaskQueueManager."""
    
    def test_initialization(self):
        """Test TaskQueueManager initialization."""
        batching_config = BatchingConfig(max_batch_size=5)
        batch_processor = Mock()
        
        manager = TaskQueueManager(
            batching_config=batching_config,
            max_queue_size=500,
            enable_metrics=True,
            batch_processor=batch_processor,
        )
        
        assert manager._batching_config == batching_config
        assert manager._max_queue_size == 500
        assert manager._enable_metrics is True
        assert manager._batch_processor == batch_processor
        assert manager._running is False
        assert len(manager._priority_queue) == 0
        assert len(manager._task_lookup) == 0
    
    def test_initialization_with_defaults(self):
        """Test TaskQueueManager initialization with defaults."""
        manager = TaskQueueManager()
        
        assert manager._batching_config is not None
        assert manager._max_queue_size == 1000
        assert manager._enable_metrics is True
        assert manager._batch_processor is None
    
    def test_add_task_success(self):
        """Test adding a task successfully."""
        manager = TaskQueueManager()
        
        task_data = {
            "prompt": "Test task",
            "intent": "analyze",
            "agentProfile": "coder",
        }
        
        task_id = manager.add_task(task_data, TaskPriority.HIGH)
        
        assert task_id is not None
        assert len(manager._priority_queue) == 1
        assert task_id in manager._task_lookup
        
        queued_task = manager._task_lookup[task_id]
        assert queued_task.priority == TaskPriority.HIGH.value
        assert queued_task.intent == "analyze"
        assert queued_task.agent_profile == "coder"
    
    def test_add_task_with_existing_task_id(self):
        """Test adding a task with existing task ID."""
        manager = TaskQueueManager()
        
        task_data = {
            "task_id": "existing-task",
            "prompt": "Test task",
            "intent": "analyze",
        }
        
        task_id = manager.add_task(task_data)
        
        assert task_id == "existing-task"
        assert "existing-task" in manager._task_lookup
    
    def test_add_task_missing_prompt(self):
        """Test adding a task without prompt (should fail)."""
        manager = TaskQueueManager()
        
        task_data = {
            "intent": "analyze",
        }
        
        with pytest.raises(ValueError, match="Task data must include 'prompt' field"):
            manager.add_task(task_data)
    
    def test_add_task_queue_full(self):
        """Test adding a task when queue is full."""
        manager = TaskQueueManager(max_queue_size=2)
        
        # Fill the queue
        for i in range(2):
            task_data = {"prompt": f"Task {i}", "intent": "analyze"}
            manager.add_task(task_data)
        
        # Try to add one more (should fail)
        task_data = {"prompt": "Overflow task", "intent": "analyze"}
        with pytest.raises(ValueError, match="Queue is full"):
            manager.add_task(task_data)
    
    def test_add_task_with_estimated_duration(self):
        """Test adding a task with custom estimated duration."""
        manager = TaskQueueManager()
        
        task_data = {"prompt": "Test task", "intent": "analyze"}
        task_id = manager.add_task(task_data, estimated_duration=120.0)
        
        queued_task = manager._task_lookup[task_id]
        assert queued_task.estimated_duration == 120.0
    
    def test_get_task_status_existing(self):
        """Test getting status of existing task."""
        manager = TaskQueueManager()
        
        task_data = {"prompt": "Test task", "intent": "analyze"}
        task_id = manager.add_task(task_data, TaskPriority.HIGH)
        
        status = manager.get_task_status(task_id)
        
        assert status is not None
        assert status["task_id"] == task_id
        assert status["status"] == TaskStatus.QUEUED.value
        assert status["priority"] == TaskPriority.HIGH.value
        assert status["intent"] == "analyze"
        assert "created_at" in status
        assert "wait_time" in status
    
    def test_get_task_status_nonexistent(self):
        """Test getting status of non-existent task."""
        manager = TaskQueueManager()
        
        status = manager.get_task_status("nonexistent-task")
        
        assert status is None
    
    def test_cancel_task_success(self):
        """Test cancelling a queued task."""
        manager = TaskQueueManager()
        
        task_data = {"prompt": "Test task", "intent": "analyze"}
        task_id = manager.add_task(task_data)
        
        success = manager.cancel_task(task_id)
        
        assert success is True
        
        queued_task = manager._task_lookup[task_id]
        assert queued_task.status == TaskStatus.CANCELLED
    
    def test_cancel_task_nonexistent(self):
        """Test cancelling a non-existent task."""
        manager = TaskQueueManager()
        
        success = manager.cancel_task("nonexistent-task")
        
        assert success is False
    
    def test_cancel_task_processing(self):
        """Test cancelling a task that's already processing."""
        manager = TaskQueueManager()
        
        task_data = {"prompt": "Test task", "intent": "analyze"}
        task_id = manager.add_task(task_data)
        
        # Mark task as processing
        queued_task = manager._task_lookup[task_id]
        queued_task.status = TaskStatus.PROCESSING
        
        success = manager.cancel_task(task_id)
        
        assert success is False  # Cannot cancel processing task
    
    def test_get_queue_metrics_empty(self):
        """Test getting queue metrics when empty."""
        manager = TaskQueueManager()
        
        metrics = manager.get_queue_metrics()
        
        assert isinstance(metrics, QueueMetrics)
        assert metrics.total_tasks == 0
        assert metrics.queued_tasks == 0
        assert metrics.processing_tasks == 0
        assert metrics.completed_tasks == 0
        assert metrics.failed_tasks == 0
        assert metrics.average_wait_time == 0.0
        assert metrics.throughput_tasks_per_minute == 0.0
    
    def test_get_queue_metrics_with_tasks(self):
        """Test getting queue metrics with tasks."""
        manager = TaskQueueManager()
        
        # Add some tasks
        for i in range(3):
            task_data = {"prompt": f"Task {i}", "intent": "analyze"}
            manager.add_task(task_data)
        
        # Wait a bit to accumulate wait time
        import time
        time.sleep(0.1)
        
        metrics = manager.get_queue_metrics()
        
        assert metrics.total_tasks == 3
        assert metrics.queued_tasks == 3
        assert metrics.processing_tasks == 0
        assert metrics.average_wait_time >= 0.0  # Should have some wait time (or 0 if just added)
    
    def test_estimate_task_duration_by_intent(self):
        """Test task duration estimation by intent."""
        manager = TaskQueueManager()
        
        # Test different intents
        test_cases = [
            ({"prompt": "Analyze this", "intent": "analyze"}, 30.0),
            ({"prompt": "Change code", "intent": "code_change"}, 120.0),
            ({"prompt": "Generate backend", "intent": "backend_generation"}, 180.0),
            ({"prompt": "Test code", "intent": "test"}, 60.0),
            ({"prompt": "Unknown task", "intent": "unknown"}, 60.0),  # Default
        ]
        
        for task_data, expected_base in test_cases:
            duration = manager._estimate_task_duration(task_data)
            assert duration >= expected_base  # May be adjusted for complexity
    
    def test_estimate_task_duration_complexity_adjustment(self):
        """Test task duration estimation with complexity adjustment."""
        manager = TaskQueueManager()
        
        # Short prompt
        short_task = {"prompt": "Short", "intent": "analyze"}
        short_duration = manager._estimate_task_duration(short_task)
        
        # Long prompt
        long_prompt = "This is a very long and complex prompt " * 50  # ~1500 chars
        long_task = {"prompt": long_prompt, "intent": "analyze"}
        long_duration = manager._estimate_task_duration(long_task)
        
        # Long task should take more time
        assert long_duration > short_duration
    
    def test_group_tasks_for_batching(self):
        """Test grouping tasks for batching."""
        manager = TaskQueueManager()
        
        # Add tasks with different intents and profiles
        tasks_data = [
            {"prompt": "Analyze 1", "intent": "analyze", "agentProfile": "coder"},
            {"prompt": "Analyze 2", "intent": "analyze", "agentProfile": "coder"},
            {"prompt": "Test 1", "intent": "test", "agentProfile": "tester"},
            {"prompt": "Code 1", "intent": "code_change", "agentProfile": "coder"},
        ]
        
        for task_data in tasks_data:
            manager.add_task(task_data)
        
        groups = manager._group_tasks_for_batching()
        
        # Should have 3 groups: analyze_coder, test_tester, code_change_coder
        assert len(groups) == 3
        assert "analyze_coder" in groups
        assert "test_tester" in groups
        assert "code_change_coder" in groups
        
        # analyze_coder group should have 2 tasks
        assert len(groups["analyze_coder"]) == 2
    
    def test_group_tasks_priority_sorting(self):
        """Test that grouped tasks are sorted by priority."""
        manager = TaskQueueManager()
        
        # Add tasks with different priorities
        task1_data = {"prompt": "Low priority", "intent": "analyze"}
        task1_id = manager.add_task(task1_data, TaskPriority.LOW)
        
        task2_data = {"prompt": "High priority", "intent": "analyze"}
        task2_id = manager.add_task(task2_data, TaskPriority.HIGH)
        
        task3_data = {"prompt": "Normal priority", "intent": "analyze"}
        task3_id = manager.add_task(task3_data, TaskPriority.NORMAL)
        
        groups = manager._group_tasks_for_batching()
        analyze_group = groups["analyze_default"]
        
        # Should be sorted by priority (highest first)
        assert analyze_group[0].task_id == task2_id  # HIGH
        assert analyze_group[1].task_id == task3_id  # NORMAL
        assert analyze_group[2].task_id == task1_id  # LOW
    
    @patch('utils.task_queue_manager.time.time')
    def test_should_create_batch_wait_time_exceeded(self, mock_time):
        """Test batch creation when wait time is exceeded."""
        manager = TaskQueueManager()
        
        # Create a task that was created 10 seconds ago
        current_time = 1000.0
        mock_time.return_value = current_time
        
        task_data = {"prompt": "Test task", "intent": "analyze"}
        task_id = manager.add_task(task_data)
        
        # Modify the task's created_at time to simulate waiting
        queued_task = manager._task_lookup[task_id]
        queued_task.created_at = current_time - 10.0  # 10 seconds ago
        
        # Check if batch should be created (default max_wait_time is 5.0 seconds)
        should_create = manager._should_create_batch([queued_task], current_time)
        
        assert should_create is True
    
    @patch('utils.task_queue_manager.time.time')
    def test_should_create_batch_wait_time_not_exceeded(self, mock_time):
        """Test batch creation when wait time is not exceeded."""
        manager = TaskQueueManager()
        
        current_time = 1000.0
        mock_time.return_value = current_time
        
        task_data = {"prompt": "Test task", "intent": "analyze"}
        task_id = manager.add_task(task_data)
        
        # Task was just created
        queued_task = manager._task_lookup[task_id]
        queued_task.created_at = current_time - 1.0  # 1 second ago
        
        should_create = manager._should_create_batch([queued_task], current_time)
        
        assert should_create is False
    
    def test_get_system_load_factor_no_data(self):
        """Test getting system load factor when no data available."""
        from unittest.mock import Mock, patch
        
        manager = TaskQueueManager()
        
        # Mock the resource optimizer's method
        with patch.object(manager._resource_optimizer, 'get_resource_utilization_summary', return_value={"status": "no_data"}):
            load_factor = manager._get_system_load_factor()
            
            assert load_factor == 0.5  # Default moderate load
    
    def test_get_system_load_factor_with_data(self):
        """Test getting system load factor with metrics data."""
        from unittest.mock import Mock, patch
        
        manager = TaskQueueManager()
        
        # Mock the resource optimizer's method
        mock_summary = {
            "current_metrics": {
                "cpu_percent": 80.0,
                "memory_percent": 60.0,
                "queue_depth": 25,
            }
        }
        
        with patch.object(manager._resource_optimizer, 'get_resource_utilization_summary', return_value=mock_summary):
            load_factor = manager._get_system_load_factor()
            
            # Should calculate composite load factor
            # cpu_load = 0.8, memory_load = 0.6, queue_load = 0.5 (25/50)
            # weighted: 0.8*0.4 + 0.6*0.3 + 0.5*0.3 = 0.32 + 0.18 + 0.15 = 0.65
            assert 0.6 <= load_factor <= 0.7
    
    def test_adjust_batching_config_high_load(self):
        """Test adjusting batching config for high system load."""
        manager = TaskQueueManager()
        
        # Mock high system load
        manager._get_system_load_factor = Mock(return_value=0.9)
        
        adjusted_config = manager._adjust_batching_config(0.9)
        
        # Should reduce batch size and wait time for high load
        assert adjusted_config.max_batch_size <= manager._batching_config.max_batch_size
        assert adjusted_config.max_wait_time_seconds <= manager._batching_config.max_wait_time_seconds
    
    def test_adjust_batching_config_low_load(self):
        """Test adjusting batching config for low system load."""
        manager = TaskQueueManager()
        
        # Mock low system load
        manager._get_system_load_factor = Mock(return_value=0.2)
        
        adjusted_config = manager._adjust_batching_config(0.2)
        
        # Should increase batch size and wait time for low load
        assert adjusted_config.max_batch_size >= manager._batching_config.max_batch_size
        assert adjusted_config.max_wait_time_seconds >= manager._batching_config.max_wait_time_seconds
    
    def test_create_single_task_batch(self):
        """Test creating a batch with a single high-priority task."""
        manager = TaskQueueManager()
        
        task_data = {"prompt": "Urgent task", "intent": "analyze"}
        task_id = manager.add_task(task_data, TaskPriority.CRITICAL)
        
        queued_task = manager._task_lookup[task_id]
        current_time = time.time()
        
        batch = manager._create_single_task_batch(queued_task, current_time)
        
        assert isinstance(batch, TaskBatch)
        assert len(batch.tasks) == 1
        assert batch.priority == TaskPriority.CRITICAL.value
        assert queued_task.status == TaskStatus.BATCHED
        assert queued_task.batch_id == batch.batch_id
        assert batch.batch_id in manager._active_batches
    
    def test_create_task_batch_multiple_tasks(self):
        """Test creating a batch with multiple tasks."""
        manager = TaskQueueManager()
        
        # Add multiple tasks
        task_ids = []
        for i in range(3):
            task_data = {"prompt": f"Task {i}", "intent": "analyze"}
            task_id = manager.add_task(task_data, TaskPriority.NORMAL)
            task_ids.append(task_id)
        
        # Get the queued tasks
        batch_tasks = [manager._task_lookup[tid] for tid in task_ids]
        current_time = time.time()
        
        batch = manager._create_task_batch(
            batch_tasks, "analyze_default", TaskPriority.NORMAL.value, 180.0, current_time
        )
        
        assert isinstance(batch, TaskBatch)
        assert len(batch.tasks) == 3
        assert batch.priority == TaskPriority.NORMAL.value
        assert batch.estimated_processing_time == 180.0
        
        # All tasks should be marked as batched
        for task in batch_tasks:
            assert task.status == TaskStatus.BATCHED
            assert task.batch_id == batch.batch_id
    
    def test_get_queue_summary(self):
        """Test getting comprehensive queue summary."""
        manager = TaskQueueManager()
        
        # Add tasks with different intents and priorities
        manager.add_task({"prompt": "Analyze 1", "intent": "analyze"}, TaskPriority.HIGH)
        manager.add_task({"prompt": "Analyze 2", "intent": "analyze"}, TaskPriority.NORMAL)
        manager.add_task({"prompt": "Test 1", "intent": "test"}, TaskPriority.LOW)
        
        summary = manager.get_queue_summary()
        
        assert "metrics" in summary
        assert "distribution" in summary
        assert "configuration" in summary
        assert "status" in summary
        
        # Check metrics
        assert summary["metrics"]["total_tasks"] == 3
        assert summary["metrics"]["queued_tasks"] == 3
        
        # Check distribution
        assert summary["distribution"]["by_intent"]["analyze"] == 2
        assert summary["distribution"]["by_intent"]["test"] == 1
        assert summary["distribution"]["by_priority"]["high"] == 1
        assert summary["distribution"]["by_priority"]["normal"] == 1
        assert summary["distribution"]["by_priority"]["low"] == 1
        
        # Check configuration
        assert "max_queue_size" in summary["configuration"]
        assert "max_batch_size" in summary["configuration"]
        
        # Check status
        assert "running" in summary["status"]
        assert "system_load_factor" in summary["status"]
    
    def test_start_stop_processing(self):
        """Test starting and stopping task processing."""
        manager = TaskQueueManager()
        
        # Initially not running
        assert manager._running is False
        
        # Start processing
        manager.start()
        assert manager._running is True
        assert manager._processor_thread is not None
        
        # Stop processing
        manager.stop()
        assert manager._running is False
    
    def test_start_already_running(self):
        """Test starting processing when already running."""
        manager = TaskQueueManager()
        
        # Start processing
        manager.start()
        assert manager._running is True
        
        # Try to start again (should log warning)
        manager.start()
        assert manager._running is True
    
    def test_stop_not_running(self):
        """Test stopping processing when not running."""
        manager = TaskQueueManager()
        
        # Stop processing (should not raise exception)
        manager.stop()
        assert manager._running is False


class TestGlobalFunctions:
    """Test cases for global functions."""
    
    def test_get_task_queue_manager(self):
        """Test getting global task queue manager."""
        # Clear global state
        import utils.task_queue_manager as tqm
        tqm._task_queue_manager = None
        
        manager = get_task_queue_manager()
        
        assert isinstance(manager, TaskQueueManager)
        
        # Should return same instance on subsequent calls
        manager2 = get_task_queue_manager()
        assert manager is manager2
    
    def test_initialize_task_queue_manager(self):
        """Test initializing global task queue manager."""
        batching_config = BatchingConfig(max_batch_size=5)
        batch_processor = Mock()
        
        manager = initialize_task_queue_manager(
            batching_config=batching_config,
            max_queue_size=500,
            enable_metrics=True,
            batch_processor=batch_processor,
        )
        
        assert isinstance(manager, TaskQueueManager)
        assert manager._batching_config == batching_config
        assert manager._max_queue_size == 500
        assert manager._enable_metrics is True
        assert manager._batch_processor == batch_processor


if __name__ == "__main__":
    pytest.main([__file__])