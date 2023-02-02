# import sys
from PyQt5.QtCore import *
from pyqtgraph import *
from PyQt5.QtWidgets import *
import numpy as np
import random as rnd
import time as t
from ctypes import c_int32
import socket

import matlabdata


UDP_IP = '192.168.1.1'
UDP_PORT = 9090
plot_length = 40960 * 16
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


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.fn()


class MainWindow(QMainWindow):

    def __init__(self, app):
        super().__init__()

        self.graph = PlotWidget()
        self.data_line = self.graph.plot(data[1], data[0])

        self.threadpool = QThreadPool()
        print('Number of available threads: ', self.threadpool.maxThreadCount())

        self.load_data = bool

        self.start_plot = QPushButton('Start Plotting')
        self.start_plot.clicked.connect(self.run)

        self.end_plot = QPushButton('Stop Plotting')
        self.end_plot.clicked.connect(self.stop_run)

        layout = QGridLayout()
        layout.addWidget(self.graph)
        layout.addWidget(self.start_plot)
        layout.addWidget(self.end_plot)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.app = app

    '''
        self.multi_input = QLineEdit()
        self.multi_input.setPlaceholderText('Enter an integer to test the plotting speed')
        self.multi_input.returnPressed.connect(self.update_multi)
        self.load_data = True

        self.updateTimer = QCheckBox()
        self.updateTimer.stateChanged.connect(self.update_data)
'''

    def run(self):
        self.load_data = True
        load = Worker(update_package_list)
        self.threadpool.start(load)
        t.sleep(5)
        update = Worker(self.update_fpga_data)
        self.threadpool.start(update)
        while self.load_data:                                 # This condition is to be bound to a user input of some form
            plotter = Worker(self.update_plot)
            self.threadpool.start(plotter)
            QApplication.processEvents()

    def stop_run(self):
        self.load_data = False
        self.threadpool.clear()

    def update_fpga_data(self):
        print('Loading data into data object started')
        data_array = np.array([])
        while self.load_data:
            if len(package_list) != 0:
                udp_package = package_list[0]
                package_list.pop(0)
                split_package = matlabdata.split_data(udp_package, marker)
                if sum(len(i) for i in split_package) == 350:
                    data_array = np.append(data_array, split_package[0], axis=0)
                else:
                    data_array = np.append(data_array, split_package[0], axis=0)
                    if len(data_array) == plot_length:
                        data[0] = data_array
                    data_array = np.array([])
                    data_array = np.append(data_array, split_package[1], axis=0)

    def update_plot(self):
        self.data_line.setData(data[1], data[0])

# Unused methods!!!
    def time_dialogue(self, start, end, runs=1):
        time = end - start
        avgtime = time / runs
        dlg = QMessageBox(self)
        dlg.setWindowTitle('Time taken')
        dlg.setText(f'Time:         {time.__round__(3)} seconds\nAvg. Time: {avgtime.__round__(5)} seconds')
        dlg.exec()

    def update_multi(self):
        self.load_data = True
        update_data = Worker(self.update_data)
        self.threadpool.start(update_data)
        times = int(self.multi_input.text())
        st = t.time()
        for i in range(times):
            update_plot = Worker(self.update_plot)
            self.threadpool.start(update_plot)
            QApplication.processEvents()
        et = t.time()
        self.load_data = False
        self.time_dialogue(st, et, times)

    def update_data(self):
        while self.load_data:
            data[0] += rnd.randint(-4000, 5000)
            t.sleep(0.008)



def main():
    app = QApplication(sys.argv)
    window = MainWindow(app)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()