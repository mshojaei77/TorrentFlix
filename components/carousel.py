from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QTimer

class Carousel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        
        # Image Label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap("resources/icons/placeholder.png").scaled(800, 450, Qt.KeepAspectRatio)
        self.image_label.setPixmap(pixmap)
        layout.addWidget(self.image_label)
        
        # Navigation Buttons
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("<")
        self.next_button = QPushButton(">")
        nav_layout.addWidget(self.prev_button)
        nav_layout.addStretch()
        nav_layout.addWidget(self.next_button)
        layout.addLayout(nav_layout)
        
        self.setLayout(layout)
        
        # Connect buttons
        self.prev_button.clicked.connect(self.prev_image)
        self.next_button.clicked.connect(self.next_image)
        
        # Timer for auto-sliding
        self.timer = QTimer()
        self.timer.setInterval(5000)  # 5 seconds
        self.timer.timeout.connect(self.next_image)
        self.timer.start()
        
        # Image list
        self.images = [
            "resources/icons/placeholder.png",
            "resources/icons/placeholder.png",
            "resources/icons/placeholder.png"
        ]
        self.current_index = 0
        
    def next_image(self):
        self.current_index = (self.current_index + 1) % len(self.images)
        self.update_image()
        
    def prev_image(self):
        self.current_index = (self.current_index - 1) % len(self.images)
        self.update_image()
        
    def update_image(self):
        pixmap = QPixmap(self.images[self.current_index]).scaled(800, 450, Qt.KeepAspectRatio)
        self.image_label.setPixmap(pixmap)