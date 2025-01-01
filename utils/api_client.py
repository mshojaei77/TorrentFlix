import requests
import logging

logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self):
        self.base_url = "https://api.example.com/movies"  # Replace with actual API endpoint
        # Initialize other parameters like API keys if needed
    
    def get_movies(self, category="All"):
        # Fetch movies from API based on category
        try:
            params = {"category": category} if category != "All" else {}
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            # Assuming API returns {'movies': [...]}
            return data.get("movies", [])
        except Exception as e:
            logger.error(f"Error fetching movies: {e}")
            return []
        
    def search_movies(self, query):
        # Search movies based on query
        try:
            params = {"search": query}
            response = requests.get(f"{self.base_url}/search", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            logger.error(f"Error searching movies: {e}")
            return []
        
    def get_user_list(self, list_name):
        # Fetch user's list like Watchlist, Watched, etc.
        try:
            response = requests.get(f"{self.base_url}/user/{list_name}")
            response.raise_for_status()
            data = response.json()
            return data.get("movies", [])
        except Exception as e:
            logger.error(f"Error fetching user list '{list_name}': {e}")
            return []