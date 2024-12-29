import logging
import os
import subprocess
from dataclasses import dataclass
from typing import List
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout,
                                QWidget, QDialog, QListWidget, QAbstractItemView,QListWidgetItem,QGridLayout,QSizePolicy)
from PyQt5.QtCore import Qt, QFile, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon, QPainter, QPainterPath, QBrush, QPalette
from app_ui import Ui_MainWindow
import sys
import json
from collections import deque
from pathlib import Path
from datetime import datetime
import tempfile

from movie_info_mata import get_metacritic_info

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class Torrent:
    quality: str
    type: str
    url: str
    size: str  # Add size information
    seeds: int
    peers: int
    date_uploaded: str
    video_codec: str
    

@dataclass(frozen=True)
class Movie:
    title: str
    torrents: List[Torrent]
    poster_url: str  # Add poster URL
    rating: float
    genres: List[str]
    description_full: str
    year: int
    language: str
    runtime: int
    imdb_code: str
    cast: List[str]  # Add cast information
    download_count: int
    yt_trailer_code: str
    background_image_original: str
    metacritic_url: str = ''  # Add new field for Metacritic URL
    metacritic_info: dict = None  # Add new field for Metacritic data

    def with_metacritic_data(self, url: str, info: dict) -> 'Movie':
        """Creates a new Movie instance with updated Metacritic data"""
        return Movie(
            title=self.title,
            torrents=self.torrents,
            poster_url=self.poster_url,
            rating=self.rating,
            genres=self.genres,
            description_full=self.description_full,
            year=self.year,
            language=self.language,
            runtime=self.runtime,
            imdb_code=self.imdb_code,
            cast=self.cast,
            download_count=self.download_count,
            yt_trailer_code=self.yt_trailer_code,
            background_image_original=self.background_image_original,
            metacritic_url=url,
            metacritic_info=info
        )

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
        self.setFixedSize(600, 600)  # Use setFixedSize for better control
        
        layout = QVBoxLayout(self)  # Set layout directly to the dialog
        self.movie_list = QListWidget()
        self.movie_list.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # Add this line to remove the focus rectangle
        self.movie_list.setFocusPolicy(Qt.NoFocus)
        
        # Populate the movie list with items
        for movie in movies:
            item = QListWidgetItem(f"{movie.title} ({movie.year})")
            item.setData(Qt.UserRole, movie)
            # Remove dots by disabling text elision
            item.setTextAlignment(Qt.AlignLeft)
            self.movie_list.addItem(item)
            
        # Disable text elision at the widget level
        self.movie_list.setTextElideMode(Qt.ElideNone)
        
        layout.addWidget(self.movie_list)
        
        # Connect double click to accept
        self.movie_list.itemDoubleClicked.connect(self.accept)

    def get_selected_movie(self):
        return self.movie_list.currentItem().data(Qt.UserRole) if self.movie_list.currentItem() else None

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
        self.background_cache = {}  # Add cache for background images
        self.current_movies = []  # Store current search results
        self.download_threads = []  # Track download threads
        self.detailsTabWidget.hide()

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
            # Move to previous item in history, wrapping around to end if at start
            if not self.history:
                return
                
            if self.current_history_index <= 0:
                self.current_history_index = len(self.history) - 1
            else:
                self.current_history_index -= 1
                
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
                    # Find Metacritic URL and fetch info only for selected movie
                    metacritic_url = self._find_metacritic_url(selected_movie.title, selected_movie.year)
                    metacritic_info = get_metacritic_info(metacritic_url) if metacritic_url else None
                    # Create new instance with Metacritic data
                    selected_movie = selected_movie.with_metacritic_data(metacritic_url, metacritic_info)
                    self._display_movies([selected_movie])
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
        
        # Hide details tab widget while updating
        self.detailsTabWidget.hide()
        
        # Display first movie's detailed information
        if movies:
            movie = movies[0]
            self._display_movie_details(movie)
            
            # Setup torrents in torrents tab
            self._setup_torrents_tab(movie.torrents)
            
            # Show details tab widget after updating
            self.detailsTabWidget.show()

            # Download and set background image
            if movie.background_image_original:
                if movie.title in self.background_cache:
                    self._set_background(self.background_cache[movie.title])
                else:
                    downloader = PosterDownloader(movie.background_image_original, movie.title)
                    downloader.finished.connect(self._handle_background_downloaded)
                    downloader.start()
                    self.download_threads.append(downloader)

            # Download and display movie poster
            if movie.poster_url:
                if movie.title in self.poster_cache:
                    self.posterLabel.setPixmap(self.poster_cache[movie.title])
                else:
                    downloader = PosterDownloader(movie.poster_url, movie.title)
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
        
        # Set plot/description with preference for Metacritic description when original is short/missing
        description = getattr(movie, 'description_full', '')
        metacritic_description = movie.metacritic_info.get('description', '') if movie.metacritic_info else ''
        
        # Use Metacritic description if original is missing/short or Metacritic is longer
        if not description and not metacritic_description:
            self.plotLabel.setText("")
        elif not description or len(description) < 100 or (metacritic_description and len(metacritic_description) > len(description)):
            self.plotLabel.setText(metacritic_description or description)
        else:
            self.plotLabel.setText(description)
        
        # Set basic movie details
        details = {
            'releaseYearValue': getattr(movie, 'year', 'N/A'),
            'languageValue': getattr(movie, 'language', 'N/A'),
            'durationValue': f"{getattr(movie, 'runtime', 'N/A')} min" if getattr(movie, 'runtime', 'N/A') != 'N/A' else 'N/A',
        }
        
        # Set title labels
        self.releaseYearLabel.setText("Release Year:")
        self.languageLabel.setText("Language:")
        self.durationLabel.setText("Duration:")
        
        # Update basic detail labels
        for label_name, value in details.items():
            if hasattr(self, label_name):
                getattr(self, label_name).setText(str(value))
        
        # Set Metacritic scores if available
        if movie.metacritic_info:
            if 'metascore' in movie.metacritic_info:
                metascore = movie.metacritic_info['metascore']
                self.metascoreLabel.setText("Metascore:")
                self.metascoreValue.setText(f"{metascore['score']} - {metascore['sentiment']}")
            
            if 'user_score' in movie.metacritic_info:
                user_score = movie.metacritic_info['user_score']
                self.userScoreLabel.setText("User Score:")
                self.userScoreValue.setText(f"{user_score['score']} - {user_score['sentiment']}")
            
            # Set director
            if 'director' in movie.metacritic_info:
                self.directorLabel.setText("Director:")
                self.directorValue.setText(movie.metacritic_info['director'])
            
            # Set writers
            if 'writers' in movie.metacritic_info:
                self.writersLabel.setText("Writers:")
                self.writersValue.setText(", ".join(movie.metacritic_info['writers']))
            
            # Populate cast group box
            if 'cast' in movie.metacritic_info:
                # Create grid layout for cast info if not exists
                if not self.castGroupBox.layout():
                    cast_layout = QGridLayout()
                    self.castGroupBox.setLayout(cast_layout)
                else:
                    cast_layout = self.castGroupBox.layout()
                    # Clear existing widgets
                    while cast_layout.count():
                        item = cast_layout.takeAt(0)
                        if item.widget():
                            item.widget().deleteLater()
                
                # Add header row
                name_header = QLabel("Actor")
                role_header = QLabel("Role")
                cast_layout.addWidget(name_header, 0, 0)
                cast_layout.addWidget(role_header, 0, 1)
                
                # Add cast members
                for i, cast_member in enumerate(movie.metacritic_info['cast'], 1):
                    name_label = QLabel(cast_member['name'])
                    role_label = QLabel(cast_member['role'])
                    cast_layout.addWidget(name_label, i, 0)
                    cast_layout.addWidget(role_label, i, 1)
                
                self.castGroupBox.setLayout(cast_layout)
        # Set YouTube trailer link if available
        if hasattr(movie, 'yt_trailer_code') and movie.yt_trailer_code:
            self.ytLabel.setText("Trailer:")
            trailer_url = f"https://www.youtube.com/watch?v={movie.yt_trailer_code}"
            self.ytValue.setText(f'''
                <a href="{trailer_url}" style="
                    color: #2196F3;
                    text-decoration: none;
                    font-weight: 500;
                    padding: 4px 8px;
                    border-radius: 4px;
                    transition: all 0.2s ease;
                ">Watch Trailer</a>
            ''')
            self.ytValue.setOpenExternalLinks(True)
        else:
            self.ytLabel.setText("Trailer:")
            self.ytValue.setText("Not available")

    def _setup_torrents_tab(self, torrents: List[Torrent]):
        # Remove existing layout if it exists
        if self.torrentsTab.layout():
            QWidget().setLayout(self.torrentsTab.layout())
    
        # Create and set new layout
        layout = QVBoxLayout()
        
        # Add headers for the torrent information
        header_widget = QHBoxLayout()
        header_widget.addWidget(QLabel("Quality"))
        header_widget.addWidget(QLabel("Video Codec"))  
        header_widget.addWidget(QLabel("Size"))
        header_widget.addWidget(QLabel("Seeds"))
        header_widget.addWidget(QLabel("Peers"))
        
        header_widget.addWidget(QLabel(""))
        layout.addLayout(header_widget)

        for torrent in torrents:
            torrent_widget = QHBoxLayout()
            
            quality_label = QLabel(torrent.quality)
            size_label = QLabel(torrent.size)
            seeds_label = QLabel(str(torrent.seeds))
            peers_label = QLabel(str(torrent.peers))
            video_codec_label = QLabel(torrent.video_codec)  # Added Video Codec label
            
            download_btn = QPushButton("Download")
            download_btn.clicked.connect(
                lambda checked, t=torrent: self._download_torrent(t)
            )
            
            # Add widgets to the torrent layout
            torrent_widget.addWidget(quality_label)
            torrent_widget.addWidget(video_codec_label)
            torrent_widget.addWidget(size_label)
            torrent_widget.addWidget(seeds_label)
            torrent_widget.addWidget(peers_label)     
            torrent_widget.addWidget(download_btn)
            
            layout.addLayout(torrent_widget)

        # Add spacer to push content to top
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(spacer)

        self.torrentsTab.setLayout(layout)

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
            'with_rt_ratings': True
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
                        type=t.get('type', 'unknown'),
                        url=t['url'],
                        size=t['size'],
                        seeds=t['seeds'],
                        peers=t['peers'],
                        date_uploaded=datetime.fromisoformat(t['date_uploaded']).strftime('%Y-%m-%d'),
                        video_codec=t.get('video_codec', 'unknown')
                    )
                    for t in movie_data['torrents']
                ]

                movie = Movie(
                    title=movie_data['title'],
                    torrents=torrents,
                    poster_url=movie_data.get('large_cover_image'),
                    rating=movie_data.get('rating', 0.0),
                    genres=movie_data.get('genres', []),
                    description_full=movie_data.get('description_full', 'No description available'),
                    year=movie_data.get('year', 0),
                    language=movie_data.get('language', 'N/A'),
                    runtime=movie_data.get('runtime', 0),
                    imdb_code=movie_data.get('imdb_code', ''),
                    cast=movie_data.get('cast', []),
                    download_count=movie_data.get('download_count', 0),
                    yt_trailer_code=movie_data.get('yt_trailer_code', ''),
                    background_image_original=movie_data.get('background_image_original', ''),
                    metacritic_url='',  # Initialize empty, will be set when movie is selected
                    metacritic_info=None
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
            # Get the label size
            label_size = self.posterLabel.size()
            # Scale pixmap to fit label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # Create rounded corners mask
            rounded = QPixmap(scaled_pixmap.size())
            rounded.fill(Qt.transparent)
            
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(0, 0, scaled_pixmap.width(), scaled_pixmap.height(), 20, 20)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, scaled_pixmap)
            painter.end()
            
            self.posterLabel.setPixmap(rounded)

    def _handle_background_downloaded(self, movie_title: str, pixmap: QPixmap):
        """Handle the downloaded background image"""
        self.background_cache[movie_title] = pixmap
        if self.current_movies and self.current_movies[0].title == movie_title:
            self._set_background(pixmap)

    def _set_background(self, pixmap: QPixmap):
        """Set the background image with a semi-transparent overlay"""
        # Scale pixmap to window size
        scaled_pixmap = pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        
        # Create a semi-transparent overlay
        overlay = QPixmap(scaled_pixmap.size())
        overlay.fill(Qt.black)
        
        # Create the final background with overlay
        painter = QPainter(scaled_pixmap)
        painter.setOpacity(0.7)  # Adjust opacity (0.0 to 1.0)
        painter.drawPixmap(0, 0, overlay)
        painter.end()
        
        # Set as window background
        palette = self.palette()
        palette.setBrush(QPalette.Window, QBrush(scaled_pixmap))
        self.setPalette(palette)

    def resizeEvent(self, event):
        """Handle window resize events to adjust background"""
        super().resizeEvent(event)
        if self.current_movies and self.current_movies[0].title in self.background_cache:
            self._set_background(self.background_cache[self.current_movies[0].title])

    def _find_metacritic_url(self, title: str, year: int) -> str:
        """
        Constructs a Metacritic URL for a given movie title and year.
        
        Args:
            title (str): The movie/TV show title
            year (int): The release year
            
        Returns:
            str: The constructed Metacritic URL for either movie or TV show
        """
        try:
            # Convert title to lowercase and replace spaces with hyphens
            formatted_title = title.lower()
            # Remove special characters and replace spaces with hyphens
            formatted_title = ''.join(c for c in formatted_title if c.isalnum() or c.isspace())
            formatted_title = formatted_title.replace(' ', '-')
            
            # Try both movie and TV show URLs since we don't know the type
            urls = [
                f"https://www.metacritic.com/movie/{formatted_title}/",
                f"https://www.metacritic.com/tv/{formatted_title}/"
            ]
            
            # Try each URL and return the first one that exists
            for url in urls:
                try:
                    response = requests.head(url)
                    if response.status_code == 200:
                        return url
                except requests.RequestException as e:
                    logger.error(f"Error checking URL {url}: {str(e)}")
                    continue
                except Exception as e:
                    logger.error(f"Unexpected error checking URL {url}: {str(e)}")
                    continue
                    
            # Default to movie URL if neither found
            return urls[0]
            
        except Exception as e:
            logger.error(f"Error constructing Metacritic URL: {str(e)}")
            return ""

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('app.png'))
    window = MovieSearchApp()
    window.show()
    sys.exit(app.exec_())