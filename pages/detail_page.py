from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from components.video_player import VideoPlayer

class DetailPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        
        # Movie Title
        self.title_label = QLabel("Movie Title")
        self.title_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.title_label)
        
        # Poster and Description
        poster_desc_layout = QHBoxLayout()
        
        self.poster_label = QLabel()
        pixmap = QPixmap("resources/icons/placeholder.png").scaled(200, 300, Qt.KeepAspectRatio)
        self.poster_label.setPixmap(pixmap)
        poster_desc_layout.addWidget(self.poster_label)
        
        self.description_label = QLabel("Movie description goes here...")
        self.description_label.setWordWrap(True)
        poster_desc_layout.addWidget(self.description_label)
        
        layout.addLayout(poster_desc_layout)
        
        # Play Button
        self.play_button = QPushButton("Play")
        self.play_button.setFixedWidth(100)
        layout.addWidget(self.play_button, alignment=Qt.AlignCenter)
        
        # Video Player
        self.video_player = VideoPlayer()
        layout.addWidget(self.video_player)
        
        self.setLayout(layout)
        
        # Connect Play Button
        self.play_button.clicked.connect(self.play_movie)
        
    def set_movie_details(self, movie):
        # Update UI elements with movie details
        self.title_label.setText(movie.get('title', 'Unknown'))
        self.description_label.setText(movie.get('description', 'No description available.'))
        poster_path = movie.get('poster', 'resources/icons/placeholder.png')
        pixmap = QPixmap(poster_path).scaled(200, 300, Qt.KeepAspectRatio)
        self.poster_label.setPixmap(pixmap)
        # Set video source if available
        video_path = movie.get('video', None)
        if video_path:
            self.video_player.open_file(video_path)
        
    def play_movie(self):
        self.video_player.play_pause()