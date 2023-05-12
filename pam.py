import socket
import pickle
import sys

import numpy as np
import time
from math import ceil
import psutil

from PyQt5.QtCore import *
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QMainWindow, QWidget, QApplication, QSizePolicy, QSplashScreen, QHBoxLayout, QPushButton, \
    QBoxLayout
from PyQt5.QtGui import QIcon, QPixmap, QColor
from PyQt5 import uic
from PyQt5.QtMultimedia import QAudio

from pyqtgraph import mkPen, AxisItem, PlotWidget, InfiniteLine, ViewBox
from collections import deque
import definitions
from pams_functions import Handler, averager, change_dict, exact_polynom_interp_max, unconnect, zero_padding


resource_path = "C:/Users/dasa/PycharmProjects/MatlabData/resources/"


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
        except OSError as err:
            if err.errno == 10048:
                self.st_connect_failed.emit('os_exists')
            else:
                self.st_connect_failed.emit('os_unknown')
        except TypeError:
            self.st_connect_failed.emit('type')

    def run(self):
        handler = Handler(self.sock, shifts=ceil(self.shifts/80)*80, sequence_reps=self.s_reps,
                          samples_per_sequence=self.sps)
        g = handler.assembler_2()
        t0 = time.time()
        while not self.stop_receive:
            r = next(g)
            if not r:
                self.packageLost.emit()
            else:
                time_stamp = round(time.time() - t0, 10)
                yData = np.frombuffer(r, dtype=np.int32)[:self.set_len] * 8.192 / pow(2, 18)
                # yData = np.frombuffer(r, dtype=np.int32) * 8.192 / pow(2, 18)
                # xData = np.arange(0, self.set_len*1000/4.9e+06, 1000/4.9e+06)
                xData = np.linspace(0, self.mes_len/self.sps*2e-10*self.set_len, self.set_len)
                self.packageReady.emit((xData, yData, time_stamp))
        self.sock.close()

    def stop(self):
        self.stop_receive = True
        # self.quit()
        # self.wait()


class SecondData(QObject):
    package2Ready = pyqtSignal(tuple)
    package3aReady = pyqtSignal(tuple)
    package3bReady = pyqtSignal(tuple)
    package4Ready = pyqtSignal(tuple)

    def __init__(self, samples_per_sequence, shifts, sequence_reps, length, last_n_values_plot1, last_n_values_plot2,
                 cable_length_constant):
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
        self.cable_constant = cable_length_constant

    def irf(self, data):
        yData = averager(data[1], self.shifts, self.sps, self.sr)
        yData = yData - np.average(yData[len(yData)-100:])
        xData = np.arange(1, self.shifts+1) / 5e+09
        # yData = np.angle(fft(yData), deg=True)
        # xData, yData = zero_padding(xData, yData, 2.4e+09, 16080)
        # print(find_peaks(data[1], height=0.05))
        # self.package2Ready.emit((data[0], data[1]))
        self.package2Ready.emit((xData, yData, data[2]))

    def distance(self, data):
        self.time_stamps.append(data[2])
        data = zero_padding(data[0], data[1], 2.5e+09, 2**5*self.shifts)
        # print(find_peaks(data[1]))
        # print(np.argsort(data[1][:5000])[-3:])
        # self.maxima.append(data[0][data[1].argmax()])
        # self.maxima.append(polynom_interp_max(data[0][:int(len(data[0])/2)], data[1][:int(len(data[0])/2)], 50))
        self.maxima.append(exact_polynom_interp_max(data[0], np.absolute(data[1]), True,
                                                    self.cable_constant))
        if self.refresh_x1:
            self.package3aReady.emit((self.time_stamps[-self.last_values1:], self.maxima[-self.last_values1:]))
        else:
            self.package3aReady.emit((list(self.time_stamps), list(self.maxima)))
        if self.refresh_x2:
            self.package3bReady.emit((self.time_stamps[-self.last_values2:], self.maxima[-self.last_values2:]))
        else:
            self.package3bReady.emit((list(self.time_stamps), list(self.maxima)))

    def irf_interp(self, data):
        data = zero_padding(data[0], data[1], 2.5e+09, 2**5*self.shifts)
        yData = data[1]
        xData = data[0]
        exact_max = exact_polynom_interp_max(data[0], np.absolute(data[1]), False)
        # self.package4Ready.emit((xData, 20*np.log10(np.absolute(yData)), exact_max))
        self.package4Ready.emit((xData, yData, exact_max))

    def option_4(self, data):
        pass


