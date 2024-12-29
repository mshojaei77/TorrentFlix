import logging
import requests
from dataclasses import dataclass
from typing import List
from enum import Enum
from datetime import datetime
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
import re
from bs4 import BeautifulSoup
from collections import defaultdict

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

TMDB_API_KEY = "917cce472ff1093d25cd89d8c007aacd"  # Replace with your key

class TMDBClient:
    """Helper class to manage TMDB API calls"""
    BASE_URL = "https://api.themoviedb.org/3"
    CACHE_DURATION = 3600  # 1 hour cache

    def __init__(self):
        self.api_key = TMDB_API_KEY
        self._cache = {}
    
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
        "params": {
            "with_rt_ratings": True
        }
    }
    LEETX_TV = {
        "name": "1337x (TV)",
        "category": "TV Series",
        "base_url": "https://1337x.to",
        "search_url": "https://1337x.to/category-search/{query}/TV/1/",
        "params": {}
    }

    @property
    def config(self) -> dict:
        """Returns the configuration dictionary for the source"""
        return self.value

    @classmethod
    def from_display_name(cls, name: str) -> 'TorrentSource':
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

class MovieMetadata:
    def __init__(self):
        self.sources = {
            'metacritic': MetacriticSource(),
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
        self.current_source = TorrentSource.YTS

    def search_movies(self, query: str, source: TorrentSource, limit: int = 10) -> List[Movie]:
        """Main search method that delegates to specific source searchers"""
        try:
            if source == TorrentSource.YTS:
                return self._search_yts(query, limit)
            elif source == TorrentSource.LEETX_TV:
                return self._search_leetx_tv(query, limit)
            else:
                raise ValueError(f"Unsupported torrent source: {source.config['name']}")
        except Exception as e:
            logger.error(f"Search failed for {source.config['name']}: {str(e)}")
            raise MovieSearchError(f"Search failed: {str(e)}")

    def _search_yts(self, query: str, limit: int) -> List[Movie]:
        """Search YTS.mx API for movies"""
        source_config = TorrentSource.YTS.config
        api_url = source_config["api_url"]
        
        # Merge default params with search params
        params = {
            **source_config["params"],
            'query_term': query,
            'limit': limit,
        }

        try:
            logger.debug(f"Searching for {query} on {api_url}")
            response = make_api_request(api_url, params=params)
            response.raise_for_status()
            data = response.json()

            if not data.get('data', {}).get('movies'):
                return []

            movies = []
            for movie_data in data['data']['movies']:
                torrents = [
                    Torrent(
                        quality=t['quality'],
                        type=t.get('type', 'unknown'),
                        url=t['url'],
                        size=t['size'],
                        seeds=t['seeds'],
                        peers=t['peers'],
                        date_uploaded=datetime.fromisoformat(t['date_uploaded']).strftime('%Y-%m-%d'),
                        video_codec=t.get('video_codec', 'unknown')
                    )
                    for t in movie_data['torrents']
                ]

                movie = Movie(
                    title=movie_data['title'],
                    torrents=torrents,
                    poster_url=movie_data.get('large_cover_image'),
                    rating=movie_data.get('rating', 0.0),
                    genres=movie_data.get('genres', []),
                    description_full=movie_data.get('description_full', 'No description available'),
                    year=movie_data.get('year', 0),
                    language=movie_data.get('language', 'N/A'),
                    runtime=movie_data.get('runtime', 0),
                    imdb_code=movie_data.get('imdb_code', ''),
                    cast=movie_data.get('cast', []),
                    download_count=movie_data.get('download_count', 0),
                    yt_trailer_code=movie_data.get('yt_trailer_code', ''),
                    background_image_original=movie_data.get('background_image_original', '')
                )
                movies.append(movie)

            return movies

        except requests.exceptions.HTTPError as e:
            raise MovieAPIError(f"Failed to fetch movies: {str(e)}")
        except (requests.exceptions.ConnectionError, ConnectionResetError) as e:
            raise ConnectionBlockedError("Connection blocked. Please ensure your VPN is enabled and try again.")
        except Exception as e:
            raise MovieSearchError(f"Failed to process movie data: {str(e)}")

    def _search_leetx_tv(self, query: str, limit: int) -> List[Movie]:
        """Search 1337x for TV series using web scraping"""
        source_config = TorrentSource.LEETX_TV.config
        search_url = source_config["search_url"].format(query=query.replace(' ', '+'))
        tmdb_client = TMDBClient()
        
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

            # First get all torrents regardless of metadata availability
            shows = defaultdict(lambda: defaultdict(list))
            
            response = session.get(search_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = soup.select('table.table-list tbody tr')[:limit]

            # First pass: collect all torrents
            for result in results:
                try:
                    name_cell = result.select_one('td.name')
                    if not name_cell:
                        continue

                    raw_title = name_cell.select_one('a:nth-of-type(2)').text
                    torrent_url = source_config["base_url"] + name_cell.select_one('a:nth-of-type(2)')['href']
                    
                    # Basic torrent info that doesn't depend on parsing
                    size = result.select_one('td.size').text.strip()
                    seeds = int(result.select_one('td.seeds').text.strip() or 0)
                    leeches = int(result.select_one('td.leeches').text.strip() or 0)
                    date = result.select_one('td.coll-date').text.strip()

                    # Get magnet link
                    try:
                        detail_response = session.get(torrent_url)
                        detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                        magnet = detail_soup.select_one('a[href^="magnet:"]')['href']
                    except Exception as e:
                        logger.warning(f"Failed to get magnet link: {e}")
                        magnet = ""

                    # Parse show info - make everything optional
                    show_info = self._parse_show_title(raw_title) or {
                        'title': raw_title,
                        'season': 1,  # default to season 1
                        'quality': 'unknown',
                        'codec': 'unknown'
                    }
                    
                    torrent = Torrent(
                        quality=show_info.get('quality', 'unknown'),
                        type='tv',
                        url=magnet,
                        size=size,
                        seeds=seeds,
                        peers=leeches,
                        date_uploaded=date,
                        video_codec=show_info.get('codec', 'unknown')
                    )

                    # Use the raw title if parsing failed
                    show_name = show_info.get('title', raw_title)
                    season = show_info.get('season', 1)
                    shows[show_name][season].append(torrent)

                except Exception as e:
                    logger.warning(f"Failed to parse torrent: {str(e)}")
                    continue

            # Second pass: try to get metadata but don't fail if unavailable
            tmdb_shows = []
            for show_name, seasons in shows.items():
                # Create basic show info even if TMDB fails
                base_show = {
                    'title': show_name,
                    'poster_url': '',
                    'rating': 0.0,
                    'genres': [],
                    'description_full': 'No description available',
                    'year': 0,
                    'language': 'unknown',
                    'runtime': 0,
                    'imdb_code': '',
                    'cast': [],
                    'download_count': 0,
                    'yt_trailer_code': '',
                    'background_image_original': ''
                }

                # Try to get TMDB metadata
                try:
                    clean_name = re.sub(r'\([^)]*\)', '', show_name).strip()
                    clean_name = re.sub(r'(Season|S)\s*\d+.*$', '', clean_name, flags=re.IGNORECASE).strip()
                    tmdb_show = tmdb_client.search_tv_show(clean_name)
                    
                    if tmdb_show:
                        details = tmdb_client.get_tv_details(tmdb_show['id'])
                        if details:
                            # Update base_show with TMDB data if available
                            base_show.update({
                                'poster_url': f"https://image.tmdb.org/t/p/w500{tmdb_show.get('poster_path', '')}",
                                'rating': tmdb_show.get('vote_average', 0.0),
                                'genres': [g.get('name', '') for g in details.get('genres', [])],
                                'description_full': tmdb_show.get('overview', base_show['description_full']),
                                'year': int(tmdb_show.get('first_air_date', '0')[:4]) if tmdb_show.get('first_air_date') else 0,
                                'language': tmdb_show.get('original_language', 'unknown'),
                                'runtime': details.get('episode_run_time', [0])[0] if details.get('episode_run_time') else 0,
                                'imdb_code': details.get('external_ids', {}).get('imdb_id', ''),
                                'cast': [cast.get('name', '') for cast in details.get('credits', {}).get('cast', [])[:5]] if details.get('credits') else [],
                                'yt_trailer_code': next((v.get('key', '') for v in details.get('videos', {}).get('results', []) 
                                                    if v.get('type') == 'Trailer'), '') if details.get('videos') else '',
                                'background_image_original': f"https://image.tmdb.org/t/p/original{tmdb_show.get('backdrop_path', '')}"
                            })
                except Exception as e:
                    logger.warning(f"Failed to get TMDB metadata for {show_name}: {str(e)}")

                # Create show entries for each season
                for season_num, torrents in seasons.items():
                    # Remove title from base_show since we'll pass it explicitly
                    show_info = base_show.copy()
                    del show_info['title']
                    
                    show = Movie(
                        title=f"{show_name} Season {season_num}",
                        torrents=torrents,
                        **show_info  # Pass remaining parameters
                    )
                    tmdb_shows.append(show)

            return tmdb_shows

        except requests.exceptions.HTTPError as e:
            raise MovieAPIError(f"Failed to fetch TV series: {str(e)}")
        except (requests.exceptions.ConnectionError, ConnectionResetError) as e:
            raise ConnectionBlockedError("Connection blocked. Please ensure your VPN is enabled.")
        except Exception as e:
            raise MovieSearchError(f"Failed to process TV series data: {str(e)}")

    def _parse_show_title(self, raw_title: str) -> dict:
        """Parse show title into components with improved accuracy"""
        # Common patterns
        quality_patterns = {
            '2160p': '2160p', 
            '1080p': '1080p', 
            '720p': '720p', 
            '480p': '480p',
            'HDTV': 'HDTV'
        }
        codec_patterns = {
            'x264': 'x264',
            'x265': 'x265',
            'HEVC': 'HEVC',
            'XviD': 'XviD',
            'H264': 'H264',
            'H.264': 'H264'
        }
        
        # Initialize result
        result = {
            'title': '',
            'season': 0,
            'episode': 0,
            'quality': 'unknown',
            'codec': 'unknown'
        }
        
        try:
            # Extract season and episode using multiple patterns
            patterns = [
                r'S(\d{1,2})E(\d{1,2})',  # S01E01
                r'[.\s](\d{1,2})x(\d{1,2})[.\s]',  # 1x01
                r'Season\s*(\d{1,2})\s*Episode\s*(\d{1,2})',  # Season 1 Episode 1
            ]
            
            for pattern in patterns:
                match = re.search(pattern, raw_title, re.IGNORECASE)
                if match:
                    result['season'] = int(match.group(1))
                    result['episode'] = int(match.group(2))
                    title_part = raw_title[:match.start()]
                    break
            else:
                # Check for season pack
                season_match = re.search(r'Season\s*(\d{1,2})|S(\d{1,2})\s*Complete', raw_title, re.IGNORECASE)
                if season_match:
                    result['season'] = int(season_match.group(1) or season_match.group(2))
                    title_part = raw_title[:season_match.start()]
                else:
                    title_part = raw_title
            
            # Clean up title
            result['title'] = re.sub(
                r'[\.\-\s]*$',  # Remove trailing dots, dashes and spaces
                '',
                title_part.replace('.', ' ')
            ).strip()
            
            # Extract quality
            for pattern, quality in quality_patterns.items():
                if pattern in raw_title:
                    result['quality'] = quality
                    break
            
            # Extract codec
            for pattern, codec in codec_patterns.items():
                if pattern in raw_title:
                    result['codec'] = codec
                    break
            
            return result
        
        except Exception as e:
            logger.error(f"Error parsing title '{raw_title}': {str(e)}")
            return None

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
