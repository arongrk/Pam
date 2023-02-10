from PyQt5.QtCore import *
from pyqtgraph import *
from PyQt5.QtWidgets import *
import numpy as np
import random as rnd
import time as t
import ctypes
import threading
import logging.config
import asyncio
import functools

import matlabdata


data = matlabdata.load_adc()
data = np.append([data], [[i for i in range(1, 40961)]], axis=0)

package_list = list()


UDP_PORT = 9090

logger = logging.getLogger(__name__)


class Server(asyncio.DatagramProtocol, QThread):
    """
    UDP Server that listens on a given port and handles UDP Datagrams
    with arrays of floating point numbers.
    """

    dataReceived = pyqtSignal(object)

    def __init__(self, port: int):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self.port = port
        self.server = None
        self.transport = None
        self.start()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        logger.debug("received a datagram package")
        numbers = numpy.frombuffer(data)
        self.dataReceived.emit(numbers)

    def run(self):
        asyncio.set_event_loop(self.loop)
        print(f"creating datagram endpoint on port {self.port}")
        co_endp = self.loop.create_datagram_endpoint(lambda: self, local_addr=('0.0.0.0', self.port))
        self.transport, protocol = self.loop.run_until_complete(co_endp)
        print(f"datagram endpoint ready, switching to loop now")
        print(f"starting loop run_forever (thread: {threading.get_ident()})")
        self.loop.run_forever()
        self.transport.close()
        self.loop.close()
        print("Loop finished graceful")

    def stop(self):
        """Call loops stop method. Thread safe"""
        self.loop.call_soon_threadsafe(self.loop.stop)

long_data = matlabdata.load_dataFPGA()
long_data = np.append([long_data], [[i for i in range(1, len(long_data) + 1)]], axis=0)


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
        print(f'Available threads: {self.threadpool.maxThreadCount()}')


        self.load_data = bool

        self.start_plot = QPushButton('Start Plotting')
        self.start_plot.clicked.connect(self.run)

        layout = QGridLayout()
        layout.addWidget(self.graph)
        layout.addWidget(self.start_plot)
        widget = QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        self.app = app

        self.server = Server(UDP_PORT)
        self.server.dataReceived.connect(self.update_package_list)

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
        update = Worker(self.update_fpga_data)
        self.threadpool.start(update)
        while True:                                 # This condition is to be bound to a user input of some form
            plotter = Worker(self.update_plot)
            self.threadpool.start(plotter)
            QApplication.processEvents()

    def update_package_list(self, package):
        package_list.append(package)
        print(len(package))

    def update_data(self):
        while self.load_data:
            data[0] += rnd.randint(-4000, 5000)
            t.sleep(0.008)

    def update_fpga_data(self):
        data_array = np.array([])

        while self.load_data:
            if len(package_list) != 0:
                udp_package = package_list[0]
                package_list.pop(0)
                split_package = matlabdata.split_data(udp_package, ctypes.c_int32(0xaaffffff).value)
                if sum(len(i) for i in split_package) == 350:
                    for i in split_package[0]:
                        data_array = np.append(data_array, i)
                else:
                    for i in split_package[0]:
                        data_array = np.append(data_array, i)
                    if len(data_array) == 40960:
                        data[0] = data_array
                    data_array = np.array([])
                    for i in split_package[1]:
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
    window = MainWindow(app)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
