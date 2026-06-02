"""
Unit tests for cache monitor.

Tests the cache monitoring, alerting, and automatic remediation features.

Requirements: 12.4
"""
import time
import unittest
from unittest.mock import MagicMock, patch

from llm.cache_monitor import CacheAlert, CacheMonitor, CacheThresholds
from llm.enhanced_cache_manager import CacheMetrics, EnhancedCacheManager


class TestCacheMonitor(unittest.TestCase):
    """Test cases for cache monitor."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.cache_manager = MagicMock(spec=EnhancedCacheManager)
        self.thresholds = CacheThresholds(
            min_hit_rate=0.95,
            warning_hit_rate=0.90,
            max_bad_cache_rate=0.05,
            warning_bad_cache_rate=0.02,
            check_interval_seconds=0.1,  # Fast for testing
            alert_cooldown_seconds=0.5,  # Short for testing
        )
        
        self.monitor = CacheMonitor(
            self.cache_manager,
            self.thresholds,
        )
        
        # Mock alert callback
        self.alert_callback = MagicMock()
        self.monitor.alert_callback = self.alert_callback
    
    def test_initialization(self):
        """Test monitor initialization."""
        self.assertEqual(self.monitor.cache_manager, self.cache_manager)
        self.assertEqual(self.monitor.thresholds, self.thresholds)
        self.assertFalse(self.monitor._monitoring)
        self.assertEqual(len(self.monitor._alerts), 0)
    
    def test_hit_rate_monitoring(self):
        """Test cache hit rate monitoring and alerting."""
        # Mock low hit rate metrics
        low_hit_rate_metrics = CacheMetrics(
            total_requests=100,
            cache_hits=85,  # 85% hit rate (below 95% threshold)
            cache_misses=15,
        )
        self.cache_manager.get_cache_metrics.return_value = low_hit_rate_metrics
        
        # Check performance (simulate monitoring check)
        self.monitor._check_cache_performance()
        
        # Should generate critical alert
        self.assertEqual(len(self.monitor._alerts), 1)
        alert = self.monitor._alerts[0]
        self.assertEqual(alert.alert_type, "hit_rate_low")
        self.assertEqual(alert.severity, "critical")
        self.assertIn("85.00%", alert.message)
        
        # Alert callback should be called
        self.alert_callback.assert_called_once_with(alert)
    
    def test_bad_cache_monitoring(self):
        """Test bad cache rate monitoring."""
        # Mock high bad cache rate metrics with good hit rate
        high_bad_cache_metrics = CacheMetrics(
            total_requests=100,
            cache_hits=96,  # 96% hit rate (above threshold)
            cache_misses=4,
            bad_cache_detections=8,  # 8% bad cache rate (above 5% threshold)
        )
        self.cache_manager.get_cache_metrics.return_value = high_bad_cache_metrics
        
        # Check performance
        self.monitor._check_cache_performance()
        
        # Should generate critical alert for bad cache (hit rate is fine)
        self.assertEqual(len(self.monitor._alerts), 1)
        alert = self.monitor._alerts[0]
        self.assertEqual(alert.alert_type, "bad_cache_high")
        self.assertEqual(alert.severity, "critical")
        self.assertIn("8.00%", alert.message)
    
    def test_cache_size_monitoring(self):
        """Test cache size monitoring."""
        # Mock large cache size metrics
        large_cache_metrics = CacheMetrics(
            cache_size_bytes=600 * 1024 * 1024,  # 600MB (above 500MB threshold)
        )
        self.cache_manager.get_cache_metrics.return_value = large_cache_metrics
        
        # Check performance
        self.monitor._check_cache_performance()
        
        # Should generate warning alert
        self.assertEqual(len(self.monitor._alerts), 1)
        alert = self.monitor._alerts[0]
        self.assertEqual(alert.alert_type, "size_limit")
        self.assertEqual(alert.severity, "warning")
        self.assertIn("600.0MB", alert.message)
    
    def test_performance_degradation_monitoring(self):
        """Test performance degradation monitoring."""
        # Mock performance degradation metrics
        degraded_metrics = CacheMetrics(
            avg_response_time_cached=2.0,  # 2 seconds cached
            avg_response_time_uncached=3.0,  # 3 seconds uncached (only 1.5x faster)
        )
        self.cache_manager.get_cache_metrics.return_value = degraded_metrics
        
        # Check performance
        self.monitor._check_cache_performance()
        
        # Should generate warning alert
        self.assertEqual(len(self.monitor._alerts), 1)
        alert = self.monitor._alerts[0]
        self.assertEqual(alert.alert_type, "performance_degraded")
        self.assertEqual(alert.severity, "warning")
        self.assertIn("1.5x", alert.message)
    
    def test_alert_cooldown(self):
        """Test alert cooldown mechanism."""
        # Mock low hit rate metrics
        low_hit_rate_metrics = CacheMetrics(
            total_requests=100,
            cache_hits=80,
            cache_misses=20,
        )
        self.cache_manager.get_cache_metrics.return_value = low_hit_rate_metrics
        
        # First check should generate alert
        self.monitor._check_cache_performance()
        self.assertEqual(len(self.monitor._alerts), 1)
        
        # Immediate second check should not generate another alert (cooldown)
        self.monitor._check_cache_performance()
        self.assertEqual(len(self.monitor._alerts), 1)  # Still only one alert
        
        # Wait for cooldown to expire
        time.sleep(0.6)  # Longer than cooldown period
        
        # Third check should generate another alert
        self.monitor._check_cache_performance()
        self.assertEqual(len(self.monitor._alerts), 2)  # Now two alerts
    
    def test_automatic_remediation(self):
        """Test automatic remediation for critical alerts."""
        # Mock critical hit rate issue
        critical_metrics = CacheMetrics(
            total_requests=100,
            cache_hits=70,  # 70% hit rate (critical)
            cache_misses=30,
        )
        self.cache_manager.get_cache_metrics.return_value = critical_metrics
        
        # Check performance
        self.monitor._check_cache_performance()
        
        # Should attempt cache warming
        self.cache_manager.warm_cache.assert_called_once()
        
        # Reset mock
        self.cache_manager.reset_mock()
        
        # Mock critical bad cache issue
        bad_cache_metrics = CacheMetrics(
            total_requests=100,
            cache_hits=90,
            cache_misses=10,
            bad_cache_detections=10,  # 10% bad cache rate (critical)
        )
        self.cache_manager.get_cache_metrics.return_value = bad_cache_metrics
        
        # Clear previous alerts to test new remediation
        self.monitor._alerts.clear()
        self.monitor._last_alert_times.clear()
        
        # Check performance
        self.monitor._check_cache_performance()
        
        # Should attempt bad cache invalidation
        self.cache_manager.invalidate_preemptively.assert_called_once_with("error")
    
    def test_monitoring_lifecycle(self):
        """Test monitoring start/stop lifecycle."""
        # Initially not monitoring
        self.assertFalse(self.monitor._monitoring)
        
        # Start monitoring
        self.monitor.start_monitoring()
        self.assertTrue(self.monitor._monitoring)
        self.assertIsNotNone(self.monitor._monitor_thread)
        
        # Stop monitoring
        self.monitor.stop_monitoring()
        self.assertFalse(self.monitor._monitoring)
    
    def test_current_status(self):
        """Test current status reporting."""
        # Mock metrics
        test_metrics = CacheMetrics(
            total_requests=100,
            cache_hits=95,
            cache_misses=5,
            bad_cache_detections=1,
            semantic_hits=20,
            cache_size_bytes=50 * 1024 * 1024,  # 50MB
        )
        self.cache_manager.get_cache_metrics.return_value = test_metrics
        
        # Get status
        status = self.monitor.get_current_status()
        
        # Verify status structure
        self.assertIn("monitoring_active", status)
        self.assertIn("metrics", status)
        self.assertIn("thresholds", status)
        self.assertIn("alerts", status)
        self.assertIn("performance_trend", status)
        
        # Verify metrics
        metrics = status["metrics"]
        self.assertEqual(metrics["hit_rate"], 0.95)
        self.assertEqual(metrics["total_requests"], 100)
        self.assertEqual(metrics["cache_hits"], 95)
        self.assertEqual(metrics["bad_cache_rate"], 0.01)
        self.assertEqual(metrics["cache_size_mb"], 50.0)
        
        # Verify thresholds
        thresholds = status["thresholds"]
        self.assertEqual(thresholds["min_hit_rate"], 0.95)
        self.assertEqual(thresholds["max_bad_cache_rate"], 0.05)
    
    def test_alert_acknowledgment(self):
        """Test alert acknowledgment."""
        # Generate some alerts
        self.monitor._alerts = [
            CacheAlert("hit_rate_low", "critical", "Test alert 1", CacheMetrics()),
            CacheAlert("bad_cache_high", "warning", "Test alert 2", CacheMetrics()),
            CacheAlert("size_limit", "warning", "Test alert 3", CacheMetrics()),
        ]
        
        # Acknowledge specific alert types
        acknowledged = self.monitor.acknowledge_alerts(["hit_rate_low", "size_limit"])
        self.assertEqual(acknowledged, 2)
        
        # Check acknowledgment status
        self.assertTrue(self.monitor._alerts[0].acknowledged)  # hit_rate_low
        self.assertFalse(self.monitor._alerts[1].acknowledged)  # bad_cache_high
        self.assertTrue(self.monitor._alerts[2].acknowledged)  # size_limit
        
        # Acknowledge all remaining
        acknowledged = self.monitor.acknowledge_alerts()
        self.assertEqual(acknowledged, 1)  # Only one unacknowledged left
        
        # All should now be acknowledged
        for alert in self.monitor._alerts:
            self.assertTrue(alert.acknowledged)
    
    def test_force_optimization(self):
        """Test forced cache optimization."""
        # Mock metrics before optimization
        before_metrics = CacheMetrics(
            total_requests=100,
            cache_hits=80,
            cache_misses=20,
        )
        
        # Mock metrics after optimization
        after_metrics = CacheMetrics(
            total_requests=100,
            cache_hits=90,
            cache_misses=10,
            cache_warmings=5,
            preemptive_invalidations=3,
        )
        
        # Mock cache manager methods
        self.cache_manager.get_cache_metrics.side_effect = [before_metrics, after_metrics]
        self.cache_manager.warm_cache.return_value = 5
        self.cache_manager.invalidate_preemptively.return_value = 3
        
        # Force optimization
        results = self.monitor.force_cache_optimization()
        
        # Verify results
        self.assertIn("actions_taken", results)
        self.assertIn("metrics_before", results)
        self.assertIn("metrics_after", results)
        
        actions = results["actions_taken"]
        self.assertIn("warmed_5_entries", actions)
        self.assertIn("invalidated_3_bad_entries", actions)
        
        # Verify methods were called
        self.cache_manager.warm_cache.assert_called_once()
        self.cache_manager.invalidate_preemptively.assert_called_once_with("error")
    
    def test_performance_trend_calculation(self):
        """Test performance trend calculation."""
        # Create performance history
        old_metrics = [
            CacheMetrics(cache_hits=80, cache_misses=20),  # 80% hit rate
            CacheMetrics(cache_hits=82, cache_misses=18),  # 82% hit rate
            CacheMetrics(cache_hits=81, cache_misses=19),  # 81% hit rate
            CacheMetrics(cache_hits=83, cache_misses=17),  # 83% hit rate
            CacheMetrics(cache_hits=79, cache_misses=21),  # 79% hit rate
        ]
        
        new_metrics = [
            CacheMetrics(cache_hits=90, cache_misses=10),  # 90% hit rate
            CacheMetrics(cache_hits=92, cache_misses=8),   # 92% hit rate
            CacheMetrics(cache_hits=91, cache_misses=9),   # 91% hit rate
            CacheMetrics(cache_hits=93, cache_misses=7),   # 93% hit rate
            CacheMetrics(cache_hits=89, cache_misses=11),  # 89% hit rate
        ]
        
        # Set up history
        self.monitor._performance_history = old_metrics + new_metrics
        
        # Get trend
        trend = self.monitor._get_performance_trend()
        
        # Should show improving trend
        self.assertEqual(trend["trend"], "improving")
        self.assertGreater(trend["hit_rate_change"], 0.05)  # Significant improvement
        self.assertGreater(trend["recent_hit_rate"], trend["older_hit_rate"])
    
    def test_insufficient_data_handling(self):
        """Test handling of insufficient data for monitoring."""
        # Mock metrics with very few requests
        insufficient_metrics = CacheMetrics(
            total_requests=5,  # Below minimum threshold
            cache_hits=3,
            cache_misses=2,
        )
        self.cache_manager.get_cache_metrics.return_value = insufficient_metrics
        
        # Check performance
        self.monitor._check_cache_performance()
        
        # Should not generate alerts due to insufficient data
        self.assertEqual(len(self.monitor._alerts), 0)
    
    @patch('llm.cache_monitor.log_structured')
    def test_structured_logging(self, mock_log):
        """Test structured logging of alerts and status."""
        # Mock metrics that will trigger alert
        alert_metrics = CacheMetrics(
            total_requests=100,
            cache_hits=80,  # Below threshold
            cache_misses=20,
        )
        self.cache_manager.get_cache_metrics.return_value = alert_metrics
        
        # Check performance
        self.monitor._check_cache_performance()
        
        # Verify structured logging was called
        mock_log.assert_called()
        
        # Check log call arguments
        log_calls = mock_log.call_args_list
        alert_log_call = None
        
        for call in log_calls:
            if call[0][0] == "cache_alert_generated":
                alert_log_call = call
                break
        
        self.assertIsNotNone(alert_log_call)
        
        # Verify log content
        log_kwargs = alert_log_call[1]
        self.assertEqual(log_kwargs["stage"], "CacheMonitor")
        self.assertEqual(log_kwargs["error_code"], "hit_rate_low")
        
        # Check extra data
        extra = log_kwargs.get("extra", {})
        self.assertEqual(extra["alert_type"], "hit_rate_low")
        self.assertEqual(extra["severity"], "critical")
        self.assertEqual(extra["hit_rate"], 0.8)


if __name__ == '__main__':
    unittest.main()