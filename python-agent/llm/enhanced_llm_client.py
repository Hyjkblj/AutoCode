"""
Enhanced LLM client with intelligent caching capabilities.

This module extends the existing LLM client with advanced caching features
including intelligent cache key generation, monitoring, and optimization.

Requirements: 12.4
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from llm.cache_monitor import CacheMonitor, create_cache_monitor
from llm.enhanced_cache_manager import EnhancedCacheManager
from llm.llm_client import LLMClient, LLMClientError, LLMSettings
from utils.observability import TaskObservability

logger = logging.getLogger(__name__)


class EnhancedLLMClient:
    """
    Enhanced LLM client with intelligent caching capabilities.
    
    This client wraps the existing LLM client and adds:
    - Intelligent cache key generation with semantic similarity
    - Real-time cache performance monitoring
    - Bad cache detection and automatic invalidation
    - Proactive cache warming and optimization
    - Comprehensive metrics and alerting
    """
    
    def __init__(
        self,
        base_client: Optional[LLMClient] = None,
        enable_enhanced_caching: bool = True,
        enable_monitoring: bool = True,
        **kwargs,
    ) -> None:
        """
        Initialize enhanced LLM client.
        
        Args:
            base_client: Existing LLM client (creates new if None)
            enable_enhanced_caching: Whether to enable enhanced caching features
            enable_monitoring: Whether to enable cache monitoring
            **kwargs: Arguments passed to base LLM client if creating new
        """
        # Initialize base client
        self.base_client = base_client or LLMClient(**kwargs)
        
        # Enhanced caching components
        self.enhanced_caching_enabled = enable_enhanced_caching
        self.cache_manager: Optional[EnhancedCacheManager] = None
        self.cache_monitor: Optional[CacheMonitor] = None
        
        if self.enhanced_caching_enabled:
            self._init_enhanced_caching(enable_monitoring)
        
        logger.info(
            "Enhanced LLM client initialized: enhanced_caching=%s monitoring=%s",
            self.enhanced_caching_enabled,
            enable_monitoring,
        )
    
    def _init_enhanced_caching(self, enable_monitoring: bool) -> None:
        """Initialize enhanced caching components."""
        try:
            # Create enhanced cache manager
            self.cache_manager = EnhancedCacheManager()
            
            # Create cache monitor if requested
            if enable_monitoring:
                self.cache_monitor = create_cache_monitor(
                    self.cache_manager,
                    auto_start=True,
                )
            
            logger.info("Enhanced caching initialized successfully")
            
        except Exception as e:
            logger.warning("Failed to initialize enhanced caching, falling back to basic: %s", e)
            self.enhanced_caching_enabled = False
            self.cache_manager = None
            self.cache_monitor = None
    
    @property
    def settings(self) -> LLMSettings:
        """Get LLM settings from base client."""
        return self.base_client.settings
    
    def has_required_key(self) -> bool:
        """Check if required API key is available."""
        return self.base_client.has_required_key()
    
    def is_configured(self) -> bool:
        """Check if client is properly configured."""
        return self.base_client.is_configured()
    
    def required_key_name(self) -> str | None:
        """Get name of required API key if missing."""
        return self.base_client.required_key_name()
    
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """
        Generate response with enhanced caching.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
        
        Returns:
            Generated response
        """
        messages: List[Dict[str, str]] = []
        if system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": (prompt or "").strip()})
        
        return self.chat(messages)
    
    def chat(self, messages: List[Dict[str, str]]) -> str:
        """
        Chat with enhanced caching capabilities.
        
        Args:
            messages: Conversation messages
        
        Returns:
            Generated response
        """
        if not self.enhanced_caching_enabled or self.cache_manager is None:
            # Fall back to base client
            return self.base_client.chat(messages)
        
        start_time = time.time()
        
        try:
            # Generate intelligent cache key
            cache_key, key_components = self.cache_manager.generate_cache_key(
                messages,
                backend=self.settings.backend,
                model=self.settings.model,
                temperature=self.settings.temperature,
            )
            
            # Try to get cached response
            hit, cached_response, cache_entry = self.cache_manager.get_cached_response(cache_key)
            
            if hit and cached_response:
                # Validate cached response quality
                if not self.cache_manager.detect_bad_cache(cache_key, cached_response):
                    logger.debug("Cache hit for key: %s", cache_key[:16])
                    return cached_response
                else:
                    logger.debug("Bad cache detected, falling through to generation")
            
            # Generate new response using base client
            response = self.base_client.chat(messages)
            response_time = time.time() - start_time
            
            # Store in enhanced cache
            self.cache_manager.store_cached_response(
                cache_key,
                response,
                key_components,
                response_time,
            )
            
            # Check for bad cache after generation
            self.cache_manager.detect_bad_cache(cache_key, response)
            
            return response
            
        except Exception as e:
            logger.error("Enhanced caching failed, falling back to base client: %s", e)
            return self.base_client.chat(messages)
    
    def cache_stats(self):
        """Get cache statistics."""
        if self.enhanced_caching_enabled and self.cache_manager:
            return self.cache_manager.get_cache_metrics()
        else:
            return self.base_client.cache_stats()
    
    def last_cache_event(self):
        """Get last cache event."""
        return self.base_client.last_cache_event()
    
    def clear_cache(self, *, reset_stats: bool = False) -> None:
        """Clear cache."""
        self.base_client.clear_cache(reset_stats=reset_stats)
        
        if self.enhanced_caching_enabled and self.cache_manager:
            if reset_stats:
                self.cache_manager.reset_metrics()
    
    def discard_last_cache_entry(self, *, reason: str = "discarded_by_caller") -> bool:
        """Discard last cache entry."""
        return self.base_client.discard_last_cache_entry(reason=reason)
    
    def discard_cache_entries_since(self, sequence: int, *, reason: str = "discarded_by_caller") -> int:
        """Discard cache entries since sequence."""
        return self.base_client.discard_cache_entries_since(sequence, reason=reason)
    
    def cache_event_cursor(self) -> int:
        """Get cache event cursor."""
        return self.base_client.cache_event_cursor()
    
    def record_cache_metrics(
        self,
        observation: TaskObservability,
        *,
        stage: str,
        backend: str = "",
        since_sequence: int | None = None,
    ) -> None:
        """
        Record cache metrics with enhanced monitoring.
        
        Args:
            observation: Task observability instance
            stage: Stage name for metrics
            backend: Backend name
            since_sequence: Sequence number for incremental metrics
        """
        # Record base client metrics
        self.base_client.record_cache_metrics(
            observation,
            stage=stage,
            backend=backend,
            since_sequence=since_sequence,
        )
        
        # Record enhanced cache metrics
        if self.enhanced_caching_enabled and self.cache_manager:
            self.cache_manager.record_cache_metrics(observation, stage)
    
    def warm_cache(self, patterns: Optional[List] = None) -> int:
        """
        Warm cache with frequently used patterns.
        
        Args:
            patterns: Specific patterns to warm (auto-detected if None)
        
        Returns:
            Number of cache entries warmed
        """
        if not self.enhanced_caching_enabled or self.cache_manager is None:
            logger.warning("Enhanced caching not enabled, cannot warm cache")
            return 0
        
        return self.cache_manager.warm_cache(patterns)
    
    def invalidate_cache_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching pattern.
        
        Args:
            pattern: Pattern to match for invalidation
        
        Returns:
            Number of entries invalidated
        """
        if not self.enhanced_caching_enabled or self.cache_manager is None:
            logger.warning("Enhanced caching not enabled, cannot invalidate pattern")
            return 0
        
        return self.cache_manager.invalidate_preemptively(pattern)
    
    def get_cache_status(self) -> Dict[str, Any]:
        """
        Get comprehensive cache status.
        
        Returns:
            Dictionary with cache status information
        """
        status = {
            "enhanced_caching_enabled": self.enhanced_caching_enabled,
            "base_client_configured": self.base_client.is_configured(),
        }
        
        # Base client stats
        base_stats = self.base_client.cache_stats()
        status["base_cache"] = {
            "enabled": base_stats.enabled,
            "hit_rate": base_stats.hit_rate,
            "size": base_stats.size,
            "requests": base_stats.requests,
        }
        
        # Enhanced cache stats
        if self.enhanced_caching_enabled and self.cache_manager:
            enhanced_metrics = self.cache_manager.get_cache_metrics()
            status["enhanced_cache"] = {
                "hit_rate": enhanced_metrics.hit_rate,
                "semantic_hit_rate": enhanced_metrics.semantic_hit_rate,
                "bad_cache_rate": enhanced_metrics.bad_cache_rate,
                "total_requests": enhanced_metrics.total_requests,
                "cache_warmings": enhanced_metrics.cache_warmings,
                "preemptive_invalidations": enhanced_metrics.preemptive_invalidations,
            }
        
        # Monitor status
        if self.cache_monitor:
            status["monitoring"] = self.cache_monitor.get_current_status()
        
        return status
    
    def optimize_cache(self) -> Dict[str, Any]:
        """
        Force cache optimization.
        
        Returns:
            Dictionary with optimization results
        """
        if not self.enhanced_caching_enabled or self.cache_manager is None:
            return {"error": "Enhanced caching not enabled"}
        
        # Warm cache
        warmed = self.cache_manager.warm_cache()
        
        # Invalidate bad cache entries
        invalidated = self.cache_manager.invalidate_preemptively("error")
        
        return {
            "cache_warmed": warmed,
            "bad_cache_invalidated": invalidated,
            "timestamp": time.time(),
        }
    
    def get_monitoring_alerts(self) -> List[Dict[str, Any]]:
        """
        Get current monitoring alerts.
        
        Returns:
            List of alert dictionaries
        """
        if not self.cache_monitor:
            return []
        
        status = self.cache_monitor.get_current_status()
        return status.get("alerts", {}).get("recent_alerts", [])
    
    def acknowledge_alerts(self, alert_types: Optional[List[str]] = None) -> int:
        """
        Acknowledge monitoring alerts.
        
        Args:
            alert_types: Specific alert types to acknowledge (all if None)
        
        Returns:
            Number of alerts acknowledged
        """
        if not self.cache_monitor:
            return 0
        
        return self.cache_monitor.acknowledge_alerts(alert_types)
    
    def shutdown(self) -> None:
        """Shutdown enhanced caching components."""
        if self.cache_monitor:
            self.cache_monitor.stop_monitoring()
        
        logger.info("Enhanced LLM client shutdown completed")


def create_enhanced_llm_client(
    backend: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    timeout_seconds: int | None = None,
    enable_enhanced_caching: bool = True,
    enable_monitoring: bool = True,
    **kwargs,
) -> EnhancedLLMClient:
    """
    Create enhanced LLM client with intelligent caching.
    
    Args:
        backend: LLM backend ("openai" or "claude")
        model: Model name
        temperature: Generation temperature
        timeout_seconds: Request timeout
        enable_enhanced_caching: Enable enhanced caching features
        enable_monitoring: Enable cache monitoring
        **kwargs: Additional arguments for base LLM client
    
    Returns:
        Configured enhanced LLM client
    """
    base_client = LLMClient(
        backend=backend,
        model=model,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        **kwargs,
    )
    
    return EnhancedLLMClient(
        base_client=base_client,
        enable_enhanced_caching=enable_enhanced_caching,
        enable_monitoring=enable_monitoring,
    )