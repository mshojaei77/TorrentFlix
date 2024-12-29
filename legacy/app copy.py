import logging
import os
import subprocess
from dataclasses import dataclass
from typing import List
import requests
from PyQt5.QtWidgets import QApplication, QMainWindow, QSizePolicy, QPushButton, QLineEdit, QVBoxLayout, QTableWidget, QTableWidgetItem, QDialog, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt, QFile, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon
from app_ui import Ui_MainWindow
import sys
import json
from collections import deque
from pathlib import Path
from datetime import datetime
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class Torrent:
    quality: str
    url: str
    size: str  # Add size information
    seeds: int
    peers: int
    date_uploaded: str

@dataclass(frozen=True)
class Movie:
    title: str
    torrents: List[Torrent]
    poster_url: str  # Add poster URL
    rating: float
    genres: List[str]
    synopsis: str
    year: int
    language: str
    runtime: int
    imdb_code: str
    cast: List[str]  # Add cast information
    download_count: int

class MovieSearchError(Exception):
    """Base exception for movie search errors"""
    pass

class MovieAPIError(MovieSearchError):
    """Raised when the movie API returns an error"""
    pass

class ConnectionBlockedError(MovieSearchError):
    """Raised when connection is blocked or reset"""
    pass

class PosterDownloader(QThread):
    finished = pyqtSignal(str, QPixmap)
    
    def __init__(self, url: str, movie_title: str):
        super().__init__()
        self.url = url
        self.movie_title = movie_title
        
    def run(self):
        try:
            response = requests.get(self.url)
            response.raise_for_status()
            
            # Save temporarily and create QPixmap
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp.write(response.content)
                pixmap = QPixmap(tmp.name)
                self.finished.emit(self.movie_title, pixmap)
        except Exception as e:
            logger.error(f"Failed to download poster: {e}")

