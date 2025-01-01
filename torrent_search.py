from providers.metadata.metacritic import MetacriticSource
from providers.metadata.rotten_tomatoes import RottenTomatoesSource
from providers.metadata.tmdb import TMDBClient
from domin.models import Movie, Torrent, TorrentSource
from utils.chaching import Cache
from providers.metadata import MetadataSource
from utils.error_hadlings import MovieSearchError, MovieAPIError, ConnectionBlockedError
from utils.http_client import make_api_request


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
        self.current_source = TorrentSource.YTS
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

    def search_movies(self, query: str, source: TorrentSource, limit: int = 50) -> List[Movie]:
        """Main search method that delegates to specific source searchers"""
        try:
            # Clear caches before each new search
            self.clear_cache()
            
            if source == TorrentSource.YTS:
                return self._search_yts(query, limit)
            elif source == TorrentSource.LEETX:
                return self._search_leetx_tv(query, limit)
            else:
                raise ValueError(f"Unsupported torrent source: {source.config['name']}")
        except Exception as e:
            logger.error(f"Search failed for {source.config['name']}: {str(e)}")
            raise MovieSearchError(f"Search failed: {str(e)}")

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
            response = self._make_request(api_url, params=params)
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

            # Handle image URLs
            for movie_data in data['data']['movies']:
                if 'large_cover_image' in movie_data:
                    movie_data['large_cover_image'] = self._get_image_url(movie_data['large_cover_image'])
                if 'background_image_original' in movie_data:
                    movie_data['background_image_original'] = self._get_image_url(movie_data['background_image_original'])

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
            # Create a new session for each search
            session = self._create_session()
            
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

            return final_results

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

    def _get_torrent_details(self, url: str) -> dict:
        """Get details from torrent page with caching"""
        try:
            # Check cache first
            cache_key = f"torrent_details_{url}"
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data

            # Fetch and parse the page
            detail_response = self._session.get(url)
            detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
            
            # Extract details
            details = {
                'magnet': detail_soup.select_one('a[href^="magnet:"]')['href'],
                # Add any other details you want to extract
            }
            
            # Cache the results
            self.cache.set(cache_key, details)
            
            return details
            
        except Exception as e:
            logger.warning(f"Failed to get torrent details for {url}: {e}")
            return {}

