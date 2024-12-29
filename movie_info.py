from imdb import IMDb

def get_movie_cast(imdb_code: str) -> list:
    """Get movie cast from IMDb using IMDbPY"""
    if not imdb_code:
        return []
        
    try:
        ia = IMDb()
        # Handle both formats - with or without 'tt' prefix
        movie_id = imdb_code.replace('tt', '') if imdb_code.startswith('tt') else imdb_code
        movie = ia.get_movie(movie_id)
        cast = []
        if movie and 'cast' in movie:
            for actor in movie['cast'][:5]:  # Get top 5 cast members
                if actor and hasattr(actor, 'get'):
                    cast.append(actor.get('name', ''))
        return cast
    except Exception as e:
        print(f"Error getting cast: {e}")
        return []



# Example usage
if __name__ == "__main__":
    # Example IMDb code for "Barbie" (2023)
    imdb_code = "tt1517268"
    cast = get_movie_cast(imdb_code)
    print(f"Cast for movie with IMDb code {imdb_code}:")
    for actor in cast:
        print(f"- {actor}")
