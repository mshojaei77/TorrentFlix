from providers.metadata.metacritic import MetacriticSource
from providers.metadata.rotten_tomatoes import RottenTomatoesSource
from providers.metadata.tmdb import TMDBClient
from domin.models import Movie, Torrent, TorrentSource
from utils.chaching import Cache
from providers.metadata import MetadataSource
from utils.error_hadlings import MovieSearchError, MovieAPIError, ConnectionBlockedError
from utils.http_client import make_api_request
from providers.torrent import BaseTorrentSearcher
from providers.torrent.yts_searcher import YTSSearcher
from providers.torrent.leetx_searcher import LeetxTVSearcher
import logging
import requests
from typing import List, Optional, Any
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
from collections import defaultdict
import time
import json
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class MovieMetadata:
    def __init__(self):
        self.sources = {
            'metacritic': MetacriticSource(),
            'rottentomatoes': RottenTomatoesSource(),
            # Add more sources here as needed
        }

    def get_metadata(self, title: str, year: int, sources: List[str] = None) -> dict:
        """
        Get metadata from specified sources for a movie
        
        Args:
            title: Movie title
            year: Release year
            sources: List of source names to query (defaults to all)
            
        Returns:
            Dictionary containing metadata from each source
        """
        if sources is None:
            sources = list(self.sources.keys())
            
        metadata = {}
        
        for source_name in sources:
            if source_name not in self.sources:
                logger.warning(f"Unknown metadata source: {source_name}")
                continue
                
            source = self.sources[source_name]
            try:
                url = source.get_url(title, year)
                if url:
                    info = source.get_info(url)
                    metadata[source_name] = {
                        'url': url,
                        'info': info
                    }
            except Exception as e:
                logger.error(f"Error getting metadata from {source_name}: {e}")
                metadata[source_name] = {'error': str(e)}
                
        return metadata

        

class TorrentSearcher:
    def __init__(self):
        self.searchers = {
            TorrentSource.YTS: YTSSearcher(),
            TorrentSource.LEETX: LeetxTVSearcher(),
            # Add more searchers here as needed
        }

    def search(self, query: str, source: TorrentSource, limit: int = 50) -> List[Movie]:
        """
        Search torrents based on the source.

        Args:
            query: Search query.
            source: Torrent source enum.
            limit: Maximum number of results to return.

        Returns:
            List of Movie objects.
        """
        if source not in self.searchers:
            logger.warning(f"Unsupported torrent source: {source.config['name']}")
            raise ValueError(f"Unsupported torrent source: {source.config['name']}")

        searcher = self.searchers[source]
        if isinstance(searcher, YTSSearcher):
            return searcher.search_movies(query, limit)
        elif isinstance(searcher, LeetxTVSearcher):
            return searcher.search_tv_series(query, limit)
        else:
            logger.warning(f"No search method implemented for source: {source.config['name']}")
            raise NotImplementedError(f"No search method implemented for source: {source.config['name']}")