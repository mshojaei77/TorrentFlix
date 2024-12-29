import requests

api_url = 'https://yts.mx/api/v2/list_movies.json'
params = {
    'query_term': 'pulp fiction',
    'limit': 10
}

try:
    response = requests.get(api_url, params=params)
    response.raise_for_status()
    data = response.json()
    for movie in data['data']['movies']:
        print(f"Title: {movie['title']}")
        for torrent in movie['torrents']:
            print(f"Quality: {torrent['quality']}")
            print(f"Magnet Link: {torrent['url']}\n")
except requests.exceptions.HTTPError as errh:
    print("HTTP Error:", errh)
except Exception as e:
    print("An error occurred:", e)