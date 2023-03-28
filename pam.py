import sys

import numpy as np
from scipy.signal import find_peaks
import time
import struct
import socket
import tomllib
import tomlkit

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import uic
from pyqtgraph import mkPen, PlotWidget, DateAxisItem
from collections import deque

# from hacker import Hacker
import definitions
from PamsFunctions import Handler, averager, unconnect, zero_padding, polynom_interp_max, exact_polynom_interp_max


class Receiver(QThread):
    packageReady = pyqtSignal(tuple)
    st_connecting = pyqtSignal()
    st_connected = pyqtSignal()
    st_connect_failed = pyqtSignal(str)
    packageLost = pyqtSignal()

    def __init__(self, shifts, sequence_repetitions, samples_per_sequence, port=9090, ip_address='192.168.1.1', ):
        QThread.__init__(self)

        self.ip = ip_address
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2**18)

        self.shifts = shifts
        self.s_reps = sequence_repetitions
        self.sps = samples_per_sequence
        self.set_len = self.shifts * self.s_reps * self.sps

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
        handler = Handler(self.socket, shifts=self.shifts, sequence_reps=self.s_reps, samples_per_sequence=self.sps)
        g = handler.assembler_2()
        while not self.stop_receive:
            r = next(g)
            if not r:
                self.packageLost.emit()
            else:
                yData = np.absolute(np.frombuffer(r, dtype=np.int32)) * 8.192 / pow(2, 18)
                # yData = np.frombuffer(r, dtype=np.int32) * 8.192 / pow(2, 18)
                xData = np.arange(0, (1000 * self.set_len)/4.9e+06, 1000/4.9e+06)
                self.packageReady.emit((xData, yData))
        self.socket.close()

    def stop(self):
        self.stop_receive = True
        # self.quit()
        # self.wait()


class SecondData(QObject):
    package2Ready = pyqtSignal(tuple)
    package3aReady = pyqtSignal(tuple)
    package3bReady = pyqtSignal(tuple)

    def __init__(self, samples_per_sequence, shifts, sequence_reps):
        QObject.__init__(self)
        self.sps = samples_per_sequence
        self.shifts = shifts
        self.sr = sequence_reps
        self.refresh_x1 = False
        self.refresh_x2 = False
        self.t0 = time.time()
        self.maxima, self.time_stamps = list(), list()

    def irf(self, data):
        yData = averager(data[1], self.shifts, self.sps, self.sr)
        yData = yData - np.average(yData[len(yData)-100:])
        xData = np.arange(1, self.shifts+1) / 5e+09
        # data = zero_padding(xData, yData, 2.4e+09, 16080)
        # print(find_peaks(data[1], height=0.05))
        # self.package2Ready.emit((data[0], data[1]))
        self.package2Ready.emit((xData, yData))

    def distance(self, data):
        data = zero_padding(data[0], data[1], 2.4e+09, 8160)
        # print(find_peaks(data[1]))
        # print(np.argsort(data[1][:5000])[-3:])
        # self.maxima.append(data[0][data[1].argmax()])
        # self.maxima.append(polynom_interp_max(data[0][:int(len(data[0])/2)], data[1][:int(len(data[0])/2)], 50))
        self.maxima.append(exact_polynom_interp_max(data[0][:int(len(data[0])/2)], data[1][:int(len(data[0])/2)]))
        self.time_stamps.append(round(time.time() - self.t0, 5))
        if self.refresh_x1:
            self.package3aReady.emit((self.time_stamps[-1000:], self.maxima[-1000:]))
        else:
            self.package3aReady.emit((self.time_stamps, self.maxima))
        if self.refresh_x2:
            self.package3bReady.emit((self.time_stamps[-1000:], self.maxima[-1000:]))
        else:
            self.package3bReady.emit((self.time_stamps, self.maxima))


    def option_3(self, data):
        pass

    def option_4(self, data):
        pass


