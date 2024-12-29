import logging
import requests
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
import re
from bs4 import BeautifulSoup
from collections import defaultdict
import concurrent.futures
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables

# Replace hard-coded API key with environment variable
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
if not TMDB_API_KEY:
    raise ValueError("TMDB_API_KEY environment variable is not set")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TMDBClient:
    """Helper class to manage TMDB API calls"""
    BASE_URL = "https://api.themoviedb.org/3"
    CACHE_DURATION = 3600  # 1 hour cache

    def __init__(self) -> None:
        self.api_key: str = TMDB_API_KEY
        self._cache: Dict[str, Any] = {}
    
    def search_tv_show(self, title: str) -> dict:
        """Search for a TV show with caching"""
        cache_key = f"search_{title}"
        if cache_key in self._cache:
            return self._cache[cache_key]

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
            return data['results'][0]
        return None

    def get_tv_details(self, show_id: int) -> dict:
        """Get detailed TV show info with caching"""
        cache_key = f"details_{show_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

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
        return data

@dataclass(frozen=True)
class Torrent:
    quality: str
    type: str
    url: str
    size: str
    seeds: int
    peers: int
    date_uploaded: str
    video_codec: str

@dataclass(frozen=True)
class Movie:
    title: str
    torrents: List[Torrent]
    poster_url: str
    rating: float
    genres: List[str]
    description_full: str
    year: int
    language: str
    runtime: int
    imdb_code: str
    cast: List[str]
    download_count: int
    yt_trailer_code: str
    background_image_original: str
    metacritic_url: str = ''
    metacritic_info: dict = None
    metadata: dict = None

    def with_metacritic_data(self, url: str, info: dict) -> 'Movie':
        """Creates a new Movie instance with updated Metacritic data"""
        return Movie(
            title=self.title,
            torrents=self.torrents,
            poster_url=self.poster_url,
            rating=self.rating,
            genres=self.genres,
            description_full=self.description_full,
            year=self.year,
            language=self.language,
            runtime=self.runtime,
            imdb_code=self.imdb_code,
            cast=self.cast,
            download_count=self.download_count,
            yt_trailer_code=self.yt_trailer_code,
            background_image_original=self.background_image_original,
            metacritic_url=url,
            metacritic_info=info
        )

    def with_metadata(self, metadata: dict) -> 'Movie':
        """Creates a new Movie instance with updated metadata"""
        return Movie(
            title=self.title,
            torrents=self.torrents,
            poster_url=self.poster_url,
            rating=self.rating,
            genres=self.genres,
            description_full=self.description_full,
            year=self.year,
            language=self.language,
            runtime=self.runtime,
            imdb_code=self.imdb_code,
            cast=self.cast,
            download_count=self.download_count,
            yt_trailer_code=self.yt_trailer_code,
            background_image_original=self.background_image_original,
            metadata=metadata
        )

