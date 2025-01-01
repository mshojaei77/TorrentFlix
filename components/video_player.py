from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSlider, QLabel, QHBoxLayout
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import Qt, QUrl

class VideoPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        
        # Video Widget
        self.video_widget = QVideoWidget()
        layout.addWidget(self.video_widget)
        
        # Media Player
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.setVideoOutput(self.video_widget)
        
        # Control Layout
        control_layout = QHBoxLayout()
        
        # Play/Pause Button
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_pause)
        control_layout.addWidget(self.play_button)
        
        # Position Slider
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        control_layout.addWidget(self.position_slider)
        
        # Time Label
        self.time_label = QLabel("00:00 / 00:00")
        control_layout.addWidget(self.time_label)
        
        layout.addLayout(control_layout)
        self.setLayout(layout)
        
        # Connections
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.stateChanged.connect(self.state_changed)
        
    def open_file(self, file_path):
        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        self.play_button.setText("Play")
        
    def play_pause(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            self.media_player.play()
        
    def position_changed(self, position):
        self.position_slider.setValue(position)
        self.update_time_label(position, self.media_player.duration())
        
    def duration_changed(self, duration):
        self.position_slider.setRange(0, duration)
        self.update_time_label(self.media_player.position(), duration)
        
    def set_position(self, position):
        self.media_player.setPosition(position)
        
    def state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_button.setText("Pause")
        else:
            self.play_button.setText("Play")
        
    def update_time_label(self, position, duration):
        pos_minutes = position // 60000
        pos_seconds = (position % 60000) // 1000
        dur_minutes = duration // 60000
        dur_seconds = (duration % 60000) // 1000
        self.time_label.setText(f"{pos_minutes:02}:{pos_seconds:02} / {dur_minutes:02}:{dur_seconds:02}")