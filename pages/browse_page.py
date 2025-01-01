from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QComboBox, QGridLayout, QScrollArea
from components.media_card import MediaCard
from utils.api_client import APIClient

class BrowsePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        
        # Filter Section
        filter_layout = QComboBox()
        filter_layout.addItems(["All", "Action", "Drama", "Comedy", "Horror"])
        layout.addWidget(filter_layout)
        filter_layout.currentTextChanged.connect(self.apply_filter)
        
        # Scroll Area for Movies
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.grid_layout = QGridLayout()
        scroll_widget.setLayout(self.grid_layout)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        self.setLayout(layout)
        
        # Populate movies
        self.api_client = APIClient()
        self.display_movies("All")
        
    def apply_filter(self, genre):
        self.display_movies(genre)
        
    def display_movies(self, genre):
        # Clear current grid
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Fetch movies based on genre
        movies = self.api_client.get_movies(genre)
        
        # Populate grid
        row = 0
        col = 0
        for movie in movies:
            card = MediaCard(movie)
            self.grid_layout.addWidget(card, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1