class TorrentSource(Enum):
    YTS = {
        "name": "YTS.mx",
        "category": "Movies",
        "api_url": "https://yts.mx/api/v2/list_movies.json",
        "type": "api",
        "params": {"with_rt_ratings": True}
    }
    LEETX = {
        "name": "1337x",
        "category": "All",
        "base_url": "https://1337x.to",
        "search_url": "https://1337x.to/search/{query}/1/",
        "type": "scrape",
        "params": {}
    }
    RARBG = {
        "name": "RARBG",
        "category": "All",
        "api_url": "https://torrentapi.org/pubapi_v2.php",
        "type": "api",
        "params": {"mode": "search", "ranked": 0, "token": None}
    }
    TORRENTGALAXY = {
        "name": "TorrentGalaxy",
        "category": "All",
        "search_url": "https://torrentgalaxy.to/torrents.php?search={query}#results",
        "params": {}
    }
    EZTVX = {
        "name": "EZTVx",
        "category": "TV Series",
        "search_url": "https://eztvx.to/search/{query}",
        "params": {}
    }
    EXT = {
        "name": "EXT",
        "category": "All",
        "search_url": "https://ext.to/search/?q={query}",
        "params": {}
    }
    OXTORRENT = {
        "name": "OxTorrent",
        "category": "All",
        "search_url": "https://www.oxtorrent.co/recherche/{query}",
        "params": {}
    }
    THEPIRATEBAY = {
        "name": "The Pirate Bay",
        "category": "All",
        "search_url": "https://thepiratebay.org/search.php?q={query}&all=on&search=Pirate+Search&page=0&orderby=",
        "params": {}
    }
    LIMETORRENTS = {
        "name": "LimeTorrents",
        "category": "All",
        "search_url": "https://www.limetorrents.lol/search/all/{query}/",
        "params": {}
    }
    TORRENTDOWNLOADS = {
        "name": "TorrentDownloads",
        "category": "All",
        "search_url": "https://www.torrentdownloads.pro/search/?search={query}",
        "params": {}
    }
    TORLOCK = {
        "name": "Torlock",
        "category": "All",
        "search_url": "https://www.torlock.com/?qq=1&q={query}",
        "params": {}
    }
    # Add more sources as needed

    @property
    def config(self) -> Dict[str, Any]:
        """Returns the configuration dictionary for the source"""
        return self.value

    @classmethod
    def from_display_name(cls, name: str):
        """Returns the TorrentSource enum based on its display name"""
        for source in cls:
            if source.value["name"] == name:
                return source
        raise ValueError(f"No TorrentSource found with name: {name}")

    @classmethod
    def get_category(cls, source) -> str:
        """Returns the category of the torrent source"""
        return source.config["category"]

    @classmethod
    def get_sources_by_category(cls) -> dict:
        """Returns a dictionary of sources grouped by category"""
        categories = {}
        for source in cls:
            category = cls.get_category(source)
            if category not in categories:
                categories[category] = []
            categories[category].append(source)
        return categories

class MovieSearchError(Exception):
    """Base exception for movie search errors"""
    pass

class MovieAPIError(MovieSearchError):
    """Raised when the movie API returns an error"""
    pass

class ConnectionBlockedError(MovieSearchError):
    """Raised when connection is blocked or reset"""
    pass

class MetadataSource(ABC):
    @abstractmethod
    def get_url(self, title: str, year: int) -> str:
        pass
    
    @abstractmethod
    def get_info(self, url: str) -> dict:
        pass

