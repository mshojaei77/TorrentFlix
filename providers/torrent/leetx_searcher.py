from providers.torrent import BaseTorrentSearcher
from domin.models import Movie, Torrent, TorrentSource
from utils.error_hadlings import MovieSearchError, MovieAPIError, ConnectionBlockedError
from datetime import datetime
from typing import List
import requests
import logging
from providers.metadata.tmdb import TMDBClient
from bs4 import BeautifulSoup
from collections import defaultdict
import re
import time
from providers.metadata.tmdb import TMDBClient
from typing import Optional

logger = logging.getLogger(__name__)

class LeetxTVSearcher(BaseTorrentSearcher):
    def __init__(self):
        super().__init__()
        self.current_source = TorrentSource.LEETX

    def search_tv_series(self, query: str, limit: int = 50) -> List[Movie]:
        """Search 1337x for TV series using web scraping"""
        try:
            # Clear caches before each new search
            self.clear_cache()
            
            return self._search_leetx_tv(query, limit)
        except Exception as e:
            logger.error(f"Search failed for {self.current_source.config['name']}: {str(e)}")
            raise MovieSearchError(f"Search failed: {str(e)}")

    def _search_leetx_tv(self, query: str, limit: int) -> List[Movie]:
        """Internal method to search 1337x for TV series"""
        source_config = self.current_source.config
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
                next_page = soup.select_one('div.pagination a', text=re.compile(r'Next', re.IGNORECASE))
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

    def _parse_show_title(self, raw_title: str) -> Optional[dict]:
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
