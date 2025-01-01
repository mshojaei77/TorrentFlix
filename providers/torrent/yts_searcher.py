from providers.torrent import BaseTorrentSearcher
from domin.models import Movie, Torrent, TorrentSource
from utils.error_hadlings import MovieSearchError, MovieAPIError, ConnectionBlockedError
from datetime import datetime
from typing import List
import requests
import logging

logger = logging.getLogger(__name__)

class YTSSearcher(BaseTorrentSearcher):
    def __init__(self):
        super().__init__()
        self.current_source = TorrentSource.YTS

    def search_movies(self, query: str, limit: int = 50) -> List[Movie]:
        """Search YTS.mx API for movies"""
        try:
            # Clear caches before each new search
            self.clear_cache()
            
            return self._search_yts(query, limit)
        except Exception as e:
            logger.error(f"Search failed for {self.current_source.config['name']}: {str(e)}")
            raise MovieSearchError(f"Search failed: {str(e)}")

    def _search_yts(self, query: str, limit: int) -> List[Movie]:
        """Internal method to search YTS"""
        source_config = self.current_source.config
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