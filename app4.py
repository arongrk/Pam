# import sys
from PyQt5.QtCore import *
from pyqtgraph import *
from PyQt5 import uic
from PyQt5.QtWidgets import *
import numpy as np
import random as rnd
import time as t
from ctypes import c_int32
import socket

import matlabdata

'''
UDP_IP = '192.168.1.1'
UDP_PORT = 9090
plot_length = 40960
marker = c_int32(0xaaffffff).value

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
data = np.array([np.arange(1, plot_length + 1), np.arange(1, plot_length + 1)])
package_list = list()


def update_package_list():
    print('Filling package list for 5 seconds')
    while True:
        encoded_package, addr = sock.recvfrom(1400)
        package = np.frombuffer(encoded_package, dtype=np.int32)
        package_list.append(package)
'''


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.fn()


class UI(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('resources/window1.ui', self)
        self.show()


def main():
    app = QApplication(sys.argv)
    window = UI()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
