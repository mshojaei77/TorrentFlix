from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QLineEdit, QFormLayout, QMessageBox
from core.state_manager import StateManager
from PyQt5.QtCore import Qt
class ProfilePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("User Profile")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        # Form Layout for User Info
        form_layout = QFormLayout()
        self.username_input = QLineEdit()
        self.email_input = QLineEdit()
        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Email:", self.email_input)
        layout.addLayout(form_layout)
        
        # Save Button
        self.save_button = QPushButton("Save Changes")
        layout.addWidget(self.save_button, alignment=Qt.AlignCenter)
        
        # Settings Button
        self.settings_button = QPushButton("Settings")
        layout.addWidget(self.settings_button, alignment=Qt.AlignCenter)
        
        self.setLayout(layout)
        
        # Load user data
        self.state_manager = StateManager()
        self.load_user_data()
        
        # Connect buttons
        self.save_button.clicked.connect(self.save_changes)
        self.settings_button.clicked.connect(self.open_settings)
        
    def load_user_data(self):
        user_data = self.state_manager.get_user_data()
        self.username_input.setText(user_data.get('username', ''))
        self.email_input.setText(user_data.get('email', ''))
        
    def save_changes(self):
        username = self.username_input.text().strip()
        email = self.email_input.text().strip()
        if not username or not email:
            QMessageBox.warning(self, "Input Error", "Username and Email cannot be empty.")
            return
        # Update state manager
        self.state_manager.set_user_data({'username': username, 'email': email})
        QMessageBox.information(self, "Success", "Profile updated successfully.")
        
    def open_settings(self):
        # Placeholder for settings
        QMessageBox.information(self, "Settings", "Settings page is under construction.")