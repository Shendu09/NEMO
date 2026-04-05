"""
NEMO Cache Layer - Performance Optimization

Provides intelligent caching for:
- Model caching (lazy-loaded, thread-safe)
- Screenshot element detection (by hash)
- Intent matching (by query)
- Text summarization (LRU with hash-based eviction)
- Vision inference results (by image hash)

Thread-safe with automatic cache invalidation.
"""

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("nemo.cache")


class LRUCache:
    """Thread-safe LRU cache with size limits."""
    
    def __init__(self, max_size: int = 100, ttl_seconds: Optional[int] = None):
        """
        Args:
            max_size: Maximum number of items to store
            ttl_seconds: Time-to-live for cache entries (None = no expiry)
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            
            value, timestamp = self.cache[key]
            
            # Check TTL
            if self.ttl_seconds and time.time() - timestamp > self.ttl_seconds:
                del self.cache[key]
                self.misses += 1
                return None
            
            # Move to end (mark as recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            return value
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            
            self.cache[key] = (value, time.time())
            
            # Evict oldest if over limit
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': f"{hit_rate:.1f}%",
                'total_requests': total,
            }


def hash_b64_image(image_b64: str, salt: str = "") -> str:
    """Generate hash of base64 image."""
    key = f"{image_b64[:100]}:{salt}"  # Use first 100 chars + salt
    return hashlib.md5(key.encode()).hexdigest()


def hash_text(text: str, salt: str = "") -> str:
    """Generate hash of text."""
    key = f"{text}:{salt}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


class CacheManager:
    """Global cache manager for NEMO models and inference results."""
    
    def __init__(self):
        """Initialize cache manager."""
        # Vision caches
        self.element_detection_cache = LRUCache(max_size=200, ttl_seconds=3600)  # 1 hour TTL
        self.screen_state_cache = LRUCache(max_size=100, ttl_seconds=1800)  # 30 min TTL
        self.florence2_cache = LRUCache(max_size=150, ttl_seconds=3600)
        
        # NLP caches
        self.intent_cache = LRUCache(max_size=500, ttl_seconds=7200)  # 2 hour TTL
        self.summary_cache = LRUCache(max_size=100, ttl_seconds=3600)
        
        # Statistics
        self.lock = threading.RLock()
        self.startup_time = time.time()
    
    def get_element_cached(
        self,
        screenshot_b64: str,
        target: str,
        fetch_fn: Callable,
    ) -> Dict[str, Any]:
        """
        Get element detection result with caching.
        
        Args:
            screenshot_b64: Base64 screenshot
            target: Element name
            fetch_fn: Function to call if cache miss (takes screenshot_b64, target)
        
        Returns:
            Element detection result
        """
        # Create cache key
        img_hash = hash_b64_image(screenshot_b64)
        cache_key = f"element:{img_hash}:{target}"
        
        # Try cache
        cached = self.element_detection_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT: {target} on screenshot {img_hash[:8]}")
            return cached
        
        # Cache miss - fetch
        logger.debug(f"Cache MISS: {target} on screenshot {img_hash[:8]}")
        result = fetch_fn(screenshot_b64, target)
        
        # Store result
        self.element_detection_cache.set(cache_key, result)
        return result
    
    def get_screen_state_cached(
        self,
        screenshot_b64: str,
        fetch_fn: Callable,
    ) -> Dict[str, Any]:
        """Get screen state with caching."""
        img_hash = hash_b64_image(screenshot_b64)
        cache_key = f"screen_state:{img_hash}"
        
        cached = self.screen_state_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT: screen state for {img_hash[:8]}")
            return cached
        
        logger.debug(f"Cache MISS: screen state for {img_hash[:8]}")
        result = fetch_fn(screenshot_b64)
        self.screen_state_cache.set(cache_key, result)
        return result
    
    def get_intent_cached(
        self,
        query: str,
        threshold: float,
        fetch_fn: Callable,
    ) -> Tuple[str, float]:
        """Get intent match with caching."""
        query_hash = hash_text(query, salt=str(threshold))
        cache_key = f"intent:{query_hash}"
        
        cached = self.intent_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT: intent for '{query[:30]}'")
            return cached
        
        logger.debug(f"Cache MISS: intent for '{query[:30]}'")
        result = fetch_fn(query, threshold=threshold)
        self.intent_cache.set(cache_key, result)
        return result
    
    def get_summary_cached(
        self,
        text: str,
        max_length: int,
        fetch_fn: Callable,
    ) -> str:
        """Get summary with caching."""
        text_hash = hash_text(text, salt=str(max_length))
        cache_key = f"summary:{text_hash}"
        
        cached = self.summary_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT: summary ({len(text)} chars)")
            return cached
        
        logger.debug(f"Cache MISS: summary ({len(text)} chars)")
        result = fetch_fn(text, max_length=max_length)
        self.summary_cache.set(cache_key, result)
        return result
    
    def get_florence2_cached(
        self,
        screenshot_b64: str,
        description: str,
        fetch_fn: Callable,
    ) -> Dict[str, Any]:
        """Get Florence-2 result with caching."""
        img_hash = hash_b64_image(screenshot_b64)
        cache_key = f"florence2:{img_hash}:{description}"
        
        cached = self.florence2_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT: Florence-2 '{description[:30]}' on {img_hash[:8]}")
            return cached
        
        logger.debug(f"Cache MISS: Florence-2 '{description[:30]}' on {img_hash[:8]}")
        result = fetch_fn(screenshot_b64, description)
        self.florence2_cache.set(cache_key, result)
        return result
    
    def clear_all(self) -> None:
        """Clear all caches."""
        self.element_detection_cache.clear()
        self.screen_state_cache.clear()
        self.intent_cache.clear()
        self.summary_cache.clear()
        self.florence2_cache.clear()
        logger.info("Cleared all caches")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            uptime = time.time() - self.startup_time
            return {
                'uptime_seconds': f"{uptime:.1f}",
                'element_detection': self.element_detection_cache.stats(),
                'screen_state': self.screen_state_cache.stats(),
                'intent': self.intent_cache.stats(),
                'summary': self.summary_cache.stats(),
                'florence2': self.florence2_cache.stats(),
            }


# Global cache instance
_cache_manager: Optional[CacheManager] = None
_cache_lock = threading.Lock()


def get_cache() -> CacheManager:
    """Get or create global cache manager."""
    global _cache_manager
    
    if _cache_manager is not None:
        return _cache_manager
    
    with _cache_lock:
        if _cache_manager is not None:
            return _cache_manager
        
        _cache_manager = CacheManager()
        logger.info("✓ Cache manager initialized")
        return _cache_manager
