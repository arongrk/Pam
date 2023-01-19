import sys
from PyQt5.QtCore import Qt, QSize
from pyqtgraph import PlotWidget, plot
from PyQt5.QtWidgets import QApplication, QGridLayout, QMainWindow, QPushButton, QWidget, QLineEdit, QDialog, QMessageBox
import numpy as np
import random as rnd
import time as t
import functools

import matlabdata

data = matlabdata.load_ABC()
data = np.append([data], [[i for i in range(1, 40961)]], axis=0)
print(data)


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        layout = QGridLayout()

        self.graph = PlotWidget()

        self.data_line = self.graph.plot(data[1], data[0])

        self.button = QPushButton('Assign random numbers')
        self.button.setFixedSize(QSize(200, 50))
        self.button.clicked.connect(functools.partial(self.update_plot, True))

#        self.button2 = QPushButton('Assign 10000 random numbers')
#        self.button2.setFixedSize(QSize(200, 50))
#        self.button2.clicked.connect(self.update10000_plot)

        self.button2input = QLineEdit()
        self.button2input.returnPressed.connect(self.update_multi)
        layout.addWidget(self.graph)
        layout.addWidget(self.button)
        layout.addWidget(self.button2input)

        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        self.print_it = True

    def update_plot(self, print_it):
        if print_it:
            st = t.time()
        data[0] += rnd.randint(-900, 1000)
        self.data_line.setData(data[1], data[0])
        QApplication.processEvents()
        if print_it:
            et = t.time()
        if print_it:
            print(et-st)


    def update_multi(self):
        times = int(self.button2input.text())
        st = t.time()
        for i in range(times):
            self.update_plot(False)
        et = t.time()
        time = et - st
        avgtime = time / times
        dlg = QMessageBox(self)
        dlg.setWindowTitle('Time taken')
        dlg.setText(f'It took {time} seconds\nAverage seconds: {avgtime}')
        dlg.exec()





def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()