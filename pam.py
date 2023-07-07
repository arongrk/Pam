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
import logging
from collections import deque

from PyQt5.QtCore import *
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QMainWindow, QWidget, QApplication, QSizePolicy, QSplashScreen, QHBoxLayout, QPushButton, \
    QBoxLayout, QCheckBox, QLabel, QLineEdit, QComboBox, QSpinBox, QGroupBox
from PyQt5.QtGui import QIcon, QPixmap, QColor, QFontDatabase, QFont
from PyQt5 import uic
from pyqtgraph import mkPen, PlotWidget, InfiniteLine, ViewBox

import definitions
from pams_functions import Handler, averager, exact_polynom_interp_max, unconnect, zero_padding, \
    CustomAxis, compare_sender, check_args
from Audioslider import SineAudioEmitter


resource_path = "C:/Users/dasa/PycharmProjects/MatlabData/resources/"


class Receiver(QThread):
    measurement_ready = pyqtSignal(tuple)
    irf_measurement_ready = pyqtSignal(tuple)
    st_connecting = pyqtSignal()
    st_connected = pyqtSignal()
    st_connect_failed = pyqtSignal(str)
    packageReceived = pyqtSignal()
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
                self.packageReceived.emit()
                time_stamp = round(time.time() - self.t0, 10)
                y_mes_data = np.frombuffer(r, dtype=np.int32)[:self.set_len] * 8.192 / pow(2, 18)
                x_mes_data = np.linspace(0, self.mes_len / self.sps * 2e-10 * self.set_len, self.set_len)
                self.measurement_ready.emit((x_mes_data, y_mes_data, time_stamp))
                y_irf_data = averager(y_mes_data, self.shifts, self.sps, self.s_reps)
                y_irf_data -= np.average(y_irf_data[-100:])
                x_irf_data = np.arange(1, self.shifts + 1) / 4.975e+09
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
        self.cable_constant = cable_length_constant
        self.YRefPos = np.array([])
        self.idx_start, self.idx_stop = None, None
        self.lim_distance = 25
        self.block_norm_signals = False

    def distance(self, data):
        t = data[2]
        data = zero_padding(data[0], data[1], 2.5e+09, 2**5*self.shifts)
        exact_max = exact_polynom_interp_max(data[0], np.absolute(data[1]), True, self.cable_constant)
        self.distance_ready.emit((t, exact_max[0], exact_max[1]))

    def irf_interp(self, data):
        data = zero_padding(data[0], data[1], 2.5e+09, 2**5*self.shifts)
        exact_max = exact_polynom_interp_max(data[0], np.absolute(data[1]), False)
        self.irf_interp_ready.emit((data[0], data[1], exact_max))

    def irf_interp_norm(self, data):
        if not self.block_norm_signals:
            data = zero_padding(data[0], data[1], 2.5e+09, 2 ** 5 * self.shifts, True, self.YRefPos)
            idx_start, idx_stop = np.argwhere(data[0] > self.idx_start)[0][0], np.argwhere(data[0] > self.idx_stop)[0][0]
            exact_max = exact_polynom_interp_max(data[0],
                                                 np.absolute(data[1]),
                                                 get_y=True,
                                                 interval=slice(idx_start, idx_stop))
            self.irf_interp_ready.emit((data[0], data[1], exact_max[0], exact_max[1]))

    def distance_norm(self, data):
        if not self.block_norm_signals:
            t = data[2]
            data = zero_padding(data[0], data[1], 2.5e+09, 2 ** 5 * self.shifts, True, self.YRefPos)
            idx_start, idx_stop = np.argwhere(data[0] > self.idx_start)[0][0], np.argwhere(data[0] > self.idx_stop)[0][0]
            exact_max = exact_polynom_interp_max(data[0],
                                                 np.absolute(data[1]),
                                                 get_distance=True,
                                                 get_y=True,
                                                 interval=slice(idx_start, idx_stop))
            # logging.info(exact_max[1])
            if exact_max[1] < self.lim_distance:
                self.distance_ready.emit((t, 0, exact_max[1]))
            else:
                self.distance_ready.emit((t, exact_max[0], exact_max[1]))

    def return_functions(self):
        return self.distance, self.irf_interp,  self.irf_interp_norm, self.distance_norm

    def refresh_y_ref(self, data, interval):
        self.unconnect_receiver_from_y_ref.emit()
        self.refresh_idx_lim(data, interval)
        yData = data[1]
        yData[150:161] = np.linspace(yData[150], 0, 11)
        yData[161:] = 0
        Ly = len(yData)
        YRefTemp = fft(yData, Ly) / Ly
        self.YRefPos = YRefTemp[0:trunc(Ly / 2) + 1]
        self.block_norm_signals = False

    def refresh_idx_lim(self, data, interval):
        xData = data[0]
        self.idx_start = interval[0]*1e-09
        self.idx_stop = interval[1]*1e-09
        logging.info(f'idx_start: {self.idx_start}, idx_stop: {self.idx_stop}')


