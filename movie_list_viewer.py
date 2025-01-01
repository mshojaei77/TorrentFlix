import os
import json
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QComboBox, QVBoxLayout, 
                            QWidget, QScrollArea, QLabel, QHBoxLayout, QGridLayout)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import urllib.request
import logging
from typing import Optional, Dict, Any
import time
from app import MovieSearchApp

logger = logging.getLogger(__name__)

class PosterDownloader(QThread):
    poster_ready = pyqtSignal(str, str)  # movie_title, poster_path
    
    def __init__(self, movie_title: str, yts_api_url: str, posters_dir: str):
        super().__init__()
        self.movie_title = movie_title
        self.yts_api_url = yts_api_url
        self.posters_dir = posters_dir
        
    def run(self):
        poster_path = self._get_movie_poster()
        if poster_path:
            self.poster_ready.emit(self.movie_title, poster_path)
            
    def _get_movie_poster(self) -> Optional[str]:
        """Get movie poster path, downloading if needed"""
        try:
            safe_filename = "".join(x for x in self.movie_title if x.isalnum() or x in (' ','-','_')).rstrip()
            poster_path = os.path.join(self.posters_dir, f"{safe_filename}.jpg")

            if os.path.exists(poster_path):
                logger.debug(f"Using saved poster for {self.movie_title}")
                return poster_path

            params = {
                'query_term': self.movie_title,
                'limit': 1,
                'with_rt_ratings': True
            }
            
            retries = 3
            backoff_factor = 0.5
            
            for attempt in range(retries):
                try:
                    logger.debug(f"Searching for {self.movie_title} on YTS API (attempt {attempt + 1})")
                    
                    if attempt > 0:
                        time.sleep(backoff_factor * (2 ** attempt))
                    
                    response = requests.get(
                        self.yts_api_url, 
                        params=params,
                        timeout=10,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                            'Accept': 'application/json'
                        }
                    )
                    response.raise_for_status()
                    data = response.json()

                    if data.get('data', {}).get('movies'):
                        movie_data = data['data']['movies'][0]
                        poster_url = movie_data.get('large_cover_image')
                        
                        if poster_url:
                            request = urllib.request.Request(
                                poster_url,
                                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                            )
                            with urllib.request.urlopen(request, timeout=10) as response:
                                with open(poster_path, 'wb') as f:
                                    f.write(response.read())
                            return poster_path
                            
                    break
                    
                except requests.exceptions.RequestException as e:
                    if attempt == retries - 1:
                        logger.error(f"Failed to fetch movie after {retries} attempts: {str(e)}")
                        return None
                    continue
                    
        except Exception as e:
            logger.error(f"Error fetching poster for {self.movie_title}: {str(e)}")
        return None

class MovieListViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Movie List Viewer")
        self.setGeometry(100, 100, 1800, 1000)

        # Apply stylesheet
        with open('movie_list_viewer.qss', 'r') as f:
            self.setStyleSheet(f.read())

        self.yts_api_url = "https://yts.mx/api/v2/list_movies.json"
        self.movie_posters = {}
        self.poster_downloaders = []
        
        # Simplified layout structure
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Combobox setup
        self.file_combo = QComboBox()
        self.file_combo.setFixedHeight(80)
        self.file_combo.setMinimumWidth(400)
        self.file_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.file_combo.setObjectName("fileCombo")
        main_layout.addWidget(self.file_combo, 0, Qt.AlignCenter)

        # Direct grid layout in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("scrollArea")
        
        self.scroll_widget = QWidget()
        self.scroll_widget.setObjectName("scrollWidget")
        self.scroll_layout = QGridLayout(self.scroll_widget)
        self.scroll_layout.setSpacing(10)
        scroll_area.setWidget(self.scroll_widget)
        main_layout.addWidget(scroll_area)

        self.json_files = [f for f in os.listdir('lists') if f.endswith('.json')]
        formatted_files = [f.replace('-', ' ').replace('_', ' ').replace('.json', '').title() 
                         for f in self.json_files]
        self.file_combo.addItems(formatted_files)

        self.posters_dir = 'posters'
        if not os.path.exists(self.posters_dir):
            os.makedirs(self.posters_dir)

        self.file_combo.currentTextChanged.connect(self.update_movie_list)

        if self.json_files:
            self.update_movie_list(formatted_files[0])

        # Modify scroll area
        scroll_area.setObjectName("scrollArea")
        self.scroll_widget.setObjectName("scrollWidget")
        
        # Store reference to search app
        self.search_app = None
        
    def update_poster(self, movie_title: str, poster_path: str):
        """Update movie poster when downloaded"""
        if movie_title in self.movie_posters:
            try:
                pixmap = QPixmap(poster_path)
                pixmap = pixmap.scaled(200, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # Larger poster size
                self.movie_posters[movie_title].setPixmap(pixmap)
            except Exception as e:
                logger.error(f"Error loading poster image for {movie_title}: {str(e)}")

        

    def update_movie_list(self, formatted_name: str) -> None:
        """Update the movie list display"""
        try:
            # Clear existing widgets
            for i in reversed(range(self.scroll_layout.count())): 
                self.scroll_layout.itemAt(i).widget().setParent(None)

            filename = formatted_name.lower().replace(' ', '-') + '.json'
            file_path = os.path.join('lists', filename)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                movies = json.load(f)

            self.movie_posters.clear()
            self.poster_downloaders.clear()
            placeholder = QPixmap(200, 300)  # Larger placeholder
            placeholder.fill(Qt.lightGray)

            # Calculate grid dimensions
            num_columns = 6  # Number of movies per row
            current_row = 0
            current_col = 0

            for movie in movies:
                # Movie widget creation
                movie_widget = QWidget()
                movie_widget.setObjectName("movieWidget")
                movie_layout = QVBoxLayout(movie_widget)
                movie_layout.setContentsMargins(5, 5, 5, 5)

                # Add click handling to movie widget
                movie_widget.mousePressEvent = lambda e, title=movie: self._handle_movie_click(e, title)
                movie_widget.setCursor(Qt.PointingHandCursor)  # Change cursor to hand on hover

                # Poster label
                poster_label = QLabel()
                poster_label.setObjectName("posterLabel")
                poster_label.setPixmap(placeholder.scaled(180, 270, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                movie_layout.addWidget(poster_label, alignment=Qt.AlignCenter)
                self.movie_posters[movie] = poster_label

                # Title label
                title_label = QLabel(movie)
                title_label.setObjectName("movieTitle")
                title_label.setWordWrap(True)
                title_label.setAlignment(Qt.AlignCenter)
                movie_layout.addWidget(title_label)

                self.scroll_layout.addWidget(movie_widget, current_row, current_col)
                
                # Update grid position
                current_col += 1
                if current_col >= num_columns:
                    current_col = 0
                    current_row += 1

                # Start poster download
                downloader = PosterDownloader(movie, self.yts_api_url, self.posters_dir)
                downloader.poster_ready.connect(self.update_poster)
                self.poster_downloaders.append(downloader)
                downloader.start()

        except Exception as e:
            error_label = QLabel(f"Error reading {formatted_name}: {str(e)}")
            error_label.setStyleSheet("color: red;")
            self.scroll_layout.addWidget(error_label, 0, 0)

    def _handle_movie_click(self, event, movie_title: str):
        """Handle click on movie widget by opening search app"""
        if event.button() == Qt.LeftButton:
            # Create search app if not exists
            if not self.search_app:
                self.search_app = MovieSearchApp()
                self.search_app.resize(1280, 900)
                
                # Center window on screen
                screen = QApplication.primaryScreen().geometry()
                x = (screen.width() - self.search_app.width()) // 2
                y = (screen.height() - self.search_app.height()) // 2
                self.search_app.move(x, y)

            # Set search text and perform search
            self.search_app.searchInput.setText(movie_title)
            self.search_app._perform_search()
            self.search_app.show()
            self.search_app.raise_()
            self.search_app.activateWindow()

if __name__ == '__main__':
    app = QApplication([])
    window = MovieListViewer()
    window.show()
    app.exec_()
