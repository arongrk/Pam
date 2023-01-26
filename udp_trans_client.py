"""
Encode numpy arrays and send them via udp periodically
"""
import ctypes
import logging.config
import socket
import sys

import numpy
import numpy.random
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, QThread, QTimer
from PyQt5.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QPushButton, QWidget

from app import UDP_PORT

logger = logging.getLogger(__name__)



class DatagramThread(QObject):

    sig_cleanup = pyqtSignal()
    sig_finished = pyqtSignal()

    def __init__(self):
        super().__init__(None)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.thread = QThread()
        self.moveToThread(self.thread)
        self.sig_finished.connect(self.thread.quit)
        self.sig_cleanup.connect(self.cleanup)
        self.thread.start()

    def close(self):
        self.sig_cleanup.emit()

    @pyqtSlot()
    def send_data(self):
        buffer_numbers = 600.0 * (numpy.random.random_sample((40960,)) + 1)
        buffer_numbers = numpy.append(buffer_numbers, [ctypes.c_int32(0xaaffffff).value], axis=0)
        s = 0
        while True:
            numbers = buffer_numbers
            buffer_numbers = 600.0 * (numpy.random.random_sample((40960,)) + 1)
            buffer_numbers = numpy.append(buffer_numbers, [ctypes.c_int32(0xaaffffff).value], axis = 0)
            if not s + 350 > len(numbers):
                package = numbers[[i for i in range(s, s+350)]]
                s += 350
            else:
                package = numbers[[i for i in range(s, len(numbers))]]
                numbers = buffer_numbers
                s = s + 350 - len(numbers)
                package = numpy.append(package, numbers[[i for i in range(s)]], axis=0)
            data = package.tobytes('C')
            self.socket.sendto(data, ('192.168.1.1', UDP_PORT))

    @pyqtSlot()
    def cleanup(self):
        print("Cleanin up dgram sender")
        self.socket.close()
        self.socket = None
        self.sig_finished.emit()


class MainWindow(QMainWindow):

    sig_cleanup = pyqtSignal()

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.setWindowTitle("Trans Client")
        self.central_widget = QWidget()
        self.layout = QVBoxLayout()
        self.btnStart = QPushButton("Start Transmission")
        self.btnStop = QPushButton("Stop Transmission")
        self.btnExit = QPushButton("Exit")
        for _btn in (self.btnStart, self.btnStop, self.btnExit):
            self.layout.addWidget(_btn)
        self.central_widget.setLayout(self.layout)
        self.btnStop.clicked.connect(self.hstop)
        self.btnExit.clicked.connect(self.app.quit)
        self.setCentralWidget(self.central_widget)
        self.dgram = DatagramThread()

        self.btnStart.clicked.connect(self.dgram.send_data)
        self.timer = QTimer()
        self.timer.timeout.connect(self.dgram.send_data)
        self.app.aboutToQuit.connect(self.cleanup)

    def hstart(self):
        self.timer.start(10)

    def hstop(self):
        self.timer.stop()

    @pyqtSlot()
    def cleanup(self):
        print("Cleaning up main window")
        self.dgram.close()


def qt_main():
    app = QApplication(sys.argv)
    window = MainWindow(app)
    window.show()
    app.exec()


if __name__ == "__main__":
    qt_main()