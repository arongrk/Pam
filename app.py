# import sys
from PyQt5.QtCore import *
from pyqtgraph import *
from PyQt5.QtWidgets import *
import numpy as np
import random as rnd
import time as t
import ctypes
import functools

import matlabdata


data = matlabdata.load_adc()
data = np.append([data], [[i for i in range(1, 40961)]], axis=0)

long_data = matlabdata.load_fpga()
split_array = matlabdata.split_data(long_data, -1426063361)

package_list = matlabdata.split_350(long_data)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.fn()


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.graph = PlotWidget()
        self.data_line = self.graph.plot(data[1], data[0])

        self.threadpool = QThreadPool()
        print(self.threadpool.maxThreadCount())

        self.load_data = bool

        self.start_plot = QPushButton('Start Plotting')
        self.start_plot.clicked.connect(self.run)

        layout = QGridLayout()
        layout.addWidget(self.graph)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

    '''
        self.multi_input = QLineEdit()
        self.multi_input.setPlaceholderText('Enter an integer to test the plotting speed')
        self.multi_input.returnPressed.connect(self.update_multi)
        self.load_data = True

        self.updateTimer = QCheckBox()
        self.updateTimer.stateChanged.connect(self.update_data)
'''

    def run(self):
        # Insert the start of a separate thread here:
        # Method for receiving the UDP-packages and inserting them to package_list

        self.load_data = True
        update = Worker(self.update_fpga_data)
        self.threadpool.start(update)
        while True:                                 # This condition is to be bound to a user input of some form
            plotter = Worker(self.update_plot)
            self.threadpool.start(plotter)
            QApplication.processEvents()

    def update_data(self):
        while self.load_data:
            data[0] += rnd.randint(-4000, 5000)
            t.sleep(0.008)

    def update_fpga_data(self):
        data_array = np.array([])

        while self.load_data:
            if len(package_list) != 0:
                array350 = package_list[0]
                package_list.pop(0)
                split350 = matlabdata.split_data(array350, ctypes.c_int32(0xaaffffff).value)
                if sum(len(i) for i in split350) == 350:
                    for i in split350[0]:
                        data_array = np.append(data_array, i)
                else:
                    for i in split350[0]:
                        data_array = np.append(data_array, i)
                    if len(data_array) == 40960:
                        data[0] = data_array
                    data_array = np.array([])
                    for i in split350[1]:
                        data_array = np.append(data_array, i)

    def update_plot(self):
        self.data_line.setData(data[1], data[0])

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


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
