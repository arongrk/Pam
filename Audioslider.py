'''import sys

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
    '''


import sys
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QBuffer, QIODevice, QByteArray, QDataStream
from PyQt5.QtMultimedia import QAudioDeviceInfo, QAudioFormat, QAudioOutput
from PyQt5.QtWidgets import QApplication, QMainWindow, QSlider, QVBoxLayout, QWidget
import pyqtgraph


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Player")

        # Create sliders for frequency and volume
        self.freq_slider = QSlider(Qt.Orientation.Horizontal)
        self.freq_slider.setMinimum(1)
        self.freq_slider.setMaximum(2000)
        self.freq_slider.setValue(440)
        self.freq_slider.valueChanged.connect(self.update_frequency)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.update_volume)

        self.plotwidget = pyqtgraph.PlotWidget()
        self.line = self.plotwidget.plot([0,1,2,3,4,5],[0,0,0,0,0,0])

        # Create layout for sliders
        self.slider_layout = QVBoxLayout()
        self.slider_layout.addWidget(self.freq_slider)
        self.slider_layout.addWidget(self.volume_slider)
        self.slider_layout.addWidget(self.plotwidget)

        # Create widget and set layout
        self.centralWidget = QWidget()
        self.centralWidget.setLayout(self.slider_layout)
        self.setCentralWidget(self.centralWidget)

        # Set up audio output
        self.device = QAudioDeviceInfo.defaultOutputDevice()
        self.format = QAudioFormat()
        self.format.setSampleRate(164000)
        self.format.setChannelCount(1)
        self.format.setSampleSize(16)
        self.format.setCodec("audio/pcm")
        self.format.setByteOrder(QAudioFormat.Endian.LittleEndian)
        self.format.setSampleType(QAudioFormat.SampleType.SignedInt)

        self.output = QAudioOutput(self.device, self.format)
        self.output.setBufferSize(328000)
        print(self.output.bufferSize())
        self.buffer = QBuffer()
        self.timer = QTimer()
        self.timer.timeout.connect(self.timer_callback)
        self.duration = 1000
        self.timer.start(self.duration)

        self.frequency = 440
        self.volume = 0.5
        # self.timer_callback()


    def update_frequency(self, value):
        self.frequency = value

    def update_volume(self, value):
        self.volume = value

    def timer_callback(self):
        sample_rate = self.format.sampleRate()
        duration = self.duration / 1000
        self.buffer = QBuffer()
        self.buffer.open(QIODevice.ReadWrite)
        stream = QDataStream(self.buffer)
        tone = ((2**15-1) * np.sin(np.linspace(0, duration, int(duration*sample_rate)) * 2 * np.pi * self.frequency)).astype(np.int16)
        self.line.setData(np.linspace(0, duration, int(duration*sample_rate)), tone)
        stream.writeRawData(tone.tobytes())
        self.buffer.seek(0)
        self.output.start(self.buffer)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
