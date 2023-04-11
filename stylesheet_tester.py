from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import Qt
from PyQt5 import uic
import sys


class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()

        # Load the ui file
        uic.loadUi('resources/testui.ui', self)
        with open('resources/pams_style.qss', 'r') as f:
            self.setStyleSheet(f.read())
        self.setWindowFlags(Qt.FramelessWindowHint)


def main():
    app = QApplication(sys.argv)
    window = UI()
    window.show()
    app.exec()


if __name__ == '__main__':
    main()