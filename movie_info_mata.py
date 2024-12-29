import requests
from bs4 import BeautifulSoup

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

if __name__ == "__main__":
    # Test with both a movie and TV show
    movie_data = get_metacritic_info("https://www.metacritic.com/movie/killer-heat/")
    print(movie_data)

