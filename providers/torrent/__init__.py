from utils.chaching import Cache
import requests
import os
import time
import logging

logger = logging.getLogger(__name__)

class BaseTorrentSearcher:
    def __init__(self):
        self.current_source = None
        self._session = self._create_session()
        self.cache = Cache()  # File-based cache
        self._request_cache = {}  # In-memory session cache for URLs

    def clear_cache(self):
        """Clear both in-memory and file caches"""
        self._request_cache.clear()
        if os.path.exists(self.cache.cache_dir):
            for file in os.listdir(self.cache.cache_dir):
                os.remove(os.path.join(self.cache.cache_dir, file))

    def _create_session(self) -> requests.Session:
        """Create a configured requests session"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        })
        return session

    def _make_request(self, url: str, method: str = 'GET', **kwargs) -> requests.Response:
        """Make a request with session-level caching"""
        # Add query parameter to cache key to differentiate between searches
        cache_key = f"{method}:{url}:{kwargs.get('params', {}).get('query_term', '')}"
        
        # Check if cache is still valid (implement cache expiration)
        if cache_key in self._request_cache:
            cache_time = self._request_cache.get(f"{cache_key}_timestamp", 0)
            if time.time() - cache_time > 300:  # 5 minutes cache expiration
                del self._request_cache[cache_key]
            else:
                logger.debug(f"Using cached response for: {url}")
                return self._request_cache[cache_key]
            
        # Make the actual request
        response = self._session.request(method, url, **kwargs)
        
        # Cache successful responses with timestamp
        if response.status_code == 200:
            self._request_cache[cache_key] = response
            self._request_cache[f"{cache_key}_timestamp"] = time.time()
            
        return response

    def _get_image_url(self, url: str) -> str:
        """Handle image URL redirects with caching"""
        cache_key = f"image_redirect:{url}"
        
        # Check cache first
        if cache_key in self._request_cache:
            return self._request_cache[cache_key]
            
        try:
            response = self._session.head(url, allow_redirects=True)
            final_url = response.url
            
            # Cache the final URL after redirect
            self._request_cache[cache_key] = final_url
            return final_url
            
        except Exception as e:
            logger.warning(f"Failed to resolve image URL {url}: {e}")
            return url