class MovieSelectionDialog(QDialog):
    def __init__(self, movies, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Movie")
        self.setMinimumWidth(400)
        self.setMinimumHeight(600)
        
        layout = QVBoxLayout()
        self.movie_list = QListWidget()
        
        for movie in movies:
            item = QListWidgetItem(f"{movie.title} ({movie.year})")
            item.setData(Qt.UserRole, movie)
            self.movie_list.addItem(item)
            
        layout.addWidget(self.movie_list)
        self.setLayout(layout)
        
        # Connect double click to accept
        self.movie_list.itemDoubleClicked.connect(self.accept)

    def get_selected_movie(self):
        if self.movie_list.currentItem():
            return self.movie_list.currentItem().data(Qt.UserRole)
        return None

class MovieSearchApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon('app.png'))
        self._init_ui()
        self._connect_signals()
        self.history = deque(maxlen=50)  # Limit history to 50 items
        self.current_history_index = -1
        self._load_history()
        self.poster_cache = {}  # Cache for movie posters
        self.current_movies = []  # Store current search results
        self.download_threads = []  # Track download threads

    def _init_ui(self):
        self.setupUi(self)
        self._load_stylesheet()
        self.resultsLayout.setAlignment(Qt.AlignTop)

    def _load_stylesheet(self):
        style_file = QFile("style.qss")
        style_file.open(QFile.ReadOnly | QFile.Text)
        stylesheet = str(style_file.readAll(), encoding='utf-8')
        self.setStyleSheet(stylesheet)

    def _connect_signals(self):
        self.searchInput.returnPressed.connect(self._perform_search)
        self.searchButton.clicked.connect(self._perform_search)
        # Add key press event handlers
        self.searchInput.keyPressEvent = self._handle_key_press

    def _handle_key_press(self, event):
        if event.key() == Qt.Key_Up:
            # Move to next item in history, wrapping around to start if at end
            if not self.history:
                return
                
            if self.current_history_index >= len(self.history) - 1:
                self.current_history_index = 0
            else:
                self.current_history_index += 1
                
            self.searchInput.setText(self.history[self.current_history_index])
        else:
            # Call the original QLineEdit keyPressEvent for other keys
            QLineEdit.keyPressEvent(self.searchInput, event)

    def _navigate_history(self, direction):
        if not self.history:
            return

        new_index = self.current_history_index + direction
        if -1 <= new_index < len(self.history):
            self.current_history_index = new_index
            if new_index == -1:
                self.searchInput.setText("")
            else:
                self.searchInput.setText(self.history[new_index])

    def _perform_search(self):
        query = self.searchInput.text()
        if not query:
            self._show_error("Please enter a movie title")
            return

        # Add to history only if it's a new search
        if not self.history or query != self.history[-1]:
            self.history.append(query)
            self._save_history()
        
        self.current_history_index = -1  # Reset history index
        try:
            self._clear_results()
            movies = self._search_movies(query)
            if not movies:
                self._show_no_results()
                return

            # Show movie selection dialog
            dialog = MovieSelectionDialog(movies, self)
            if dialog.exec_() == QDialog.Accepted:
                selected_movie = dialog.get_selected_movie()
                if selected_movie:
                    self._display_movies([selected_movie])  # Pass as list to maintain compatibility
            else:
                self._clear_results()

        except ConnectionBlockedError as e:
            logger.error(f"Connection blocked: {str(e)}")
            self._show_error("ERROR: Please enable your VPN before searching for torrents!", "vpnErrorLabel")
        except MovieSearchError as e:
            logger.error(f"Search failed: {str(e)}")
            self._show_error(f"Error: {str(e)}")

    def _show_error(self, message: str, label_id: str = "errorLabel"):
        self._clear_results()
        self.errorLabel.setText(message)
        self.errorLabel.setObjectName(label_id)
        self.errorLabel.setVisible(True)

    def _show_no_results(self):
        self.noResultsLabel.setVisible(True)

    def _clear_results(self):
        self.errorLabel.setVisible(False)
        self.noResultsLabel.setVisible(False)

    def _display_movies(self, movies: List[Movie]):
        self.current_movies = movies
        # Clear previous results first
        self._clear_results()
        
        # Display first movie's detailed information
        if movies:
            movie = movies[0]
            self._display_movie_details(movie)
            
            # Setup torrents in torrents tab
            self._setup_torrents_tab(movie.torrents)

        # Download and display movie poster
        if movies and movies[0].poster_url:
            if movies[0].title in self.poster_cache:
                self.posterLabel.setPixmap(self.poster_cache[movies[0].title])
            else:
                downloader = PosterDownloader(movies[0].poster_url, movies[0].title)
                downloader.finished.connect(self._handle_poster_downloaded)
                downloader.start()
                self.download_threads.append(downloader)

    def _display_movie_details(self, movie):
        # Set movie title
        self.movieTitleLabel.setText(movie.title)
        
        # Set IMDb rating if available
        if hasattr(movie, 'rating'):
            self.imdbRatingLabel.setText(f"★ {movie.rating}/10")
        else:
            self.imdbRatingLabel.setText("Rating not available")
        
        # Set genres
        if hasattr(movie, 'genres'):
            self.genresLabel.setText(", ".join(movie.genres))

        
        # Set plot/synopsis
        if hasattr(movie, 'synopsis'):
            self.plotLabel.setText(movie.synopsis)
        
        # Set detailed information
        details = {
            'releaseYearValue': getattr(movie, 'year', 'N/A'),
            'languageValue': getattr(movie, 'language', 'N/A'),
            'durationValue': getattr(movie, 'runtime', 'N/A'),
        }
        
        # Update all detail labels
        for label_name, value in details.items():
            if hasattr(self, label_name):
                getattr(self, label_name).setText(str(value))

    def _setup_torrents_tab(self, torrents: List[Torrent]):
        # Clear existing content in torrents tab
        if self.torrentsTab.layout():
            while self.torrentsTab.layout().count():
                item = self.torrentsTab.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            self.torrentsTab.setLayout(QVBoxLayout())

        # Create table for torrents
        table = QTableWidget()
        table.setColumnCount(6)  # Increase column count
        table.setHorizontalHeaderLabels(["Quality", "Size", "Seeds", "Peers", "Date", "Download"])
        table.setRowCount(len(torrents))
        table.verticalHeader().setVisible(False)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        for i, torrent in enumerate(torrents):
            table.setItem(i, 0, QTableWidgetItem(torrent.quality))
            table.setItem(i, 1, QTableWidgetItem(torrent.size))
            table.setItem(i, 2, QTableWidgetItem(str(torrent.seeds)))
            table.setItem(i, 3, QTableWidgetItem(str(torrent.peers)))
            table.setItem(i, 4, QTableWidgetItem(torrent.date_uploaded))
            
            download_btn = QPushButton("Download")
            download_btn.clicked.connect(
                lambda checked, t=torrent: self._download_torrent(t)
            )
            table.setCellWidget(i, 5, download_btn)

        
        # Resize columns to fit content
        table.horizontalHeader().setStretchLastSection(True)  # Stretch last column
        table.resizeColumnsToContents()
        table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        table.horizontalHeader().setMinimumSectionSize(100)  # Minimum column width
        table.verticalHeader().setDefaultSectionSize(50)  # Set minimum row height
        self.torrentsTab.layout().addWidget(table)

    def _download_torrent(self, torrent: Torrent):
        fdm_path = r"C:\Program Files\Softdeluxe\Free Download Manager\fdm.exe"

        if not os.path.exists(fdm_path):
            logger.error("Free Download Manager not found")
            self._show_error("Free Download Manager not found. Please install it first.")
            return

        try:
            subprocess.run([fdm_path, torrent.url, "--saveto", "movie.torrent"], check=True)
            logger.info("Torrent file download started in Free Download Manager")
            self.successLabel.setText("Download started in Free Download Manager")
            self.successLabel.setVisible(True)

            # Add download statistics logging
            try:
                with open(Path.home() / '.movie_downloads.json', 'a') as f:
                    download_info = {
                        'date': datetime.now().isoformat(),
                        'quality': torrent.quality,
                        'size': torrent.size,
                        'seeds': torrent.seeds
                    }
                    json.dump(download_info, f)
                    f.write('\n')
            except Exception as e:
                logger.error(f"Failed to log download: {e}")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error launching Free Download Manager: {e}")
            self._show_error(f"Error launching Free Download Manager: {e}")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            self._show_error(f"An error occurred: {e}")

    def _search_movies(self, query: str, limit: int = 10) -> List[Movie]:
        api_url = 'https://yts.mx/api/v2/list_movies.json'
        params = {
            'query_term': query, 
            'limit': limit,
            'with_rt_ratings': True  # Get additional movie details
        }

        try:
            logger.info(f"Searching for movies with query: {query}")
            response = requests.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()

            if not data.get('data', {}).get('movies'):
                logger.warning(f"No movies found for query: {query}")
                return []

            movies = []
            for movie_data in data['data']['movies']:
                torrents = [
                    Torrent(
                        quality=t['quality'],
                        url=t['url'],
                        size=t['size'],
                        seeds=t['seeds'],
                        peers=t['peers'],
                        date_uploaded=datetime.fromisoformat(t['date_uploaded']).strftime('%Y-%m-%d')
                    )
                    for t in movie_data['torrents']
                ]
                
                movie = Movie(
                    title=movie_data['title'],
                    torrents=torrents,
                    poster_url=movie_data.get('large_cover_image'),
                    rating=movie_data.get('rating', 0.0),
                    genres=movie_data.get('genres', []),
                    synopsis=movie_data.get('synopsis', 'No plot available'),
                    year=movie_data.get('year', 0),
                    language=movie_data.get('language', 'N/A'),
                    runtime=movie_data.get('runtime', 0),
                    imdb_code=movie_data.get('imdb_code', ''),
                    cast=movie_data.get('cast', []),
                    download_count=movie_data.get('download_count', 0)
                )
                
                movies.append(movie)

            return movies

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error occurred: {str(e)}")
            raise MovieAPIError(f"Failed to fetch movies: {str(e)}")
        except (requests.exceptions.ConnectionError, ConnectionResetError) as e:
            logger.error(f"Connection blocked or reset: {str(e)}")
            raise ConnectionBlockedError("Connection blocked. Please ensure your VPN is enabled and try again.")
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}")
            raise MovieSearchError(f"Failed to process movie data: {str(e)}")

    def _load_history(self):
        history_file = Path.home() / '.movie_search_history.json'
        try:
            if history_file.exists():
                with open(history_file, 'r') as f:
                    self.history = deque(json.load(f), maxlen=50)
        except Exception as e:
            logger.error(f"Error loading search history: {e}")

    def _save_history(self):
        history_file = Path.home() / '.movie_search_history.json'
        try:
            with open(history_file, 'w') as f:
                json.dump(list(self.history), f)
        except Exception as e:
            logger.error(f"Error saving search history: {e}")

    def _handle_poster_downloaded(self, movie_title: str, pixmap: QPixmap):
        self.poster_cache[movie_title] = pixmap
        if self.current_movies and self.current_movies[0].title == movie_title:
            scaled_pixmap = pixmap.scaled(300, 400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.posterLabel.setPixmap(scaled_pixmap)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('app.png'))
    window = MovieSearchApp()
    window.show()
    sys.exit(app.exec_())