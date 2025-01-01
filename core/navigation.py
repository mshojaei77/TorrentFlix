from PyQt5.QtCore import QObject, pyqtSignal

class NavigationManager(QObject):
    page_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
    def navigate_to(self, page_name: str):
        self.page_changed.emit(page_name)