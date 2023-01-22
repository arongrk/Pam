# import sys
from PyQt5.QtCore import *
from pyqtgraph import *
from PyQt5.QtWidgets import *
import numpy as np
import random as rnd
import time as t
import functools

import matlabdata

data = matlabdata.load_ABC()
data = np.append([data], [[i for i in range(1, 40961)]], axis=0)


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

        self.button = QPushButton('Assign random numbers')
        self.button.setFixedSize(QSize(200, 50))
        self.button.clicked.connect(functools.partial(self.update_plot, True))

        self.threadpool = QThreadPool()
        print(self.threadpool.maxThreadCount())
        self.multi_input = QLineEdit()
        self.multi_input.returnPressed.connect(self.update_multi)
        self.load_data = True

        layout = QGridLayout()
        layout.addWidget(self.graph)
        layout.addWidget(self.button)
        layout.addWidget(self.multi_input)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

    def update_data(self):
        while self.load_data:
            data[0] += rnd.randint(-4000, 5000)
            t.sleep(0.008)

    def update_plot(self):
        self.data_line.setData(data[1], data[0])

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
        self.time_taken(st, et, times)

    def time_taken(self, start, end, runs):
        time = end - start
        avgtime = time / runs
        dlg = QMessageBox(self)
        dlg.setWindowTitle('Time taken')
        dlg.setText(f'Time:         {time.__round__(3)} seconds\nAvg. Time: {avgtime.__round__(5)} seconds')
        dlg.exec()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
