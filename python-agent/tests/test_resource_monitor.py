"""
Unit tests for the resource monitor.

Tests the resource monitoring functionality including:
- System resource collection
- Cost tracking integration
- Alert handling
- Background monitoring service

Requirements: Task 33.2 - Optimize resource utilization
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.resource_monitor import (
    ResourceMonitor,
    MonitoringConfig,
    get_resource_monitor,
    initialize_resource_monitor,
)
from utils.resource_optimizer import (
    ResourceOptimizer,
    ResourceMetrics,
    CostMetrics,
)


class TestMonitoringConfig:
    """Test cases for MonitoringConfig."""
    
    def test_default_config(self):
        """Test default monitoring configuration."""
        config = MonitoringConfig()
        
        assert config.collection_interval_seconds == 30.0
        assert config.cpu_collection_interval == 1.0
        assert config.enable_network_monitoring is True
        assert config.enable_process_monitoring is True
        assert config.enable_cost_tracking is True
        assert config.alert_thresholds["cpu_percent"] == 90.0
        assert config.alert_thresholds["memory_percent"] == 95.0
    
    def test_custom_config(self):
        """Test custom monitoring configuration."""
        custom_thresholds = {
            "cpu_percent": 80.0,
            "memory_percent": 85.0,
            "queue_depth": 30,
        }
        
        config = MonitoringConfig(
            collection_interval_seconds=60.0,
            enable_network_monitoring=False,
            enable_cost_tracking=False,
            alert_thresholds=custom_thresholds,
        )
        
        assert config.collection_interval_seconds == 60.0
        assert config.enable_network_monitoring is False
        assert config.enable_cost_tracking is False
        assert config.alert_thresholds["cpu_percent"] == 80.0


class TestResourceMonitor:
    """Test cases for ResourceMonitor."""
    
    def test_initialization(self):
        """Test ResourceMonitor initialization."""
        optimizer = Mock(spec=ResourceOptimizer)
        config = MonitoringConfig()
        
        monitor = ResourceMonitor(config=config, optimizer=optimizer)
        
        assert monitor._config == config
        assert monitor._optimizer == optimizer
        assert monitor._running is False
        assert monitor._monitor_thread is None
    
    def test_initialization_with_defaults(self):
        """Test ResourceMonitor initialization with defaults."""
        monitor = ResourceMonitor()
        
        assert monitor._config is not None
        assert monitor._optimizer is not None
        assert monitor._running is False
    
    @patch('utils.resource_monitor.psutil.cpu_percent')
    @patch('utils.resource_monitor.psutil.virtual_memory')
    def test_collect_metrics(self, mock_memory, mock_cpu):
        """Test metrics collection."""
        # Mock psutil responses
        mock_cpu.return_value = 65.0
        mock_memory.return_value = Mock(percent=75.0)
        
        optimizer = Mock(spec=ResourceOptimizer)
        monitor = ResourceMonitor(optimizer=optimizer)
        
        # Mock internal methods
        monitor._calculate_network_io_rate = Mock(return_value=12.5)
        monitor._get_active_connections = Mock(return_value=25)
        monitor._get_queue_metrics = Mock(return_value=(8, 16))
        monitor._calculate_llm_token_rate = Mock(return_value=750)
        
        metrics = monitor._collect_metrics()
        
        assert isinstance(metrics, ResourceMetrics)
        assert metrics.cpu_percent == 65.0
        assert metrics.memory_percent == 75.0
        assert metrics.network_io_mbps == 12.5
        assert metrics.active_connections == 25
        assert metrics.queue_depth == 8
        assert metrics.pending_tasks == 16
        assert metrics.llm_tokens_per_minute == 750
    
    @patch('utils.resource_monitor.psutil.net_io_counters')
    def test_calculate_network_io_rate_first_call(self, mock_net_io):
        """Test network I/O rate calculation on first call."""
        mock_net_io.return_value = Mock(bytes_sent=1000000, bytes_recv=2000000)
        
        monitor = ResourceMonitor()
        rate = monitor._calculate_network_io_rate()
        
        # First call should return 0.0
        assert rate == 0.0
        assert monitor._last_network_io is not None
        assert monitor._last_network_time is not None
    
    @patch('utils.resource_monitor.psutil.net_io_counters')
    def test_calculate_network_io_rate_subsequent_call(self, mock_net_io):
        """Test network I/O rate calculation on subsequent calls."""
        monitor = ResourceMonitor()
        
        # First call
        mock_net_io.return_value = Mock(bytes_sent=1000000, bytes_recv=2000000)
        monitor._calculate_network_io_rate()
        
        # Wait a bit and make second call
        time.sleep(0.1)
        mock_net_io.return_value = Mock(bytes_sent=2000000, bytes_recv=4000000)
        rate = monitor._calculate_network_io_rate()
        
        # Should calculate a positive rate
        assert rate >= 0.0
    
    @patch('utils.resource_monitor.psutil.net_io_counters')
    def test_calculate_network_io_rate_disabled(self, mock_net_io):
        """Test network I/O rate calculation when disabled."""
        config = MonitoringConfig(enable_network_monitoring=False)
        monitor = ResourceMonitor(config=config)
        
        rate = monitor._calculate_network_io_rate()
        
        assert rate == 0.0
        mock_net_io.assert_not_called()
    
    def test_get_active_connections_disabled(self):
        """Test getting active connections when process monitoring is disabled."""
        config = MonitoringConfig(enable_process_monitoring=False)
        monitor = ResourceMonitor(config=config)
        
        connections = monitor._get_active_connections()
        
        assert connections == 0
    
    @patch('utils.resource_monitor.psutil.Process')
    def test_get_active_connections_with_connections(self, mock_process_class):
        """Test getting active connections with established connections."""
        # Mock process and connections
        mock_conn1 = Mock()
        mock_conn1.status = 'ESTABLISHED'
        mock_conn2 = Mock()
        mock_conn2.status = 'LISTEN'
        mock_conn3 = Mock()
        mock_conn3.status = 'ESTABLISHED'
        
        mock_process = Mock()
        mock_process.connections.return_value = [mock_conn1, mock_conn2, mock_conn3]
        mock_process_class.return_value = mock_process
        
        monitor = ResourceMonitor()
        monitor._process = mock_process
        
        connections = monitor._get_active_connections()
        
        # Should count only ESTABLISHED connections
        assert connections == 2
    
    def test_get_queue_metrics(self):
        """Test getting queue metrics from optimizer."""
        optimizer = Mock(spec=ResourceOptimizer)
        optimizer.get_resource_utilization_summary.return_value = {
            "queue_status": {
                "pending_tasks": 12,
                "pending_batches": 3,
            }
        }
        
        monitor = ResourceMonitor(optimizer=optimizer)
        queue_depth, pending_tasks = monitor._get_queue_metrics()
        
        assert queue_depth == 12
        assert pending_tasks == 27  # 12 + (3 * 5)
    
    def test_get_queue_metrics_no_data(self):
        """Test getting queue metrics when no data available."""
        optimizer = Mock(spec=ResourceOptimizer)
        optimizer.get_resource_utilization_summary.return_value = {"status": "no_data"}
        
        monitor = ResourceMonitor(optimizer=optimizer)
        queue_depth, pending_tasks = monitor._get_queue_metrics()
        
        assert queue_depth == 0
        assert pending_tasks == 0
    
    def test_calculate_llm_token_rate(self):
        """Test LLM token rate calculation."""
        monitor = ResourceMonitor()
        monitor._llm_token_count = 3000
        monitor._start_time = time.time() - 120.0  # 2 minutes ago
        
        rate = monitor._calculate_llm_token_rate()
        
        # Should be approximately 1500 tokens per minute
        assert 1400 <= rate <= 1600
    
    def test_calculate_llm_token_rate_no_time(self):
        """Test LLM token rate calculation with no elapsed time."""
        monitor = ResourceMonitor()
        monitor._llm_token_count = 1000
        monitor._start_time = time.time()  # Just started
        
        rate = monitor._calculate_llm_token_rate()
        
        assert rate == 0
    
    def test_collect_cost_metrics(self):
        """Test cost metrics collection."""
        monitor = ResourceMonitor()
        monitor._llm_token_count = 5000  # 5K tokens
        monitor._llm_api_calls = 10
        monitor._start_time = time.time() - 3600.0  # 1 hour ago
        
        cost_metrics = monitor._collect_cost_metrics()
        
        assert isinstance(cost_metrics, CostMetrics)
        assert cost_metrics.llm_api_cost_usd == 0.01  # 5K tokens * $0.002/1K
        assert cost_metrics.compute_cost_usd == 0.10  # 1 hour * $0.10/hour
        assert cost_metrics.total_cost_usd > 0.0
        assert cost_metrics.cost_per_task > 0.0
    
    def test_check_alerts_cpu_high(self):
        """Test alert checking for high CPU."""
        alert_callback = Mock()
        monitor = ResourceMonitor(alert_callback=alert_callback)
        
        metrics = ResourceMetrics(
            cpu_percent=95.0,  # Above 90% threshold
            memory_percent=50.0,
            network_io_mbps=5.0,
            active_connections=20,
            queue_depth=10,
            pending_tasks=20,
            llm_tokens_per_minute=500,
        )
        
        monitor._check_alerts(metrics)
        
        # Should trigger CPU alert
        alert_callback.assert_called_once()
        call_args = alert_callback.call_args
        assert call_args[0][0] == "cpu_high"
        assert "CPU utilization" in call_args[0][1]["message"]
    
    def test_check_alerts_memory_high(self):
        """Test alert checking for high memory."""
        alert_callback = Mock()
        monitor = ResourceMonitor(alert_callback=alert_callback)
        
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_percent=98.0,  # Above 95% threshold
            network_io_mbps=5.0,
            active_connections=20,
            queue_depth=10,
            pending_tasks=20,
            llm_tokens_per_minute=500,
        )
        
        monitor._check_alerts(metrics)
        
        # Should trigger memory alert
        alert_callback.assert_called_once()
        call_args = alert_callback.call_args
        assert call_args[0][0] == "memory_high"
        assert "Memory utilization" in call_args[0][1]["message"]
    
    def test_check_alerts_queue_high(self):
        """Test alert checking for high queue depth."""
        alert_callback = Mock()
        monitor = ResourceMonitor(alert_callback=alert_callback)
        
        metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_percent=60.0,
            network_io_mbps=5.0,
            active_connections=20,
            queue_depth=60,  # Above 50 threshold
            pending_tasks=120,
            llm_tokens_per_minute=500,
        )
        
        monitor._check_alerts(metrics)
        
        # Should trigger queue alert
        alert_callback.assert_called_once()
        call_args = alert_callback.call_args
        assert call_args[0][0] == "queue_high"
        assert "Queue depth" in call_args[0][1]["message"]
    
    def test_check_alerts_no_alerts(self):
        """Test alert checking with normal metrics."""
        alert_callback = Mock()
        monitor = ResourceMonitor(alert_callback=alert_callback)
        
        metrics = ResourceMetrics(
            cpu_percent=50.0,  # Below 90%
            memory_percent=60.0,  # Below 95%
            network_io_mbps=5.0,
            active_connections=20,
            queue_depth=10,  # Below 50
            pending_tasks=20,
            llm_tokens_per_minute=500,
        )
        
        monitor._check_alerts(metrics)
        
        # Should not trigger any alerts
        alert_callback.assert_not_called()
    
    def test_check_alerts_no_callback(self):
        """Test alert checking without callback (should log warning)."""
        monitor = ResourceMonitor()
        
        metrics = ResourceMetrics(
            cpu_percent=95.0,  # Above threshold
            memory_percent=50.0,
            network_io_mbps=5.0,
            active_connections=20,
            queue_depth=10,
            pending_tasks=20,
            llm_tokens_per_minute=500,
        )
        
        # Should not raise exception
        monitor._check_alerts(metrics)
    
    def test_record_llm_usage(self):
        """Test recording LLM usage."""
        monitor = ResourceMonitor()
        initial_count = monitor._llm_token_count
        initial_calls = monitor._llm_api_calls
        
        monitor.record_llm_usage(1500)
        
        assert monitor._llm_token_count == initial_count + 1500
        assert monitor._llm_api_calls == initial_calls + 1
    
    def test_get_current_metrics(self):
        """Test getting current metrics."""
        monitor = ResourceMonitor()
        
        # Mock the collect_metrics method
        expected_metrics = ResourceMetrics(
            cpu_percent=60.0,
            memory_percent=70.0,
            network_io_mbps=10.0,
            active_connections=25,
            queue_depth=8,
            pending_tasks=16,
            llm_tokens_per_minute=600,
        )
        monitor._collect_metrics = Mock(return_value=expected_metrics)
        
        metrics = monitor.get_current_metrics()
        
        assert metrics == expected_metrics
    
    def test_get_current_metrics_error(self):
        """Test getting current metrics with error."""
        monitor = ResourceMonitor()
        
        # Mock the collect_metrics method to raise exception
        monitor._collect_metrics = Mock(side_effect=Exception("Test error"))
        
        metrics = monitor.get_current_metrics()
        
        assert metrics is None
    
    def test_get_monitoring_status(self):
        """Test getting monitoring status."""
        monitor = ResourceMonitor()
        monitor._llm_token_count = 2500
        monitor._llm_api_calls = 5
        
        status = monitor.get_monitoring_status()
        
        assert "running" in status
        assert "collection_interval" in status
        assert "uptime_seconds" in status
        assert status["total_llm_tokens"] == 2500
        assert status["total_llm_calls"] == 5
        assert "config" in status
    
    def test_start_stop_monitoring(self):
        """Test starting and stopping monitoring."""
        monitor = ResourceMonitor()
        
        # Initially not running
        assert monitor._running is False
        
        # Start monitoring
        monitor.start()
        assert monitor._running is True
        assert monitor._monitor_thread is not None
        
        # Stop monitoring
        monitor.stop()
        assert monitor._running is False
    
    def test_start_already_running(self):
        """Test starting monitoring when already running."""
        monitor = ResourceMonitor()
        
        # Start monitoring
        monitor.start()
        assert monitor._running is True
        
        # Try to start again (should log warning)
        monitor.start()
        assert monitor._running is True
    
    def test_stop_not_running(self):
        """Test stopping monitoring when not running."""
        monitor = ResourceMonitor()
        
        # Stop monitoring (should not raise exception)
        monitor.stop()
        assert monitor._running is False
    
    @patch('utils.resource_monitor.time.sleep')
    def test_monitoring_loop_single_iteration(self, mock_sleep):
        """Test a single iteration of the monitoring loop."""
        optimizer = Mock(spec=ResourceOptimizer)
        config = MonitoringConfig(collection_interval_seconds=1.0)
        monitor = ResourceMonitor(config=config, optimizer=optimizer)
        
        # Mock methods
        expected_metrics = ResourceMetrics(
            cpu_percent=50.0,
            memory_percent=60.0,
            network_io_mbps=5.0,
            active_connections=20,
            queue_depth=5,
            pending_tasks=10,
            llm_tokens_per_minute=400,
        )
        monitor._collect_metrics = Mock(return_value=expected_metrics)
        monitor._check_alerts = Mock()
        monitor._collect_cost_metrics = Mock(return_value=Mock(spec=CostMetrics))
        
        # Set up to run one iteration
        monitor._running = True
        monitor._stop_event = Mock()
        monitor._stop_event.is_set.side_effect = [False, True]  # Run once, then stop
        
        # Run the monitoring loop
        monitor._monitor_loop()
        
        # Verify methods were called
        monitor._collect_metrics.assert_called_once()
        optimizer.record_metrics.assert_called_once_with(expected_metrics)
        monitor._check_alerts.assert_called_once_with(expected_metrics)
        optimizer.track_cost.assert_called_once()


class TestGlobalFunctions:
    """Test cases for global functions."""
    
    def test_get_resource_monitor(self):
        """Test getting global resource monitor."""
        # Clear global state
        import utils.resource_monitor as rm
        rm._resource_monitor = None
        
        monitor = get_resource_monitor()
        
        assert isinstance(monitor, ResourceMonitor)
        
        # Should return same instance on subsequent calls
        monitor2 = get_resource_monitor()
        assert monitor is monitor2
    
    def test_initialize_resource_monitor(self):
        """Test initializing global resource monitor."""
        config = MonitoringConfig(collection_interval_seconds=60.0)
        optimizer = Mock(spec=ResourceOptimizer)
        alert_callback = Mock()
        
        monitor = initialize_resource_monitor(
            config=config,
            optimizer=optimizer,
            alert_callback=alert_callback,
        )
        
        assert isinstance(monitor, ResourceMonitor)
        assert monitor._config == config
        assert monitor._optimizer == optimizer
        assert monitor._alert_callback == alert_callback


if __name__ == "__main__":
    pytest.main([__file__])