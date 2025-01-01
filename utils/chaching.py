from typing import Optional, Any
from datetime import datetime, timedelta
import json
import os
import logging

logger = logging.getLogger(__name__)

class Cache:
    """File-based cache system with daily expiration"""
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = cache_dir
        self.cache_duration = timedelta(minutes=5)  # Reduced cache duration to 5 minutes
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def _get_cache_path(self, key: str) -> str:
        """Generate a safe filename for the cache key"""
        # Create a safe filename from the key
        safe_key = "".join(c for c in key if c.isalnum() or c in ('-', '_')).rstrip()
        return os.path.join(self.cache_dir, f"{safe_key}.json")
    
    def get(self, key: str) -> Optional[dict]:
        """Retrieve data from cache if not expired"""
        try:
            cache_path = self._get_cache_path(key)
            if not os.path.exists(cache_path):
                return None
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # Check if cache has expired
            cached_time = datetime.fromisoformat(cached_data['timestamp'])
            if datetime.now() - cached_time > self.cache_duration:
                os.remove(cache_path)  # Clean up expired cache
                return None
                
            return cached_data['data']
            
        except Exception as e:
            logger.warning(f"Cache read error for {key}: {e}")
            return None
    
    def set(self, key: str, data: Any) -> None:
        """Store data in cache with timestamp"""
        try:
            cache_path = self._get_cache_path(key)
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.warning(f"Cache write error for {key}: {e}")

    def clear(self):
        """Clear all cached files"""
        if os.path.exists(self.cache_dir):
            for file in os.listdir(self.cache_dir):
                try:
                    os.remove(os.path.join(self.cache_dir, file))
                except OSError as e:
                    logger.warning(f"Failed to remove cache file {file}: {e}")