import os
import socket
import pickle
import sys

import numpy as np
import time
from math import ceil
import psutil
from math import trunc
from scipy.fft import fft, ifft
from scipy.constants import speed_of_light

from PyQt5.QtCore import *
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QMainWindow, QWidget, QApplication, QSizePolicy, QSplashScreen, QHBoxLayout, QPushButton, \
    QBoxLayout, QCheckBox, QLabel, QLineEdit, QComboBox, QSpinBox
from PyQt5.QtGui import QIcon, QPixmap, QColor, QFontDatabase, QFont
from PyQt5 import uic

from pyqtgraph import mkPen, PlotWidget, InfiniteLine, ViewBox
from collections import deque
import definitions
from pams_functions import Handler, averager, change_dict, exact_polynom_interp_max, unconnect, zero_padding, \
    CustomAxis, compare_sender
from Audioslider import SineAudioEmitter


resource_path = "C:/Users/dasa/PycharmProjects/MatlabData/resources/"


class Receiver(QThread):
    measurement_ready = pyqtSignal(tuple)
    irf_measurement_ready = pyqtSignal(tuple)
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

        self.t0 = 0

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
        self.t0 = time.time()
        while not self.stop_receive:
            r = next(g)
            if not r:
                self.packageLost.emit()
            else:
                time_stamp = round(time.time() - self.t0, 10)
                y_mes_data = np.frombuffer(r, dtype=np.int32)[:self.set_len] * 8.192 / pow(2, 18)
                x_mes_data = np.linspace(0, self.mes_len / self.sps * 2e-10 * self.set_len, self.set_len)
                self.measurement_ready.emit((x_mes_data, y_mes_data, time_stamp))
                y_irf_data = averager(y_mes_data, self.shifts, self.sps, self.s_reps)
                y_irf_data -= np.average(y_irf_data[-100:])
                x_irf_data = np.arange(1, self.shifts + 1) / 5e+09
                self.irf_measurement_ready.emit((x_irf_data, y_irf_data, time_stamp))
        self.sock.close()

    def stop(self):
        self.stop_receive = True
        # self.quit()
        # self.wait()


class SecondData(QObject):
    distance_ready = pyqtSignal(tuple)
    irf_interp_ready = pyqtSignal(tuple)
    unconnect_receiver_from_y_ref = pyqtSignal()

    def __init__(self, samples_per_sequence, shifts, sequence_reps, length, cable_length_constant):
        QObject.__init__(self)
        self.sps = samples_per_sequence
        self.shifts = shifts
        self.sr = sequence_reps
        self.mes_len = length
        self.maxima, self.time_stamps = deque(maxlen=1000), deque(maxlen=1000)
        self.cable_constant = cable_length_constant
        self.YRefPos = np.array([])

    def distance(self, data):
        t = data[2]
        data = zero_padding(data[0], data[1], 2.5e+09, 2**5*self.shifts)
        max = exact_polynom_interp_max(data[0], np.absolute(data[1]), True, self.cable_constant)
        self.distance_ready.emit((t, max))

    def irf_interp(self, data):
        data = zero_padding(data[0], data[1], 2.5e+09, 2**5*self.shifts)
        exact_max = exact_polynom_interp_max(data[0], np.absolute(data[1]), False)
        self.irf_interp_ready.emit((data[0], data[1], exact_max))

    def irf_interp_norm(self, data):
        data = zero_padding(data[0], data[1], 2.5e+09, 2 ** 5 * self.shifts, True, self.YRefPos)
        idx_start = np.absolute(data[0]-1.0e-09).argmin()
        idx_stop = np.absolute(data[0]-12.0e-09).argmin()
        exact_max = exact_polynom_interp_max(data[0], np.absolute(data[1]), False, intervall=slice(idx_start, idx_stop))
        self.irf_interp_ready.emit((data[0], data[1], exact_max))

    def distance_norm(self, data):
        t = data[2]
        data = zero_padding(data[0], data[1], 2.5e+09, 2 ** 5 * self.shifts, True, self.YRefPos)
        idx_start = np.absolute(data[0]-1.0e-09).argmin()
        idx_stop = np.absolute(data[0]-12.0e-09).argmin()
        exact_max = exact_polynom_interp_max(data[0], np.absolute(data[1]), True, intervall=slice(idx_start, idx_stop))
        self.distance_ready.emit((t, exact_max))

    def return_functions(self):
        return self.distance, self.irf_interp,  self.irf_interp_norm, self.distance_norm

    def refresh_y_ref(self, data):
        self.unconnect_receiver_from_y_ref.emit()
        yData = data[1]
        yData[150:161] = np.linspace(yData[150], 0, 11)
        yData[161:] = 0
        Ly = len(yData)
        YRefTemp = fft(yData, Ly) / Ly
        self.YRefPos = YRefTemp[0:trunc(Ly / 2) + 1]


