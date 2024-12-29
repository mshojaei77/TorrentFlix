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
import time
import json

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
        "params": {"with_rt_ratings": True}
    }
    LEETX = {
        "name": "1337x",
        "category": "All",
        "base_url": "https://1337x.to",
        "search_url": "https://1337x.to/search/{query}/1/",
        "params": {}
    }
    RARBG = {
        "name": "RARBG",
        "category": "All",
        "api_url": "https://torrentapi.org/pubapi_v2.php",
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
        """Returns a dictionary of sources grouped by category with specific ordering"""
        # Define preferred order for each category
        category_order = {
            'Movies': [cls.YTS],  # YTS first for movies
            'TV Series': [cls.LEETX, cls.EZTVX],  # LEETX first for TV series
            'All': [cls.LEETX, cls.RARBG, cls.TORRENTGALAXY, cls.EXT, 
                   cls.OXTORRENT, cls.THEPIRATEBAY, cls.LIMETORRENTS,
                   cls.TORRENTDOWNLOADS, cls.TORLOCK]
        }
        
        # Initialize categories dict
        categories = {cat: [] for cat in category_order.keys()}
        
        # First add sources in preferred order
        for category, preferred_sources in category_order.items():
            categories[category].extend(preferred_sources)
            
        # Then add remaining sources that weren't explicitly ordered
        for source in cls:
            category = cls.get_category(source)
            if category in categories and source not in categories[category]:
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
            # Clean and format the title
            clean_title = re.sub(r'(Season|S)\s*\d+.*$', '', title, flags=re.IGNORECASE).strip()
            clean_title = re.sub(r'\([^)]*\)', '', clean_title).strip()
            clean_title = re.sub(r'\s+\d{4}$', '', clean_title).strip()
            clean_title = re.sub(r'[^\w\s-]', '', clean_title.lower())
            clean_title = clean_title.replace(' ', '-')
            
            # Try multiple URL patterns
            url_patterns = [
                f"https://www.metacritic.com/movie/{clean_title}/",
                f"https://www.metacritic.com/tv/{clean_title}/",
                f"https://www.metacritic.com/movie/{clean_title}-{year}/",
                f"https://www.metacritic.com/tv/{clean_title}-{year}/"
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

class RottenTomatoesSource(MetadataSource):
    def get_url(self, title: str, year: int) -> str:
        """Get Rotten Tomatoes URL"""
        try:
            # Clean and format the title
            clean_title = re.sub(r'[^\w\s-]', '', title.lower())
            clean_title = re.sub(r'\s+', '_', clean_title.strip())
            
            # Try both movie and TV show URLs with year
            url_patterns = [
                f"https://www.rottentomatoes.com/m/{clean_title}_{year}",
                f"https://www.rottentomatoes.com/m/{clean_title}",
                f"https://www.rottentomatoes.com/tv/{clean_title}_{year}",
                f"https://www.rottentomatoes.com/tv/{clean_title}"
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
                    
            logger.warning(f"No valid Rotten Tomatoes URL found for: {title} ({year})")
            return ""
            
        except Exception as e:
            logger.error(f"Error constructing Rotten Tomatoes URL: {str(e)}")
            return ""

    def get_info(self, url: str) -> dict:
        """Get Rotten Tomatoes info"""
        if not url:
            return self._get_empty_info()
            
        try:
            response = requests.get(
                url,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract scores from score-board element
            score_board = soup.find('score-board')
            critics_score = score_board.get('tomatometerscore', '') if score_board else ''
            audience_score = score_board.get('audiencescore', '') if score_board else ''
            
            # Get critic consensus
            consensus_elem = soup.find('rt-text', {'data-qa': 'critics-consensus'})
            critics_consensus = consensus_elem.text.strip() if consensus_elem else ''
            
            # Get reviews
            critic_reviews = []
            audience_reviews = []
            
            # Get critic reviews
            for card in soup.find_all('media-review-card-critic'):
                review_text = card.find('rt-text', {'data-qa': 'review-text'})
                critic_name = card.find('rt-text', {'context': 'label'})
                publication = card.find('rt-text', {'slot': 'publicationName'})
                
                if review_text and critic_name:
                    critic_reviews.append({
                        'text': review_text.text.strip(),
                        'critic': critic_name.text.strip(),
                        'publication': publication.text.strip() if publication else ''
                    })
                    
            # Get audience reviews  
            for card in soup.find_all('media-review-card-audience'):
                review_text = card.find('rt-text', {'data-qa': 'review-text'})
                reviewer = card.find('rt-link', {'slot': 'displayName'})
                rating = card.find('rt-text', {'slot': 'originalScore'})
                date = card.find('rt-text', {'slot': 'createDate'})
                
                if review_text and reviewer:
                    audience_reviews.append({
                        'text': review_text.text.strip(),
                        'reviewer': reviewer.text.strip(),
                        'rating': rating.text.strip() if rating else '',
                        'date': date.text.strip() if date else ''
                    })
            
            # Extract movie info
            info = {}
            
            # Get synopsis
            synopsis_elem = soup.find('rt-text', {'data-qa': 'synopsis-value'})
            info['description'] = synopsis_elem.text.strip() if synopsis_elem else ''
            
            # Get movie info items
            info_items = soup.find_all('div', {'class': 'category-wrap'})
            for item in info_items:
                label = item.find('rt-text', {'class': 'key'})
                if not label:
                    continue
                    
                label = label.text.strip().lower()
                values = item.find_all('rt-link')
                value_list = [v.text.strip() for v in values]
                
                if label in ['director', 'producer', 'screenwriter', 'cast']:
                    info[label] = value_list
                    
            # Get additional info using regex patterns
            for pattern, key in [
                (r'Rating:', 'rating'),
                (r'Genre:', 'genre'),
                (r'Runtime:', 'runtime'),
                (r'Release Date:', 'release_date')
            ]:
                elem = soup.find('rt-text', text=re.compile(pattern))
                if elem:
                    value = elem.parent.text.replace(pattern, '').strip()
                    info[key] = [g.strip() for g in value.split(',')] if key == 'genre' else value
                else:
                    info[key] = [] if key == 'genre' else ''
            
            return {
                'tomatometer_score': f"{critics_score}%" if critics_score else '',
                'popcornmeter_score': f"{audience_score}%" if audience_score else '',
                'critics_consensus': critics_consensus,
                'critic_reviews': critic_reviews[:5],  # Limit to first 5 reviews
                'audience_reviews': audience_reviews[:5],  # Limit to first 5 reviews
                'rating': info.get('rating', ''),
                'genre': info.get('genre', []),
                'description': info.get('description', ''),
                'director': info.get('director', []),
                'producer': info.get('producer', []),
                'screenwriter': info.get('screenwriter', []),
                'cast': info.get('cast', []),
                'runtime': info.get('runtime', ''),
                'release_date': info.get('release_date', ''),
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Error getting Rotten Tomatoes info: {str(e)}")
            return self._get_empty_info()
    
    def _get_empty_info(self) -> dict:
        """Return a default empty info structure"""
        return {
            'tomatometer_score': '',
            'popcornmeter_score': '',
            'critics_consensus': '',
            'critic_reviews': [],
            'audience_reviews': [],
            'rating': '',
            'genre': [],
            'description': '',
            'director': [],
            'producer': [],
            'screenwriter': [],
            'cast': [],
            'runtime': '',
            'release_date': '',
            'error': None
        }

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
        self.current_source = TorrentSource.YTS
        self._session = self._create_session()  # Add persistent session
        
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

    def search_movies(self, query: str, source: TorrentSource, limit: int = 50) -> List[Movie]:
        """Main search method that delegates to specific source searchers"""
        try:
            if source == TorrentSource.YTS:
                return self._search_yts(query, limit)
            elif source == TorrentSource.LEETX:
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
        """Search 1337x for TV series using web scraping with comprehensive season/episode coverage"""
        source_config = TorrentSource.LEETX.config
        base_url = source_config["base_url"]
        search_url = f"{base_url}/search/{query.replace(' ', '+')}/{{page}}/"
        tmdb_client = TMDBClient()
        
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            })

            # Group episodes by show name, season, and episode
            shows = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
            
            page = 1
            total_results = 0
            max_pages = 5  # Limit pages to avoid too many requests
            
            while total_results < limit and page <= max_pages:
                current_url = search_url.format(page=page)
                response = session.get(current_url, verify=True)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                results = soup.select('table.table-list tbody tr')
                
                if not results:
                    break
                    
                # Process each torrent result
                for result in results:
                    try:
                        name_cell = result.select_one('td.name')
                        if not name_cell:
                            continue

                        raw_title = name_cell.select_one('a:nth-of-type(2)').text
                        torrent_url = base_url + name_cell.select_one('a:nth-of-type(2)')['href']
                        
                        # Parse show info
                        show_info = self._parse_show_title(raw_title)
                        if not show_info:
                            continue

                        show_name = show_info['title']
                        season = show_info['season']
                        episode = show_info.get('episode')

                        # Get torrent details
                        size = result.select_one('td.size').text.strip()
                        seeds = int(result.select_one('td.seeds').text.strip() or 0)
                        leeches = int(result.select_one('td.leeches').text.strip() or 0)
                        date = result.select_one('td.coll-date').text.strip()

                        # Get magnet link from torrent page
                        detail_response = session.get(torrent_url)
                        detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                        magnet = detail_soup.select_one('a[href^="magnet:"]')['href']

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

                        # Organize torrents by show, season, and episode
                        if episode:
                            shows[show_name][season][episode].append(torrent)
                        else:
                            # Full season pack - store under episode 0
                            shows[show_name][season][0].append(torrent)

                        total_results += 1
                        if total_results >= limit:
                            break

                    except Exception as e:
                        logger.warning(f"Failed to parse torrent: {str(e)}")
                        continue

                # Check if there's a next page (fix pagination check)
                next_page = soup.select_one('div.pagination a:contains("Next")')
                if not next_page:
                    logger.debug(f"No more pages found after page {page}")
                    break

                page += 1
                logger.debug(f"Moving to page {page}")

                # Add a small delay between pages to avoid rate limiting
                time.sleep(1)

            # Create Movie objects for each show with TMDB metadata
            final_results = []
            for show_name, seasons in shows.items():
                try:
                    # Get TMDB metadata
                    clean_name = re.sub(r'\([^)]*\)', '', show_name).strip()
                    clean_name = re.sub(r'(Season|S)\s*\d+.*$', '', clean_name, flags=re.IGNORECASE).strip()
                    tmdb_show = tmdb_client.search_tv_show(clean_name)
                    
                    if tmdb_show:
                        details = tmdb_client.get_tv_details(tmdb_show['id'])
                        
                        base_show = {
                            'poster_url': f"https://image.tmdb.org/t/p/w500{tmdb_show.get('poster_path', '')}",
                            'rating': tmdb_show.get('vote_average', 0.0),
                            'genres': [g.get('name', '') for g in details.get('genres', [])] if details else [],
                            'description_full': tmdb_show.get('overview', 'No description available'),
                            'year': int(tmdb_show.get('first_air_date', '0')[:4]) if tmdb_show.get('first_air_date') else 0,
                            'language': tmdb_show.get('original_language', 'unknown'),
                            'runtime': details.get('episode_run_time', [0])[0] if details and details.get('episode_run_time') else 0,
                            'imdb_code': details.get('external_ids', {}).get('imdb_id', '') if details else '',
                            'cast': [cast.get('name', '') for cast in details.get('credits', {}).get('cast', [])[:5]] if details and details.get('credits') else [],
                            'download_count': 0,
                            'yt_trailer_code': next((v.get('key', '') for v in details.get('videos', {}).get('results', []) 
                                                if v.get('type') == 'Trailer'), '') if details and details.get('videos') else '',
                            'background_image_original': f"https://image.tmdb.org/t/p/original{tmdb_show.get('backdrop_path', '')}"
                        }
                    else:
                        base_show = {
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

                    # Create Movie objects for each season and episode
                    for season_num, episodes in seasons.items():
                        # Add season pack if available
                        if 0 in episodes:
                            show = Movie(
                                title=f"{show_name} Season {season_num} (Complete)",
                                torrents=episodes[0],
                                **base_show
                            )
                            final_results.append(show)

                        # Add individual episodes
                        for ep_num, torrents in episodes.items():
                            if ep_num == 0:  # Skip season packs as they're already added
                                continue
                            show = Movie(
                                title=f"{show_name} S{season_num:02d}E{ep_num:02d}",
                                torrents=torrents,
                                **base_show
                            )
                            final_results.append(show)

                except Exception as e:
                    logger.warning(f"Failed to get TMDB data for {show_name}: {e}")
                    continue

            return sorted(final_results, key=lambda x: (x.title, x.year))

        except requests.exceptions.HTTPError as e:
            raise MovieAPIError(f"Failed to fetch TV series: {str(e)}")
        except (requests.exceptions.ConnectionError, ConnectionResetError) as e:
            raise ConnectionBlockedError("Connection blocked. Please ensure your VPN is enabled.")
        except Exception as e:
            raise MovieSearchError(f"Failed to process TV series data: {str(e)}")

    def _parse_show_title(self, raw_title: str) -> dict:
        """Parse show title into components with improved TV show handling"""
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
        
        try:
            # Initialize result
            result = {
                'title': '',
                'season': 0,
                'episode': 0,
                'quality': 'unknown',
                'codec': 'unknown'
            }
            
            # Extract season and episode using multiple patterns
            season_episode_patterns = [
                (r'S(\d{1,2})E(\d{1,2})', lambda m: (int(m.group(1)), int(m.group(2)))),  # S01E01
                (r'[.\s](\d{1,2})x(\d{1,2})[.\s]', lambda m: (int(m.group(1)), int(m.group(2)))),  # 1x01
                (r'Season\s*(\d{1,2})\s*Episode\s*(\d{1,2})', lambda m: (int(m.group(1)), int(m.group(2)))),  # Season 1 Episode 1
                (r'[.\s]E(\d{1,2})[.\s]', lambda m: (1, int(m.group(1)))),  # E01 (assumes season 1)
            ]
            
            # Season pack patterns
            season_patterns = [
                r'Season\s*(\d{1,2})',  # Season 1
                r'S(\d{1,2})\s*Complete',  # S1 Complete
                r'Complete\s*S(\d{1,2})',  # Complete S1
            ]
            
            # Try to match season and episode
            title_part = raw_title
            for pattern, extract in season_episode_patterns:
                match = re.search(pattern, raw_title, re.IGNORECASE)
                if match:
                    result['season'], result['episode'] = extract(match)
                    title_part = raw_title[:match.start()]
                    break
            else:
                # Check for season pack
                for pattern in season_patterns:
                    match = re.search(pattern, raw_title, re.IGNORECASE)
                    if match:
                        result['season'] = int(match.group(1))
                        title_part = raw_title[:match.start()]
                        break
            
            # Clean up title and remove year for series
            title_part = re.sub(r'\(\d{4}\)', '', title_part)  # Remove year in parentheses
            title_part = re.sub(r'\s\d{4}\s', ' ', title_part)  # Remove standalone year
            result['title'] = re.sub(
                r'[\.\-\s]*$',  # Remove trailing dots, dashes and spaces
                '',
                title_part.replace('.', ' ')
            ).strip()
            
            # Extract quality and codec
            for pattern, quality in quality_patterns.items():
                if pattern in raw_title:
                    result['quality'] = quality
                    break
            
            for pattern, codec in codec_patterns.items():
                if pattern in raw_title:
                    result['codec'] = codec
                    break
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing title '{raw_title}': {str(e)}")
            return None

# Define a single request template with timeout and retries
def make_api_request(api_url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> requests.Response:
    """Make API request with improved error handling and retries"""
    session = requests.Session()
    retries = 3
    backoff_factor = 0.5

    for attempt in range(retries):
        try:
            # First try - fast attempt
            if attempt == 0:
                response = session.get(
                    api_url,
                    params=params,
                    timeout=1,
                    allow_redirects=False
                )
                response.raise_for_status()
                return response

            # Subsequent retries - more robust attempt
            headers = headers or {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            }
            
            # Add exponential backoff delay
            time.sleep(backoff_factor * (2 ** attempt))
            
            response = session.get(
                api_url,
                params=params,
                headers=headers,
                timeout=10,
                allow_redirects=True,
                verify=True
            )
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:  # Last attempt
                raise
            logger.warning(f"Request failed (attempt {attempt + 1}/{retries}): {str(e)}")
            continue
