from PyQt5.QtWidgets import QApplication
import sys
from core.app import MainApp

def main():
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()