import sys

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6 import uic
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtMultimedia import QAudioFormat, QAudio, QAudioOutput, QAudioDevice
from pysine import sine
from pyaudio import PyAudio


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        if True:
            with open('resources/pams_style.qss', 'r') as f:
                self.setStyleSheet(f.read())
            uic.loadUi('resources/audio_slider.ui', self)
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.maximize_button.clicked.connect(self.maximize_button_clicked)
            self.med_ic = QIcon('resources/medimize_button.svg')
            self.med_ic_white = QIcon('resources/medimize_button_white.svg')
            self.max_ic = QIcon('resources/maximize_button.svg')
            self.max_ic_white = QIcon('resources/maximize_button_white.svg')
            self.min_ic = QIcon('resources/minimize_button.svg')
            self.min_ic_white = QIcon('resources/minimize_button_white.svg')
            self.clos_ic = QIcon('resources/closing_button.svg')
            self.clos_ic_white = QIcon('resources/closing_button_white.svg')
            self.maximize_button.enterEvent = self.maximize_button_hover
            self.maximize_button.leaveEvent = self.maximize_button_exit
            self.minimize_button.enterEvent = self.minimize_button_hover
            self.minimize_button.leaveEvent = self.minimize_button_exit
            self.close_button.enterEvent = self.close_button_hover
            self.close_button.leaveEvent = self.close_button_exit
        self.sine = sine(440.0, duration=5.0)
        self.pyaudio = PyAudio()
        self.stream = self.pyaudio.open(rate=96000,
                                        format=self.pyaudio.get_format_from_width(1),
                                        channels=1,
                                        output=True)


    def close_button_hover(self, event):
        self.close_button.setIcon(self.clos_ic_white)

    def close_button_exit(self, event):
        self.close_button.setIcon(self.clos_ic)

    def maximize_button_hover(self, event):
        if self.isFullScreen():
            self.maximize_button.setIcon(self.med_ic_white)
        else:
            self.maximize_button.setIcon(self.max_ic_white)

    def maximize_button_exit(self, event):
        if self.isFullScreen():
            self.maximize_button.setIcon(self.med_ic)
        else:
            self.maximize_button.setIcon(self.max_ic)

    def minimize_button_hover(self, event):
        self.minimize_button.setIcon(self.min_ic_white)

    def minimize_button_exit(self, event):
        self.minimize_button.setIcon(self.min_ic)

    def maximize_button_clicked(self):
        if self.isFullScreen():
            self.showNormal()
            self.maximize_button.setIcon(self.max_ic)
        else:
            self.maximize_button.setIcon(self.med_ic)
            self.showFullScreen()


def main():
    app = QApplication(sys.argv)
    pixmap = QPixmap('resources/splash_screen.png')
    splashscreen = QSplashScreen(pixmap)
    splashscreen.show()
    window = MainWindow()
    window.show()
    splashscreen.finish(window)
    app.exec()


if __name__ == '__main__':
    main()
