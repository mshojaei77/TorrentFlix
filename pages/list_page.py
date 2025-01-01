from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout, QListWidget, QScrollArea, QMessageBox
from PyQt5.QtCore import Qt
from components.media_card import MediaCard
from utils.api_client import APIClient

class ListPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("My Lists")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        # Tabs for different lists
        tabs_layout = QHBoxLayout()
        self.tabs = QListWidget()
        self.tabs.setFixedHeight(40)
        self.tabs.setStyleSheet("QListWidget::item { border: none; } QListWidget::item:selected { background-color: #555555; }")
        self.tabs.addItem("Watchlist")
        self.tabs.addItem("Watched")
        self.tabs.addItem("Favorites")
        self.tabs.setCurrentRow(0)
        tabs_layout.addWidget(self.tabs)
        layout.addLayout(tabs_layout)
        
        # Scroll Area for List Items
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.grid_layout = QHBoxLayout()
        self.grid_layout.setAlignment(Qt.AlignLeft)
        self.scroll_widget.setLayout(self.grid_layout)
        self.scroll.setWidget(self.scroll_widget)
        layout.addWidget(self.scroll)
        
        self.setLayout(layout)
        
        # Connect tab change
        self.tabs.currentItemChanged.connect(self.display_selected_list)
        
        # Populate initial list
        self.api_client = APIClient()
        self.display_selected_list(self.tabs.currentItem(), None)
        
    def display_selected_list(self, current, previous):
        if not current:
            return
        list_name = current.text()
        # Clear current grid
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        # Fetch movies in the list
        movies = self.api_client.get_user_list(list_name)
        
        if not movies:
            lbl = QLabel("No movies in this list.")
            lbl.setStyleSheet("color: #FFFFFF;")
            self.grid_layout.addWidget(lbl)
            return
        
        for movie in movies:
            card = MediaCard(movie)
            self.grid_layout.addWidget(card)