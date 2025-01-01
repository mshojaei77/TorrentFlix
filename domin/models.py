from dataclasses import dataclass
from enum import Enum
from typing import List

@dataclass(frozen=True)
class Torrent:
    quality: str
    type: str
    url: str
    size: str
    seeds: int
    peers: int
    date_uploaded: str
    video_codec: str

@dataclass(frozen=True)
class Movie:
    title: str
    torrents: List[Torrent]
    poster_url: str
    rating: float
    genres: List[str]
    description_full: str
    year: int
    language: str
    runtime: int
    imdb_code: str
    cast: List[str]
    download_count: int
    yt_trailer_code: str
    background_image_original: str
    metacritic_url: str = ''
    metacritic_info: dict = None
    metadata: dict = None

    def with_metacritic_data(self, url: str, info: dict) -> 'Movie':
        """Creates a new Movie instance with updated Metacritic data"""
        return Movie(
            title=self.title,
            torrents=self.torrents,
            poster_url=self.poster_url,
            rating=self.rating,
            genres=self.genres,
            description_full=self.description_full,
            year=self.year,
            language=self.language,
            runtime=self.runtime,
            imdb_code=self.imdb_code,
            cast=self.cast,
            download_count=self.download_count,
            yt_trailer_code=self.yt_trailer_code,
            background_image_original=self.background_image_original,
            metacritic_url=url,
            metacritic_info=info
        )

    def with_metadata(self, metadata: dict) -> 'Movie':
        """Creates a new Movie instance with updated metadata"""
        return Movie(
            title=self.title,
            torrents=self.torrents,
            poster_url=self.poster_url,
            rating=self.rating,
            genres=self.genres,
            description_full=self.description_full,
            year=self.year,
            language=self.language,
            runtime=self.runtime,
            imdb_code=self.imdb_code,
            cast=self.cast,
            download_count=self.download_count,
            yt_trailer_code=self.yt_trailer_code,
            background_image_original=self.background_image_original,
            metadata=metadata
        )

class TorrentSource(Enum):
    YTS = {
        "name": "YTS.mx",
        "category": "Movies",
        "api_url": "https://yts.mx/api/v2/list_movies.json",
        "params": {"with_rt_ratings": True}
    }
    LEETX = {
        "name": "1337x",
        "category": "All",
        "base_url": "https://1337x.to",
        "search_url": "https://1337x.to/search/{query}/1/",
        "params": {}
    }
    RARBG = {
        "name": "RARBG",
        "category": "All",
        "api_url": "https://torrentapi.org/pubapi_v2.php",
        "params": {"mode": "search", "ranked": 0, "token": None}
    }
    TORRENTGALAXY = {
        "name": "TorrentGalaxy",
        "category": "All",
        "search_url": "https://torrentgalaxy.to/torrents.php?search={query}#results",
        "params": {}
    }
    EZTVX = {
        "name": "EZTVx",
        "category": "TV Series",
        "search_url": "https://eztvx.to/search/{query}",
        "params": {}
    }
    EXT = {
        "name": "EXT",
        "category": "All",
        "search_url": "https://ext.to/search/?q={query}",
        "params": {}
    }
    OXTORRENT = {
        "name": "OxTorrent",
        "category": "All",
        "search_url": "https://www.oxtorrent.co/recherche/{query}",
        "params": {}
    }
    THEPIRATEBAY = {
        "name": "The Pirate Bay",
        "category": "All",
        "search_url": "https://thepiratebay.org/search.php?q={query}&all=on&search=Pirate+Search&page=0&orderby=",
        "params": {}
    }
    LIMETORRENTS = {
        "name": "LimeTorrents",
        "category": "All",
        "search_url": "https://www.limetorrents.lol/search/all/{query}/",
        "params": {}
    }
    TORRENTDOWNLOADS = {
        "name": "TorrentDownloads",
        "category": "All",
        "search_url": "https://www.torrentdownloads.pro/search/?search={query}",
        "params": {}
    }
    TORLOCK = {
        "name": "Torlock",
        "category": "All",
        "search_url": "https://www.torlock.com/?qq=1&q={query}",
        "params": {}
    }
    # Add more sources as needed

    @property
    def config(self) -> dict:
        """Returns the configuration dictionary for the source"""
        return self.value

    @classmethod
    def from_display_name(cls, name: str) -> 'TorrentSource':
        """Returns the TorrentSource enum based on its display name"""
        for source in cls:
            if source.value["name"] == name:
                return source
        raise ValueError(f"No TorrentSource found with name: {name}")

    @classmethod
    def get_category(cls, source) -> str:
        """Returns the category of the torrent source"""
        return source.config["category"]

    @classmethod
    def get_sources_by_category(cls) -> dict:
        """Returns a dictionary of sources grouped by category with specific ordering"""
        # Define preferred order for each category
        category_order = {
            'Movies': [cls.YTS],  # YTS first for movies
            'TV Series': [cls.LEETX, cls.EZTVX],  # LEETX first for TV series
            'All': [cls.LEETX, cls.RARBG, cls.TORRENTGALAXY, cls.EXT, 
                   cls.OXTORRENT, cls.THEPIRATEBAY, cls.LIMETORRENTS,
                   cls.TORRENTDOWNLOADS, cls.TORLOCK]
        }
        
        # Initialize categories dict
        categories = {cat: [] for cat in category_order.keys()}
        
        # First add sources in preferred order
        for category, preferred_sources in category_order.items():
            categories[category].extend(preferred_sources)
            
        # Then add remaining sources that weren't explicitly ordered
        for source in cls:
            category = cls.get_category(source)
            if category in categories and source not in categories[category]:
                categories[category].append(source)
                
        return categories
    