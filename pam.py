import numpy as np
import sys
import time
import struct
import socket

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import uic
from pyqtgraph import *

# from hacker import Hacker
import definitions
from PamsFunctions import Handler, averager
from byte_sender import create_receive, real_sender
# import funtions


class Receiver(QThread):
    packageReady = pyqtSignal(bytearray)
    st_connecting = pyqtSignal()
    st_connected = pyqtSignal()
    st_connect_failed = pyqtSignal(str)
    packageLost = pyqtSignal()

    def __init__(self, ip_address='192.168.1.1', port=9090):
        QThread.__init__(self)

        self.ip = ip_address
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # self.socket.bind(('192.168.1.1', port))

        self.stop_receive = False

    def connect(self):
        try:
            self.st_connecting.emit()
            self.socket.bind((self.ip, self.port))
            self.st_connected.emit()
        except OSError:
            self.st_connect_failed.emit('os')
        except TypeError:
            self.st_connect_failed.emit('type')

    def run(self):
        # pack_size = definitions.PACKAGE_SIZE
        # plot_size = definitions.PLOT_SIZE
        # marker = definitions.MARKER_BYTES
        # hacker = Hacker(create_receive(real_sender(self.socket)), pack_size, plot_size, marker)
        # g = hacker.hack()
        handler = Handler(self.socket)
        g = handler.assembler_2()
        # t0 = time.time()
        while not self.stop_receive:
            r = next(g)
            if not r:
                self.packageLost.emit()
            else:
                self.packageReady.emit(r)
        self.socket.close()

    def stop(self):
        self.stop_receive = True
        # self.quit()
        # self.wait()


class SecondData(QObject):
    package2Ready = pyqtSignal(np.ndarray)

    def __init__(self):
        QObject.__init__(self)
        self.sps = definitions.SamplesPerSequence
        self.shifts = definitions.SHIFTS
        self.sr = definitions.SequenceReps

    def selector(self, edit_type):
        print(edit_type, type(edit_type))

    def data_acceptor(self, data):
        data = data
        data = averager(data, 1280, 16, 2)
        self.package2Ready.emit(data)


