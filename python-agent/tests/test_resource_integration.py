"""
Integration tests for the resource optimization system.

Tests the complete resource optimization functionality including:
- Integration between optimizer, monitor, and queue manager
- End-to-end resource optimization workflows
- Scaling recommendation handling
- Cost optimization integration

Requirements: Task 33.2 - Optimize resource utilization
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.resource_integration import (
    ResourceOptimizationManager,
    ResourceOptimizationConfig,
    get_resource_optimization_manager,
    initialize_resource_optimization,
    start_resource_optimization,
    stop_resource_optimization,
    add_optimized_task,
    record_llm_usage,
    get_optimization_status,
    get_scaling_recommendations,
    get_cost_recommendations,
)
from utils.resource_optimizer import (
    ResourceOptimizer,
    ResourceMetrics,
    CostMetrics,
    ScalingRecommendation,
    ScalingAction,
    ResourceType,
)
from utils.resource_monitor import ResourceMonitor
from utils.task_queue_manager import TaskQueueManager, TaskPriority


class TestResourceOptimizationConfig:
    """Test cases for ResourceOptimizationConfig."""
    
    def test_default_config(self):
        """Test default resource optimization configuration."""
        config = ResourceOptimizationConfig()
        
        assert config.monitoring_enabled is True
        assert config.monitoring_interval_seconds == 30.0
        assert config.cost_tracking_enabled is True
        assert config.batching_enabled is True
        assert config.max_batch_size == 10
        assert config.cpu_scale_up_threshold == 80.0
        assert config.cpu_scale_down_threshold == 30.0
        assert config.memory_scale_up_threshold == 85.0
        assert config.memory_scale_down_threshold == 40.0
    
    def test_custom_config(self):
        """Test custom resource optimization configuration."""
        config = ResourceOptimizationConfig(
            monitoring_enabled=False,
            monitoring_interval_seconds=60.0,
            cost_tracking_enabled=False,
            batching_enabled=False,
            max_batch_size=20,
            cpu_scale_up_threshold=75.0,
            cpu_scale_down_threshold=25.0,
        )
        
        assert config.monitoring_enabled is False
        assert config.monitoring_interval_seconds == 60.0
        assert config.cost_tracking_enabled is False
        assert config.batching_enabled is False
        assert config.max_batch_size == 20
        assert config.cpu_scale_up_threshold == 75.0
        assert config.cpu_scale_down_threshold == 25.0


class TestResourceOptimizationManager:
    """Test cases for ResourceOptimizationManager."""
    
    def test_initialization(self):
        """Test ResourceOptimizationManager initialization."""
        config = ResourceOptimizationConfig()
        manager = ResourceOptimizationManager(config)
        
        assert manager._config == config
        assert manager._optimizer is None
        assert manager._monitor is None
        assert manager._queue_manager is None
        assert manager._initialized is False
        assert manager._running is False
        assert len(manager._scaling_handlers) == 0
        assert len(manager._alert_handlers) == 0
        assert len(manager._cost_handlers) == 0
    
    def test_initialization_with_defaults(self):
        """Test ResourceOptimizationManager initialization with defaults."""
        manager = ResourceOptimizationManager()
        
        assert manager._config is not None
        assert isinstance(manager._config, ResourceOptimizationConfig)
    
    @patch('utils.resource_integration.initialize_resource_optimizer')
    @patch('utils.resource_integration.initialize_resource_monitor')
    @patch('utils.resource_integration.initialize_task_queue_manager')
    def test_initialize_all_components(self, mock_init_queue_manager, mock_init_monitor, mock_init_optimizer):
        """Test initializing all components."""
        # Mock the initialization functions
        mock_optimizer = Mock(spec=ResourceOptimizer)
        mock_monitor = Mock(spec=ResourceMonitor)
        mock_queue_manager = Mock(spec=TaskQueueManager)
        
        mock_init_optimizer.return_value = mock_optimizer
        mock_init_monitor.return_value = mock_monitor
        mock_init_queue_manager.return_value = mock_queue_manager
        
        config = ResourceOptimizationConfig(
            monitoring_enabled=True,
            batching_enabled=True,
        )
        manager = ResourceOptimizationManager(config)
        
        manager.initialize()
        
        assert manager._initialized is True
        assert manager._optimizer == mock_optimizer
        assert manager._monitor == mock_monitor
        assert manager._queue_manager == mock_queue_manager
        
        # Verify initialization calls
        mock_init_optimizer.assert_called_once()
        mock_init_monitor.assert_called_once()
        mock_init_queue_manager.assert_called_once()
    
    @patch('utils.resource_integration.initialize_resource_optimizer')
    def test_initialize_optimizer_only(self, mock_init_optimizer):
        """Test initializing only the optimizer when other components are disabled."""
        mock_optimizer = Mock(spec=ResourceOptimizer)
        mock_init_optimizer.return_value = mock_optimizer
        
        config = ResourceOptimizationConfig(
            monitoring_enabled=False,
            batching_enabled=False,
        )
        manager = ResourceOptimizationManager(config)
        
        manager.initialize()
        
        assert manager._initialized is True
        assert manager._optimizer == mock_optimizer
        assert manager._monitor is None
        assert manager._queue_manager is None
    
    def test_initialize_already_initialized(self):
        """Test initializing when already initialized."""
        manager = ResourceOptimizationManager()
        manager._initialized = True
        
        # Should not raise exception and should log warning
        manager.initialize()
        
        assert manager._initialized is True
    
    def test_start_not_initialized(self):
        """Test starting when not initialized (should initialize first)."""
        manager = ResourceOptimizationManager()
        
        # Mock the initialize method
        manager.initialize = Mock()
        
        manager.start()
        
        # Should call initialize first
        manager.initialize.assert_called_once()
    
    def test_start_with_components(self):
        """Test starting with all components."""
        manager = ResourceOptimizationManager()
        manager._initialized = True
        
        # Mock components
        mock_monitor = Mock(spec=ResourceMonitor)
        mock_queue_manager = Mock(spec=TaskQueueManager)
        
        manager._monitor = mock_monitor
        manager._queue_manager = mock_queue_manager
        
        manager.start()
        
        assert manager._running is True
        mock_monitor.start.assert_called_once()
        mock_queue_manager.start.assert_called_once()
    
    def test_start_already_running(self):
        """Test starting when already running."""
        manager = ResourceOptimizationManager()
        manager._initialized = True
        manager._running = True
        
        # Should not raise exception and should log warning
        manager.start()
        
        assert manager._running is True
    
    def test_stop_with_components(self):
        """Test stopping with all components."""
        manager = ResourceOptimizationManager()
        manager._running = True
        
        # Mock components
        mock_monitor = Mock(spec=ResourceMonitor)
        mock_queue_manager = Mock(spec=TaskQueueManager)
        
        manager._monitor = mock_monitor
        manager._queue_manager = mock_queue_manager
        
        manager.stop()
        
        assert manager._running is False
        mock_monitor.stop.assert_called_once()
        mock_queue_manager.stop.assert_called_once()
    
    def test_stop_not_running(self):
        """Test stopping when not running."""
        manager = ResourceOptimizationManager()
        manager._running = False
        
        # Should not raise exception
        manager.stop()
        
        assert manager._running is False
    
    def test_add_task_success(self):
        """Test adding a task successfully."""
        manager = ResourceOptimizationManager()
        
        # Mock queue manager
        mock_queue_manager = Mock(spec=TaskQueueManager)
        mock_queue_manager.add_task.return_value = "task-123"
        manager._queue_manager = mock_queue_manager
        
        task_data = {"prompt": "Test task", "intent": "analyze"}
        task_id = manager.add_task(task_data, TaskPriority.HIGH)
        
        assert task_id == "task-123"
        mock_queue_manager.add_task.assert_called_once_with(task_data, TaskPriority.HIGH)
    
    def test_add_task_no_queue_manager(self):
        """Test adding a task when queue manager is not initialized."""
        manager = ResourceOptimizationManager()
        manager._queue_manager = None
        
        task_data = {"prompt": "Test task", "intent": "analyze"}
        
        with pytest.raises(RuntimeError, match="Task queue manager not initialized"):
            manager.add_task(task_data)
    
    def test_get_scaling_recommendations(self):
        """Test getting scaling recommendations."""
        manager = ResourceOptimizationManager()
        
        # Mock optimizer
        mock_optimizer = Mock(spec=ResourceOptimizer)
        expected_recommendations = [
            ScalingRecommendation(
                resource_type=ResourceType.CPU,
                action=ScalingAction.SCALE_UP,
                current_value=85.0,
                recommended_value=100.0,
                reason="High CPU usage",
                confidence=0.8,
                estimated_cost_impact=0.5,
            )
        ]
        mock_optimizer.get_scaling_recommendations.return_value = expected_recommendations
        manager._optimizer = mock_optimizer
        
        # Add a scaling handler
        scaling_handler = Mock()
        manager.add_scaling_handler(scaling_handler)
        
        recommendations = manager.get_scaling_recommendations()
        
        assert recommendations == expected_recommendations
        scaling_handler.assert_called_once_with(expected_recommendations)
    
    def test_get_scaling_recommendations_no_optimizer(self):
        """Test getting scaling recommendations when optimizer is not initialized."""
        manager = ResourceOptimizationManager()
        manager._optimizer = None
        
        recommendations = manager.get_scaling_recommendations()
        
        assert recommendations == []
    
    def test_get_cost_optimization_recommendations(self):
        """Test getting cost optimization recommendations."""
        manager = ResourceOptimizationManager()
        
        # Mock optimizer
        mock_optimizer = Mock(spec=ResourceOptimizer)
        expected_recommendations = [
            "LLM costs are high, consider caching",
            "Cost per task is trending upward",
        ]
        mock_optimizer.get_cost_optimization_recommendations.return_value = expected_recommendations
        manager._optimizer = mock_optimizer
        
        # Add a cost handler
        cost_handler = Mock()
        manager.add_cost_handler(cost_handler)
        
        recommendations = manager.get_cost_optimization_recommendations()
        
        assert recommendations == expected_recommendations
        cost_handler.assert_called_once_with(expected_recommendations)
    
    def test_record_llm_usage(self):
        """Test recording LLM usage."""
        manager = ResourceOptimizationManager()
        
        # Mock monitor
        mock_monitor = Mock(spec=ResourceMonitor)
        manager._monitor = mock_monitor
        
        manager.record_llm_usage(1500, 0.003)
        
        mock_monitor.record_llm_usage.assert_called_once_with(1500)
    
    def test_record_llm_usage_no_monitor(self):
        """Test recording LLM usage when monitor is not initialized."""
        manager = ResourceOptimizationManager()
        manager._monitor = None
        
        # Should not raise exception
        manager.record_llm_usage(1500)
    
    def test_record_llm_usage_calculate_cost(self):
        """Test recording LLM usage with cost calculation."""
        config = ResourceOptimizationConfig(llm_token_cost_per_1k=0.005)
        manager = ResourceOptimizationManager(config)
        
        # Mock monitor
        mock_monitor = Mock(spec=ResourceMonitor)
        manager._monitor = mock_monitor
        
        manager.record_llm_usage(2000)  # No cost provided, should calculate
        
        mock_monitor.record_llm_usage.assert_called_once_with(2000)
        # Cost should be calculated as 2000/1000 * 0.005 = 0.01
    
    def test_get_system_status(self):
        """Test getting comprehensive system status."""
        manager = ResourceOptimizationManager()
        manager._initialized = True
        manager._running = True
        
        # Mock components
        mock_optimizer = Mock(spec=ResourceOptimizer)
        mock_optimizer.get_resource_utilization_summary.return_value = {"cpu": 50.0}
        mock_optimizer.get_scaling_recommendations.return_value = []
        mock_optimizer.get_cost_optimization_recommendations.return_value = []
        
        mock_queue_manager = Mock(spec=TaskQueueManager)
        mock_queue_manager.get_queue_summary.return_value = {"total_tasks": 5}
        
        mock_monitor = Mock(spec=ResourceMonitor)
        mock_monitor.get_monitoring_status.return_value = {"running": True}
        
        manager._optimizer = mock_optimizer
        manager._queue_manager = mock_queue_manager
        manager._monitor = mock_monitor
        
        status = manager.get_system_status()
        
        assert status["initialized"] is True
        assert status["running"] is True
        assert "timestamp" in status
        assert status["resource_utilization"] == {"cpu": 50.0}
        assert status["queue_status"] == {"total_tasks": 5}
        assert status["monitoring_status"] == {"running": True}
        assert "scaling_recommendations" in status
        assert "cost_recommendations" in status
    
    def test_add_handlers(self):
        """Test adding various handlers."""
        manager = ResourceOptimizationManager()
        
        scaling_handler = Mock()
        alert_handler = Mock()
        cost_handler = Mock()
        
        manager.add_scaling_handler(scaling_handler)
        manager.add_alert_handler(alert_handler)
        manager.add_cost_handler(cost_handler)
        
        assert scaling_handler in manager._scaling_handlers
        assert alert_handler in manager._alert_handlers
        assert cost_handler in manager._cost_handlers
    
    def test_handle_alert(self):
        """Test handling resource alerts."""
        manager = ResourceOptimizationManager()
        
        # Add alert handlers
        alert_handler1 = Mock()
        alert_handler2 = Mock()
        manager.add_alert_handler(alert_handler1)
        manager.add_alert_handler(alert_handler2)
        
        alert_data = {"message": "CPU usage high", "value": 95.0}
        
        manager._handle_alert("cpu_high", alert_data)
        
        # Both handlers should be called
        alert_handler1.assert_called_once_with("cpu_high", alert_data)
        alert_handler2.assert_called_once_with("cpu_high", alert_data)
    
    def test_handle_alert_handler_exception(self):
        """Test handling alert when handler raises exception."""
        manager = ResourceOptimizationManager()
        
        # Add handler that raises exception
        failing_handler = Mock(side_effect=Exception("Handler error"))
        working_handler = Mock()
        
        manager.add_alert_handler(failing_handler)
        manager.add_alert_handler(working_handler)
        
        alert_data = {"message": "Test alert"}
        
        # Should not raise exception, should continue to other handlers
        manager._handle_alert("test_alert", alert_data)
        
        failing_handler.assert_called_once()
        working_handler.assert_called_once()
    
    def test_process_task_batch(self):
        """Test processing a task batch."""
        manager = ResourceOptimizationManager()
        
        # Mock batch
        mock_batch = Mock()
        mock_batch.batch_id = "test-batch-123"
        mock_batch.tasks = [{"task_id": "task1"}, {"task_id": "task2"}]
        
        result = manager._process_task_batch(mock_batch)
        
        assert result["batch_id"] == "test-batch-123"
        assert result["status"] == "completed"
        assert result["task_count"] == 2


class TestGlobalFunctions:
    """Test cases for global functions."""
    
    def test_get_resource_optimization_manager(self):
        """Test getting global resource optimization manager."""
        # Clear global state
        import utils.resource_integration as ri
        ri._resource_optimization_manager = None
        
        manager = get_resource_optimization_manager()
        
        assert isinstance(manager, ResourceOptimizationManager)
        
        # Should return same instance on subsequent calls
        manager2 = get_resource_optimization_manager()
        assert manager is manager2
    
    def test_initialize_resource_optimization(self):
        """Test initializing global resource optimization."""
        config = ResourceOptimizationConfig(monitoring_enabled=False)
        
        with patch.object(ResourceOptimizationManager, 'initialize') as mock_init:
            manager = initialize_resource_optimization(config)
            
            assert isinstance(manager, ResourceOptimizationManager)
            assert manager._config == config
            mock_init.assert_called_once()
    
    def test_start_resource_optimization(self):
        """Test starting global resource optimization."""
        with patch.object(ResourceOptimizationManager, 'start') as mock_start:
            start_resource_optimization()
            mock_start.assert_called_once()
    
    def test_stop_resource_optimization(self):
        """Test stopping global resource optimization."""
        # Set up global manager
        import utils.resource_integration as ri
        mock_manager = Mock(spec=ResourceOptimizationManager)
        ri._resource_optimization_manager = mock_manager
        
        stop_resource_optimization()
        
        mock_manager.stop.assert_called_once()
    
    def test_stop_resource_optimization_no_manager(self):
        """Test stopping when no global manager exists."""
        # Clear global state
        import utils.resource_integration as ri
        ri._resource_optimization_manager = None
        
        # Should not raise exception
        stop_resource_optimization()
    
    def test_add_optimized_task(self):
        """Test adding optimized task via global function."""
        with patch.object(ResourceOptimizationManager, 'add_task', return_value="task-456") as mock_add:
            task_data = {"prompt": "Test task", "intent": "analyze"}
            task_id = add_optimized_task(task_data, TaskPriority.HIGH)
            
            assert task_id == "task-456"
            mock_add.assert_called_once_with(task_data, TaskPriority.HIGH)
    
    def test_record_llm_usage_global(self):
        """Test recording LLM usage via global function."""
        with patch.object(ResourceOptimizationManager, 'record_llm_usage') as mock_record:
            record_llm_usage(1000, 0.002)
            mock_record.assert_called_once_with(1000, 0.002)
    
    def test_get_optimization_status(self):
        """Test getting optimization status via global function."""
        expected_status = {"initialized": True, "running": True}
        
        with patch.object(ResourceOptimizationManager, 'get_system_status', return_value=expected_status) as mock_status:
            status = get_optimization_status()
            
            assert status == expected_status
            mock_status.assert_called_once()
    
    def test_get_scaling_recommendations_global(self):
        """Test getting scaling recommendations via global function."""
        expected_recommendations = [Mock(spec=ScalingRecommendation)]
        
        with patch.object(ResourceOptimizationManager, 'get_scaling_recommendations', return_value=expected_recommendations) as mock_get:
            recommendations = get_scaling_recommendations()
            
            assert recommendations == expected_recommendations
            mock_get.assert_called_once()
    
    def test_get_cost_recommendations_global(self):
        """Test getting cost recommendations via global function."""
        expected_recommendations = ["Optimize LLM usage", "Reduce compute costs"]
        
        with patch.object(ResourceOptimizationManager, 'get_cost_optimization_recommendations', return_value=expected_recommendations) as mock_get:
            recommendations = get_cost_recommendations()
            
            assert recommendations == expected_recommendations
            mock_get.assert_called_once()


class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    @patch('utils.resource_monitor.psutil.cpu_percent')
    @patch('utils.resource_monitor.psutil.virtual_memory')
    def test_complete_optimization_workflow(self, mock_memory, mock_cpu):
        """Test complete resource optimization workflow."""
        # Mock system metrics
        mock_cpu.return_value = 85.0  # High CPU
        mock_memory.return_value = Mock(percent=60.0)
        
        # Create manager with custom config
        config = ResourceOptimizationConfig(
            monitoring_interval_seconds=0.1,  # Fast for testing
            cpu_scale_up_threshold=80.0,
        )
        manager = ResourceOptimizationManager(config)
        
        # Initialize and start
        manager.initialize()
        
        # Add handlers to capture events
        scaling_events = []
        alert_events = []
        cost_events = []
        
        def scaling_handler(recommendations):
            scaling_events.extend(recommendations)
        
        def alert_handler(alert_type, alert_data):
            alert_events.append((alert_type, alert_data))
        
        def cost_handler(recommendations):
            cost_events.extend(recommendations)
        
        manager.add_scaling_handler(scaling_handler)
        manager.add_alert_handler(alert_handler)
        manager.add_cost_handler(cost_handler)
        
        # Record multiple metrics to establish a trend and trigger recommendations
        for i in range(10):
            metrics = ResourceMetrics(
                cpu_percent=85.0 + i,  # Increasing CPU
                memory_percent=60.0,
                network_io_mbps=10.0,
                active_connections=30,
                queue_depth=15,
                pending_tasks=30,
                llm_tokens_per_minute=1000,
            )
            manager._optimizer.record_metrics(metrics)
        
        # Record LLM usage for cost tracking
        manager.record_llm_usage(5000, 0.01)
        
        # Get recommendations
        scaling_recommendations = manager.get_scaling_recommendations()
        cost_recommendations = manager.get_cost_optimization_recommendations()
        
        # Should have scaling recommendations due to high CPU
        assert len(scaling_recommendations) > 0
        cpu_recommendations = [r for r in scaling_recommendations if r.resource_type == ResourceType.CPU]
        assert len(cpu_recommendations) > 0
        assert cpu_recommendations[0].action == ScalingAction.SCALE_UP
        
        # Get system status
        status = manager.get_system_status()
        assert status["initialized"] is True
        assert "resource_utilization" in status
        assert "scaling_recommendations" in status
        assert "cost_recommendations" in status
    
    def test_task_batching_integration(self):
        """Test task batching integration with resource optimization."""
        config = ResourceOptimizationConfig(batching_enabled=True, max_batch_size=3)
        manager = ResourceOptimizationManager(config)
        manager.initialize()
        
        # Add multiple similar tasks
        task_ids = []
        for i in range(5):
            task_data = {
                "prompt": f"Analyze task {i}",
                "intent": "analyze",
                "agentProfile": "coder",
            }
            task_id = manager.add_task(task_data, TaskPriority.NORMAL)
            task_ids.append(task_id)
        
        # Check that tasks were added
        assert len(task_ids) == 5
        
        # Get queue status
        status = manager.get_system_status()
        queue_status = status.get("queue_status", {})
        
        # Should have tasks in the queue
        assert queue_status.get("metrics", {}).get("total_tasks", 0) == 5
    
    def test_cost_tracking_integration(self):
        """Test cost tracking integration across components."""
        config = ResourceOptimizationConfig(cost_tracking_enabled=True)
        manager = ResourceOptimizationManager(config)
        manager.initialize()
        
        # Record multiple LLM usage events
        for i in range(10):
            manager.record_llm_usage(1000 + i * 100, 0.002 + i * 0.001)
        
        # Track some cost metrics
        cost_metrics = CostMetrics(
            llm_api_cost_usd=15.0,  # High LLM cost
            compute_cost_usd=5.0,
            storage_cost_usd=1.0,
            network_cost_usd=1.0,
            total_cost_usd=22.0,
            cost_per_task=0.5,
        )
        manager._optimizer.track_cost(cost_metrics)
        
        # Get cost recommendations
        recommendations = manager.get_cost_optimization_recommendations()
        
        # Should have recommendations due to high LLM costs
        llm_recommendations = [r for r in recommendations if "llm" in r.lower()]
        assert len(llm_recommendations) > 0


if __name__ == "__main__":
    pytest.main([__file__])