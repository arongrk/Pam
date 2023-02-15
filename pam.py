import numpy as np
import sys
import time

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import uic
from pyqtgraph import *

import socket

from hacker import Hacker
import definitions
import byte_sender
# import funtions


class Receiver(QThread):
    packageReady = pyqtSignal(bytearray)
    def __init__(self, ip, port):
        QThread.__init__(self)

        # self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # self.socket.bind((ip, port))

        self.stop_receive = False

    def run(self):
        pack_size = definitions.PACKAGE_SIZE
        plot_size = definitions.PLOT_SIZE
        marker = definitions.MARKER_BYTES
        # hacker = Hacker(self.socket.recv(pack_size), pack_size, plot_size, marker)
        hacker = Hacker(byte_sender.create_receive(), pack_size, plot_size, marker)
        g = hacker.hack()
        while not self.stop_receive:
            r = next(g)
            self.packageReady.emit(r)
            time.sleep(0.005)
        self.socket.close()

    def stop(self):
        self.stop_receive = True


class SecondData(QObject):
    def __init__(self):
        super().__init__(self)


class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()

        # Load the ui file
        uic.loadUi('resources/Mainwindow.ui', self)
        self.yData = np.arange(1, definitions.PLOT_LENGTH + 1)

        # Configuring both plot-widgets
        pen = mkPen(color=(0, 0, 0), width=1)
        self.graph1.setBackground('w')
        self.line1 = self.graph1.plot(self.yData, np.zeros(len(self.yData)), pen=pen)

        self.graph2.setBackground('w')
        self.graph2.plot(self.yData, np.zeros(len(self.yData)), pen=pen)

        self.receiver = Receiver(definitions.IP_Address, definitions.PORT)
        self.receiver.packageReady.connect(self.plot)

        self.start_plot1.clicked.connect(self.start_receiver)
        self.stop_plot1.clicked.connect(self.stop_receiver)

    def plot(self, data):
        # pass
        data = np.frombuffer(data, dtype=np.int32)
        self.line1.setData(self.yData, data)

    def start_receiver(self):
        self.receiver.start()

    def stop_receiver(self):
        self.receiver.stop()


def main():
    app = QApplication(sys.argv)
    window = UI()
    window.show()
    app.exec()


if __name__ == '__main__':
    main()
