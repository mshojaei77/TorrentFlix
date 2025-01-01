import requests

def get_movie_description(title: str) -> str:
    """
    Get movie description from YTS API.
    
    Args:
        title: Movie title to search for
        
    Returns:
        str: Movie description or error message
    """
    api_url = "https://yts.mx/api/v2/list_movies.json"
    params = {
        'query_term': title,
        'limit': 1  # We only need the first result
    }

    try:
        # Make API request
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()

        # Check if movies were found
        if not data.get('data', {}).get('movies'):
            return f"No movie found with title: {title}"

        # Get description from first movie result
        movie = data['data']['movies'][0]
        return movie.get('description_full', 'No description available')

    except requests.exceptions.RequestException as e:
        return f"Error fetching movie data: {str(e)}"
    except (KeyError, IndexError) as e:
        return f"Error parsing movie data: {str(e)}"

# Example usage:
description = get_movie_description("Inception")
print(description)