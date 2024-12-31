from bs4 import BeautifulSoup
import requests

def scrape_scores(url):
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

# Example usage
url = "https://www.rottentomatoes.com/m/silo"
scores = scrape_scores(url)
print(f"Critics Score: {scores['critics_score']}")
print(f"Audience Score: {scores['audience_score']}")
