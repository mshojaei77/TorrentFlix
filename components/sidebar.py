from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtCore import Qt

class Sidebar(QWidget):
    def __init__(self, navigation_manager, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)
        
        # Navigation Buttons
        self.home_button = QPushButton("Home")
        self.browse_button = QPushButton("Browse")
        self.search_button = QPushButton("Search")
        self.list_button = QPushButton("My List")
        self.profile_button = QPushButton("Profile")
        
        # Add buttons to layout
        layout.addWidget(self.home_button)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.search_button)
        layout.addWidget(self.list_button)
        layout.addWidget(self.profile_button)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Connect buttons to navigation manager
        self.home_button.clicked.connect(lambda: navigation_manager.navigate_to("Home"))
        self.browse_button.clicked.connect(lambda: navigation_manager.navigate_to("Browse"))
        self.search_button.clicked.connect(lambda: navigation_manager.navigate_to("Search"))
        self.list_button.clicked.connect(lambda: navigation_manager.navigate_to("My List"))
        self.profile_button.clicked.connect(lambda: navigation_manager.navigate_to("Profile"))
        
        # Style
        self.setStyleSheet("""
            QWidget {
                background-color: #2C2F33;
                color: #FFFFFF;
            }
            QPushButton {
                background-color: #2C2F33;
                border: none;
                padding: 15px;
                text-align: left;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #23272A;
            }
        """)