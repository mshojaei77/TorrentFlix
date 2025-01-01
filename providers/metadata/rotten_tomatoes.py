from providers.metadata import MetadataSource
import logging
import re
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

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
    
def rotten_scores(title: str, type:str):

    if type == 'movie':
        url = f"https://www.rottentomatoes.com/m/{title}"
    elif type == 'tv':
        url = f"https://www.rottentomatoes.com/tv/{title}"
    else:
        return None
    # Send HTTP request and get the HTML content
    response = requests.get(url)
    html_content = response.text
    
    # Create BeautifulSoup object to parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find critics score (Tomatometer)
    critics_score = soup.find('rt-text', {'slot': 'criticsScore'})
    critics_score = critics_score.text.strip() if critics_score else 'N/A'
    
    # Find audience score (Popcornmeter) 
    audience_score = soup.find('rt-text', {'slot': 'audienceScore'})
    audience_score = audience_score.text.strip() if audience_score else 'N/A'
    
    return {
        'critics_score': critics_score,
        'audience_score': audience_score
    }