class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()

        # Load the ui file
        uic.loadUi('resources/Mainwindow.ui', self)
        self.yData = np.arange(1, definitions.PLOT_LENGTH + 1)
        self.yData2 = np.arange(1, 1280+1)

        # Configuring both plot-widgets
        pen = mkPen(color=(0, 0, 0), width=1)
        self.graph1.setBackground('w')
        self.line1 = self.graph1.plot(self.yData, np.zeros(len(self.yData)), pen=pen)

        self.graph2.setBackground('w')
        self.line2 = self.graph2.plot(self.yData2, np.zeros(len(self.yData2)), pen=pen)

        # Setting up the IP and Port inputs and values:
        self.ip, self.port, self.sender_port = definitions.IP_Address, definitions.PORT, definitions.SENDER_PORT
        split_ip = self.ip.split('.')
        ip_inputs = (self.ip1, self.ip2, self.ip3, self.ip4)
        for i in range(4):
            ip_inputs[i].setText(split_ip[i])

        # Label SetUp
        self.ip_label.setText(f' IP:   {self.ip}')
        self.port_label.setText(f' Port: {self.port}')

        # Setting up the Receiver class
        self.receiver = Receiver(self.ip, self.port)
        self.connect_button.clicked.connect(self.receiver.connect)
        self.receiver.st_connecting.connect(self.rec_connecting)
        self.receiver.st_connecting.connect(self.rec_connected)
        self.receiver.st_connect_failed.connect(self.rec_failed)
        self.start_receive.clicked.connect(self.start_receiver)
        self.stop_receive.clicked.connect(self.reconnect_receiver)
        self.start_receive.setEnabled(False)
        self.stop_receive.setEnabled(False)

        # Setting up the ip and port changer:
        self.refresh.clicked.connect(self.refresh_connect)

        # Start and stop Plot 1
        self.start_plot1.clicked.connect(self.plot_starter)
        self.stop_plot1.clicked.connect(self.plot_breaker)

        # Setting up the SecondData class
        self.second_thread = QThread()
        self.second_data = SecondData()
        self.start_plot2.clicked.connect(self.start_second)

        # Getting the way the data should be edited
        self.plot2.currentTextChanged.connect(self.second_data.selector)

        # Setting up the plot timer:
        self.timer = QTimer()
        self.timer.timeout.connect(self.plot1_timer)
        self.timer.timeout.connect(self.receiver_timer)
        self.timer.start(1000)
        self.counter1 = 0
        self.counter_lost = 0

    def plot_starter(self):
        self.receiver.packageReady.connect(self.plot)
        self.start_plot1.setEnabled(False)
        self.stop_plot1.setEnabled(True)

    def plot_breaker(self):
        self.receiver.packageReady.disconnect(self.plot)
        self.start_plot1.setEnabled(True)
        self.stop_plot1.setEnabled(False)

    def plot(self, data):
        data = np.frombuffer(data, dtype=np.int32) * 8.192 / pow(2, 18)
        self.line1.setData(self.yData, data)
        self.counter1 += 1

    def plot_2(self, data):
        data = data
        self.line2.setData(self.yData2, data)

    def start_receiver(self):
        self.receiver.start()
        self.receiver.packageLost.connect(self.lost_counter)
        self.start_plot1.setEnabled(True)
        self.start_receive.setEnabled(False)
        self.stop_receive.setEnabled(True)
        self.label_11.setStyleSheet('color: green')
        self.label_11.setText('Receiving data')

    def reconnect_receiver(self):
        self.receiver.stop()
        self.receiver.quit()
        self.receiver.wait()
        self.receiver = Receiver(self.ip, self.port)
        # self.receiver.packageReady.connect(self.plot)
        self.receiver.st_connecting.connect(self.rec_connecting)
        self.receiver.st_connecting.connect(self.rec_connected)
        self.receiver.st_connect_failed.connect(self.rec_failed)
        self.receiver.connect()
        self.start_receive.setEnabled(True)
        self.stop_receive.setEnabled(False)
        self.start_plot1.setEnabled(False)
        self.label_11.setText('Not receiving')
        self.label_11.setStyleSheet('color: black')

    def start_second(self):
        self.second_thread.start()
        self.receiver.packageReady.connect(self.second_data.data_acceptor)
        self.second_data.package2Ready.connect(self.plot_2)

    def refresh_connect(self):
        self.ip = self.ip1.text() + '.' + self.ip2.text() + '.' + self.ip3.text() + '.' + self.ip4.text()
        self.port = int(self.recport.text())
        self.sender_port = int(self.senport.text())
        self.ip_label.setText(f' IP:   {self.ip}')
        self.port_label.setText(f' Port: {self.port}')
        self.reconnect_receiver()

    def rec_connecting(self):
        self.con_status.setStyleSheet('color: black')
        self.con_status.setText('Connecting...')

    def rec_connected(self):
        self.con_status.setStyleSheet('color: green')
        self.con_status.setText('Connected.')
        self.start_receive.setEnabled(True)

    def rec_failed(self, error):
        self.con_status.setStyleSheet('color: red')
        self.con_status.setText('Connection failed: Resetting receiver.')
        self.reconnect_receiver()
        if error == 'os':
            self.con_status.setText('Connection failed: Retry later.')
        if error == 'type':
            self.con_status.setText('Connection failed: Check inputs and try again.')
        self.start_plot1.setEnabled(False)

    def lost_counter(self):
        self.counter_lost +=1

    def plot1_timer(self):
        self.label_12.setText(f'Plot 1: {self.counter1} P/s')
        self.counter1 = 0

    def receiver_timer(self):
        self.label_21.setText(f'Lost: {self.counter_lost} p/s')
        self.counter_lost = 0


def main():
    app = QApplication(sys.argv)
    window = UI()
    window.show()
    app.exec()


if __name__ == '__main__':
    main()
