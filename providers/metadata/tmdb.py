from typing import Optional, Dict, Any
import requests
import time

TMDB_API_KEY = "917cce472ff1093d25cd89d8c007aacd"  # Replace with your key


class TMDBClient:
    """Helper class to manage TMDB API calls"""
    BASE_URL = "https://api.themoviedb.org/3"
    CACHE_DURATION = 3600  # 1 hour cache

    def __init__(self):
        self.api_key = TMDB_API_KEY
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}  # Add timestamp tracking
    
    def search_tv_show(self, title: str) -> Optional[dict]:
        """Search for a TV show with improved caching"""
        cache_key = f"search_{title}"
        
        # Check cache with expiration
        current_time = time.time()
        if cache_key in self._cache:
            if current_time - self._cache_timestamps[cache_key] < self.CACHE_DURATION:
                return self._cache[cache_key]
            else:
                # Remove expired cache entry
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]

        url = f"{self.BASE_URL}/search/tv"
        params = {
            'api_key': self.api_key,
            'query': title,
            'language': 'en-US'
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get('results'):
            self._cache[cache_key] = data['results'][0]
            self._cache_timestamps[cache_key] = current_time
            return data['results'][0]
        return None

    def get_tv_details(self, show_id: int) -> Optional[dict]:
        """Get detailed TV show info with improved caching"""
        cache_key = f"details_{show_id}"
        
        # Check cache with expiration
        current_time = time.time()
        if cache_key in self._cache:
            if current_time - self._cache_timestamps[cache_key] < self.CACHE_DURATION:
                return self._cache[cache_key]
            else:
                # Remove expired cache entry
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]

        url = f"{self.BASE_URL}/tv/{show_id}"
        params = {
            'api_key': self.api_key,
            'language': 'en-US',
            'append_to_response': 'credits,videos'
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        self._cache[cache_key] = data
        self._cache_timestamps[cache_key] = current_time
        return data
