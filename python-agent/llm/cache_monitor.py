"""
Cache monitoring service for real-time cache performance tracking.

This module provides comprehensive monitoring capabilities for LLM cache performance
including hit rate tracking, bad cache detection, and automated alerting.

Requirements: 12.4
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from llm.enhanced_cache_manager import CacheMetrics, EnhancedCacheManager
from utils.observability import TaskObservability, log_structured

logger = logging.getLogger(__name__)


@dataclass
class CacheAlert:
    """Cache performance alert."""
    
    alert_type: str  # "hit_rate_low", "bad_cache_high", "size_limit", "performance_degraded"
    severity: str  # "warning", "critical"
    message: str
    metrics: CacheMetrics
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False


@dataclass
class CacheThresholds:
    """Cache monitoring thresholds."""
    
    # Hit rate thresholds
    min_hit_rate: float = 0.95  # 95% minimum hit rate (Requirement 12.4)
    warning_hit_rate: float = 0.90  # Warning threshold
    
    # Bad cache thresholds
    max_bad_cache_rate: float = 0.05  # 5% maximum bad cache rate
    warning_bad_cache_rate: float = 0.02  # 2% warning threshold
    
    # Performance thresholds
    max_response_time_ratio: float = 2.0  # Cached should be 2x faster than uncached
    max_cache_size_mb: float = 500.0  # 500MB cache size limit
    
    # Monitoring intervals
    check_interval_seconds: float = 60.0  # Check every minute
    alert_cooldown_seconds: float = 300.0  # 5 minute cooldown between alerts


class CacheMonitor:
    """
    Real-time cache performance monitor with alerting.
    
    This monitor continuously tracks cache performance metrics and generates
    alerts when thresholds are exceeded. It provides automated responses
    to common cache issues.
    """
    
    def __init__(
        self,
        cache_manager: EnhancedCacheManager,
        thresholds: Optional[CacheThresholds] = None,
        alert_callback: Optional[Callable[[CacheAlert], None]] = None,
    ) -> None:
        """
        Initialize cache monitor.
        
        Args:
            cache_manager: Enhanced cache manager to monitor
            thresholds: Monitoring thresholds (uses defaults if None)
            alert_callback: Callback function for alerts (optional)
        """
        self.cache_manager = cache_manager
        self.thresholds = thresholds or CacheThresholds()
        self.alert_callback = alert_callback
        
        # Monitoring state
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._alerts: List[CacheAlert] = []
        self._last_alert_times: Dict[str, float] = {}
        
        # Performance tracking
        self._performance_history: List[CacheMetrics] = []
        self._max_history_size = 100
        
        logger.info("Cache monitor initialized with thresholds: hit_rate=%.2f", self.thresholds.min_hit_rate)
    
    def start_monitoring(self) -> None:
        """Start continuous cache monitoring."""
        if self._monitoring:
            logger.warning("Cache monitoring already started")
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info("Cache monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop cache monitoring."""
        if not self._monitoring:
            return
        
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        
        logger.info("Cache monitoring stopped")
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current cache monitoring status."""
        metrics = self.cache_manager.get_cache_metrics()
        
        return {
            "monitoring_active": self._monitoring,
            "metrics": {
                "hit_rate": metrics.hit_rate,
                "total_requests": metrics.total_requests,
                "cache_hits": metrics.cache_hits,
                "cache_misses": metrics.cache_misses,
                "bad_cache_rate": metrics.bad_cache_rate,
                "semantic_hit_rate": metrics.semantic_hit_rate,
                "cache_size_mb": metrics.cache_size_bytes / (1024 * 1024),
            },
            "thresholds": {
                "min_hit_rate": self.thresholds.min_hit_rate,
                "max_bad_cache_rate": self.thresholds.max_bad_cache_rate,
                "max_cache_size_mb": self.thresholds.max_cache_size_mb,
            },
            "alerts": {
                "total_alerts": len(self._alerts),
                "unacknowledged_alerts": len([a for a in self._alerts if not a.acknowledged]),
                "recent_alerts": [
                    {
                        "type": alert.alert_type,
                        "severity": alert.severity,
                        "message": alert.message,
                        "timestamp": alert.timestamp,
                    }
                    for alert in self._alerts[-5:]  # Last 5 alerts
                ],
            },
            "performance_trend": self._get_performance_trend(),
        }
    
    def acknowledge_alerts(self, alert_types: Optional[List[str]] = None) -> int:
        """
        Acknowledge alerts to stop repeated notifications.
        
        Args:
            alert_types: Specific alert types to acknowledge (all if None)
        
        Returns:
            Number of alerts acknowledged
        """
        acknowledged_count = 0
        
        for alert in self._alerts:
            if alert.acknowledged:
                continue
            
            if alert_types is None or alert.alert_type in alert_types:
                alert.acknowledged = True
                acknowledged_count += 1
        
        logger.info("Acknowledged %d cache alerts", acknowledged_count)
        return acknowledged_count
    
    def force_cache_optimization(self) -> Dict[str, Any]:
        """
        Force cache optimization actions.
        
        Returns:
            Dictionary with optimization results
        """
        results = {
            "actions_taken": [],
            "metrics_before": self.cache_manager.get_cache_metrics(),
        }
        
        # Warm cache with frequent patterns
        warmed = self.cache_manager.warm_cache()
        if warmed > 0:
            results["actions_taken"].append(f"warmed_{warmed}_entries")
        
        # Invalidate bad cache entries
        invalidated = self.cache_manager.invalidate_preemptively("error")
        if invalidated > 0:
            results["actions_taken"].append(f"invalidated_{invalidated}_bad_entries")
        
        # Wait a moment for metrics to update
        time.sleep(1.0)
        results["metrics_after"] = self.cache_manager.get_cache_metrics()
        
        logger.info("Forced cache optimization: %s", results["actions_taken"])
        return results
    
    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Cache monitoring loop started")
        
        while self._monitoring:
            try:
                self._check_cache_performance()
                time.sleep(self.thresholds.check_interval_seconds)
            except Exception as e:
                logger.error("Cache monitoring error: %s", e)
                time.sleep(10.0)  # Brief pause on error
        
        logger.info("Cache monitoring loop stopped")
    
    def _check_cache_performance(self) -> None:
        """Check cache performance and generate alerts if needed."""
        metrics = self.cache_manager.get_cache_metrics()
        
        # Store metrics history
        self._performance_history.append(metrics)
        if len(self._performance_history) > self._max_history_size:
            self._performance_history.pop(0)
        
        # Check hit rate
        self._check_hit_rate(metrics)
        
        # Check bad cache rate
        self._check_bad_cache_rate(metrics)
        
        # Check cache size
        self._check_cache_size(metrics)
        
        # Check performance degradation
        self._check_performance_degradation(metrics)
        
        # Log periodic status
        if len(self._performance_history) % 10 == 0:  # Every 10 checks
            log_structured(
                "cache_monitor_status",
                level=logging.INFO,
                stage="CacheMonitor",
                extra={
                    "hit_rate": metrics.hit_rate,
                    "bad_cache_rate": metrics.bad_cache_rate,
                    "cache_size_mb": metrics.cache_size_bytes / (1024 * 1024),
                    "total_requests": metrics.total_requests,
                },
            )
    
    def _check_hit_rate(self, metrics: CacheMetrics) -> None:
        """Check cache hit rate and generate alerts."""
        if metrics.total_requests < 10:  # Need minimum requests for meaningful hit rate
            return
        
        if metrics.hit_rate < self.thresholds.min_hit_rate:
            self._generate_alert(
                "hit_rate_low",
                "critical",
                f"Cache hit rate {metrics.hit_rate:.2%} below minimum {self.thresholds.min_hit_rate:.2%}",
                metrics,
            )
        elif metrics.hit_rate < self.thresholds.warning_hit_rate:
            self._generate_alert(
                "hit_rate_warning",
                "warning",
                f"Cache hit rate {metrics.hit_rate:.2%} below warning threshold {self.thresholds.warning_hit_rate:.2%}",
                metrics,
            )
    
    def _check_bad_cache_rate(self, metrics: CacheMetrics) -> None:
        """Check bad cache detection rate."""
        if metrics.bad_cache_rate > self.thresholds.max_bad_cache_rate:
            self._generate_alert(
                "bad_cache_high",
                "critical",
                f"Bad cache rate {metrics.bad_cache_rate:.2%} above maximum {self.thresholds.max_bad_cache_rate:.2%}",
                metrics,
            )
        elif metrics.bad_cache_rate > self.thresholds.warning_bad_cache_rate:
            self._generate_alert(
                "bad_cache_warning",
                "warning",
                f"Bad cache rate {metrics.bad_cache_rate:.2%} above warning threshold {self.thresholds.warning_bad_cache_rate:.2%}",
                metrics,
            )
    
    def _check_cache_size(self, metrics: CacheMetrics) -> None:
        """Check cache size limits."""
        cache_size_mb = metrics.cache_size_bytes / (1024 * 1024)
        
        if cache_size_mb > self.thresholds.max_cache_size_mb:
            self._generate_alert(
                "size_limit",
                "warning",
                f"Cache size {cache_size_mb:.1f}MB exceeds limit {self.thresholds.max_cache_size_mb:.1f}MB",
                metrics,
            )
    
    def _check_performance_degradation(self, metrics: CacheMetrics) -> None:
        """Check for performance degradation."""
        if (metrics.avg_response_time_cached > 0 and 
            metrics.avg_response_time_uncached > 0):
            
            ratio = metrics.avg_response_time_uncached / metrics.avg_response_time_cached
            
            if ratio < self.thresholds.max_response_time_ratio:
                self._generate_alert(
                    "performance_degraded",
                    "warning",
                    f"Cache performance ratio {ratio:.1f}x below expected {self.thresholds.max_response_time_ratio:.1f}x",
                    metrics,
                )
    
    def _generate_alert(self, alert_type: str, severity: str, message: str, metrics: CacheMetrics) -> None:
        """Generate and handle cache alert."""
        # Check cooldown period
        now = time.time()
        last_alert_time = self._last_alert_times.get(alert_type, 0)
        
        if now - last_alert_time < self.thresholds.alert_cooldown_seconds:
            return  # Still in cooldown period
        
        # Create alert
        alert = CacheAlert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            metrics=metrics,
        )
        
        # Store alert
        self._alerts.append(alert)
        self._last_alert_times[alert_type] = now
        
        # Limit alert history
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-50:]  # Keep last 50 alerts
        
        # Log alert
        log_structured(
            "cache_alert_generated",
            level=logging.WARNING if severity == "warning" else logging.ERROR,
            stage="CacheMonitor",
            error_code=alert_type,
            extra={
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "hit_rate": metrics.hit_rate,
                "bad_cache_rate": metrics.bad_cache_rate,
                "total_requests": metrics.total_requests,
            },
        )
        
        # Call alert callback if provided
        if self.alert_callback:
            try:
                self.alert_callback(alert)
            except Exception as e:
                logger.error("Alert callback failed: %s", e)
        
        # Automatic remediation for critical alerts
        if severity == "critical":
            self._attempt_automatic_remediation(alert_type, metrics)
    
    def _attempt_automatic_remediation(self, alert_type: str, metrics: CacheMetrics) -> None:
        """Attempt automatic remediation for critical alerts."""
        try:
            if alert_type == "hit_rate_low":
                # Try cache warming
                warmed = self.cache_manager.warm_cache()
                logger.info("Automatic remediation: warmed %d cache entries", warmed)
            
            elif alert_type == "bad_cache_high":
                # Invalidate bad cache entries
                invalidated = self.cache_manager.invalidate_preemptively("error")
                logger.info("Automatic remediation: invalidated %d bad cache entries", invalidated)
            
            elif alert_type == "size_limit":
                # Trigger cache cleanup (simplified)
                logger.info("Automatic remediation: cache size limit reached, consider cleanup")
        
        except Exception as e:
            logger.error("Automatic remediation failed: %s", e)
    
    def _get_performance_trend(self) -> Dict[str, Any]:
        """Calculate performance trend from history."""
        if len(self._performance_history) < 2:
            return {"trend": "insufficient_data"}
        
        recent_metrics = self._performance_history[-5:]  # Last 5 measurements
        older_metrics = self._performance_history[-10:-5] if len(self._performance_history) >= 10 else []
        
        if not older_metrics:
            return {"trend": "insufficient_history"}
        
        # Calculate average hit rates
        recent_hit_rate = sum(m.hit_rate for m in recent_metrics) / len(recent_metrics)
        older_hit_rate = sum(m.hit_rate for m in older_metrics) / len(older_metrics)
        
        hit_rate_change = recent_hit_rate - older_hit_rate
        
        # Determine trend
        if abs(hit_rate_change) < 0.01:  # Less than 1% change
            trend = "stable"
        elif hit_rate_change > 0:
            trend = "improving"
        else:
            trend = "declining"
        
        return {
            "trend": trend,
            "hit_rate_change": hit_rate_change,
            "recent_hit_rate": recent_hit_rate,
            "older_hit_rate": older_hit_rate,
        }


def create_cache_monitor(
    cache_manager: EnhancedCacheManager,
    thresholds: Optional[CacheThresholds] = None,
    auto_start: bool = True,
) -> CacheMonitor:
    """
    Create and optionally start a cache monitor.
    
    Args:
        cache_manager: Enhanced cache manager to monitor
        thresholds: Monitoring thresholds (uses defaults if None)
        auto_start: Whether to automatically start monitoring
    
    Returns:
        Configured cache monitor
    """
    monitor = CacheMonitor(cache_manager, thresholds)
    
    if auto_start:
        monitor.start_monitoring()
    
    return monitor