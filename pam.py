import socket
import pickle
import sys
import numpy as np
from scipy.signal import find_peaks
from scipy.fft import fft, ifft
import time
import struct
import tomllib
import tomlkit
from math import ceil

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import uic
from pyqtgraph import mkPen, AxisItem # PlotWidget, DateAxisItem
from collections import deque

# from hacker import Hacker
import definitions
from pams_functions import Handler, averager, change_dict, polynom_interp_max, exact_polynom_interp_max, unconnect, \
    zero_padding


class CustomAxis(AxisItem):
    @property
    def nudge(self):
        if not hasattr(self, "_nudge"):
            self._nudge = -5
        return self._nudge

    @nudge.setter
    def nudge(self, nudge):
        self._nudge = nudge
        s = self.size()
        # call resizeEvent indirectly
        self.resize(s + QSizeF(1, 1))
        self.resize(s)

    def resizeEvent(self, ev=None):
        # s = self.size()

        ## Set the position of the label
        br = self.label.boundingRect()
        p = QPointF(0, 0)
        if self.orientation == "left":
            p.setY(int(self.size().height() / 2 + br.width() / 2))
            p.setX(-self.nudge)
        elif self.orientation == "right":
            p.setY(int(self.size().height() / 2 + br.width() / 2))
            p.setX(int(self.size().width() - br.height() + self.nudge))
        elif self.orientation == "top":
            p.setY(-self.nudge)
            p.setX(int(self.size().width() / 2.0 - br.width() / 2.0))
        elif self.orientation == "bottom":
            p.setX(int(self.size().width() / 2.0 - br.width() / 2.0))
            p.setY(int(self.size().height() - br.height() + self.nudge))
        self.label.setPos(p)
        self.picture = None


class Receiver(QThread):
    packageReady = pyqtSignal(tuple)
    st_connecting = pyqtSignal()
    st_connected = pyqtSignal()
    st_connect_failed = pyqtSignal(str)
    packageLost = pyqtSignal()

    def __init__(self, shifts, sequence_repetitions, samples_per_sequence, length, port=9090, ip_address='192.168.1.1'):
        QThread.__init__(self)

        self.ip = ip_address
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 ** 18)

        self.shifts = shifts
        self.s_reps = sequence_repetitions
        self.sps = samples_per_sequence
        self.mes_len = length
        self.set_len = self.shifts * self.s_reps * self.sps

        self.stop_receive = False

    def connect(self):
        try:
            self.st_connecting.emit()
            self.sock.bind((self.ip, self.port))
            self.st_connected.emit()
        except OSError:
            self.st_connect_failed.emit('os')
        except TypeError:
            self.st_connect_failed.emit('type')

    def run(self):
        handler = Handler(self.sock, shifts=ceil(self.shifts/80)*80, sequence_reps=self.s_reps,
                          samples_per_sequence=self.sps)
        g = handler.assembler_2()
        while not self.stop_receive:
            r = next(g)
            if not r:
                self.packageLost.emit()
            else:
                yData = np.absolute(np.frombuffer(r, dtype=np.int32)[:self.set_len]) * 8.192 / pow(2, 18)
                # yData = np.frombuffer(r, dtype=np.int32) * 8.192 / pow(2, 18)
                # xData = np.arange(0, self.set_len*1000/4.9e+06, 1000/4.9e+06)
                xData = np.linspace(0, self.mes_len/self.sps*2e-10*self.set_len, self.set_len)
                self.packageReady.emit((xData, yData))
        self.sock.close()

    def stop(self):
        self.stop_receive = True
        # self.quit()
        # self.wait()