class MetacriticSource(MetadataSource):
    def get_url(self, title: str, year: int) -> str:
        """Get Metacritic URL with multiple fallback attempts"""
        try:
            # Clean the title - remove common TV show patterns first
            clean_title = re.sub(r'(Season|S)\s*\d+.*$', '', title, flags=re.IGNORECASE).strip()
            clean_title = re.sub(r'\([^)]*\)', '', clean_title).strip()
            clean_title = re.sub(r'\s+\d{4}$', '', clean_title).strip()
            
            # Format title for URL
            formatted_title = ''.join(c for c in clean_title.lower() if c.isalnum() or c.isspace())
            formatted_title = formatted_title.replace(' ', '-')
            
            # Try multiple URL patterns
            url_patterns = [
                f"https://www.metacritic.com/movie/{formatted_title}/",
                f"https://www.metacritic.com/tv/{formatted_title}/",
                f"https://www.metacritic.com/movie/{formatted_title}-{year}/",
                f"https://www.metacritic.com/tv/{formatted_title}-{year}/"
            ]
            
            for url in url_patterns:
                try:
                    response = requests.head(
                        url, 
                        headers={'User-Agent': 'Mozilla/5.0'},
                        allow_redirects=True,
                        timeout=5
                    )
                    if response.status_code == 200:
                        return url
                except requests.RequestException:
                    continue
                    
            logger.warning(f"No valid Metacritic URL found for: {title}")
            return ""
            
        except Exception as e:
            logger.error(f"Error constructing Metacritic URL: {str(e)}")
            return ""

    def get_info(self, url: str) -> dict:
        """Get Metacritic info with fallback data"""
        if not url:
            return self._get_empty_info()
            
        try:
            # Import the existing get_metacritic_info function
            from movie_info_mata import get_metacritic_info
            info = get_metacritic_info(url)
            
            # If the main function fails, return empty structure
            if not info:
                return self._get_empty_info()
                
            return info
            
        except Exception as e:
            logger.error(f"Error getting Metacritic info: {str(e)}")
            return self._get_empty_info()
    
    def _get_empty_info(self) -> dict:
        """Return a default empty info structure"""
        return {
            'score': None,
            'user_score': None,
            'critic_reviews': [],
            'user_reviews': [],
            'summary': '',
            'release_date': None,
            'rating': '',
            'genre': [],
            'developer': '',
            'publisher': '',
            'cast': [],
            'director': '',
            'runtime': '',
            'error': None
        }

    def _extract_score(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract and convert the Metacritic score safely.
        
        Args:
            soup: BeautifulSoup object containing the page content
            
        Returns:
            Optional[int]: The parsed score or None if parsing fails
        """
        score_elem = soup.find('span', class_='metascore_w')
        try:
            return int(score_elem.text) if score_elem else None
        except (ValueError, AttributeError):
            return None

class TMDBSource(MetadataSource):
    def __init__(self):
        self.client = TMDBClient()
    
    def get_url(self, title: str, year: int) -> str:
        """Get TMDB URL for the movie/show"""
        try:
            result = self.client.search_tv_show(title)
            if result:
                return f"https://www.themoviedb.org/tv/{result['id']}"
            return ""
        except Exception as e:
            logger.error(f"Error getting TMDB URL: {str(e)}")
            return ""

    def get_info(self, url: str) -> dict:
        """Get TMDB info with fallback data"""
        if not url:
            return self._get_empty_info()
            
        try:
            show_id = url.split('/')[-1]
            details = self.client.get_tv_details(int(show_id))
            
            if not details:
                return self._get_empty_info()
                
            return {
                'title': details.get('name', ''),
                'overview': details.get('overview', ''),
                'first_air_date': details.get('first_air_date', ''),
                'vote_average': details.get('vote_average', 0.0),
                'genres': [g['name'] for g in details.get('genres', [])],
                'episode_run_time': details.get('episode_run_time', [0])[0] if details.get('episode_run_time') else 0,
                'number_of_seasons': details.get('number_of_seasons', 0),
                'status': details.get('status', ''),
                'cast': [cast['name'] for cast in details.get('credits', {}).get('cast', [])[:5]] if details.get('credits') else [],
                'crew': [crew['name'] for crew in details.get('credits', {}).get('crew', [])[:5]] if details.get('credits') else [],
                'networks': [n['name'] for n in details.get('networks', [])],
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Error getting TMDB info: {str(e)}")
            return self._get_empty_info()
    
    def _get_empty_info(self) -> dict:
        """Return a default empty info structure"""
        return {
            'title': '',
            'overview': '',
            'first_air_date': '',
            'vote_average': 0.0,
            'genres': [],
            'episode_run_time': 0,
            'number_of_seasons': 0,
            'status': '',
            'cast': [],
            'crew': [],
            'networks': [],
            'error': None
        }

class IMDBSource(MetadataSource):
    def get_url(self, title: str, year: int) -> str:
        """Get IMDB URL for the movie/show"""
        # Implementation for IMDB URL lookup
        # This would typically use their API or web scraping
        return ""  # Placeholder

    def get_info(self, url: str) -> dict:
        """Get IMDB info with fallback data"""
        # Implementation for IMDB info retrieval
        return self._get_empty_info()
    
    def _get_empty_info(self) -> dict:
        """Return a default empty info structure"""
        return {
            'rating': None,
            'votes': 0,
            'plot': '',
            'directors': [],
            'writers': [],
            'cast': [],
            'genres': [],
            'runtime': '',
            'countries': [],
            'languages': [],
            'error': None
        }

class MetadataManager:
    """Manages multiple metadata sources and coordinates data retrieval"""
    
    def __init__(self, sources: List['BaseMetadataSource']):
        self.sources = {source.name: source for source in sources}
    
    def get_metadata(self, title: str, year: int, sources: List[str] = None) -> dict:
        """Get metadata from multiple sources concurrently"""
        if sources is None:
            sources = list(self.sources.keys())
            
        metadata = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(sources)) as executor:
            future_to_source = {
                executor.submit(self._get_source_metadata, source_name, title, year): source_name
                for source_name in sources if source_name in self.sources
            }
            
            for future in concurrent.futures.as_completed(future_to_source):
                source_name = future_to_source[future]
                try:
                    metadata[source_name] = future.result()
                except Exception as e:
                    logger.error(f"Error getting metadata from {source_name}: {e}")
                    metadata[source_name] = {'error': str(e)}
                
        return metadata
    
    def _get_source_metadata(self, source_name: str, title: str, year: int) -> dict:
        """Get metadata from a single source"""
        source = self.sources[source_name]
        return source.get_metadata(title, year)

class BaseMetadataSource(ABC):
    """Base class for all metadata sources"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the metadata source"""
        pass
    
    @abstractmethod
    def get_metadata(self, title: str, year: int) -> dict:
        """Get metadata for a given title and year"""
        pass
    
    def _get_empty_metadata(self) -> dict:
        """Return empty metadata structure"""
        return {
            'title': '',
            'overview': '',
            'rating': None,
            'genres': [],
            'cast': [],
            'crew': [],
            'error': None
        }

class TMDBMetadata(BaseMetadataSource):
    """TMDB metadata source implementation"""
    
    def __init__(self):
        self.client = TMDBClient()
    
    @property
    def name(self) -> str:
        return 'tmdb'
    
    def get_metadata(self, title: str, year: int) -> dict:
        try:
            result = self.client.search_tv_show(title)
            if not result:
                return self._get_empty_metadata()
                
            details = self.client.get_tv_details(result['id'])
            return {
                'title': details.get('name', ''),
                'overview': details.get('overview', ''),
                'rating': details.get('vote_average', 0.0),
                'genres': [g['name'] for g in details.get('genres', [])],
                'cast': [cast['name'] for cast in details.get('credits', {}).get('cast', [])[:5]],
                'crew': [crew['name'] for crew in details.get('credits', {}).get('crew', [])[:5]],
                'error': None
            }
        except Exception as e:
            logger.error(f"TMDB metadata error: {str(e)}")
            return {**self._get_empty_metadata(), 'error': str(e)}

class IMDBMetadata(BaseMetadataSource):
    """IMDB metadata source implementation"""
    
    @property
    def name(self) -> str:
        return 'imdb'
    
    def get_metadata(self, title: str, year: int) -> dict:
        try:
            # Implement IMDB API or scraping logic here
            return self._get_empty_metadata()
        except Exception as e:
            logger.error(f"IMDB metadata error: {str(e)}")
            return {**self._get_empty_metadata(), 'error': str(e)}

class MetacriticMetadata(BaseMetadataSource):
    """Metacritic metadata source implementation"""
    
    @property
    def name(self) -> str:
        return 'metacritic'
    
    def get_metadata(self, title: str, year: int) -> dict:
        try:
            # Clean and format the title
            clean_title = re.sub(r'(Season|S)\s*\d+.*$', '', title, flags=re.IGNORECASE).strip()
            clean_title = re.sub(r'\([^)]*\)', '', clean_title).strip()
            formatted_title = ''.join(c for c in clean_title.lower() if c.isalnum() or c.isspace())
            formatted_title = formatted_title.replace(' ', '-')
            
            # Try to get Metacritic data
            url = f"https://www.metacritic.com/movie/{formatted_title}/"
            response = requests.get(
                url,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10
            )
            
            if response.status_code != 200:
                return self._get_empty_metadata()
                
            soup = BeautifulSoup(response.text, 'html.parser')
            return {
                'title': title,
                'score': self._extract_score(soup),
                'reviews': self._extract_reviews(soup),
                'error': None
            }
        except Exception as e:
            logger.error(f"Metacritic metadata error: {str(e)}")
            return {**self._get_empty_metadata(), 'error': str(e)}
    
    def _extract_score(self, soup: BeautifulSoup) -> Optional[int]:
        """Extract and convert the Metacritic score safely.
        
        Args:
            soup: BeautifulSoup object containing the page content
            
        Returns:
            Optional[int]: The parsed score or None if parsing fails
        """
        score_elem = soup.find('span', class_='metascore_w')
        try:
            return int(score_elem.text) if score_elem else None
        except (ValueError, AttributeError):
            return None
    
    def _extract_reviews(self, soup: BeautifulSoup) -> List[dict]:
        reviews = []
        review_elems = soup.find_all('div', class_='review_content')
        for elem in review_elems[:5]:  # Get first 5 reviews
            review = {
                'score': elem.find('div', class_='metascore_w').text if elem.find('div', class_='metascore_w') else None,
                'text': elem.find('div', class_='review_body').text.strip() if elem.find('div', class_='review_body') else '',
                'author': elem.find('div', class_='author').text.strip() if elem.find('div', class_='author') else ''
            }
            reviews.append(review)
        return reviews

class TorrentSearcher:
    """Handles searching across multiple torrent sources and metadata enrichment."""
    
    DEFAULT_SEARCH_LIMIT = 10

    def __init__(self) -> None:
        self.sources = list(TorrentSource)
        self.metadata_manager = MetadataManager([
            TMDBMetadata(),
            IMDBMetadata(),
            MetacriticMetadata()
        ])
        
    def search(self, query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> List[Movie]:
        """Search all configured torrent sources concurrently.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return (default: DEFAULT_SEARCH_LIMIT)
            
        Returns:
            List[Movie]: List of found movies, sorted by seed count
        """
        results = []
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Search torrents
            torrent_futures = {
                executor.submit(self._search_source, source, query): source
                for source in self.sources
            }
            
            for future in concurrent.futures.as_completed(torrent_futures):
                try:
                    source_results = future.result()
                    results.extend(source_results)
                except Exception as e:
                    logger.error(f"Search failed for {torrent_futures[future].name}: {e}")

        # Deduplicate and sort results
        unique_results = self._deduplicate_results(results)
        sorted_results = sorted(unique_results, 
                              key=lambda x: max(t.seeds for t in x.torrents), 
                              reverse=True)[:limit]

        # Enrich with metadata concurrently
        with concurrent.futures.ThreadPoolExecutor() as executor:
            metadata_futures = {
                executor.submit(self._enrich_metadata, movie): movie
                for movie in sorted_results
            }
            
            enriched_results = []
            for future in concurrent.futures.as_completed(metadata_futures):
                try:
                    enriched_movie = future.result()
                    enriched_results.append(enriched_movie)
                except Exception as e:
                    logger.error(f"Metadata enrichment failed: {e}")

        return enriched_results

    def _search_source(self, source: TorrentSource, query: str) -> List[Movie]:
        """Search a specific source with appropriate handler"""
        if source.value['type'] == 'api':
            return self._search_api_source(source, query)
        else:
            return self._search_scrape_source(source, query)

    def _enrich_metadata(self, movie: Movie) -> Movie:
        """Enrich movie with metadata from all configured sources"""
        metadata = self.metadata_manager.get_metadata(
            title=movie.title,
            year=movie.year
        )
        return movie.with_metadata(metadata)

    def _deduplicate_results(self, results: List[Movie]) -> List[Movie]:
        """Deduplicate movies based on title and year while merging their torrents.
        
        Args:
            results: List of Movie objects potentially containing duplicates
            
        Returns:
            List[Movie]: Deduplicated list where movies with the same title and year
                        have their torrents merged into a single Movie object
        """
        seen = set()
        unique = []
        
        for movie in results:
            key = f"{movie.title.lower()}_{movie.year}"
            if key not in seen:
                seen.add(key)
                unique.append(movie)
            else:
                # Merge torrents with existing movie
                existing = next(m for m in unique 
                              if f"{m.title.lower()}_{m.year}" == key)
                existing.torrents.extend(movie.torrents)
                
        return unique

# Define a single request template with timeout and retries
def make_api_request(api_url, params=None, headers=None):
    session = requests.Session()

    # First try - fast and simple with minimal headers
    try:
        response = session.get(
            api_url,
            params=params,
            timeout=1,  # Reduced timeout for speed
            allow_redirects=False  # Disable redirects for speed
        )
        response.raise_for_status()
        return response

    # Second try - anti-bot measures
    except (requests.exceptions.RequestException, ConnectionError):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate', 
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        session.headers.update(headers)
        
        # Add random delay to appear more human-like
        import time
        import random
        time.sleep(random.uniform(1, 3))
        
        response = session.get(
            api_url,
            params=params,
            timeout=10,
            allow_redirects=True,
            verify=True
        )
        response.raise_for_status()
        return response
