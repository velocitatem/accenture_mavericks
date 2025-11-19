"""Redis cache wrapper for pipeline operations."""
import os
import json
import hashlib
import logging
from typing import Any, Optional, Callable
from functools import wraps
from decimal import Decimal
import redis

logger = logging.getLogger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Pydantic models and Decimal types."""

    def default(self, obj):
        if hasattr(obj, 'model_dump'):
            # Pydantic model
            return obj.model_dump()
        elif isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class PipelineCache:
    """Redis-based cache for pipeline operations."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        db: int = 0,
        ttl: int = 86400,  # 24 hours default
        enabled: bool = True
    ):
        """Initialize Redis cache.

        Args:
            host: Redis host (defaults to REDIS_HOST env or 'localhost')
            port: Redis port (defaults to REDIS_PORT env or 6379)
            db: Redis database number
            ttl: Time to live for cache entries in seconds
            enabled: Whether caching is enabled
        """
        self.enabled = enabled
        self.ttl = ttl

        if not self.enabled:
            logger.info("Cache disabled")
            return

        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = int(port or os.getenv('REDIS_PORT', 6379))
        self.db = db

        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.client.ping()
            logger.info(f"Redis cache connected: {self.host}:{self.port}/{self.db}")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Redis connection failed: {e}. Disabling cache.")
            self.enabled = False

    def _generate_key(self, prefix: str, data: Any) -> str:
        """Generate cache key from data.

        Args:
            prefix: Key prefix (e.g., 'ocr', 'llm', 'validation')
            data: Data to hash

        Returns:
            Cache key string
        """
        # Create deterministic hash of input data
        if isinstance(data, (str, bytes)):
            content = data if isinstance(data, bytes) else data.encode()
        else:
            content = json.dumps(data, sort_keys=True, cls=CustomJSONEncoder).encode()

        hash_digest = hashlib.sha256(content).hexdigest()
        return f"pipeline:{prefix}:{hash_digest}"

    def get(self, prefix: str, data: Any) -> Optional[Any]:
        """Get cached result.

        Args:
            prefix: Cache key prefix
            data: Input data to generate key

        Returns:
            Cached result or None
        """
        if not self.enabled:
            return None

        try:
            key = self._generate_key(prefix, data)
            cached = self.client.get(key)

            if cached:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(cached)

            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None

    def set(self, prefix: str, data: Any, result: Any) -> bool:
        """Store result in cache.

        Args:
            prefix: Cache key prefix
            data: Input data to generate key
            result: Result to cache

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            key = self._generate_key(prefix, data)
            # Serialize result using custom encoder
            serialized = json.dumps(result, cls=CustomJSONEncoder)

            self.client.setex(key, self.ttl, serialized)
            logger.debug(f"Cache SET: {key} (TTL: {self.ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False

    def invalidate(self, prefix: str, data: Any = None) -> int:
        """Invalidate cache entries.

        Args:
            prefix: Cache key prefix
            data: Specific data to invalidate, or None for all with prefix

        Returns:
            Number of keys deleted
        """
        if not self.enabled:
            return 0

        try:
            if data is not None:
                key = self._generate_key(prefix, data)
                deleted = self.client.delete(key)
            else:
                # Delete all keys with prefix
                pattern = f"pipeline:{prefix}:*"
                keys = list(self.client.scan_iter(pattern))
                deleted = self.client.delete(*keys) if keys else 0

            logger.info(f"Cache invalidated: {deleted} keys")
            return deleted
        except Exception as e:
            logger.warning(f"Cache invalidate error: {e}")
            return 0

    def clear_all(self) -> bool:
        """Clear all pipeline cache entries.

        Returns:
            True if successful
        """
        if not self.enabled:
            return False

        try:
            pattern = "pipeline:*"
            keys = list(self.client.scan_iter(pattern))
            if keys:
                self.client.delete(*keys)
            logger.info(f"Cache cleared: {len(keys)} keys")
            return True
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")
            return False


def cached_step(prefix: str, cache: PipelineCache):
    """Decorator to cache pipeline step results.

    Args:
        prefix: Cache key prefix for this step
        cache: PipelineCache instance

    Example:
        @cached_step('ocr', cache)
        def ocr_wrapper(pdf_path: str) -> str:
            return ocr_pdf(pdf_path)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(data: Any) -> Any:
            # Try to get from cache
            cached_result = cache.get(prefix, data)
            if cached_result is not None:
                logger.info(f"Using cached result for {func.__name__}")
                return cached_result

            # Execute function
            logger.info(f"Executing {func.__name__} (no cache)")
            result = func(data)

            # Store in cache
            cache.set(prefix, data, result)
            return result

        return wrapper
    return decorator


# Global cache instance
_cache_instance: Optional[PipelineCache] = None


def get_cache(
    host: str = None,
    port: int = None,
    ttl: int = 86400,
    enabled: bool = None
) -> PipelineCache:
    """Get or create global cache instance.

    Args:
        host: Redis host
        port: Redis port
        ttl: Cache TTL in seconds
        enabled: Whether caching is enabled (defaults to CACHE_ENABLED env or True)

    Returns:
        PipelineCache instance
    """
    global _cache_instance

    if _cache_instance is None:
        if enabled is None:
            enabled = os.getenv('CACHE_ENABLED', 'true').lower() == 'true'

        _cache_instance = PipelineCache(
            host=host,
            port=port,
            ttl=ttl,
            enabled=enabled
        )

    return _cache_instance