class SecondData(QObject):
    package2Ready = pyqtSignal(tuple)
    package3aReady = pyqtSignal(tuple)
    package3bReady = pyqtSignal(tuple)

    def __init__(self, samples_per_sequence, shifts, sequence_reps, length, last_n_values_plot1, last_n_values_plot2):
        QObject.__init__(self)
        self.sps = samples_per_sequence
        self.shifts = shifts
        self.sr = sequence_reps
        self.mes_len = length
        self.refresh_x1 = False
        self.refresh_x2 = False
        self.t0 = time.time()
        self.maxima, self.time_stamps = deque(maxlen=1000), deque(maxlen=1000)
        self.last_values1 = last_n_values_plot1
        self.last_values2 = last_n_values_plot2

    def irf(self, data):
        yData = averager(data[1], self.shifts, self.sps, self.sr)
        yData = yData - np.average(yData[len(yData)-100:])
        xData = np.arange(1, self.shifts+1) / 5e+09
        # yData = np.angle(fft(yData), deg=True)
        # xData, yData = zero_padding(xData, yData, 2.4e+09, 16080)
        # print(find_peaks(data[1], height=0.05))
        # self.package2Ready.emit((data[0], data[1]))
        self.package2Ready.emit((xData, yData))

    def distance(self, data):
        data = zero_padding(data[0], data[1], 2.4e+09, 2**5*self.shifts)
        # print(find_peaks(data[1]))
        # print(np.argsort(data[1][:5000])[-3:])
        # self.maxima.append(data[0][data[1].argmax()])
        # self.maxima.append(polynom_interp_max(data[0][:int(len(data[0])/2)], data[1][:int(len(data[0])/2)], 50))
        self.maxima.append(exact_polynom_interp_max(data[0][:int(len(data[0])/2)], data[1][:int(len(data[0])/2)]))
        self.time_stamps.append(round(time.time() - self.t0, 5))
        if self.refresh_x1:
            self.package3aReady.emit((self.time_stamps[-self.last_values1:], self.maxima[-self.last_values1:]))
        else:
            self.package3aReady.emit((self.time_stamps, self.maxima))
        if self.refresh_x2:
            self.package3bReady.emit((self.time_stamps[-self.last_values2:], self.maxima[-self.last_values2:]))
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

        # Loading the values and getting the parameters for data interpreting
        with open('configurations.bin', 'rb') as f:
            self.values = pickle.load(f)
        self.samples_per_sequence = self.values['samples_per_sequence']
        self.sequence_reps = self.values['sequence_reps']
        self.shifts = self.values['shifts']
        self.length = self.values['length']
        self.last_n_values1 = self.values['last_values1']
        self.last_n_values2 = self.values['last_values2']
        self.sps_edit.setText(str(self.samples_per_sequence))
        self.sr_edit.setText(str(self.sequence_reps))
        self.shifts_edit.setText(str(self.shifts))
        self.length_edit.setCurrentText(str(self.length))
        self.last_values1.setValue(self.last_n_values1)
        self.last_values2.setValue(self.last_n_values2)
        self.refresh_config.clicked.connect(self.refresh_configuration)
        self.xData = np.arange(1, self.shifts * self.sequence_reps * self.samples_per_sequence + 1) / 5 * 10 ** 9
        self.xData2 = np.arange(0, 1280) / 5 * 10 ** 9

        # Configuring both plot-widgets
        pen = mkPen(color=(0, 0, 0), width=1)

        self.graph1.setBackground('w')
        self.graph1.setAxisItems(axisItems={'bottom': CustomAxis(orientation='bottom'),
                                            'left': CustomAxis(orientation='left')})
        self.line1 = self.graph1.plot(self.xData, np.zeros(len(self.xData)), pen=pen)

        self.graph2.setBackground('w')
        self.graph2.setAxisItems(axisItems={'bottom': CustomAxis(orientation='bottom'),
                                            'left': CustomAxis(orientation='left')})
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
        self.receiver = Receiver(self.shifts, self.sequence_reps, self.samples_per_sequence,
                                 self.length, self.port, self.ip)
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
        self.second_data = SecondData(self.samples_per_sequence, self.shifts, self.sequence_reps, self.length,
                                      self.last_n_values1, self.last_n_values2)
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

        # Refreshing how many last values are displayed
        self.last_values1.valueChanged.connect(self.last_values_changer1)
        self.last_values2.valueChanged.connect(self.last_values_changer2)

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

        # Setting up the smoother window
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.__mousePos = None
        self.close_button.clicked.connect(self.close)
        self.maximize_button.clicked.connect(self.toggle_maximized)
        self.minimize_button.clicked.connect(self.showMinimized)
        with open('resources\pams_style.qss', 'r') as f:
            self.setStyleSheet(f.read())

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
            self.graph1.setTitle('Raw data')
            self.graph1.getAxis('bottom').setLabel('Time', units='s')
            self.graph1.getAxis('left').setLabel('Voltage', units='v')
        if box == 'IRF':
            self.request1 = 2
            self.graph1.setTitle('IRF data')
            self.graph1.getAxis('bottom').setLabel('Time', units='ms')
            self.graph1.getAxis('left').setLabel('Voltage', units='v')
        if box == 'Distance':
            self.request1 = 3
            self.graph1.setTitle('Distance')
            self.graph1.getAxis('bottom').setLabel('Time', units='s')
        self.data_connector()
        # self.xdata_refresher()
        self.plot_connector1()
        self.stop_plot1.setEnabled(True)

    def plot_starter2(self):
        self.start_plot2.setEnabled(False)
        box = self.QComboBox_2.currentText()
        if box == 'Raw data':
            self.request2 = 1
            self.graph2.setTitle('Raw Data')
            self.graph2.getAxis('left').setLabel('Voltage')
            self.graph2.getAxis('bottom').setLabel('Time', units='s')
            self.graph2.getAxis('left').setLabel('Voltage', units='v')
        if box == 'IRF':
            self.request2 = 2
            self.graph2.setTitle('IRF Data')
            self.graph2.getAxis('bottom').setLabel('Time', units='ms')
            self.graph2.getAxis('left').setLabel('Voltage', units='v')
        if box == 'Distance':
            self.request2 = 3
            self.graph2.setTitle('Distance')
            self.graph2.getAxis('bottom').setLabel('Time', units='s')
            self.graph2.getAxis('left').setLabel('Distance', units='m')
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

    def last_values_changer1(self, value):
        self.second_data.last_values1 = value

    def last_values_changer2(self, value):
        self.second_data.last_values2 = value

    # Maybe double connections!!:
    def data_connector(self):
        if self.request1 <= 1 and self.request2 <= 1:
            unconnect(self.receiver.packageReady, self.second_data.irf)
        else:
            unconnect(self.receiver.packageReady, self.second_data.irf)
            self.receiver.packageReady.connect(self.second_data.irf)
        if self.request1 == 3 or self.request2 == 3:
            self.second_data.t0 = time.time()
            self.second_data.time_stamps, self.second_data.maxima = list(), list()
            if self.refresh_x1.isChecked():
                self.second_data.refresh_x1 = True
                self.last_values1.setEnabled(True)
            else:
                self.second_data.refresh_x1 = False
                self.last_values1.setEnabled(False)
            if self.refresh_x2.isChecked():
                self.second_data.refresh_x2 = True
                self.last_values2.setEnabled(True)
            else:
                self.second_data.refresh_x2 = False
                self.last_values2.setEnabled(False)
            unconnect(self.second_data.package2Ready, self.second_data.distance)
            self.second_data.package2Ready.connect(self.second_data.distance)
        else:
            unconnect(self.second_data.package2Ready, self.second_data.distance)
        if self.request1 == 4 or self.request2 == 4:
            unconnect(self.second_data.package2Ready, self.second_data.option_3)
            self.second_data.package2Ready.connect(self.second_data.option_3)
        else:
            unconnect(self.second_data.package2Ready, self.second_data.option_3)
        if self.request1 == 5 or self.request2 == 5:
            unconnect(self.second_data.package2Ready, self.second_data.option_4)
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
        self.receiver = Receiver(self.shifts, self.sequence_reps, self.samples_per_sequence, self.length,
                                 self.port, self.ip)
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
        self.length = int(self.length_edit.currentText())
        with open('configurations.bin', 'wb') as f:
            pickle.dump(change_dict(self.values, self.shifts, self.samples_per_sequence, self.sequence_reps,
                                    self.length, self.last_n_values1, self.last_n_values2), f)
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

    def mousePressEvent(self, event):
        self.__mousePos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.__mousePos:
            delta = event.globalPos() - self.__mousePos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.__mousePos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.__mousePos = None

    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()



def main():
    app = QApplication(sys.argv)
    window = UI()
    window.show()
    app.exec()


if __name__ == '__main__':
    main()
