import sys
import numpy as np
from collections import deque
import socket
from ctypes import c_int32
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from pyqtgraph import *
import time

from matlabdata import split_data

MARKER = c_int32(0xaaffffff).value
PACKAGE_LENGTH = 350
PLOT_LENGTH = 40960
IP, PORT = '192.168.1.1', 9090
t = time.time()
package_list = deque()


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.fn()


class UdpReceiver(QThread):
    # data_received = pyqtSignal(object)

    def __init__(self, addr, p):
        QThread.__init__(self)
        self.address = addr
        self.port = p
        self.stop_receive = False

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.address, self.port))

        # self.threadpool = QThreadPool()

    def run(self):
        global package_list
        while not self.stop_receive:
            # data, _ = self.sock.recvfrom(PACKAGE_LENGTH * 4)
            data = self.sock.recv(PACKAGE_LENGTH * 4)
            package_list.append(np.frombuffer(data, dtype=np.int32))
        self.sock.close()

    def stop(self):
        self.stop_receive = True


class DataHandler(QThread):
    plottable_package = pyqtSignal(object)

    def __init__(self, address, port):
        QThread.__init__(self)
        self.receiver = UdpReceiver(address, port)
        # self.receiver.data_received.connect(self.process_data)
        self.receiver.start()
        self.data_deque = deque()

    def run(self):
        global package_list
        while True:
            if len(package_list) != 0:
                package = package_list.popleft()
                if MARKER in package:
                    print('marker')
                    split_packages = split_data(package, MARKER)
                    for i in split_packages[0]:
                        self.data_deque.append(i)
                    if len(self.data_deque) == PLOT_LENGTH:
                        print('full')
                        self.plottable_package.emit(np.asarray(self.data_deque))
                    self.data_deque.clear()
                else:
                    for i in package:
                        self.data_deque.append(i)


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()

        self.x_axis = np.arange(1, PLOT_LENGTH + 1)

        self.graph = PlotWidget()
        self.graph.plot(np.ones(PLOT_LENGTH))

        self.ip_address = QLineEdit()
        self.ip_address.setPlaceholderText('Enter a receiving ip-address')
        self.ip_address.setText(IP)
        self.port = QLineEdit()
        self.port.setPlaceholderText('Enter a receiving Port')
        self.port.setText(str(PORT))

        self.dataHandler = DataHandler(self.ip_address.text(), int(self.port.text()))
        self.dataHandler.plottable_package.connect(self.plot)
        self.dataHandler.start()

        layout = QGridLayout()
        for i in (self.graph, self.ip_address, self.port):
            layout.addWidget(i)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.app = app

    def plot(self, dataset):
        self.graph.clear()
        self.graph.plot(self.x_axis, dataset)


def main():
    app = QApplication(sys.argv)
    window = MainWindow(app)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
