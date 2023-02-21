import numpy as np
import sys
import time
import struct
import socket

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import uic
from PyQt5.QtNetwork import *
from pyqtgraph import *

# from hacker import Hacker
import definitions
from PamsFunctions import Handler
from byte_sender import create_receive, real_sender
# import funtions


class Receiver(QObject):
    packageReady = pyqtSignal(bytearray)
    connecting = pyqtSignal()
    connected = pyqtSignal()
    connect_failed = pyqtSignal()
    no_connect = pyqtSignal()

    def __init__(self, ip_address='192.168.1.1', port=9090):
        QObject.__init__(self)

        self.ip = ip_address
        self.port = port
        # self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # self.socket.bind(('192.168.1.1', port))

        self.socket = QUdpSocket(self)
        self.stop_receive = False

    def run(self):
        pass

    def connect(self):
        print('trying')
        try:
            self.connecting.emit()
            self.socket.bind((self.ip, self.port))
            self.connected.emit()
        except OSError:
            self.connect_failed.emit()
        except TypeError:
            self.no_connect.emit()

    def run(self):
        self.connect()
        pack_size = definitions.PACKAGE_SIZE
        plot_size = definitions.PLOT_SIZE
        marker = definitions.MARKER_BYTES
        # hacker = Hacker(create_receive(real_sender(self.socket)), pack_size, plot_size, marker)
        # g = hacker.hack()
        handler = Handler(self.socket)
        g = handler.assembler()
        t0 = time.time()
        while not self.stop_receive:
            r = next(g)
            self.packageReady.emit(r)
        self.socket.close()

    def stop(self):
        self.stop_receive = True


class SecondData(QObject):
    package2Ready = pyqtSignal(list)

    def __init__(self):
        QObject.__init__(self)

    def selector(self, edit_type):
        print(edit_type, type(edit_type))

    def data_accepter(self, data):
        data = data
        samples_per_sequence = definitions.SamplesPerSequence
        shifts = definitions.SHIFTS
        sequence_reps = definitions.SequenceReps
        self.averager(data, samples_per_sequence, shifts, sequence_reps)

    def averager(self, sett, sps, sh, sr):
        set2 = list()
        sett = sett
        for i in range(sh):
            avg = 0
            for j in range(sr*i, sr*i+sr):
                if (j+1)/sr == int((j+1)/sr):
                    for k in range(sps*j, sps*(j+1)):
                        avg += struct.unpack('i', sett[4*k:4*(k+1)])[0]
                    set2.append(avg/sps)
        self.package2Ready.emit(set2)


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

        # Setting up the Receiver class
        self.receiver_thread = QThread()
        self.receiver = Receiver(definitions.IP_Address, definitions.PORT)
        self.receiver.moveToThread(self.receiver_thread)
        self.receiver_thread.start()
        self.receiver.run()
        self.receiver.packageReady.connect(self.plot)
        self.receiver.connected.connect(self.status_connected)
        self.receiver.connecting.connect(self.status_connecting)
        self.receiver.connect_failed.connect(self.status_con_failed)
        self.receiver.no_connect.connect(self.status_no_connect)
        # self.connect_button.clicked.connect(self.receiver.connect)
        # self.receiver.connectionStatus.connect(self.connect_checker)

        # Setting up the ip and port changer:
        self.refresh.clicked.connect(self.refresh_connect)

        # Start and stop Plot 1
        # self.start_plot1.clicked.connect(self.start_receiver)
        # self.stop_plot1.clicked.connect(self.stop_receiver)

        # Setting up the SecondData class
        self.second_thread = QThread()
        self.second_data = SecondData()
        self.second_data.moveToThread(self.second_thread)
        self.start_plot2.clicked.connect(self.start_second)

        # Getting the way the data should be edited
        self.plot2.currentTextChanged.connect(self.second_data.selector)

    def plot(self, data):
        data = np.frombuffer(data, dtype=np.int32)
        self.line1.setData(self.yData, data)

    def startplot2(self, data):
        data = data
        self.line2.setData(self.yData2, data)

    def refresh_receiver(self):
        ip = self.ip1.text() + '.' + self.ip2.text() + '.' + self.ip3.text() + '.' + self.ip4.text()
        port = int(self.recport.text())
        sender_port = int(self.senport.text())
        self.stop_receiver()
        self.receiver.connect()
        self.receiver.stop()
        self.receiver.quit()
        self.receiver.wait()
        self.receiver = Receiver(definitions.IP_Address, definitions.PORT)
        self.receiver.start()
        self.receiver.packageReady.connect(self.plot)

    def status_connected(self):
        self.con_status.setStyleSheet('color : green')
        self.con_status.setText('Connected to server')

    def status_connecting(self):
        self.con_status.setStyleSheet('Color : black')
        self.con_Status.setText('Connecting...')

    def status_con_failed(self):
        self.con_status.setStyleSheet('Color : red')
        self.con_Status.setText('Connection failed...\nrefresh to retry!')

    def no_connect(self):
        self.con_status.setStyleSheet('Color : red')
        self.con_Status.setText('Connection failed...\nCheck connection data and retry!')

    def start_second(self):
        self.second_thread.start()
        print('Second Plot-Thread initialized')
        self.receiver.packageReady.connect(self.second_data.data_accepter)
        self.second_data.package2Ready.connect(self.startplot2)

    def refresh_connect(self):
        pass



def main():
    app = QApplication(sys.argv)
    window = UI()
    window.show()
    app.exec()


if __name__ == '__main__':
    main()
