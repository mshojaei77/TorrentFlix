from typing import Optional


class MovieSearchError(Exception):
    """Base exception for movie search errors"""
    pass

class MovieAPIError(MovieSearchError):
    """Raised when the movie API returns an error"""
    pass

class ConnectionBlockedError(MovieSearchError):
    """Raised when connection is blocked or reset"""
    pass