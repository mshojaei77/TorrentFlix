import logging
import os
import subprocess
from dataclasses import dataclass
from typing import List
from collections import deque
from pathlib import Path
from datetime import datetime
import sys
import json
import tempfile
import requests
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout,
                             QWidget, QDialog, QListWidget, QAbstractItemView, QListWidgetItem, QScrollArea,
                             QSizePolicy, QFrame)
from PyQt5.QtCore import Qt, QFile, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon, QPainter, QPainterPath, QBrush, QPalette, QColor
from PyQt5.QtCore import QSize, QSettings
from app_ui import Ui_MainWindow
from torrent_search import TorrentSearcher, TorrentSource, Movie, MovieSearchError, Torrent, ConnectionBlockedError, MovieMetadata
from movie_info_mata import get_metacritic_info

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    def __init__(self, movies: List[Movie], parent=None):
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

    def get_selected_movie(self) -> Movie:
        current_item = self.movie_list.currentItem()
        return current_item.data(Qt.UserRole) if current_item else None
class MovieSearchApp(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon('app.png'))
        self.setWindowTitle("TorrentFlix - Where Pixels Meet Paradise")
        self.setWindowFlags(Qt.FramelessWindowHint)  # Make window frameless
        self.torrent_searcher = TorrentSearcher()
        self._init_ui()
        self._setup_titlebar()
        self._connect_signals()
        self.history = deque(maxlen=50)  # Limit history to 50 items
        self.current_history_index = -1
        self._load_history()
        self.poster_cache = {}  # Cache for movie posters
        self.background_cache = {}  # Cache for background images
        self.current_movies = []  # Store current search results
        self.download_threads = []  # Track download threads
        self.detailsTabWidget.hide()
    def _init_ui(self):
        self.setupUi(self)
        self._load_stylesheet()
        self.resultsLayout.setAlignment(Qt.AlignTop)
        
        # Get categories and sources
        raw_categories = TorrentSource.get_sources_by_category()
        
        # Process categories - distribute 'All' sources across other categories
        categories = {}
        all_sources = []
        
        # First get the 'All' sources if they exist
        if 'All' in raw_categories:
            all_sources = raw_categories['All']
            del raw_categories['All']
            
        # Add 'All' sources to each remaining category
        for category, sources in raw_categories.items():
            categories[category] = sources + all_sources
            
        # Setup category combo box
        self.categoryComboBox.addItems(list(categories.keys()))
        self.categoryComboBox.currentTextChanged.connect(self._update_sources)
        
        # Store categories and sources for later use
        self.categories = categories
        
        # Initial population of sources with first category
        first_category = list(categories.keys())[0]
        self._update_sources(first_category)

    def _load_stylesheet(self):
        style_file = QFile("style.qss")
        if style_file.open(QFile.ReadOnly | QFile.Text):
            stylesheet = str(style_file.readAll(), encoding='utf-8')
            self.setStyleSheet(stylesheet)
            style_file.close()
        else:
            logger.warning("Style file not found. Continuing without custom styles.")

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
        elif event.key() == Qt.Key_Down:
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

        # Clear previous results first
        self._clear_results()
        
        # Reset background and poster
        palette = self.palette()
        palette.setBrush(QPalette.Window, QBrush(QColor("#1a1a1a")))  # Reset to default dark background
        self.setPalette(palette)
        self.posterLabel.clear()  # Clear the poster image

        # Add to history only if it's a new search
        if not self.history or query != self.history[-1]:
            self.history.append(query)
            self._save_history()
        
        self.current_history_index = -1  # Reset history index
        try:
            selected_text = self.sourceComboBox.currentText()
            if selected_text.startswith("==="):
                self._show_error("Please select a specific source, not a category header")
                return
            
            selected_source = TorrentSource.from_display_name(selected_text)
            
            # Increase the limit to get more results
            movies = self.torrent_searcher.search_movies(query, selected_source, limit=50)  # Increase from default
            
            if not movies:
                self._show_no_results()
                return

            # Show movie selection dialog
            dialog = MovieSelectionDialog(movies, self)
            if dialog.exec_() == QDialog.Accepted:
                selected_movie = dialog.get_selected_movie()
                if selected_movie:
                    # Get metadata from all available sources
                    metadata_service = MovieMetadata()
                    metadata = metadata_service.get_metadata(
                        selected_movie.title,
                        selected_movie.year
                    )
                    
                    # Create new instance with metadata
                    selected_movie = selected_movie.with_metadata(metadata)
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
        self.detailsTabWidget.hide()
        # Optionally, clear previous movie details

    def _display_movies(self, movies: List[Movie]):
        self.current_movies = movies
        # Clear previous results first
        self._clear_results()
        
        # Show movie details for the first movie
        if movies:
            movie = movies[0]
            self._display_metadata(movie)
            
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

    def _setup_torrents_tab(self, torrents: List[Torrent]):
        # Remove existing layout if it exists
        if self.torrentsTab.layout():
            QWidget().setLayout(self.torrentsTab.layout())
    
        # Create main layout
        main_layout = QVBoxLayout()
        
        # Create scroll area and its widget
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Add headers for the torrent information
        header_widget = QHBoxLayout()
        header_widget.addWidget(QLabel("Quality"))
        header_widget.addWidget(QLabel("Video Codec"))  
        header_widget.addWidget(QLabel("Size"))
        header_widget.addWidget(QLabel("Seeds"))
        header_widget.addWidget(QLabel("Peers"))
        header_widget.addWidget(QLabel(""))
        scroll_layout.addLayout(header_widget)

        for torrent in torrents:
            torrent_widget = QHBoxLayout()
            
            quality_label = QLabel(torrent.quality)
            size_label = QLabel(torrent.size)
            seeds_label = QLabel(str(torrent.seeds))
            peers_label = QLabel(str(torrent.peers))
            video_codec_label = QLabel(torrent.video_codec)
            
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
            
            scroll_layout.addLayout(torrent_widget)

        # Configure scroll area
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        
        # Add scroll area to main layout
        main_layout.addWidget(scroll_area)
        
        self.torrentsTab.setLayout(main_layout)

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
            
    def _display_metadata(self, movie: Movie):
        # Set movie title if available
        if hasattr(movie, 'title'):
            self.movieTitleLabel.setText(movie.title)
        
        # Set IMDb rating if available
        if hasattr(movie, 'rating'):
            self.imdbRatingLabel.setText(f"★ {movie.rating}/10")
        else:
            self.imdbRatingLabel.setText("Rating not available")
        
        # Set genres if available
        if hasattr(movie, 'genres'):
            self.genresLabel.setText(", ".join(movie.genres))
        
        # Set plot/description if available
        description = getattr(movie, 'description_full', '')
        metacritic_description = ''
        if movie.metadata and 'metacritic' in movie.metadata:
            metacritic_description = movie.metadata['metacritic']['info'].get('description', '')
        
        if description or metacritic_description:
            if not description or len(description) < 100 or (metacritic_description and len(metacritic_description) > len(description)):
                self.plotLabel.setText(metacritic_description or description)
            else:
                self.plotLabel.setText(description)
        else:
            self.plotLabel.setText("")
        
        # Set basic movie details if available
        if hasattr(movie, 'year'):
            self.releaseYearLabel.setText("Release Year:")
            self.releaseYearValue.setText(str(movie.year))
            
        if hasattr(movie, 'language'):
            self.languageLabel.setText("Language:")
            self.languageValue.setText(movie.language)
            
        if hasattr(movie, 'runtime'):
            self.durationLabel.setText("Duration:")
            self.durationValue.setText(f"{movie.runtime} min")

        # Handle Metacritic metadata if available
        if movie.metadata and 'metacritic' in movie.metadata:
            meta_data = movie.metadata['metacritic']['info']

            # Display Metascore if available
            if 'metascore' in meta_data:
                metascore = meta_data['metascore']
                self.metascoreLabel.setText('<span style="color: #E0E0E0;">Metascore:</span>')
                score = metascore['score']
                sentiment = metascore['sentiment']
                
                score_num = int(score)
                color = '#00FF00' if score_num >= 90 else '#66CC33' if score_num >= 75 else '#FFCC33' if score_num >= 60 else '#FF9933' if score_num >= 40 else '#FF3333' if score_num >= 20 else '#990000'
                sentiment_color = {'positive': '#66FF66', 'mixed': '#FFD700', 'negative': '#FF4444'}.get(sentiment.lower(), '#CCCCCC')
                
                self.metascoreValue.setText(f'<span style="color: {color}; font-weight: bold; font-size: 14px;">{score}</span> - <span style="color: {sentiment_color};">{sentiment}</span>')
                self.metascoreValue.setTextFormat(Qt.RichText)

            # User Score if available
            if 'user_score' in meta_data:
                user_score = meta_data['user_score']
                self.userScoreLabel.setText('<span style="color: #E0E0E0;">User Score:</span>')
                
                score_text = user_score['score']
                sentiment = user_score.get('sentiment', '')
                
                if score_text == 'tbd':
                    color = '#888888'
                    display_text = 'TBD'
                else:
                    score_value = float(score_text)
                    color = '#00FF00' if score_value >= 9.0 else '#66CC33' if score_value >= 7.5 else '#FFCC33' if score_value >= 6.0 else '#FF9933' if score_value >= 4.0 else '#FF3333' if score_value >= 2.0 else '#990000'
                    display_text = f'{score_value:.1f}'
                
                sentiment_color = {'positive': '#66FF66', 'mixed': '#FFD700', 'negative': '#FF4444'}.get(sentiment.lower(), '#CCCCCC')
                sentiment_text = f' - <span style="color: {sentiment_color};">{sentiment}</span>' if sentiment else ''
                
                self.userScoreValue.setText(f'<span style="color: {color}; font-weight: bold; font-size: 14px;">{display_text}</span>{sentiment_text}')
                self.userScoreValue.setTextFormat(Qt.RichText)

            # Genre if available
            if 'genre' in meta_data and meta_data['genre']:
                self.genreLabel.setText("Genres:")
                self.genreValue.setText(', '.join(meta_data['genre']))

        # Create scroll widget if needed
        if not self.detailsScrollArea.widget():
            scroll_widget = QWidget()
            scroll_layout = QVBoxLayout(scroll_widget)
            scroll_layout.setSpacing(15)
            self.detailsScrollArea.setWidget(scroll_widget)
        else:
            scroll_widget = self.detailsScrollArea.widget()
            scroll_layout = scroll_widget.layout()
            while scroll_layout.count():
                child = scroll_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        # Handle all metadata
        if movie.metadata:
            merged_info = {}
            for source_data in movie.metadata.values():
                if 'info' in source_data:
                    self._merge_metadata(merged_info, source_data['info'])

            # Display merged metadata
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(10, 0, 10, 20)
            container_layout.setSpacing(10)

            def add_metadata_section(data, layout, indent=0):
                if isinstance(data, dict):
                    for key, value in data.items():
                        if key in ['url', 'error'] or value is None:
                            continue
                        display_key = key.replace('_', ' ').title()
                        
                        # Special formatting for cast
                        if key == 'cast' and isinstance(value, list):
                            layout.addWidget(QLabel(f'<h3 style="color: #CCCCCC; font-size: 18px; font-weight: 500; margin-left: {indent}px;">Cast:</h3>'))
                            for actor in value:
                                text = actor.get('name', '') + (' as ' + actor.get('role', '') if isinstance(actor, dict) and actor.get('role') else '') if isinstance(actor, dict) else actor
                                content = QLabel(f'<span style="color: #E0E0E0;">{text}</span>')
                                content.setWordWrap(True)
                                content.setStyleSheet(f"margin-left: {indent + 20}px;")
                                layout.addWidget(content)
                            continue
                            
                        if isinstance(value, (dict, list)):
                            label = QLabel(f'<h3 style="color: #CCCCCC; font-size: 18px; font-weight: 500; margin-left: {indent}px;">{display_key}:</h3>')
                            layout.addWidget(label)
                            add_metadata_section(value, layout, indent + 20)
                        else:
                            content = QLabel(f'<span style="color: #E0E0E0; font-weight: 500;">{display_key}:</span> <span style="color: #FFFFFF;">{value}</span>')
                            content.setWordWrap(True)
                            content.setStyleSheet(f"margin-left: {indent}px;")
                            layout.addWidget(content)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            item_widget = QWidget()
                            item_layout = QVBoxLayout(item_widget)
                            item_layout.setContentsMargins(indent, 5, 0, 5)
                            add_metadata_section(item, item_layout, 0)
                            layout.addWidget(item_widget)
                        else:
                            content = QLabel(f'<span style="color: #FFFFFF;">{item}</span>')
                            content.setWordWrap(True)
                            content.setStyleSheet(f"margin-left: {indent}px;")
                            layout.addWidget(content)

            add_metadata_section(merged_info, container_layout)
            scroll_layout.addWidget(container)
            scroll_layout.addStretch()

        # Set YouTube trailer link if available
        if hasattr(movie, 'yt_trailer_code') and movie.yt_trailer_code:
            self.ytLabel.setText("Trailer:")
            trailer_url = f"https://www.youtube.com/watch?v={movie.yt_trailer_code}"
            self.ytValue.setText(f'<a href="{trailer_url}" style="color: #2196F3; text-decoration: none; font-weight: 500; padding: 4px 8px; border-radius: 4px; transition: all 0.2s ease;">Watch Trailer</a>')
            self.ytValue.setOpenExternalLinks(True)
        else:
            self.ytLabel.setText("Trailer:")
            self.ytValue.setText("Not available")

    def _merge_metadata(self, target, source):
        for key, value in source.items():
            if key not in target:
                target[key] = value
            elif isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_metadata(target[key], value)
            elif isinstance(target[key], list) and isinstance(value, list):
                target[key].extend(value)
    def _setup_titlebar(self):
        # Create and add titlebar widgets
        titlebar_layout = QHBoxLayout()
        titlebar_layout.setContentsMargins(0, 0, 0, 0)
        titlebar_layout.setSpacing(5)
        
        # Add app icon
        app_icon = QLabel()
        app_icon.setPixmap(QPixmap("app.png").scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        titlebar_layout.addWidget(app_icon)
        
        self.titleLabel = QLabel("TorrentFlix")
        self.titleLabel.setObjectName("titleLabel")
        
        # Create window control buttons with icons
        self.minimizeButton = QPushButton()
        self.minimizeButton.setIcon(QIcon("icons/minimize.png"))
        self.minimizeButton.setFixedSize(30, 30)  # Increased button size
        self.minimizeButton.setIconSize(QSize(16, 16))  # Adjusted icon size
        
        self.maximizeButton = QPushButton()
        self.maximizeButton.setIcon(QIcon("icons/maximize.png"))
        self.maximizeButton.setFixedSize(30, 30)  # Increased button size
        self.maximizeButton.setIconSize(QSize(16, 16))  # Adjusted icon size
        
        self.closeButton = QPushButton()
        self.closeButton.setIcon(QIcon("icons/close.png"))
        self.closeButton.setFixedSize(30, 30)  # Increased button size
        self.closeButton.setIconSize(QSize(16, 16))  # Adjusted icon size
        
        # Set object names for styling
        self.minimizeButton.setObjectName("minimizeButton")
        self.maximizeButton.setObjectName("maximizeButton")
        self.closeButton.setObjectName("closeButton")
        
        # Add widgets to horizontalLayout_TITLEBAR
        titlebar_layout.addWidget(self.titleLabel)
        titlebar_layout.addStretch()
        titlebar_layout.addWidget(self.minimizeButton)
        titlebar_layout.addWidget(self.maximizeButton)
        titlebar_layout.addWidget(self.closeButton)
        
        # Add titlebar layout to main titlebar
        titlebar_widget = QWidget()
        titlebar_widget.setContentsMargins(0, 0, 0, 0)
        titlebar_widget.setLayout(titlebar_layout)
        self.horizontalLayout_TITLEBAR.addWidget(titlebar_widget)
        self.horizontalLayout_TITLEBAR.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout_TITLEBAR.setSpacing(0)
        
        # Connect button signals
        self.minimizeButton.clicked.connect(self.showMinimized)
        self.maximizeButton.clicked.connect(self._toggle_maximize)
        self.closeButton.clicked.connect(self.close)
        
        # Enable mouse dragging for the window
        titlebar_widget.mousePressEvent = self._get_pos
        titlebar_widget.mouseMoveEvent = self._move_window

    def _get_pos(self, event):
        if event.button() == Qt.LeftButton:
            self.clickPosition = event.globalPos()

    def _move_window(self, event):
        if hasattr(self, 'clickPosition') and event.buttons() == Qt.LeftButton:
            self.move(self.pos() + event.globalPos() - self.clickPosition)
            self.clickPosition = event.globalPos()

    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.maximizeButton.setIcon(QIcon("icons/maximize.png"))
        else:
            self.showMaximized()
            self.maximizeButton.setIcon(QIcon("icons/restore.png"))

    def _update_sources(self, category: str):
        """Update sources in sourceComboBox based on selected category"""
        self.sourceComboBox.clear()
        
        # Show sources for selected category
        sources = self.categories.get(category, [])
        for source in sources:
            self.sourceComboBox.addItem(source.config["name"], source)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('app.png'))
    window = MovieSearchApp()
    window.resize(1280, 900)
    
    # Center window on screen
    screen = app.primaryScreen().geometry()
    x = (screen.width() - window.width()) // 2
    y = (screen.height() - window.height()) // 2
    window.move(x, y)
    
    window.show()
    sys.exit(app.exec_())