from PyQt5.QtWidgets import QMainWindow, QStackedWidget, QWidget, QHBoxLayout
from core.navigation import NavigationManager
from pages.home_page import HomePage
from pages.browse_page import BrowsePage
from pages.detail_page import DetailPage
from pages.search_page import SearchPage
from pages.profile_page import ProfilePage
from pages.list_page import ListPage
from components.sidebar import Sidebar

class MainApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Streaming App")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize navigation manager
        self.navigation_manager = NavigationManager()
        
        # Initialize central widget and layout
        central_widget = QWidget()
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Initialize sidebar
        self.sidebar = Sidebar(self.navigation_manager)
        self.sidebar.setFixedWidth(200)
        main_layout.addWidget(self.sidebar)
        
        # Initialize stacked widget for pages
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # Initialize pages
        self.home_page = HomePage()
        self.browse_page = BrowsePage()
        self.detail_page = DetailPage()
        self.search_page = SearchPage()
        self.profile_page = ProfilePage()
        self.list_page = ListPage()
        
        # Add pages to stacked widget
        self.stacked_widget.addWidget(self.home_page)
        self.stacked_widget.addWidget(self.browse_page)
        self.stacked_widget.addWidget(self.detail_page)
        self.stacked_widget.addWidget(self.search_page)
        self.stacked_widget.addWidget(self.profile_page)
        self.stacked_widget.addWidget(self.list_page)
        
        # Connect navigation signals
        self.navigation_manager.page_changed.connect(self.change_page)
        
        # Set initial page
        self.stacked_widget.setCurrentWidget(self.home_page)
        
    def change_page(self, page_name):
        pages = {
            "Home": self.home_page,
            "Browse": self.browse_page,
            "Detail": self.detail_page,
            "Search": self.search_page,
            "Profile": self.profile_page,
            "My List": self.list_page
        }
        page = pages.get(page_name, self.home_page)
        self.stacked_widget.setCurrentWidget(page)