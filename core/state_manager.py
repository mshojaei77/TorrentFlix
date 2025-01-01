from PyQt5.QtCore import QObject, pyqtSignal

class StateManager(QObject):
    # Signals for state changes
    user_updated = pyqtSignal(dict)
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StateManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self.user_data = {}
        self._initialized = True
        
    def set_user_data(self, data: dict):
        self.user_data = data
        self.user_updated.emit(self.user_data)
        
    def get_user_data(self) -> dict:
        return self.user_data