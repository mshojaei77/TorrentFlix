from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, pyqtSignal

class MediaCard(QWidget):
    clicked = pyqtSignal(dict)
    
    def __init__(self, movie, parent=None):
        super().__init__(parent)
        self.movie = movie
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout()
        
        # Poster
        self.poster = QLabel()
        pixmap = QPixmap(movie.get('poster', 'resources/icons/placeholder.png')).scaled(150, 225, Qt.KeepAspectRatio)
        self.poster.setPixmap(pixmap)
        layout.addWidget(self.poster, alignment=Qt.AlignCenter)
        
        # Title
        self.title = QLabel(movie.get('title', 'Unknown'))
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        
        self.setLayout(layout)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.movie)