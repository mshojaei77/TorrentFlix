import requests
from bs4 import BeautifulSoup
from providers.metadata import MetadataSource
import logging
import re

logger = logging.getLogger(__name__)

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

def get_metacritic_info(url):
    """Get movie or TV show info from Metacritic page and return as dictionary"""
    try:
        # Add headers to mimic browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        movie_info = {}
        
        # Get title - works for both movies and TV shows
        title = soup.find('h1')
        if title:
            movie_info['title'] = title.text.strip()
            
        # Get description/summary
        description = soup.find('span', {'class': 'c-productDetails_description'})
        if description:
            movie_info['description'] = description.text.strip()
            
        # Get director(s) - TV shows may have multiple directors
        director_div = soup.find('div', {'class': 'c-productDetails_staff_directors'})
        if director_div:
            directors = director_div.find_all('a')
            if len(directors) == 1:
                movie_info['director'] = directors[0].text.strip()
            elif len(directors) > 1:
                movie_info['directors'] = [d.text.strip() for d in directors]
                
        # Get writers
        writers_div = soup.find('div', {'class': 'c-productDetails_staff_writers'})
        if writers_div:
            writers = writers_div.find_all('a')
            movie_info['writers'] = [w.text.strip().rstrip(',') for w in writers]
            
        # Get cast
        cast = []
        cast_cards = soup.find_all('div', {'class': 'c-globalPersonCard'})
        for card in cast_cards:
            actor = card.find('h3', {'class': 'c-globalPersonCard_name'})
            role = card.find('h4', {'class': 'c-globalPersonCard_role'})
            if actor and role:
                cast.append({
                    'name': actor.text.strip(),
                    'role': role.text.strip()
                })
        movie_info['cast'] = cast
            
        # Get Metascore - works for both movies and TV shows
        metascore_div = soup.find('div', {'class': 'c-reviewsOverview_overviewDetails'})
        if metascore_div:
            score = metascore_div.find('div', {'class': ['c-siteReviewScore_green', 'c-siteReviewScore_yellow', 'c-siteReviewScore_red']})
            sentiment = metascore_div.find('span', {'class': 'c-ScoreCard_scoreSentiment'})
            if score and sentiment:
                movie_info['metascore'] = {
                    'score': score.find('span').text.strip(),
                    'sentiment': sentiment.text.strip()
                }
                
        # Get User Score
        userscore_section = soup.find('div', {'class': 'c-reviewsSection_carouselContainer-user'})
        if userscore_section:
            score = userscore_section.find('div', {'class': 'c-siteReviewScore_user'})
            sentiment = userscore_section.find('span', {'class': 'c-ScoreCard_scoreSentiment'})
            if score and sentiment:
                movie_info['user_score'] = {
                    'score': score.find('span').text.strip(),
                    'sentiment': sentiment.text.strip()
                }
            
        # Get genres
        genres = []
        genre_list = soup.find('ul', {'class': 'c-genreList'})
        if genre_list:
            for genre in genre_list.find_all('span', {'class': 'c-globalButton_label'}):
                genres.append(genre.text.strip())
            movie_info['genres'] = genres
            
        return movie_info
            
    except Exception as e:
        print(f"Error accessing Metacritic: {e}")
        return None