class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()

        # Load the ui file
        uic.loadUi('resources/Mainwindow.ui', self)

        # Getting the parameters for data interpreting
        self.samples_per_sequence = int(self.sps_edit.text())
        self.sequence_reps = int(self.sr_edit.text())
        self.shifts = int(self.shifts_edit.text())
        self.refresh_config.clicked.connect(self.refresh_configuration)
        self.xData = np.arange(1, self.shifts * self.sequence_reps * self.samples_per_sequence + 1) / 5 * 10 ** 9
        self.xData2 = np.arange(0, 1280) / 5 * 10 ** 9

        # Configuring both plot-widgets
        pen = mkPen(color=(0, 0, 0), width=1)
        self.graph1.setBackground('w')
        self.line1 = self.graph1.plot(self.xData, np.zeros(len(self.xData)), pen=pen)

        self.graph2.setBackground('w')
        self.line2 = self.graph2.plot(self.xData2, np.zeros(len(self.xData2)), pen=pen)

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
        self.receiver = Receiver(self.shifts, self.sequence_reps, self.samples_per_sequence, self.port, self.ip)
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
        self.start_plot1.clicked.connect(self.plot_starter1)
        self.stop_plot1.clicked.connect(self.plot_breaker1)

        # Setting up the SecondData class
        self.second_thread = QThread()
        self.second_data = SecondData(self.samples_per_sequence, self.shifts, self.sequence_reps)
        self.second_data.moveToThread(self.second_thread)
        self.second_thread.start()
        self.start_plot2.clicked.connect(self.plot_starter2)
        self.stop_plot2.clicked.connect(self.plot_breaker2)

        # Refreshing the chosen plot option
        self.QComboBox_1.currentTextChanged.connect(self.running_refresher1)
        self.QComboBox_2.currentTextChanged.connect(self.running_refresher2)

        # Refreshing weather x should be refreshed or not
        self.refresh_x1.stateChanged.connect(self.refresh_x1_refresher)
        self.refresh_x2.stateChanged.connect(self.refresh_x2_refresher)

        # Setting up the plot timer:
        self.timer = QTimer()
        self.timer.timeout.connect(self.plot1_timer)
        self.timer.timeout.connect(self.plot2_timer)
        self.timer.timeout.connect(self.receiver_timer)
        self.timer.start(1000)
        self.counter1 = 0
        self.counter2 = 0
        self.counter_lost = 0


        self.request1 = 0
        self.request2 = 0

    def plot(self, data):
        self.line1.setData(data[0], data[1])
        self.counter1 += 1

    def plot_2(self, data):
        self.line2.setData(data[0], data[1])
        self.counter2 += 1

    def plot_starter1(self):
        self.start_plot1.setEnabled(False)
        box = self.QComboBox_1.currentText()
        if box == 'Raw data':
            self.request1 = 1
        if box == 'IRF':
            self.request1 = 2
        if box == 'Distance':
            self.request1 = 3
        self.data_connector()
        # self.xdata_refresher()
        self.plot_connector1()
        self.stop_plot1.setEnabled(True)

    def plot_starter2(self):
        self.start_plot2.setEnabled(False)
        box = self.QComboBox_2.currentText()
        if box == 'Raw data':
            self.request2 = 1
        if box == 'IRF':
            self.request2 = 2
        if box == 'Distance':
            self.request2 = 3
        self.data_connector()
        self.plot_connector2()
        self.stop_plot2.setEnabled(True)

    def plot_breaker1(self):
        self.stop_plot1.setEnabled(False)
        self.request1 = 0
        self.plot_disconnector1()
        self.data_connector()
        self.start_plot1.setEnabled(True)

    def plot_breaker2(self):
        self.stop_plot2.setEnabled(False)
        self.request2 = 0
        self.plot_disconnector2()
        self.data_connector()
        self.start_plot2.setEnabled(True)

    def plot_connector1(self):
        if self.request1 == 1:
            self.receiver.packageReady.connect(self.plot)
        if self.request1 == 2:
            self.second_data.package2Ready.connect(self.plot)
        if self.request1 == 3:
            self.second_data.package3aReady.connect(self.plot)

    def plot_connector2(self):
        if self.request2 == 1:
            self.receiver.packageReady.connect(self.plot_2)
        if self.request2 == 2:
            self.second_data.package2Ready.connect(self.plot_2)
        if self.request2 == 3:
            self.second_data.package3bReady.connect(self.plot_2)

    def plot_disconnector1(self):
        unconnect(self.receiver.packageReady, self.plot)
        unconnect(self.second_data.package2Ready, self.plot)
        unconnect(self.second_data.package3aReady, self.plot)

    def plot_disconnector2(self):
        unconnect(self.receiver.packageReady, self.plot_2)
        unconnect(self.second_data.package2Ready, self.plot_2)
        unconnect(self.second_data.package3bReady, self.plot_2)

    def running_refresher1(self):
        if not self.start_plot1.isEnabled():
            self.plot_breaker1()
            self.plot_starter1()
        if self.QComboBox_1.currentText() == 'Distance':
            self.refresh_x1.setEnabled(True)
        else:
            self.refresh_x1.setEnabled(False)

    def running_refresher2(self):
        if not self.start_plot2.isEnabled():
            self.plot_breaker2()
            self.plot_starter2()
        if self.QComboBox_2.currentText() == 'Distance':
            self.refresh_x2.setEnabled(True)
        else:
            self.refresh_x2.setEnabled(False)

    def refresh_x1_refresher(self):
        if not self.start_plot1.isEnabled():
            self.plot_breaker1()
            self.plot_starter1()

    def refresh_x2_refresher(self):
        if not self.start_plot2.isEnabled():
            self.plot_breaker2()
            self.plot_starter2()

    # Maybe double connections!!:
    def data_connector(self):
        if self.request1 <= 1 and self.request2 <= 1:
            unconnect(self.receiver.packageReady, self.second_data.irf)
        else:
            self.receiver.packageReady.connect(self.second_data.irf)
        if self.request1 == 3 or self.request2 == 3:
            self.second_data.t0 = time.time()
            self.second_data.time_stamps, self.second_data.maxima = list(), list()
            if self.refresh_x1.isChecked():
                self.second_data.refresh_x1 = True
            else:
                self.second_data.refresh_x1 = False
            if self.refresh_x2.isChecked():
                self.second_data.refresh_x2 = True
            else:
                self.second_data.refresh_x2 = False
            self.second_data.package2Ready.connect(self.second_data.distance)
        else:
            unconnect(self.second_data.package2Ready, self.second_data.distance)
        if self.request1 == 4 or self.request2 == 4:
            self.second_data.package2Ready.connect(self.second_data.option_3)
        else:
            unconnect(self.second_data.package2Ready, self.second_data.option_3)
        if self.request1 == 5 or self.request2 == 5:
            self.second_data.package2Ready.connect(self.second_data.option_4)
        else:
            unconnect(self.second_data.package2Ready, self.second_data.option_4)

    '''
    def plot1_starter(self):
        self.receiver.packageReady.connect(self.plot)
        self.start_plot1.setEnabled(False)
    
    def plot1_breaker(self):
        self.receiver.packageReady.disconnect(self.plot)
        self.start_plot1.setEnabled(True)
        self.stop_plot1.setEnabled(False)

    def plot2_starter(self):
        self.second_data.package2Ready.connect(self.plot_2)
        if self.QComboBox_2.currentText() == 'average':
            self.receiver.packageReady.connect(self.second_data.step_averager)
        if self.QComboBox_2.currentText() == 'option 2':
            self.receiver.packageReady.connect(self.second_data.distance)
        if self.QComboBox_2.currentText() == 'option 3':
            self.receiver.packageReady.connect(self.second_data.option_3)
        self.start_plot2.setEnabled(False)
        self.stop_plot2.setEnabled(True)

    def plot2_breaker(self):
        try:
            self.receiver.packageReady.disconnect(self.second_data.step_averager)
        except TypeError:
            pass
        try:
            self.receiver.packageReady.disconnect(self.second_data.distance)
        except TypeError:
            pass
        try:
            self.receiver.packageReady.disconnect(self.second_data.option_3)
        except TypeError:
            pass
        self.stop_plot2.setEnabled(False)
        self.start_plot2.setEnabled(True)
    '''

    def start_receiver(self):
        self.receiver.start()
        self.receiver.packageLost.connect(self.lost_counter)
        self.start_plot1.setEnabled(True)
        self.start_plot2.setEnabled(True)
        self.start_receive.setEnabled(False)
        self.stop_receive.setEnabled(True)
        self.label_11.setStyleSheet('color: green')
        self.label_11.setText('Receiving data')

    def reconnect_receiver(self):
        self.plot_breaker1()
        self.plot_breaker2()
        self.receiver.stop()
        self.receiver.quit()
        self.receiver.wait()
        self.receiver = Receiver(self.shifts, self.sequence_reps, self.samples_per_sequence, self.port, self.ip)
        # self.receiver.packageReady.connect(self.plot)
        self.receiver.st_connecting.connect(self.rec_connecting)
        self.receiver.st_connecting.connect(self.rec_connected)
        self.receiver.st_connect_failed.connect(self.rec_failed)
        self.receiver.connect()
        self.start_receive.setEnabled(True)
        self.stop_receive.setEnabled(False)
        self.start_plot1.setEnabled(False)
        self.start_plot2.setEnabled(False)
        self.label_11.setText('Not receiving')
        self.label_11.setStyleSheet('color: black')

    def refresh_connect(self):
        self.ip = self.ip1.text() + '.' + self.ip2.text() + '.' + self.ip3.text() + '.' + self.ip4.text()
        self.port = int(self.recport.text())
        self.sender_port = int(self.senport.text())
        self.ip_label.setText(f' IP:   {self.ip}')
        self.port_label.setText(f' Port: {self.port}')
        self.reconnect_receiver()

    def refresh_configuration(self):
        self.plot_breaker1()
        self.plot_breaker2()
        self.samples_per_sequence = int(self.sps_edit.text())
        self.sequence_reps = int(self.sr_edit.text())
        self.shifts = int(self.shifts_edit.text())
        self.second_data.sps = self.samples_per_sequence
        self.second_data.sr = self.sequence_reps
        self.second_data.shifts = self.shifts
        self.reconnect_receiver()
        if self.stop_plot1.isEnabled():
            self.plot_starter1()
        if self.stop_plot2.isEnabled():
            self.plot_starter2()

    '''
    def plot1_chooser(self):
        pass

    def plot2_chooser(self):
        text = self.QComboBox_2.currentText()
        if text == 'IRF':
            try:
                self.receiver.packageReady.disconnect(self.second_data.distance)
            except TypeError:
                pass
            try:
                self.receiver.packageReady.disconnect(self.second_data.option_3)
            except TypeError:
                pass
            self.receiver.packageReady.connect(self.second_data.irf)
        if text == 'option 2':
            try:
                self.receiver.packageReady.disconnect(self.second_data.irf)
            except TypeError:
                pass
            try:
                self.receiver.packageReady.disconnect(self.second_data.option_3)
            except TypeError:
                pass
            self.receiver.packageReady.connect(self.second_data.distance)
        if text == 'option 3':
            try:
                self.receiver.packageReady.disconnect(self.second_data.irf)
            except TypeError:
                pass
            try:
                self.receiver.packageReady.disconnect(self.second_data.distance)
            except TypeError:
                pass
            self.receiver.packageReady.connect(self.second_data.option_3)

    def xdata_refresher(self):
        if self.QComboBox_1.currentText() == 'Raw data':
            self.xData = np.arange(1, self.samples_per_sequence * self.shifts * self.sequence_reps + 1) / 5e+09
        if self.QComboBox_1.currentText() == 'IRF':
            self.xData = np.arange(1, self.shifts + 1) / 5e+09
        if self.QComboBox_1.currentText() == 'Distance':
            self.xData = np.arange(-999, 1)                                     # Not finished!
        if self.QComboBox_2.currentText() == 'Raw data':
            self.xData2 = np.arange(1, self.samples_per_sequence * self.shifts * self.sequence_reps + 1) / 5e+09
        if self.QComboBox_2.currentText() == 'IRF':
            self.xData2 = np.arange(1, self.shifts + 1) / 5e+09
        if self.QComboBox_2.currentText() == 'Distance':
            self.xData2 = np.arange(-999, 1)                                    # Not finished!
    '''

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
        self.counter_lost += 1

    def plot1_timer(self):
        self.label_12.setText(f'Plot 1: {self.counter1} P/s')
        self.counter1 = 0

    def plot2_timer(self):
        self.label_22.setText(f'Plot 2: {self.counter2} P/s')
        self.counter2 = 0

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