class UI(QMainWindow):
    def __init__(self):
        super(UI, self).__init__()

        # Load the ui file
        uic.loadUi('resources/Mainwindow.ui', self)

        # Loading the values and getting the parameters for data interpreting
        with open('resources/configurations.bin', 'rb') as f:
            self.values = pickle.load(f)
        if True:
            self.samples_per_sequence = self.values['samples_per_sequence']
            self.sequence_reps = self.values['sequence_reps']
            self.shifts = self.values['shifts']
            self.length = self.values['length']
            self.last_n_values1 = self.values['last_values1']
            self.last_n_values2 = self.values['last_values2']
            self.cable_const = self.values['cable_length_constant']
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
        if True:
            pen = mkPen(color=(0, 0, 0), width=1)

            self.graph1.setBackground('w')
            self.graph1.setAxisItems(axisItems={'bottom': CustomAxis(orientation='bottom'),
                                                'left': CustomAxis(orientation='left')})
            self.line1 = self.graph1.plot(self.xData, np.zeros(len(self.xData)), pen=pen)
            self.graph1.enableAutoRange(axis=ViewBox.XYAxes)
            self.graph1.hideButtons()
            print(type(self.graph1))

            self.graph2.setBackground('w')
            self.graph2.setAxisItems(axisItems={'bottom': CustomAxis(orientation='bottom'),
                                                'left': CustomAxis(orientation='left')})
            self.line2 = self.graph2.plot(self.xData2, np.zeros(len(self.xData2)), pen=pen)
            self.graph2.enableAutoRange(axis=ViewBox.XYAxes)
            self.graph2.hideButtons()

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
        if True:
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
        if True:
            self.second_thread = QThread()
            self.second_data = SecondData(self.samples_per_sequence, self.shifts, self.sequence_reps, self.length,
                                          self.last_n_values1, self.last_n_values2, self.cable_const)
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

        # Setting up the distance calibration:
        self.distance_const.setDecimals(5)
        self.distance_const.setValue(self.cable_const)
        self.tare_distance.clicked.connect(self.cable_constant_refresher)

        # Setting up the plot timer:
        self.make_plot_timers = True
        if self.make_plot_timers:
            self.timer = QTimer()
            self.timer.timeout.connect(self.plot1_timer)
            self.timer.timeout.connect(self.plot2_timer)
            self.timer.timeout.connect(self.receiver_timer)
            self.timer.timeout.connect(self.data_rate_timer)
            self.timer.start(500)
            self.counter1 = 0
            self.counter2 = 0
            self.counter_lost = 0
            self.bytes_received = 0

        self.request1 = 0
        self.request2 = 0

        # Setting up the qss style sheet
        with open('resources/pams_style.qss', 'r') as f:
            self.setStyleSheet(f.read())

        # Setting up the three window buttons and hiding the frame
        self.make_own_window_buttons = True
        if self.make_own_window_buttons:
            self.setWindowFlags(Qt.FramelessWindowHint)
            self.maximize_button.clicked.connect(self.maximize_button_clicked)
            self.med_ic = QIcon('resources/medimize_button.svg')
            self.med_ic_white = QIcon('resources/medimize_button_white.svg')
            self.max_ic = QIcon('resources/maximize_button.svg')
            self.max_ic_white = QIcon('resources/maximize_button_white.svg')
            self.min_ic = QIcon('resources/minimize_button.svg')
            self.min_ic_white = QIcon('resources/minimize_button_white.svg')
            self.clos_ic = QIcon('resources/closing_button.svg')
            self.clos_ic_white = QIcon('resources/closing_button_white.svg')
            self.maximize_button.enterEvent = self.maximize_button_hover
            self.maximize_button.leaveEvent = self.maximize_button_exit
            self.minimize_button.enterEvent = self.minimize_button_hover
            self.minimize_button.leaveEvent = self.minimize_button_exit
            self.close_button.enterEvent = self.close_button_hover
            self.close_button.leaveEvent = self.close_button_exit

        # Setting up the animations for QTabWidget
        self.animate_tab_buttons = True
        if self.animate_tab_buttons:
            self.tabWidget.tabBar().installEventFilter(self)
            self.tabBar = self.tabWidget.tabBar()

            # First rectangle:
            self.tabRect1 = self.tabBar.tabRect(0)
            self.rect1 = QRect(self.tabRect1.x(), self.tabRect1.y()+self.tabRect1.height(), self.tabRect1.width(), 5)
            self.hover_bar1 = QWidget(self.tabBar)
            self.hover_bar1.setStyleSheet('background-color:  #8dae10')
            self.hover_bar1.setGeometry(self.rect1)

            # First animation:
            self.tab_animation1 = QPropertyAnimation(self.hover_bar1, b"pos")
            self.tab_animation1.setDuration(100)
            self.tab_animation1.setStartValue(QPoint(self.tabRect1.x(), self.tabRect1.height()))
            self.tab_animation1.setEndValue(QPoint(self.tabRect1.x(), self.tabRect1.height() - 5))

            # First antimation:
            self.tab_antimation1 = QPropertyAnimation(self.hover_bar1, b"pos")
            self.tab_antimation1.setDuration(0)
            self.tab_antimation1.setStartValue(QPoint(self.tabRect1.x(), self.tabRect1.height() - 5))
            self.tab_antimation1.setEndValue(QPoint(self.tabRect1.x(), self.tabRect1.height()))

            # Second rectangle:
            self.tabRect2 = self.tabBar.tabRect(1)
            self.rect2 = QRect(self.tabRect2.x(), self.tabRect2.y()+self.tabRect2.height(), self.tabRect2.width(), 5)
            self.hover_bar2 = QWidget(self.tabBar)
            self.hover_bar2.setStyleSheet('background-color:  #8dae10')
            self.hover_bar2.setGeometry(self.rect2)

            # Second animation
            self.tab_animation2 = QPropertyAnimation(self.hover_bar2, b"pos")
            self.tab_animation2.setDuration(100)
            self.tab_animation2.setStartValue(QPoint(self.tabRect2.x(), self.tabRect2.height()))
            self.tab_animation2.setEndValue(QPoint(self.tabRect2.x(), self.tabRect2.height() - 5))

            # Second antimation:
            self.tab_antimation2 = QPropertyAnimation(self.hover_bar2, b"pos")
            self.tab_antimation2.setDuration(0)
            self.tab_antimation2.setStartValue(QPoint(self.tabRect2.x(), self.tabRect2.height() - 5))
            self.tab_antimation2.setEndValue(QPoint(self.tabRect2.x(), self.tabRect2.height()))
            self.tabIndex = -1

            # Third rectangle:
            self.tabRect3 = self.tabBar.tabRect(2)
            self.rect3 = QRect(self.tabRect3.x(), self.tabRect3.y()+self.tabRect3.height(), self.tabRect3.width(), 5)
            self.hover_bar3 = QWidget(self.tabBar)
            self.hover_bar3.setStyleSheet('background-color:  #8dae10')
            self.hover_bar3.setGeometry(self.rect3)

            # Third animation
            self.tab_animation3 = QPropertyAnimation(self.hover_bar3, b"pos")
            self.tab_animation3.setDuration(100)
            self.tab_animation3.setStartValue(QPoint(self.tabRect3.x(), self.tabRect3.height()))
            self.tab_animation3.setEndValue(QPoint(self.tabRect3.x(), self.tabRect3.height() - 5))

            # Second antimation:
            self.tab_antimation3 = QPropertyAnimation(self.hover_bar3, b"pos")
            self.tab_antimation3.setDuration(0)
            self.tab_antimation3.setStartValue(QPoint(self.tabRect3.x(), self.tabRect3.height() - 5))
            self.tab_antimation3.setEndValue(QPoint(self.tabRect3.x(), self.tabRect3.height()))
            self.tabIndex = -1

        # Set up the auto-range checkboxes and home buttons:
        if True:
            self.auto_x1.stateChanged.connect(self.auto_x_changer1)
            self.auto_y1.stateChanged.connect(self.auto_y_changer1)
            self.auto_x2.stateChanged.connect(self.auto_x_changer2)
            self.auto_y2.stateChanged.connect(self.auto_y_changer2)
            self.plot_home1.clicked.connect(self.auto_graph1)
            self.plot_home2.clicked.connect(self.auto_graph2)

        # Add the RUB- and EST-logo
        if True:
            self.rub_logo = QSvgWidget('resources/Logo_RUB_weiss_rgb.svg')
            self.rub_logo.setMaximumHeight(40)
            self.rub_logo.setMaximumWidth(150)
            self.horizontalLayout_9.insertWidget(3, self.rub_logo)
            self.est_logo = QSvgWidget('resources/est_logo.svg')
            # self.est_logo.setMaximumHeight(40)
            # self.est_logo.setMaximumWidth(92)
            # self.horizontalLayout_9.insertWidget(3, self.est_logo)
            self.est_logo.setParent(self)
            self.est_logo.setGeometry(QRect(570, 5, 69, 30))
            # self.est_animation = QPropertyAnimation(self.est_logo, b"pos")
            # self.est_animation.setStartValue(QPoint(self.est_logo.x(), self.est_logo.y()))
            # self.est_animation.setEndValue(QPoint(self.est_logo.x(), self.est_logo.y()-10))
            # self.est_animation.setDuration(0)
            # self.est_animation.start()

        # Setting up the vertical lines:
        self.make_infinite_lines = True
        if self.make_infinite_lines:
            self.inf_line1 = InfiniteLine(angle=90, pen=mkPen(color=(255, 0, 0), width=1))
            self.inf_line2 = InfiniteLine(angle=90, pen=mkPen(color=(255, 0, 0), width=1))
            self.vert_line1.stateChanged.connect(self.inf_line1_refresher)
            self.vert_line2.stateChanged.connect(self.inf_line2_refresher)

        self.pixmap = QPixmap('resources/est_logo.svg')

    def plot(self, data):
        if self.log_y1.isChecked():
            self.line1.setData(data[0], np.log10(np.absolute(data[1])))
        else:
            self.line1.setData(data[0], data[1])
        if self.vert_line1.isChecked():
            self.inf_line1.setPos(data[2])
        self.counter1 += 1

    def plot_2(self, data):
        if self.log_y2.isChecked():
            self.line2.setData(data[0], np.log10(np.absolute(data[1])))
        else:
            self.line2.setData(data[0], data[1])
        if self.vert_line2.isChecked():
            self.inf_line2.setPos(data[2])
        self.counter2 += 1

    def plot_starter1(self):
        self.start_plot1.setEnabled(False)
        box = self.QComboBox_1.currentText()
        self.plot1_label.setText('Plot 1: ' + box)
        match box:
            case 'Raw data':
                self.request1 = 1
                self.graph1.setTitle('Raw data')
                self.graph1.getAxis('bottom').setLabel('Time', units='s')
                self.graph1.getAxis('left').setLabel('Voltage', units='v')
                self.vert_line1.setEnabled(False)
                self.vert_line1.setChecked(False)
                self.log_y1.setEnabled(False)
                self.log_y1.setChecked(False)
            case 'IRF':
                self.request1 = 2
                self.graph1.setTitle('IRF data')
                self.graph1.getAxis('bottom').setLabel('Time', units='ms')
                self.graph1.getAxis('left').setLabel('Voltage', units='v')
                self.vert_line1.setEnabled(False)
                self.vert_line1.setChecked(False)
                self.log_y1.setEnabled(False)
                self.log_y1.setChecked(False)
            case 'Distance':
                self.request1 = 3
                self.graph1.setTitle('Distance')
                self.graph1.getAxis('bottom').setLabel('Time', units='s')
                self.graph1.getAxis('left').setLabel('Distance', units='m')
                self.auto_x1.setChecked(True)
                self.auto_y1.setChecked(True)
                self.vert_line1.setEnabled(False)
                self.vert_line1.setChecked(False)
                self.log_y1.setEnabled(False)
                self.log_y1.setChecked(False)
            case 'IRF Interpolated':
                self.request1 = 4
                self.graph1.getAxis('bottom').setLabel('Time', units='s')
                self.graph1.getAxis('left').setLabel('Voltage', units='v')
                self.vert_line1.setEnabled(True)
                self.log_y1.setEnabled(True)
        self.data_connector()
        self.plot_connector1()
        self.stop_plot1.setEnabled(True)

    def plot_starter2(self):
        self.start_plot2.setEnabled(False)
        box = self.QComboBox_2.currentText()
        self.plot2_label.setText('Plot 2: ' + box)
        match box:
            case 'Raw data':
                self.request2 = 1
                self.graph2.setTitle('Raw Data')
                self.graph2.getAxis('left').setLabel('Voltage')
                self.graph2.getAxis('bottom').setLabel('Time', units='s')
                self.graph2.getAxis('left').setLabel('Voltage', units='v')
                self.vert_line2.setEnabled(False)
                self.vert_line2.setChecked(False)
                self.log_y2.setEnabled(False)
                self.log_y2.setChecked(False)
            case 'IRF':
                self.request2 = 2
                self.graph2.setTitle('IRF Data')
                self.graph2.getAxis('bottom').setLabel('Time', units='ms')
                self.graph2.getAxis('left').setLabel('Voltage', units='v')
                self.vert_line2.setEnabled(False)
                self.vert_line2.setChecked(False)
                self.log_y2.setEnabled(False)
                self.log_y2.setChecked(False)
            case 'Distance':
                self.request2 = 3
                self.graph2.setTitle('Distance')
                self.graph2.getAxis('bottom').setLabel('Time', units='s')
                self.graph2.getAxis('left').setLabel('Distance', units='m')
                self.auto_x2.setChecked(True)
                self.auto_y2.setChecked(True)
                self.vert_line2.setEnabled(False)
                self.vert_line2.setChecked(False)
                self.log_y2.setEnabled(False)
                self.log_y2.setChecked(False)
            case 'IRF Interpolated':
                self.request2 = 4
                self.graph2.getAxis('bottom').setLabel('Time', units='s')
                self.graph2.getAxis('left').setLabel('Voltage', units='v')
                self.vert_line2.setEnabled(True)
                self.log_y2.setEnabled(True)
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
        match self.request1:
            case 1:
                self.receiver.packageReady.connect(self.plot)
            case 2:
                self.second_data.package2Ready.connect(self.plot)
            case 3:
                self.second_data.package3aReady.connect(self.plot)
            case 4:
                self.second_data.package4Ready.connect(self.plot)

    def plot_connector2(self):
        match self.request2:
            case 1:
                self.receiver.packageReady.connect(self.plot_2)
            case 2:
                self.second_data.package2Ready.connect(self.plot_2)
            case 3:
                self.second_data.package3bReady.connect(self.plot_2)
            case 4:
                self.second_data.package4Ready.connect(self.plot_2)

    def plot_disconnector1(self):
        unconnect(self.receiver.packageReady, self.plot)
        unconnect(self.second_data.package2Ready, self.plot)
        unconnect(self.second_data.package3aReady, self.plot)
        unconnect(self.second_data.package4Ready, self.plot)

    def plot_disconnector2(self):
        unconnect(self.receiver.packageReady, self.plot_2)
        unconnect(self.second_data.package2Ready, self.plot_2)
        unconnect(self.second_data.package3bReady, self.plot_2)
        unconnect(self.second_data.package4Ready, self.plot_2)

    def running_refresher1(self):
        if self.stop_plot1.isEnabled():
            self.plot_breaker1()
            self.plot_starter1()
        if self.QComboBox_1.currentText() == 'Distance':
            self.refresh_x1.setEnabled(True)
            self.tare_distance.setEnabled(True)                     # <- I might wanna put these in an extra function
            self.distance_const.setEnabled(True)
        else:
            self.refresh_x1.setEnabled(False)
            if self.QComboBox_2.currentText() != 'Distance':        # <-
                self.tare_distance.setEnabled(False)
                self.distance_const.setEnabled(False)

    def running_refresher2(self):
        if self.stop_plot2.isEnabled():
            self.plot_breaker2()
            self.plot_starter2()
        if self.QComboBox_2.currentText() == 'Distance':
            self.refresh_x2.setEnabled(True)
            self.tare_distance.setEnabled(True)                     # <-
            self.distance_const.setEnabled(True)
        else:
            self.refresh_x2.setEnabled(False)
            if self.QComboBox_1.currentText() != 'Distance':        # <-
                self.tare_distance.setEnabled(False)
                self.distance_const.setEnabled(False)

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

    def auto_x_changer1(self):
        if self.auto_x1.isChecked():
            self.graph1.enableAutoRange(axis=ViewBox.XAxis)
        else:
            self.graph1.disableAutoRange(axis=ViewBox.XAxis)

    def auto_x_changer2(self):
        if self.auto_x2.isChecked():
            self.graph2.enableAutoRange(axis=ViewBox.XAxis)
        else:
            self.graph2.disableAutoRange(axis=ViewBox.XAxis)

    def auto_y_changer1(self):
        if self.auto_y1.isChecked():
            self.graph1.enableAutoRange(axis=ViewBox.YAxis)
        else:
            self.graph1.disableAutoRange(axis=ViewBox.YAxis)

    def auto_y_changer2(self):
        if self.auto_y2.isChecked():
            self.graph2.enableAutoRange(axis=ViewBox.YAxis)
        else:
            self.graph2.disableAutoRange(axis=ViewBox.YAxis)

    def auto_graph1(self):
        self.graph1.autoRange(padding=0.04)

    def auto_graph2(self):
        self.graph2.autoRange(padding=0.04)

    def inf_line1_refresher(self, state):
        if state == 2:
            self.graph1.addItem(self.inf_line1)
        else:
            self.graph1.removeItem(self.inf_line1)

    def inf_line2_refresher(self, state):
        if state == 2:
            self.graph2.addItem(self.inf_line2)
        else:
            self.graph2.removeItem(self.inf_line2)

    def cable_constant_refresher(self):
        self.cable_const = self.second_data.cable_constant = np.average(np.array(self.second_data.maxima)[-20:])+self.cable_const
        self.distance_const.setValue(self.cable_const)

    def data_connector(self):
        if self.request1 <= 1 and self.request2 <= 1:
            unconnect(self.receiver.packageReady, self.second_data.irf)
        else:
            unconnect(self.receiver.packageReady, self.second_data.irf)
            self.receiver.packageReady.connect(self.second_data.irf)
        if self.request1 == 3 or self.request2 == 3:
            self.second_data.t0 = time.time()
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
            unconnect(self.second_data.package2Ready, self.second_data.irf_interp)
            self.second_data.package2Ready.connect(self.second_data.irf_interp)
        else:
            unconnect(self.second_data.package2Ready, self.second_data.irf_interp)
        if self.request1 == 5 or self.request2 == 5:
            unconnect(self.second_data.package2Ready, self.second_data.option_4)
            self.second_data.package2Ready.connect(self.second_data.option_4)
        else:
            unconnect(self.second_data.package2Ready, self.second_data.option_4)

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
        # with open('resources/configurations.bin', 'wb') as f:
        #     pickle.dump(change_dict(self.values, self.shifts, self.samples_per_sequence, self.sequence_reps,
        #                             self.length, self.last_n_values1, self.last_n_values2), f)
        self.second_data.sps = self.samples_per_sequence
        self.second_data.sr = self.sequence_reps
        self.second_data.shifts = self.shifts
        self.reconnect_receiver()
        if self.stop_plot1.isEnabled():
            self.plot_starter1()
        if self.stop_plot2.isEnabled():
            self.plot_starter2()

    def rec_connecting(self):
        self.con_status.setStyleSheet('color: black')
        self.con_status.setText('Connecting...')

    def rec_connected(self):
        self.con_status.setStyleSheet('color: green')
        self.con_status.setText('Connected.')
        self.label_11.setText('Not receiving')
        self.start_receive.setEnabled(True)

    def rec_failed(self, error):
        self.con_status.setStyleSheet('color: red')
        self.con_status.setText('Connection failed: Resetting receiver.')
        self.reconnect_receiver()
        if error == 'os_exists':
            self.con_status.setText('Connection failed: Socket already in use.')
        if error == 'os_unkown':
            self.con_status.setText('Connection failed: try again later!')
        if error == 'type':
            self.con_status.setText('Connection failed: Check inputs and try again.')
        self.start_receive.setEnabled(False)
        self.start_plot1.setEnabled(False)
        self.label_11.setText('receiver not bound')

    def lost_counter(self):
        self.counter_lost += 1

    def plot1_timer(self):
        self.label_12.setText(f'Plot 1: {self.counter1*2} P/s')
        self.counter1 = 0

    def plot2_timer(self):
        self.label_22.setText(f'Plot 2: {self.counter2*2} P/s')
        self.counter2 = 0

    def receiver_timer(self):
        self.label_21.setText(f'Lost: {self.counter_lost*2} p/s')
        self.counter_lost = 0

    def data_rate_timer(self):
        byties = psutil.net_io_counters(pernic=True)['Ethernet 2'][1]
        self.ethernet_rate.setText(f'Ethernet 2: {round((byties - self.bytes_received) * 8e-06 * 2, 1)} MBit/s')
        self.bytes_received = byties

    def close_button_hover(self, event):
        self.close_button.setIcon(self.clos_ic_white)

    def close_button_exit(self, event):
        self.close_button.setIcon(self.clos_ic)

    def maximize_button_hover(self, event):
        if self.isFullScreen():
            self.maximize_button.setIcon(self.med_ic_white)
        else:
            self.maximize_button.setIcon(self.max_ic_white)

    def maximize_button_exit(self, event):
        if self.isFullScreen():
            self.maximize_button.setIcon(self.med_ic)
        else:
            self.maximize_button.setIcon(self.max_ic)

    def minimize_button_hover(self, event):
        self.minimize_button.setIcon(self.min_ic_white)

    def minimize_button_exit(self, event):
        self.minimize_button.setIcon(self.min_ic)

    def maximize_button_clicked(self):
        if self.isFullScreen():
            self.showNormal()
            self.maximize_button.setIcon(self.max_ic)
        else:
            self.maximize_button.setIcon(self.med_ic)
            self.showFullScreen()

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

    def eventFilter(self, object, event):
        if object == self.tabWidget.tabBar():
            match event.type():
                case  10 | 129:
                    tab_index = object.tabAt(event.pos())
                    if tab_index not in [self.tabIndex, self.tabWidget.currentIndex()]:
                        self.animation_starter(tab_index)
                    if self.tabIndex not in [self.tabWidget.currentIndex(), tab_index]:
                        self.antimation_starter(self.tabIndex)
                    self.tabIndex = tab_index
                    return True
                case 11 | 2:
                    if self.tabIndex != self.tabWidget.currentIndex():
                        self.antimation_starter(self.tabIndex)
                        self.tabIndex = -1
        return False

    def animation_starter(self, index):
        match index:
            case 0:
                self.tab_animation1.start()
            case 1:
                self.tab_animation2.start()
            case 2:
                self.tab_animation3.start()

    def antimation_starter(self, index):
        match index:
            case 0:
                self.tab_antimation1.start()
            case 1:
                self.tab_antimation2.start()
            case 2:
                self.tab_antimation3.start()

    def close(self):
        with open('resources/configurations.bin', 'wb') as f:
            pickle.dump(change_dict(self.values, self.shifts, self.samples_per_sequence, self.sequence_reps,
                                    self.length, self.last_n_values1, self.last_n_values2, self.cable_const), f)
        super().close()


'''
class SplashScreen(QSplashScreen):
    def __init__(self):
        super().__init__()
        self.widget = QWidget()
        self.widget.resize(300, 300)
        self.widget.setStyleSheet('background: green')
        self.layout1 = QHBoxLayout()
        self.layout1.addWidget(self.widget)
        self.setLayout(self.layout1)
        pixmap = QPixmap(self.widget())
        self.setPixmap(pixmap)
'''


def main():
    app = QApplication(sys.argv)
    pixmap = QPixmap('resources/splash_screen.png')
    splashscreen = QSplashScreen(pixmap)
    splashscreen.show()
    window = UI()
    window.show()
    splashscreen.finish(window)
    app.exec()


if __name__ == '__main__':
    main()