class UI(QMainWindow):
    distance_ready = pyqtSignal(tuple)

    def __init__(self):
        super(UI, self).__init__()

        # Load the ui file
        uic.loadUi('resources/Mainwindow.ui', self)

        # Loading the values and getting the parameters for data interpreting
        if True:
            with open('resources/configurations.bin', 'rb') as f:
                try:
                    self.values = pickle.load(f)
                except EOFError:
                    self.values = dict(shifts=0, samples_per_sequence=0, sequence_reps=0, length=0, last_values1=0,
                                       last_values2=0, cable_length_constants=(0, 0))
            print(self.values)
            self.samples_per_sequence = self.values['samples_per_sequence']
            self.sequence_reps = self.values['sequence_reps']
            self.shifts = self.values['shifts']
            self.length = self.values['length']
            self.last_n_values1 = self.values['last_values1']
            self.last_n_values2 = self.values['last_values2']
            cable_constants = self.values['cable_length_constants']
            self.sps_edit.setText(str(self.samples_per_sequence))
            self.sr_edit.setText(str(self.sequence_reps))
            self.shifts_edit.setText(str(self.shifts))
            self.length_edit.setCurrentText(str(self.length))
            self.last_values1.setValue(self.last_n_values1)
            self.last_values2.setValue(self.last_n_values2)
            self.refresh_config.clicked.connect(self.refresh_configuration)
            self.xData = np.arange(1, self.shifts * self.sequence_reps * self.samples_per_sequence + 1) / 5 * 10 ** 9
            self.xData2 = np.arange(0, 1280) / 5 * 10 ** 9
            self.plot_count = 2

        # Configuring both plot-widgets
        if True:
            pen = mkPen(color=(0, 0, 0), width=1)

            self.graph1.setBackground('w')
            self.graph1.setAxisItems(axisItems={'bottom': CustomAxis(orientation='bottom'),
                                                'left': CustomAxis(orientation='left')})
            self.line1 = self.graph1.plot(self.xData, np.zeros(len(self.xData)), pen=pen)
            self.graph1.enableAutoRange(axis=ViewBox.XYAxes)
            self.graph1.hideButtons()

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

        # Setting up the plot slots:
        self.plot_slots = []
        plot_indices = [i for i in range(self.plot_count)]
        for plot in plot_indices:
            slot = lambda data, index=plot: self.plot(data, index)
            self.plot_slots.append(slot)


        # Start and stop Plot 1 and 2
        self.start_plot1.clicked.connect(self.plot_starter_func)
        self.stop_plot1.clicked.connect(self.plot_breaker1)
        self.start_plot2.clicked.connect(self.plot_starter_func)
        self.stop_plot2.clicked.connect(self.plot_breaker2)
        self.start_plot_buttons = [self.start_plot1, self.start_plot2]
        self.stop_plot_buttons = [self.stop_plot1, self.stop_plot2]

        # Setting up the SecondData classes
        if True:
            self.second_data_classes = list()
            for i in range(self.plot_count):
                self.second_data_classes.append([
                    SecondData(self.samples_per_sequence,
                               self.shifts,
                               self.sequence_reps,
                               self.length,
                               cable_constants[i]),
                    QThread()
                    ])
                self.second_data_classes[i][0].moveToThread(self.second_data_classes[i][1])
                self.second_data_classes[i][1].start()

        # Other Connections:
        if True:
            # Refreshing the chosen plot option
            self.x_data_box1.currentTextChanged.connect(self.running_refresher1)
            self.x_data_box2.currentTextChanged.connect(self.running_refresher2)

            # Refreshing the last_values boxes
            self.last_values1.valueChanged.connect(lambda value: setattr(self, 'last_n_values1', value))
            self.last_values2.valueChanged.connect(lambda value: setattr(self, 'last_n_values2', value))

            # Setting up the distance calibration:
            self.distance_const_box_1.setDecimals(5)
            self.distance_const_box_2.setDecimals(5)
            self.distance_const_box_1.setValue(cable_constants[0])
            self.distance_const_box_2.setValue(cable_constants[1])
            self.tare_distance_button_1.clicked.connect(self.cable_constant_refresher)
            self.tare_distance_button_2.clicked.connect(self.cable_constant_refresher)
            self.distance_const_box_1.valueChanged.connect(lambda value: setattr(self.second_data_classes[0][0],
                                                                           'cable_constant', value))
            self.distance_const_box_2.valueChanged.connect(lambda value: setattr(self.second_data_classes[1][0],
                                                                           'cable_constant', value))

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
        self.requests = [0, 0]

        # Setting up the qss style sheet
        f = open('resources/pams_style.qss', 'r')
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
            self.close_button.setStyleSheet('QToolButton:hover {background-color: #FF4D4D}')

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
            self.est_logo.setMaximumHeight(30)
            self.est_logo.setMaximumWidth(92)
            self.horizontalLayout_9.insertWidget(3, self.est_logo)

        # Setting up the vertical lines:
        self.make_infinite_lines = True
        if self.make_infinite_lines:
            self.inf_line1 = InfiniteLine(angle=90, pen=mkPen(color=(255, 0, 0), width=1))
            self.inf_line2 = InfiniteLine(angle=90, pen=mkPen(color=(255, 0, 0), width=1))
            self.inf_line_box1.stateChanged.connect(self.inf_line1_refresher)
            self.inf_line_box2.stateChanged.connect(self.inf_line2_refresher)
            self.inf_lines = [self.inf_line1, self.inf_line2]
            self.inf_line_boxes = [self.inf_line_box1, self.inf_line_box2]

        # Setting up the Audio Emitter:
        if True:
            self.sinSender = SineAudioEmitter(44100, 10, self.frequency_slider.value(), self.volume_slider.value())
            self.start_sound_button.clicked.connect(self.sinSender.start)
            self.frequency_slider.valueChanged.connect(self.sinSender.set_frequency)
            self.volume_slider.valueChanged.connect(self.sinSender.set_volume)
            self.stop_sound_button.clicked.connect(self.sinSender.stop)
            for i in range(self.plot_count):
                self.second_data_classes[i][0].distance_ready.connect(self.set_audio_frequency)


        # Setting up the distance plot calculation
        if True:
            self.distance_values = deque()
            self.distance_time_values = deque()

            # refresh_distance_button
            self.refresh_distance_button.clicked.connect(self.refresh_distance_array)

        # Setting up the animations for QTabWidget
        self.animate_tab_buttons = True
        if self.animate_tab_buttons:
            self.tabWidget.tabBar().installEventFilter(self)
            self.tabBar = self.tabWidget.tabBar()
            tabcount = self.tabBar.count()
            self.tab_animations = [list(), list(), list()]
            for i in range(tabcount):

                # Creating the rectangle
                tabrect = self.tabBar.tabRect(i)
                rect = QRect(tabrect.x(), tabrect.y()+tabrect.height(), tabrect.width(), 5)
                hover_bar = QWidget(self.tabBar)
                hover_bar.setGeometry(rect)
                hover_bar.setStyleSheet('background-color: #8dae10')
                self.tab_animations[0].append(hover_bar)

                # Creating the up-animation
                tab_animation = QPropertyAnimation(self.tab_animations[0][i], b"pos")
                tab_animation.setDuration(100)
                tab_animation.setStartValue(QPoint(tabrect.x(), tabrect.height()))
                tab_animation.setEndValue(QPoint(tabrect.x(), tabrect.height() - 5))
                self.tab_animations[1].append(tab_animation)

                # Creating the down-animation
                tab_antimation = QPropertyAnimation(self.tab_animations[0][i], b"pos")
                tab_antimation.setDuration(100)
                tab_antimation.setStartValue(tab_animation.endValue())
                tab_antimation.setEndValue(tab_animation.startValue())
                self.tab_animations[2].append(tab_antimation)

                self.old_tab_index = None

        # Setting up the fonts
        if True:
            for file in os.listdir('resources/RUB-Corporate-Design-Fonts'):
                QFontDatabase.addApplicationFont(file)
            flama9 = QFont('RubFlama', 9)
            flama10 = QFont('RubFlama', 10)
            flama10u = QFont('RubFlama', 10)
            flama10u.setUnderline(True)
            flamaBold12 = QFont('RubFlama', 12)
            flamaBold12.setBold(True)
            self.tabWidget.setFont(flamaBold12)
            # self.tabBar.setFont(QFont('RubFlama Bold', 12))
            for i in self.groupBox, self.groupBox_2, self.groupBox_3:
                i.setFont(flama10u)
            for i in self.findChildren(QPushButton):
                i.setFont(flama10)
            for _ in QLabel, QLineEdit, QSpinBox, QComboBox, QCheckBox:
                for i in self.findChildren(_):
                    i.setFont(flama9)

            self.label_31.setFont(QFont('RubFlama Light', 14))
            self.plot_home1.setIcon(QIcon('resources/icons8-home.svg'))
            self.plot_home2.setIcon(QIcon('resources/icons8-home.svg'))

        self.graphs = [self.graph1, self.graph2]
        self.log_y_boxes = self.log_y_box1, self.log_y_box2
        self.auto_range_boxes = ((self.auto_x1, self.auto_x2), (self.auto_y1, self.auto_y2))

    @pyqtSlot(tuple, int)
    def plot(self, data, plot):
        match plot:
            case 0:
                if self.log_y_box1.isChecked():
                    self.line1.setData(data[0], np.log10(np.absolute(data[1])))
                else:
                    self.line1.setData(data[0], data[1])
                if self.inf_line_box1.isChecked():
                    self.inf_line1.setPos(data[2])
                self.counter1 += 1
            case 1:
                if self.log_y_box2.isChecked():
                    self.line2.setData(data[0], np.log10(np.absolute(data[1])))
                else:
                    self.line2.setData(data[0], data[1])
                if self.inf_line_box2.isChecked():
                    self.inf_line2.setPos(data[2])
                self.counter2 += 1

    def plot_starter_func(self):
        self.plot_starter()

    def plot_starter(self, plot=None):
        if plot is None:
            plot = compare_sender(self, ('start_plot1', 'start_plot2'), True)
        print(f'plot_starter on plot: {plot}')
        match plot:
            case 0:
                self.start_plot1.setEnabled(False)
                box = self.x_data_box1.currentText()
                self.plot1_label.setText('Plot 1: ' + box)
            case 1:
                self.start_plot2.setEnabled(False)
                box = self.x_data_box2.currentText()
                self.plot2_label.setText('Plot 2: ' + box)
        match box:
            case 'Raw data':
                self.requests[plot] = 1
                self.graphs[plot].setTitle('Raw data')
                self.graphs[plot].getAxis('bottom').setLabel('Time', units='s')
                self.graphs[plot].getAxis('left').setLabel('Voltage', units='v')
                self.inf_line_boxes[plot].setEnabled(False)
                self.inf_line_boxes[plot].setChecked(False)
                self.log_y_boxes[plot].setChecked(False)
            case 'IRF':
                self.requests[plot] = 2
                self.graphs[plot].setTitle('IRF data')
                self.graphs[plot].getAxis('bottom').setLabel('Time', units='ms')
                self.graphs[plot].getAxis('left').setLabel('Voltage', units='v')
                self.inf_line_boxes[plot].setEnabled(False)
                self.inf_line_boxes[plot].setChecked(False)
                self.log_y_boxes[plot].setChecked(False)
            case 'Distance':
                self.requests[plot] = 3
                self.graphs[plot].setTitle('Distance')
                self.graphs[plot].getAxis('bottom').setLabel('Time', units='s')
                self.graphs[plot].getAxis('left').setLabel('Distance', units='m')
                self.auto_range_boxes[0][plot].setChecked(True)
                self.auto_range_boxes[1][plot].setChecked(True)
                self.inf_line_boxes[plot].setEnabled(False)
                self.inf_line_boxes[plot].setChecked(False)
                self.log_y_boxes[plot].setChecked(False)
            case 'IRF Interpolated':
                self.requests[plot] = 4
                self.graphs[plot].getAxis('bottom').setLabel('Time', units='s')
                self.graphs[plot].getAxis('left').setLabel('Voltage', units='v')
                self.inf_line_boxes[plot].setEnabled(True)
        self.data_connector(plot)
        self.plot_connector(self.requests[plot], plot)
        self.stop_plot_buttons[plot].setEnabled(True)

    def plot_breaker(self, plot=None):
        if plot is None:
            plot = compare_sender(self, ('stop_plot1', 'stop_plot2'), True)
        print(f'plot_breaker on plot: {plot}')
        self.stop_plot_buttons[plot].setEnabled(False)
        self.requests[plot] = 0
        self.plot_disconnector(plot)
        self.data_connector(plot)
        self.start_plot_buttons[plot].setEnabled(True)

    def plot_breaker1(self, plot):
        self.stop_plot1.setEnabled(False)
        self.request1 = 0
        self.plot_disconnector(0)
        self.data_connector(0)
        self.start_plot1.setEnabled(True)

    def plot_breaker2(self):
        self.stop_plot2.setEnabled(False)
        self.request2 = 0
        self.plot_disconnector(1)
        self.data_connector(1)
        self.start_plot2.setEnabled(True)

    def data_connector(self, plot):
        for i in self.second_data_classes[plot][0].return_functions():
            unconnect(self.receiver.irf_measurement_ready, i)
        match self.requests:
            case (3, _) | (_, 3):
                match self.norm_interp_box.isChecked():
                    case True:
                        self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].distance_norm)
                    case False:
                        self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].distance)
            case (4, _) | (_, 4):
                match self.norm_interp_box.isChecked():
                    case True:
                        self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].irf_interp_norm)
                    case False:
                        self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].irf_interp)

    def plot_connector(self, request, plot):
        print(f'plot_connector on plot: {plot}')
        match request:
            case 1:
                self.receiver.measurement_ready.connect(self.plot_slots[plot])
            case 2:
                self.receiver.irf_measurement_ready.connect(self.plot_slots[plot])
            case 3:
                self.second_data_classes[plot][0].distance_ready.connect(self.make_distance_array)
            case 4:
                self.second_data_classes[plot][0].irf_interp_ready.connect(self.plot_slots[plot])

    def plot_disconnector(self, plot):
        print('disconnector')
        unconnect(self.receiver.measurement_ready, self.plot_slots[plot])
        unconnect(self.receiver.irf_measurement_ready, self.plot_slots[plot])
        unconnect(self.second_data_classes[plot][0].distance_ready, self.plot_slots[plot])
        unconnect(self.second_data_classes[plot][0].irf_interp_ready, self.plot_slots[plot])

    def running_refresher1(self):
        if self.stop_plot1.isEnabled():
            self.plot_breaker(0)
            self.plot_starter(0)
        if self.x_data_box1.currentText() == 'Distance':
            self.tare_distance_button_1.setEnabled(True)                     # <- I might wanna put these in an extra function
            self.distance_const_box_1.setEnabled(True)
        else:      # <-
            self.tare_distance_button_1.setEnabled(False)
            self.distance_const_box_1.setEnabled(False)

    def running_refresher2(self):
        if self.stop_plot2.isEnabled():
            self.plot_breaker(1)
            self.plot_starter(1)
        if self.x_data_box2.currentText() == 'Distance':
            self.tare_distance_button_2.setEnabled(True)                     # <-
            self.distance_const_box_2.setEnabled(True)
        else:        # <-
            self.tare_distance_button_2.setEnabled(False)
            self.distance_const_box_2.setEnabled(False)

    def refresh_x1_refresher(self):
        if not self.start_plot1.isEnabled():
            self.plot_breaker1()
            self.plot_starter(0)

    def refresh_x2_refresher(self):
        if not self.start_plot2.isEnabled():
            self.plot_breaker2()
            self.plot_starter2(1)

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
        plot = compare_sender(self, ('tare_distance_button_1', 'tare_distance_button_2'))
        self.second_data_classes[plot][0].cable_constant += np.average(np.array(self.distance_values)[-20:])
        if plot == 0:
            self.distance_const_box_1.setValue(self.second_data_classes[plot][0].cable_constant)
        else:
            self.distance_const_box_2.setValue(self.second_data_classes[plot][0].cable_constant)

    def make_distance_array(self, data):
        self.distance_values.append(data[1])
        self.distance_time_values.append(data[0])
        l1 = self.last_n_values1
        l2 = self.last_n_values2
        if self.requests[0] == 3:
            self.plot((np.array(self.distance_time_values)[-l1:], np.array(self.distance_values)[-l1:]), 0)
        if self.requests[1] == 3:
            self.plot((np.array(self.distance_time_values)[-l2:], np.array(self.distance_values)[-l2:]), 1)

    def refresh_distance_array(self):
        self.distance_values = deque()
        self.distance_time_values = deque()
        self.receiver.t0 = time.time()

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
        # self.receiver.measurement_ready.connect(self.plot)
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
        for i in range(self.plot_count):
            self.second_data_classes[i][0].sps = self.samples_per_sequence
            self.second_data_classes[i][0].sr = self.sequence_reps
            self.second_data_classes[i][0].shifts = self.shifts
        self.reconnect_receiver()
        if self.stop_plot1.isEnabled():
            self.plot_starter(0)
        if self.stop_plot2.isEnabled():
            self.plot_starter(1)

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
        self.reconnect_receiver()
        if error == 'os_exists':
            self.con_status.setText('Connection failed: Socket already in use.')
        elif error == 'os_unkown':
            self.con_status.setText('Connection failed: try again later!')
        elif error == 'type':
            self.con_status.setText('Connection failed: Check inputs and try again.')
        else:

            self.con_status.setText('Connection failed: Resetting receiver.')
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

    def set_audio_frequency(self, data):
        freq = data[1] * 20000
        self.frequency_slider.setValue(int(freq))

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

    # The following three methods overwrite members of QMainWindow. Used to move the window.
    def mousePressEvent(self, event):
        self.__mousePos = event.globalPos()

    def mouseMoveEvent(self, event):
        try:
            if self.__mousePos.y()-self.pos().y() <= 40:
                delta = event.globalPos() - self.__mousePos
                self.move(self.x() + delta.x(), self.y() + delta.y())
                self.__mousePos = event.globalPos()
        except:
            pass

    def mouseReleaseEvent(self, event):
        self.__mousePos = None

    def toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def eventFilter(self, object, event):
    # Overwrites the eventFilter of the QMainWindow. Only used to animate the tab-bar's boxes.
        if object == self.tabWidget.tabBar():
            match event.type():
            # Comparing the event type. The numbers stand for different event.type(), see:
            # https://doc.qt.io/qt-5/qevent.html#Type-enum
                case  10 | 129:
                    tab_index = object.tabAt(event.pos())
                    if tab_index not in [self.old_tab_index, self.tabWidget.currentIndex()]:
                        self.tab_animations[1][tab_index].start()
                    if self.old_tab_index not in [self.tabWidget.currentIndex(), tab_index]:
                        try:
                            self.tab_animations[2][self.old_tab_index].start()
                        except TypeError:
                            pass
                    self.old_tab_index = tab_index
                    return True
                case 11 | 2:
                    if self.old_tab_index != self.tabWidget.currentIndex():
                        try:
                            self.tab_animations[2][self.old_tab_index].start()
                        except TypeError:
                            pass
                        self.old_tab_index = None
        return False

    def close(self):
        with open('resources/configurations.bin', 'wb') as f:
            pickle.dump(dict(shifts=self.shifts,
                             samples_per_sequence=self.samples_per_sequence,
                             sequence_reps=self.sequence_reps,
                             length=self.length,
                             last_values1=self.last_n_values1,
                             last_values2=self.last_n_values2,
                             cable_length_constants=tuple(i[0].cable_constant for i in self.second_data_classes)), f)
        self.sinSender.stop()
        for i in self.second_data_classes:
            i[1].quit()
            i[1].wait()
        self.receiver.quit()
        self.sinSender.quit()
        super().close()


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