class UI(QMainWindow):

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
            logging.info(self.values)
            self.samples_per_sequence = self.values['samples_per_sequence']
            self.sequence_reps = self.values['sequence_reps']
            self.shifts = self.values['shifts']
            self.length = self.values['length']
            self.last_n_values = self.values['last_values1'], self.values['last_values2']
            cable_constants = self.values['cable_length_constants']
            self.sps_edit.setText(str(self.samples_per_sequence))
            self.sr_edit.setText(str(self.sequence_reps))
            self.shifts_edit.setText(str(self.shifts))
            self.length_edit.setCurrentText(str(self.length))
            self.last_values1.setValue(self.last_n_values[0])
            self.last_values2.setValue(self.last_n_values[1])
            self.refresh_config.clicked.connect(self.refresh_configuration)
            self.xData = np.arange(1, self.shifts * self.sequence_reps * self.samples_per_sequence + 1) / 5 * 10 ** 9
            self.xData2 = np.arange(0, 1280) / 5 * 10 ** 9
            self.plot_count = 2

        # Setting up double widget lists, used for simplifying by calling
        # ...[plot]
        # instead of
        # ...1
        # ...2
        # everytime
        if True:
            self.log_y_boxes = self.log_y_box1, self.log_y_box2
            self.enableAutoX_buttons = [self.enable_auto_x1, self.enable_auto_x2]
            self.disableAutoX_buttons = [self.disable_auto_x1, self.disable_auto_x2]
            self.enableAutoY_buttons = [self.enable_auto_y1, self.enable_auto_y2]
            self.disableAutoY_buttons = [self.disable_auto_y1, self.disable_auto_y2]
            self.x_data_boxes = [self.x_data_box1, self.x_data_box2]
            self.y_data_boxes = [self.y_data_box1, self.y_data_box2]
            self.tare_distance_buttons = [self.tare_distance_button_1, self.tare_distance_button_2]
            self.distance_const_boxes = [self.distance_const_box_1, self.distance_const_box_2]
            self.start_plot_buttons = [self.start_plot1, self.start_plot2]
            self.stop_plot_buttons = [self.stop_plot1, self.stop_plot2]
            self.plot_home_buttons = [self.plot_home1, self.plot_home2]
            self.plot_rate_labels = [self.plot_rate_1, self.plot_rate_2]
            self.plot_labels = [self.plot_label1, self.plot_label2]

        # Setting up the connections for the log file
        for i in self.findChildren(QPushButton):
            i.clicked.connect(self.button_clicked_log)
        for i in self.findChildren(QComboBox):
            i.currentTextChanged.connect(self.combobox_changed_log)

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

            self.graphs = [self.graph1, self.graph2]
            self.lines = [self.line1, self.line2]

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

        # SLOT-MAKER
        # Setting up the slots for the different plots as lambda functions:
        for name, method in [(n, f) for n, f in vars(self.__class__).items() if callable(f) and not n.startswith('__')]:
            plot_is_argument, other_args = check_args(method, 'plot', True, 'self')
            if plot_is_argument:
                exec(f'self.{name}_slots = list()')
                arg_string = ', '.join(other_args) + ', ' if len(other_args) > 0 else ''
                for index in range(self.plot_count):
                    exec(f'lambda_slot = lambda {arg_string}plot=index, self=self: self.{name}({arg_string}plot)')
                    exec(f'self.{name}_slots.append(lambda_slot)')

        # Start and stop Plot 1 and 2
        self.start_plot1.clicked.connect(self.plot_starter_slots[0])
        self.stop_plot1.clicked.connect(self.plot_breaker_slots[0])
        self.start_plot2.clicked.connect(self.plot_starter_slots[1])
        self.stop_plot2.clicked.connect(self.plot_breaker_slots[1])

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
            for plot in range(self.plot_count):
                self.y_data_boxes[plot].currentTextChanged.connect(self.y_data_refresher_slots[plot])
                self.x_data_boxes[plot].currentTextChanged.connect(self.x_data_refresher_slots[plot])

            # Refreshing the last_values boxes
            self.last_values1.valueChanged.connect(lambda value: setattr(self, 'last_n_values1', value))
            self.last_values2.valueChanged.connect(lambda value: setattr(self, 'last_n_values2', value))

            # Setting up the distance calibration:
            self.distance_const_box_1.setDecimals(5)
            self.distance_const_box_2.setDecimals(5)
            self.distance_const_box_1.setValue(cable_constants[0])
            self.distance_const_box_2.setValue(cable_constants[1])
            self.tare_distance_button_1.clicked.connect(self.cable_constant_refresher_slots[0])
            self.tare_distance_button_2.clicked.connect(self.cable_constant_refresher_slots[1])
            self.distance_const_box_1.valueChanged.connect(lambda value: setattr(self.second_data_classes[0][0],
                                                                                 'cable_constant', value))
            self.distance_const_box_2.valueChanged.connect(lambda value: setattr(self.second_data_classes[1][0],
                                                                                 'cable_constant', value))

        # Setting up the auto range and plot home feature:
        for i in range(self.plot_count):
            self.enableAutoX_buttons[i].pressed.connect(lambda _=i: self.graphs[_].enableAutoRange(axis=ViewBox.XAxis))
            self.disableAutoX_buttons[i].pressed.connect(lambda _=i: self.graphs[_].disableAutoRange(axis=ViewBox.XAxis))
            self.enableAutoY_buttons[i].pressed.connect(lambda _=i: self.graphs[_].enableAutoRange(axis=ViewBox.YAxis))
            self.disableAutoY_buttons[i].pressed.connect(lambda _=i: self.graphs[_].disableAutoRange(axis=ViewBox.YAxis))
            self.plot_home_buttons[i].pressed.connect(lambda _=i: self.graphs[_].autoRange())
        self.plot_home_requests = [False for _ in range(self.plot_count)]

        # Setting up the plot timer:
        self.make_plot_timers = True
        if self.make_plot_timers:
            self.timer = QTimer()
            self.timer.timeout.connect(self.plot1_timer)
            self.timer.timeout.connect(self.plot2_timer)
            self.timer.timeout.connect(self.receiver_timer)
            self.timer.timeout.connect(self.data_rate_timer)
            self.timer.start(500)
            self.counters_plot = [0, 0]
            self.counter_lost = 0
            self.counter_received = 0
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
            self.inf_lines = [self.inf_line1, self.inf_line2]
            self.inf_line_boxes = [self.inf_line_box1, self.inf_line_box2]
            for plot in range(self.plot_count):
                self.inf_line_boxes[plot].stateChanged.connect(self.inf_line_refresher_slots[plot])

        # Setting up the Audio Emitter:
        if True:
            self.sinSender = SineAudioEmitter(44100, 10, self.frequency_slider.value(), self.volume_slider.value())
            self.start_sound_button.clicked.connect(self.sinSender.start)
            self.frequency_slider.valueChanged.connect(self.sinSender.set_frequency)
            self.volume_slider.valueChanged.connect(self.sinSender.set_volume)
            self.stop_sound_button.clicked.connect(self.sinSender.stop)
            self.second_data_classes[0][0].distance_ready.connect(self.set_audio_frequency)
            self.second_data_classes[0][0].distance_ready.connect(self.set_audio_volume)


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
            for i in self.findChildren(QGroupBox):
                i.setFont(flama10u)
            for i in self.findChildren(QPushButton):
                i.setFont(flama10)
            for _ in QLabel, QLineEdit, QSpinBox, QComboBox, QCheckBox:
                for i in self.findChildren(_):
                    i.setFont(flama9)

            self.label_31.setFont(QFont('RubFlama Light', 14))
            self.plot_home1.setIcon(QIcon('resources/icons8-home.svg'))
            self.plot_home2.setIcon(QIcon('resources/icons8-home.svg'))

    def plot_signal(self, data, plot):
        if self.log_y_boxes[plot].isChecked():
            self.lines[plot].setData(data[0], np.log10(np.absolute(data[1])))
        else:
            if self.x_data_boxes[plot].currentIndex() == 1:
                self.lines[plot].setData(data[0]*speed_of_light/2, data[1])
            else:
                self.lines[plot].setData(data[0], data[1])
        if self.inf_line_boxes[plot].isChecked():
            self.inf_lines[plot].setPos(data[2])
        self.counters_plot[plot] += 1
        if self.plot_home_requests[plot]:
            logging.info(f'autoRange requested on plot: {plot}, autoRanging now')
            self.graphs[plot].autoRange()
            self.plot_home_requests[plot] = False

    def plot_starter(self, _=None, plot=None):
        logging.info(f'plot_starter on plot: {plot}')
        self.start_plot_buttons[plot].setEnabled(False)
        box = self.y_data_boxes[plot].currentText()
        self.plot_labels[plot].setText(f'Plot {plot}: {box}')
        match box:
            case 'Raw data':
                self.requests[plot] = 1
                self.graphs[plot].setTitle('Raw data')
                self.graphs[plot].getAxis('bottom').setLabel('Time', units='s')
                self.graphs[plot].getAxis('left').setLabel('Voltage', units='v')
                self.inf_line_boxes[plot].setEnabled(False)
                self.inf_line_boxes[plot].setChecked(False)
                self.log_y_boxes[plot].setChecked(False)
                self.plot_home_requests[plot] = True
            case 'IRF':
                self.requests[plot] = 2
                self.graphs[plot].setTitle('IRF data')
                if self.x_data_boxes[plot].currentIndex() == 1:
                    self.graphs[plot].getAxis('bottom').setLabel('Distance', units='m')
                else:
                    self.graphs[plot].getAxis('bottom').setLabel('time', units='s')
                self.graphs[plot].getAxis('left').setLabel('Voltage', units='v')
                self.inf_line_boxes[plot].setEnabled(False)
                self.inf_line_boxes[plot].setChecked(False)
                self.log_y_boxes[plot].setChecked(False)
                self.plot_home_requests[plot] = True
            case 'Distance':
                self.requests[plot] = 3
                self.graphs[plot].setTitle('Distance')
                self.graphs[plot].getAxis('bottom').setLabel('Time', units='s')
                self.graphs[plot].getAxis('left').setLabel('Distance', units='m')
                self.inf_line_boxes[plot].setEnabled(False)
                self.inf_line_boxes[plot].setChecked(False)
                self.log_y_boxes[plot].setChecked(False)
                self.graphs[plot].enableAutoRange()
            case 'Distance Norm':
                self.requests[plot] = 4
                y_ref = lambda data, interval=(1, 12): self.second_data_classes[plot][0].refresh_y_ref(data, interval)
                self.second_data_classes[plot][0].unconnect_receiver_from_y_ref.connect(
                    lambda: unconnect(self.receiver.irf_measurement_ready, y_ref))
                self.receiver.irf_measurement_ready.connect(y_ref)
                self.second_data_classes[plot][0].block_norm_signals = True
                self.graphs[plot].enableAutoRange()
            case 'IRF Interpolated':
                self.requests[plot] = 5
                if self.x_data_boxes[plot].currentIndex() == 1:
                    self.graphs[plot].getAxis('bottom').setLabel('Distance', units='m')
                else:
                    self.graphs[plot].getAxis('bottom').setLabel('time', units='s')
                self.graphs[plot].getAxis('left').setLabel('Voltage', units='v')
                self.inf_line_boxes[plot].setEnabled(True)
                self.plot_home_requests[plot] = True
            case 'IRF Interpolated Norm':
                self.requests[plot] = 6
                y_ref = lambda data, interval=(1, 12): self.second_data_classes[plot][0].refresh_y_ref(data, interval)
                self.second_data_classes[plot][0].unconnect_receiver_from_y_ref.connect(
                    lambda: unconnect(self.receiver.irf_measurement_ready, y_ref))
                self.receiver.irf_measurement_ready.connect(y_ref)
                self.second_data_classes[plot][0].block_norm_signals = True
                self.plot_home_requests[plot] = True
        self.data_connector(plot)
        self.plot_connector(self.requests[plot], plot)
        self.stop_plot_buttons[plot].setEnabled(True)

    def plot_breaker(self, _=None, plot: tuple or int = None):
        logging.info(f'plot_breaker on plot: {plot}')
        self.stop_plot_buttons[plot].setEnabled(False)
        self.requests[plot] = 0
        self.plot_disconnector(plot)
        self.data_disconnector(plot)
        self.start_plot_buttons[plot].setEnabled(True)

    def data_connector(self, plot):
        logging.info(f'data connector on plot: {plot}, requests[{plot}] = {self.requests[plot]}')
        match self.requests[plot]:
            case 3:
                self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].distance)
            case 4:
                self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].distance_norm)
            case 5:
                self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].irf_interp)
            case 6:
                self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].irf_interp_norm)

    def data_disconnector(self, plot):
        logging.info(f'data_disconnector on plot: {plot}, requests[{plot}] = {self.requests[plot]}')
        for i in self.second_data_classes[plot][0].return_functions():
            unconnect(self.receiver.irf_measurement_ready, i)

    def plot_connector(self, request, plot):
        logging.info(f'plot_connector on plot: {plot}, requests[{plot}] = {self.requests[plot]}')
        match request:
            case 1:
                unconnect(self.receiver.measurement_ready, self.plot_signal_slots[plot])
                self.receiver.measurement_ready.connect(self.plot_signal_slots[plot])
            case 2:
                unconnect(self.receiver.irf_measurement_ready, self.plot_signal_slots[plot])
                self.receiver.irf_measurement_ready.connect(self.plot_signal_slots[plot])
            case 3 | 4:
                unconnect(self.second_data_classes[plot][0].distance_ready, self.make_distance_array_slots[plot])
                self.second_data_classes[plot][0].distance_ready.connect(self.make_distance_array_slots[plot])
            case 5 | 6:
                unconnect(self.second_data_classes[plot][0].irf_interp_ready, self.plot_signal_slots[plot])
                self.second_data_classes[plot][0].irf_interp_ready.connect(self.plot_signal_slots[plot])

    def plot_disconnector(self, plot):
        logging.info(f'plot_disconnector on plot: {plot}')
        unconnect(self.receiver.measurement_ready, self.plot_signal_slots[plot])
        unconnect(self.receiver.irf_measurement_ready, self.plot_signal_slots[plot])
        unconnect(self.second_data_classes[plot][0].distance_ready, self.plot_signal_slots[plot])
        unconnect(self.second_data_classes[plot][0].irf_interp_ready, self.plot_signal_slots[plot])

    def y_data_refresher(self, item, plot):
        unconnect(self.x_data_boxes[plot].currentTextChanged, self.x_data_refresher_slots[plot])
        unconnect(self.x_data_boxes[plot].currentTextChanged, self.combobox_changed_log)
        self.x_data_boxes[plot].clear()
        match item:
            case 'Raw data':
                self.x_data_boxes[plot].addItems(['time'])
                self.tare_distance_buttons[plot].setEnabled(False)
                self.distance_const_boxes[plot].setEnabled(False)
            case 'IRF' | 'IRF Interpolated':
                self.x_data_boxes[plot].addItems(['time', 'distance'])
                self.tare_distance_buttons[plot].setEnabled(False)
                self.distance_const_boxes[plot].setEnabled(False)
            case 'IRF Interpolated Norm':
                self.x_data_boxes[plot].addItems(['time'])
            case 'Distance' | 'Distance Norm':
                self.x_data_boxes[plot].addItems(['duration'])
                self.tare_distance_buttons[plot].setEnabled(True)
                self.distance_const_boxes[plot].setEnabled(True)
        self.x_data_boxes[plot].setCurrentIndex(0)
        self.x_data_boxes[plot].currentTextChanged.connect(self.x_data_refresher_slots[plot])
        self.x_data_boxes[plot].currentTextChanged.connect(self.combobox_changed_log)
        if self.stop_plot_buttons[plot].isEnabled():
            self.plot_breaker(plot=plot)
            self.plot_starter(plot=plot)

    def x_data_refresher(self, _, plot):
        if self.stop_plot_buttons[plot].isEnabled():
            self.plot_breaker(plot=plot)
            self.plot_starter(plot=plot)

    def inf_line_refresher(self, state, plot):
        if state == 2:
            self.graphs[plot].addItem(self.inf_lines[plot])
        else:
            self.graphs[plot].removeItem(self.inf_lines[plot])

    def cable_constant_refresher(self, plot):
        self.second_data_classes[plot][0].cable_constant += np.average(np.array(self.distance_values)[-20:])
        if plot == 0:
            self.distance_const_box_1.setValue(self.second_data_classes[plot][0].cable_constant)
        else:
            self.distance_const_box_2.setValue(self.second_data_classes[plot][0].cable_constant)

    def make_distance_array(self, data, plot):
        self.distance_values.append(data[1])
        self.distance_time_values.append(data[0])
        l_v = self.last_n_values[plot]
        if self.requests[0] in (3, 4):
            self.plot_signal((np.array(self.distance_time_values)[-l_v:], np.array(self.distance_values)[-l_v:]), plot)

    def refresh_distance_array(self):
        self.distance_values = deque()
        self.distance_time_values = deque()
        self.receiver.t0 = time.time()

    def start_receiver(self):
        self.receiver.start()
        self.receiver.packageLost.connect(self.lost_counter)
        self.receiver.packageReceived.connect(self.received_counter)
        self.start_plot1.setEnabled(True)
        self.start_plot2.setEnabled(True)
        self.start_receive.setEnabled(False)
        self.stop_receive.setEnabled(True)
        self.label_11.setStyleSheet('color: green')
        self.label_11.setText('Receiving data')

    def reconnect_receiver(self):
        self.plot_breaker(0)
        self.plot_breaker(1)
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

    def button_clicked_log(self):
        button = self.sender()
        button_name = button.objectName()
        logging.info('')
        logging.info(f'Button clicked: {button_name}')

    def combobox_changed_log(self):
        combobox = self.sender()
        combobox_name = combobox.objectName()
        combobox_new_text = combobox.currentText()
        logging.info('')
        logging.info(f'ComboBox {combobox_name} changed to: {combobox_new_text}')

    def lost_counter(self):
        self.counter_lost += 1

    def received_counter(self):
        self.counter_received += 1

    def plot1_timer(self):
        self.plot_rate_1.setText(f'Plot 1: {self.counters_plot[0]*2} P/s')
        self.counters_plot[0] = 0

    def plot2_timer(self):
        self.plot_rate_2.setText(f'Plot 2: {self.counters_plot[1]*2} P/s')
        self.counters_plot[1] = 0

    def receiver_timer(self):
        self.lost_packs_label.setText(f'Loosing: {self.counter_lost*2} p/s')
        self.received_packs_label.setText(f'Receiving: {self.counter_received*2} p/s')
        self.counter_lost = 0
        self.counter_received = 0

    def data_rate_timer(self):
        byties = psutil.net_io_counters(pernic=True)['Ethernet 2'][1]
        self.ethernet_rate.setText(f'Ethernet 2: {round((byties - self.bytes_received) * 8e-06 * 2, 1)} MBit/s')
        self.bytes_received = byties

    def set_audio_frequency(self, data):
        freq = (data[1] - 0.15) * 5000
        self.frequency_slider.setValue(int(freq))

    def set_audio_volume(self, data):
        vol = 0 if data[2] - 25 < 0 else (data[2] - 25) * 2
        self.volume_slider.setValue(int(vol))

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
                             last_values1=self.last_n_values[0],
                             last_values2=self.last_n_values[1],
                             cable_length_constants=tuple(i[0].cable_constant for i in self.second_data_classes)), f)
        self.sinSender.stop()
        for i in self.second_data_classes:
            i[1].quit()
            i[1].wait()
        self.receiver.quit()
        # self.receiver.wait()
        self.sinSender.quit()
        self.sinSender.wait()
        super().close()

    def return_methods(self):
        # Only used for the SLOT-MAKER code in self.init()
        return [name for name, _ in self.__dict__.items() if callable(_) and not name.startswith('__')]


def main():
    logging.basicConfig(filename='pam.log', level=logging.INFO, filemode='w')
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
