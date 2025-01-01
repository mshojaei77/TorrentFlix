from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from components.carousel import Carousel
from components.media_card import MediaCard
from utils.api_client import APIClient

class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Welcome to Streaming App")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        # Featured Carousel
        self.featured_carousel = Carousel()
        layout.addWidget(self.featured_carousel)
        
        # Content Rows
        self.trending_label = QLabel("Trending Now")
        self.trending_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.trending_label)
        
        self.trending_layout = QHBoxLayout()
        layout.addLayout(self.trending_layout)
        
        self.new_releases_label = QLabel("New Releases")
        self.new_releases_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.new_releases_label)
        
        self.new_releases_layout = QHBoxLayout()
        layout.addLayout(self.new_releases_layout)
        
        self.setLayout(layout)
        
        # Populate content
        self.populate_content()
        
    def populate_content(self):
        api_client = APIClient()
        trending_movies = api_client.get_movies("Trending")
        new_releases = api_client.get_movies("New Releases")
        
        for movie in trending_movies:
            card = MediaCard(movie)
            self.trending_layout.addWidget(card)
        
        for movie in new_releases:
            card = MediaCard(movie)
            self.new_releases_layout.addWidget(card)