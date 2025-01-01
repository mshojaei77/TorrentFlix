from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QGridLayout, QScrollArea
from PyQt5.QtCore import Qt, QTimer
from components.media_card import MediaCard
from utils.api_client import APIClient

class SearchPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        
        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for movies...")
        layout.addWidget(self.search_input)
        
        # Live Search Timer
        self.timer = QTimer()
        self.timer.setInterval(500)  # 500 ms
        self.timer.setSingleShot(True)
        self.search_input.textChanged.connect(self.on_text_changed)
        self.timer.timeout.connect(self.perform_search)
        
        # Scroll Area for Results
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.grid_layout = QGridLayout()
        scroll_widget.setLayout(self.grid_layout)
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        self.setLayout(layout)
        
        # Populate Search Results
        self.api_client = APIClient()
        
    def on_text_changed(self, text):
        self.timer.start()
        
    def perform_search(self):
        query = self.search_input.text().strip()
        if not query:
            return
        # Clear previous results
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        # Fetch search results
        results = self.api_client.search_movies(query)
        
        # Display results
        row = 0
        col = 0
        for movie in results:
            card = MediaCard(movie)
            self.grid_layout.addWidget(card, row, col)
            col += 1
            if col >= 4:
                col = 0
                row += 1