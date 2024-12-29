from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QFileDialog, QVBoxLayout, QWidget, QMessageBox
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
import os
import sys

class VideoPlayer(QMainWindow):
    def __init__(self):
        super().__init__()

        # Set up the main window
        self.setWindowTitle("MP4 Player")
        self.setGeometry(100, 100, 800, 600)

        # Create a video widget and media player
        self.video_widget = QVideoWidget()
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)

        # Set environment variables for codec
        klite_path = r"C:\Program Files (x86)\K-Lite Codec Pack"
        os.environ["PATH"] = f"{klite_path};{os.environ['PATH']}"
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp"  # Use FFMPEG

        # Connect error handler
        self.media_player.error.connect(self.handle_error)

        # Set the video output to the video widget
        self.media_player.setVideoOutput(self.video_widget)

        # Create buttons for opening files and playing videos
        self.open_button = QPushButton("Open Video")
        self.open_button.clicked.connect(self.open_file)

        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_video)
        self.play_button.setEnabled(False)  # Disable until video is loaded

        # Layout setup
        layout = QVBoxLayout()
        layout.addWidget(self.video_widget)
        layout.addWidget(self.open_button)
        layout.addWidget(self.play_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def handle_error(self):
        error = self.media_player.error()
        if error != QMediaPlayer.NoError:
            error_msg = self.media_player.errorString()
            QMessageBox.critical(self, "Media Player Error", 
                               f"Error: {error_msg}\n"
                               "K-Lite Codec Pack not found or error occurred.\n"
                               "Please verify installation at: C:\\Program Files (x86)\\K-Lite Codec Pack")
            self.play_button.setEnabled(False)

    def open_file(self):
        videos_dir = os.path.join(os.environ['USERPROFILE'], 'Videos')
        file_name, _ = QFileDialog.getOpenFileName(self, "Open Video", videos_dir,
            "Video Files (*.mp4 *.avi *.mov *.wmv *.mkv)")
        
        if file_name:
            media_content = QMediaContent(QUrl.fromLocalFile(file_name))
            self.media_player.setMedia(media_content)
            self.play_button.setEnabled(True)
            # Auto-play when file is opened
            self.media_player.play()
            self.play_button.setText("Pause")

    def play_video(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.play_button.setText("Play")
        else:
            self.media_player.play()
            self.play_button.setText("Pause")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    player = VideoPlayer()
    player.show()
    sys.exit(app.exec_())
