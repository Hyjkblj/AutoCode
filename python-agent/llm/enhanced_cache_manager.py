"""
Enhanced LLM cache manager with intelligent key generation and monitoring.

This module provides advanced caching capabilities for LLM requests including:
- Intelligent cache key generation with semantic similarity
- Cache hit rate monitoring and bad cache detection
- Cache warming and preemptive invalidation strategies
- Redis-based distributed caching with fallback to local cache

Requirements: 12.4
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple

from config.cache_config import CacheConfig, DEFAULT_CACHE_CONFIG
from utils.observability import TaskObservability

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheKeyComponents:
    """Components used for intelligent cache key generation."""
    
    # Core request components
    backend: str
    model: str
    temperature: float
    messages: List[Dict[str, str]]
    
    # Semantic components for intelligent grouping
    intent_hash: str  # Hash of extracted intent/purpose
    context_hash: str  # Hash of relevant context
    template_hash: str  # Hash of prompt template structure
    
    # Metadata for cache management
    complexity_score: float  # Estimated complexity (0.0-1.0)
    cache_priority: str  # "high", "medium", "low"


@dataclass
class CacheMetrics:
    """Comprehensive cache performance metrics."""
    
    # Basic metrics
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_bypasses: int = 0
    cache_failures: int = 0
    
    # Advanced metrics
    semantic_hits: int = 0  # Hits from semantic similarity
    bad_cache_detections: int = 0
    preemptive_invalidations: int = 0
    cache_warmings: int = 0
    
    # Performance metrics
    avg_response_time_cached: float = 0.0
    avg_response_time_uncached: float = 0.0
    cache_size_bytes: int = 0
    
    # Time-based metrics
    last_reset_time: float = field(default_factory=time.time)
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total) if total > 0 else 0.0
    
    @property
    def semantic_hit_rate(self) -> float:
        """Calculate semantic similarity hit rate."""
        return (self.semantic_hits / self.cache_hits) if self.cache_hits > 0 else 0.0
    
    @property
    def bad_cache_rate(self) -> float:
        """Calculate bad cache detection rate."""
        return (self.bad_cache_detections / self.total_requests) if self.total_requests > 0 else 0.0


@dataclass
class CacheEntry:
    """Enhanced cache entry with metadata for intelligent management."""
    
    value: str
    created_at: float
    last_accessed: float
    access_count: int
    key_components: CacheKeyComponents
    response_time: float
    quality_score: float  # Quality assessment (0.0-1.0)
    
    # Flags for cache management
    is_warmed: bool = False
    is_validated: bool = False
    invalidation_scheduled: bool = False


class EnhancedCacheManager:
    """
    Enhanced LLM cache manager with intelligent key generation and monitoring.
    
    This manager provides advanced caching capabilities including:
    - Semantic similarity-based cache key generation
    - Real-time cache performance monitoring
    - Bad cache detection and automatic invalidation
    - Proactive cache warming for frequently used patterns
    - Redis-based distributed caching with local fallback
    """
    
    def __init__(
        self,
        config: Optional[CacheConfig] = None,
        redis_client: Optional[Any] = None,
        namespace: str = "autocode:llm_cache",
    ) -> None:
        """
        Initialize enhanced cache manager.
        
        Args:
            config: Cache configuration (uses default if None)
            redis_client: Pre-configured Redis client (optional)
            namespace: Redis key namespace for cache data
        """
        self.config = config or DEFAULT_CACHE_CONFIG
        self.namespace = namespace
        self._lock = Lock()
        
        # Initialize Redis client
        self._redis_client = redis_client
        self._redis_available = False
        self._init_redis()
        
        # Local cache fallback
        self._local_cache: Dict[str, CacheEntry] = {}
        
        # Metrics and monitoring
        self.metrics = CacheMetrics()
        self._key_patterns: Dict[str, int] = defaultdict(int)
        self._bad_cache_keys: Set[str] = set()
        self._warming_queue: List[CacheKeyComponents] = []
        
        # Semantic similarity tracking
        self._intent_patterns: Dict[str, List[str]] = defaultdict(list)
        self._template_patterns: Dict[str, List[str]] = defaultdict(list)
        
        logger.info(
            "Enhanced cache manager initialized: redis_available=%s namespace=%s",
            self._redis_available,
            self.namespace,
        )
    
    def _init_redis(self) -> None:
        """Initialize Redis connection with fallback handling."""
        if self._redis_client is not None:
            self._redis_available = True
            return
        
        try:
            import redis
            
            redis_url = os.getenv("MVP_REDIS_URL", "redis://127.0.0.1:6379/0")
            pool = redis.ConnectionPool.from_url(
                redis_url,
                **self.config.redis_connection_kwargs(),
            )
            self._redis_client = redis.Redis(connection_pool=pool)
            
            # Test connection
            self._redis_client.ping()
            self._redis_available = True
            logger.info("Redis cache backend initialized successfully")
            
        except Exception as e:
            logger.warning("Redis unavailable, falling back to local cache: %s", e)
            self._redis_available = False
    
    def generate_cache_key(self, messages: List[Dict[str, str]], **kwargs) -> Tuple[str, CacheKeyComponents]:
        """
        Generate intelligent cache key with semantic analysis.
        
        Args:
            messages: LLM conversation messages
            **kwargs: Additional parameters (backend, model, temperature, etc.)
        
        Returns:
            Tuple of (cache_key, key_components)
        """
        # Extract basic components
        backend = kwargs.get("backend", "openai")
        model = kwargs.get("model", "gpt-4")
        temperature = kwargs.get("temperature", 0.2)
        
        # Analyze message content for semantic components
        intent_hash = self._extract_intent_hash(messages)
        context_hash = self._extract_context_hash(messages)
        template_hash = self._extract_template_hash(messages)
        
        # Calculate complexity and priority
        complexity_score = self._calculate_complexity_score(messages)
        cache_priority = self._determine_cache_priority(messages, complexity_score)
        
        # Create key components
        components = CacheKeyComponents(
            backend=backend,
            model=model,
            temperature=temperature,
            messages=messages,
            intent_hash=intent_hash,
            context_hash=context_hash,
            template_hash=template_hash,
            complexity_score=complexity_score,
            cache_priority=cache_priority,
        )
        
        # Generate cache key with semantic grouping
        cache_key = self._build_semantic_cache_key(components)
        
        # Track patterns for warming
        self._track_key_patterns(components)
        
        return cache_key, components
    
    def get_cached_response(self, cache_key: str) -> Tuple[bool, str, Optional[CacheEntry]]:
        """
        Retrieve cached response with hit rate monitoring.
        
        Args:
            cache_key: Cache key to lookup
        
        Returns:
            Tuple of (hit, response, cache_entry)
        """
        start_time = time.time()
        
        with self._lock:
            self.metrics.total_requests += 1
        
        # Check for bad cache
        if cache_key in self._bad_cache_keys:
            with self._lock:
                self.metrics.cache_bypasses += 1
            return False, "", None
        
        # Try Redis first if available
        if self._redis_available:
            try:
                entry = self._get_from_redis(cache_key)
                if entry is not None:
                    self._record_cache_hit(entry, time.time() - start_time)
                    return True, entry.value, entry
            except Exception as e:
                logger.warning("Redis cache get failed: %s", e)
                with self._lock:
                    self.metrics.cache_failures += 1
        
        # Fallback to local cache
        entry = self._local_cache.get(cache_key)
        if entry is not None:
            # Check TTL
            if time.time() - entry.created_at < self.config.llm_response_ttl:
                self._record_cache_hit(entry, time.time() - start_time)
                return True, entry.value, entry
            else:
                # Expired entry
                del self._local_cache[cache_key]
        
        # Cache miss
        with self._lock:
            self.metrics.cache_misses += 1
        
        return False, "", None
    
    def store_cached_response(
        self,
        cache_key: str,
        response: str,
        components: CacheKeyComponents,
        response_time: float,
    ) -> None:
        """
        Store response in cache with quality assessment.
        
        Args:
            cache_key: Cache key for storage
            response: LLM response to cache
            components: Cache key components
            response_time: Time taken to generate response
        """
        # Assess response quality
        quality_score = self._assess_response_quality(response, components)
        
        # Skip caching low-quality responses
        if quality_score < 0.3:
            logger.debug("Skipping cache storage for low-quality response: %s", cache_key[:16])
            return
        
        # Create cache entry
        entry = CacheEntry(
            value=response,
            created_at=time.time(),
            last_accessed=time.time(),
            access_count=1,
            key_components=components,
            response_time=response_time,
            quality_score=quality_score,
        )
        
        # Store in Redis if available
        if self._redis_available:
            try:
                self._store_in_redis(cache_key, entry)
            except Exception as e:
                logger.warning("Redis cache store failed: %s", e)
                with self._lock:
                    self.metrics.cache_failures += 1
        
        # Store in local cache
        with self._lock:
            self._local_cache[cache_key] = entry
            
            # Evict old entries if needed
            if len(self._local_cache) > 1000:  # Local cache size limit
                oldest_key = min(
                    self._local_cache.keys(),
                    key=lambda k: self._local_cache[k].last_accessed,
                )
                del self._local_cache[oldest_key]
    
    def detect_bad_cache(self, cache_key: str, response: str, expected_quality: float = 0.5) -> bool:
        """
        Detect and mark bad cache entries.
        
        Args:
            cache_key: Cache key to check
            response: Response to evaluate
            expected_quality: Minimum expected quality threshold
        
        Returns:
            True if bad cache detected
        """
        # Simple heuristics for bad cache detection
        is_bad = (
            len(response.strip()) < 10 or  # Too short
            response.count("error") > 2 or  # Too many errors
            response.count("sorry") > 1 or  # Apologetic responses
            "I cannot" in response or  # Refusal responses
            "I don't know" in response  # Uncertain responses
        )
        
        if is_bad:
            with self._lock:
                self._bad_cache_keys.add(cache_key)
                self.metrics.bad_cache_detections += 1
            
            # Remove from caches
            self._invalidate_cache_entry(cache_key)
            
            logger.info("Bad cache detected and invalidated: %s", cache_key[:16])
            return True
        
        return False
    
    def warm_cache(self, patterns: Optional[List[CacheKeyComponents]] = None) -> int:
        """
        Proactively warm cache with frequently used patterns.
        
        Args:
            patterns: Specific patterns to warm (uses auto-detected if None)
        
        Returns:
            Number of cache entries warmed
        """
        if patterns is None:
            patterns = self._get_warming_candidates()
        
        warmed_count = 0
        for components in patterns[:10]:  # Limit warming batch size
            cache_key = self._build_semantic_cache_key(components)
            
            # Skip if already cached
            hit, _, _ = self.get_cached_response(cache_key)
            if hit:
                continue
            
            # Mark as warming candidate
            self._warming_queue.append(components)
            warmed_count += 1
        
        with self._lock:
            self.metrics.cache_warmings += warmed_count
        
        logger.info("Cache warming completed: %d entries queued", warmed_count)
        return warmed_count
    
    def invalidate_preemptively(self, pattern: str) -> int:
        """
        Preemptively invalidate cache entries matching pattern.
        
        Args:
            pattern: Pattern to match for invalidation
        
        Returns:
            Number of entries invalidated
        """
        invalidated_count = 0
        
        # Invalidate from Redis
        if self._redis_available:
            try:
                keys = self._redis_client.keys(f"{self.namespace}:*{pattern}*")
                if keys:
                    self._redis_client.delete(*keys)
                    invalidated_count += len(keys)
            except Exception as e:
                logger.warning("Redis preemptive invalidation failed: %s", e)
        
        # Invalidate from local cache
        with self._lock:
            keys_to_remove = [
                key for key in self._local_cache.keys()
                if pattern in key
            ]
            for key in keys_to_remove:
                del self._local_cache[key]
            invalidated_count += len(keys_to_remove)
            
            self.metrics.preemptive_invalidations += invalidated_count
        
        logger.info("Preemptive invalidation completed: %d entries removed", invalidated_count)
        return invalidated_count
    
    def get_cache_metrics(self) -> CacheMetrics:
        """Get current cache performance metrics."""
        with self._lock:
            # Update cache size
            self.metrics.cache_size_bytes = self._calculate_cache_size()
            return self.metrics
    
    def record_cache_metrics(self, observation: TaskObservability, stage: str = "LLM") -> None:
        """
        Record cache metrics to observability system.
        
        Args:
            observation: Task observability instance
            stage: Stage name for metrics
        """
        metrics = self.get_cache_metrics()
        
        # Record basic metrics
        observation.record_metric("llm_cache_hit_rate", metrics.hit_rate, unit="ratio", stage=stage)
        observation.record_metric("llm_cache_requests_total", metrics.total_requests, stage=stage)
        observation.record_metric("llm_cache_hits_total", metrics.cache_hits, stage=stage)
        observation.record_metric("llm_cache_misses_total", metrics.cache_misses, stage=stage)
        
        # Record advanced metrics
        observation.record_metric("llm_cache_semantic_hit_rate", metrics.semantic_hit_rate, unit="ratio", stage=stage)
        observation.record_metric("llm_cache_bad_detections_total", metrics.bad_cache_detections, stage=stage)
        observation.record_metric("llm_cache_warmings_total", metrics.cache_warmings, stage=stage)
        observation.record_metric("llm_cache_invalidations_total", metrics.preemptive_invalidations, stage=stage)
        
        # Record performance metrics
        if metrics.avg_response_time_cached > 0:
            observation.record_metric("llm_cache_response_time_cached", metrics.avg_response_time_cached, unit="seconds", stage=stage)
        if metrics.avg_response_time_uncached > 0:
            observation.record_metric("llm_cache_response_time_uncached", metrics.avg_response_time_uncached, unit="seconds", stage=stage)
        
        observation.record_metric("llm_cache_size_bytes", metrics.cache_size_bytes, unit="bytes", stage=stage)
    
    def reset_metrics(self) -> None:
        """Reset cache metrics."""
        with self._lock:
            self.metrics = CacheMetrics()
    
    # Private helper methods
    
    def _extract_intent_hash(self, messages: List[Dict[str, str]]) -> str:
        """Extract intent hash from messages for semantic grouping."""
        # Combine all user messages to understand intent
        user_content = " ".join(
            msg.get("content", "") for msg in messages
            if msg.get("role") == "user"
        )
        
        # Extract key intent indicators
        intent_keywords = []
        
        # Common intent patterns
        if re.search(r'\b(generate|create|build|make)\b', user_content, re.IGNORECASE):
            intent_keywords.append("generate")
        if re.search(r'\b(fix|repair|debug|solve)\b', user_content, re.IGNORECASE):
            intent_keywords.append("fix")
        if re.search(r'\b(analyze|review|check|examine)\b', user_content, re.IGNORECASE):
            intent_keywords.append("analyze")
        if re.search(r'\b(test|validate|verify)\b', user_content, re.IGNORECASE):
            intent_keywords.append("test")
        
        # Code-specific intents
        if re.search(r'\b(function|class|method|api)\b', user_content, re.IGNORECASE):
            intent_keywords.append("code")
        if re.search(r'\b(frontend|backend|fullstack|web)\b', user_content, re.IGNORECASE):
            intent_keywords.append("web")
        
        intent_string = "|".join(sorted(intent_keywords))
        return hashlib.md5(intent_string.encode()).hexdigest()[:8]
    
    def _extract_context_hash(self, messages: List[Dict[str, str]]) -> str:
        """Extract context hash for semantic similarity."""
        # Extract system prompts and context
        system_content = " ".join(
            msg.get("content", "") for msg in messages
            if msg.get("role") == "system"
        )
        
        # Normalize and hash context
        normalized = re.sub(r'\s+', ' ', system_content.lower().strip())
        return hashlib.md5(normalized.encode()).hexdigest()[:8]
    
    def _extract_template_hash(self, messages: List[Dict[str, str]]) -> str:
        """Extract template structure hash."""
        # Create template from message structure
        template_parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            # Extract template structure (remove specific values)
            template_content = re.sub(r'\b\d+\b', 'NUM', content)
            template_content = re.sub(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', 'VAR', template_content)
            template_content = re.sub(r'\s+', ' ', template_content.strip())
            
            template_parts.append(f"{role}:{template_content[:100]}")
        
        template_string = "|".join(template_parts)
        return hashlib.md5(template_string.encode()).hexdigest()[:8]
    
    def _calculate_complexity_score(self, messages: List[Dict[str, str]]) -> float:
        """Calculate complexity score for cache prioritization."""
        total_length = sum(len(msg.get("content", "")) for msg in messages)
        message_count = len(messages)
        
        # Base complexity on length and message count
        length_score = min(total_length / 5000, 1.0)  # Normalize to 0-1
        count_score = min(message_count / 10, 1.0)  # Normalize to 0-1
        
        # Adjust for content complexity
        complexity_indicators = 0
        for msg in messages:
            content = msg.get("content", "")
            if "```" in content:  # Code blocks
                complexity_indicators += 1
            if len(re.findall(r'\n', content)) > 10:  # Multi-line
                complexity_indicators += 1
            if re.search(r'\b(algorithm|optimization|performance)\b', content, re.IGNORECASE):
                complexity_indicators += 1
        
        complexity_bonus = min(complexity_indicators * 0.2, 0.5)
        
        return min(length_score + count_score + complexity_bonus, 1.0)
    
    def _determine_cache_priority(self, messages: List[Dict[str, str]], complexity_score: float) -> str:
        """Determine cache priority based on content analysis."""
        if complexity_score > 0.7:
            return "high"
        elif complexity_score > 0.4:
            return "medium"
        else:
            return "low"
    
    def _build_semantic_cache_key(self, components: CacheKeyComponents) -> str:
        """Build cache key with semantic grouping."""
        # Create semantic key components
        semantic_parts = [
            components.backend,
            components.model,
            f"temp_{components.temperature:.1f}",
            f"intent_{components.intent_hash}",
            f"ctx_{components.context_hash}",
            f"tpl_{components.template_hash}",
            f"pri_{components.cache_priority}",
        ]
        
        # Add message hash for exact matching
        message_json = json.dumps(components.messages, sort_keys=True, separators=(',', ':'))
        message_hash = hashlib.sha256(message_json.encode()).hexdigest()[:16]
        semantic_parts.append(f"msg_{message_hash}")
        
        return ":".join(semantic_parts)
    
    def _track_key_patterns(self, components: CacheKeyComponents) -> None:
        """Track key patterns for cache warming."""
        pattern_key = f"{components.intent_hash}:{components.template_hash}"
        with self._lock:
            self._key_patterns[pattern_key] += 1
            
            # Track intent and template patterns
            self._intent_patterns[components.intent_hash].append(components.cache_priority)
            self._template_patterns[components.template_hash].append(components.backend)
    
    def _record_cache_hit(self, entry: CacheEntry, lookup_time: float) -> None:
        """Record cache hit with metrics update."""
        with self._lock:
            self.metrics.cache_hits += 1
            entry.access_count += 1
            entry.last_accessed = time.time()
            
            # Update average response times
            if self.metrics.cache_hits == 1:
                self.metrics.avg_response_time_cached = lookup_time
            else:
                self.metrics.avg_response_time_cached = (
                    (self.metrics.avg_response_time_cached * (self.metrics.cache_hits - 1) + lookup_time) /
                    self.metrics.cache_hits
                )
    
    def _assess_response_quality(self, response: str, components: CacheKeyComponents) -> float:
        """Assess response quality for cache storage decisions."""
        score = 1.0
        
        # Length-based assessment
        if len(response.strip()) < 20:
            score -= 0.4
        elif len(response.strip()) > 1000:
            score += 0.1
        
        # Content quality indicators
        if "error" in response.lower():
            score -= 0.3
        if "sorry" in response.lower():
            score -= 0.2
        if "I cannot" in response or "I don't know" in response:
            score -= 0.5
        
        # Positive indicators
        if "```" in response:  # Code blocks
            score += 0.2
        if response.count('\n') > 5:  # Well-structured
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _get_from_redis(self, cache_key: str) -> Optional[CacheEntry]:
        """Get cache entry from Redis."""
        if not self._redis_available:
            return None
        
        redis_key = f"{self.namespace}:{cache_key}"
        data = self._redis_client.get(redis_key)
        
        if data is None:
            return None
        
        try:
            entry_data = json.loads(data)
            return CacheEntry(**entry_data)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to deserialize cache entry: %s", e)
            return None
    
    def _store_in_redis(self, cache_key: str, entry: CacheEntry) -> None:
        """Store cache entry in Redis."""
        if not self._redis_available:
            return
        
        redis_key = f"{self.namespace}:{cache_key}"
        entry_data = {
            "value": entry.value,
            "created_at": entry.created_at,
            "last_accessed": entry.last_accessed,
            "access_count": entry.access_count,
            "key_components": entry.key_components.__dict__,
            "response_time": entry.response_time,
            "quality_score": entry.quality_score,
            "is_warmed": entry.is_warmed,
            "is_validated": entry.is_validated,
            "invalidation_scheduled": entry.invalidation_scheduled,
        }
        
        self._redis_client.setex(
            redis_key,
            self.config.llm_response_ttl,
            json.dumps(entry_data),
        )
    
    def _invalidate_cache_entry(self, cache_key: str) -> None:
        """Invalidate cache entry from all storage."""
        # Remove from Redis
        if self._redis_available:
            try:
                redis_key = f"{self.namespace}:{cache_key}"
                self._redis_client.delete(redis_key)
            except Exception as e:
                logger.warning("Redis cache invalidation failed: %s", e)
        
        # Remove from local cache
        with self._lock:
            self._local_cache.pop(cache_key, None)
    
    def _get_warming_candidates(self) -> List[CacheKeyComponents]:
        """Get cache warming candidates based on usage patterns."""
        candidates = []
        
        with self._lock:
            # Find frequently used patterns
            frequent_patterns = [
                pattern for pattern, count in self._key_patterns.items()
                if count >= 3  # Used at least 3 times
            ]
        
        # Create warming candidates (simplified for now)
        for pattern in frequent_patterns[:5]:  # Limit candidates
            intent_hash, template_hash = pattern.split(":", 1)
            
            # Create synthetic components for warming
            components = CacheKeyComponents(
                backend="openai",
                model="gpt-4",
                temperature=0.2,
                messages=[{"role": "user", "content": "warming_placeholder"}],
                intent_hash=intent_hash,
                context_hash="warming",
                template_hash=template_hash,
                complexity_score=0.5,
                cache_priority="medium",
            )
            candidates.append(components)
        
        return candidates
    
    def _calculate_cache_size(self) -> int:
        """Calculate approximate cache size in bytes."""
        size = 0
        
        # Local cache size
        for entry in self._local_cache.values():
            size += len(entry.value.encode('utf-8'))
            size += 200  # Approximate metadata size
        
        return size