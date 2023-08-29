import os
import sys
import numpy as np
import time
import psutil
import logging
from collections import deque

from PyQt5.QtCore import *
from PyQt5.QtSvg import QSvgWidget
from PyQt5.QtWidgets import QMainWindow, QWidget, QApplication, QSplashScreen, QPushButton, QCheckBox, QLabel,\
    QLineEdit, QComboBox, QSpinBox, QGroupBox, QDoubleSpinBox
from PyQt5.QtGui import QIcon, QPixmap, QFontDatabase, QFont
from PyQt5 import uic
from pyqtgraph import mkPen, InfiniteLine, ViewBox

import definitions
from pams_functions import SecondData, Receiver, unconnect, CustomAxis, check_args, MagicValuesFinder
from Audioslider import SineAudioEmitter


class UI(QMainWindow):

    def __init__(self):
        super(UI, self).__init__()

        # Load the ui file made with qt-designer
        uic.loadUi('resources/Mainwindow.ui', self)

        # Loading the values and getting the parameters for data interpreting
        if True:
            self.settings = QSettings('RUB', 'pam')
            for setting in [f'{i}: {self.settings.value(i)}' for i in self.settings.allKeys()]:
                logging.info(setting)

            # This block finds all the children of the ui_file of the given kind and looks for their values in QSettings
            for i in self.findChildren(QSpinBox):
                i.setValue(self.settings.value(i.objectName(), type=int))
            for i in self.findChildren(QDoubleSpinBox):
                i.setValue(self.settings.value(i.objectName(), type=float))
            for i in self.findChildren(QLineEdit):
                if i.objectName() != 'qt_spinbox_lineedit':     # This excludes QSpinboxes as they are also found
                    i.setText(self.settings.value(i.objectName(), type=str))
            for i in self.findChildren(QCheckBox):
                i.setChecked(self.settings.value(i.objectName(), type=bool))

            # Loading the values into the parameter if needed
            self.samples_per_sequence = int(self.sps_edit.text())
            self.sequence_reps = int(self.sr_edit.text())
            self.shifts = int(self.shifts_edit.text())
            self.length = int(self.length_edit.currentText())
            self.last_n_values1, self.last_n_values2 = int(self.last_values1.text()), int(self.last_values2.text())
            cable_constants = int(self.distance_const_box_1.value()), int(self.distance_const_box_1.value())
            self.refresh_config.clicked.connect(self.refresh_configuration)
            self.xData = np.arange(1, self.shifts * self.sequence_reps * self.samples_per_sequence + 1) / 5 * 10 ** 9
            self.xData2 = np.arange(0, 1280) / 5 * 10 ** 9
            self.plot_count = 2

        if True:
            '''
            Setting up double widget lists, used for simplifying by calling
            self.objectName[plot]
            instead of
            self.objectName1
            self.objectName2
            everytime
            
            This could be automated if needed, for example when many new features are added
            '''
            self.last_n_values_boxes = [self.last_values1, self.last_values2]
            self.log_y_boxes = [self.log_y_box1, self.log_y_box2]
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
            self.norm_mes_start_boxes = [self.norm_mes_start_box1, self.norm_mes_start_box2]
            self.norm_mes_end_boxes = [self.norm_mes_end_box1, self.norm_mes_end_box2]
            self.calibration_start_boxes = [self.calibration_start_box1, self.calibration_start_box2]
            self.calibration_end_boxes = [self.calibration_end_box1, self.calibration_end_box2]
            self.normalization_refresh_buttons = [self.normation_refresh_button1, self.normation_refresh_button2]
            self.copy_norm_config_buttons = [self.copy_norm_config_1, self.copy_norm_config_2]
            self.lim_distance_boxes = [self.lim_distance_box1, self.lim_distance_box2]

        # Setting up the connections for the log file
        if True:
            for i in self.findChildren(QPushButton):
                i.clicked.connect(self.button_clicked_log)
            for i in self.findChildren(QComboBox):
                i.currentTextChanged.connect(self.combobox_changed_log)
            for i in self.findChildren(QLineEdit):
                i.editingFinished.connect(self.lineedit_changed_log)

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
            for plot in range(self.plot_count):
                self.second_data_classes.append([
                    SecondData(self.samples_per_sequence,
                               self.shifts,
                               self.sequence_reps,
                               self.length,
                               cable_length_constant=cable_constants[plot],
                               norm_measurement_start=self.norm_mes_start_boxes[plot].value(),
                               norm_measurement_end=self.norm_mes_end_boxes[plot].value(),
                               calibration_start=self.calibration_start_boxes[plot].value(),
                               calibration_end=self.calibration_end_boxes[plot].value(),
                               distance_limit=self.lim_distance_boxes[plot].value(),
                               x_data_request=self.x_data_boxes[plot].currentText(),
                               ),
                    QThread()
                    ])
                self.second_data_classes[plot][0].moveToThread(self.second_data_classes[plot][1])
                self.second_data_classes[plot][1].start()

        # Other Connections:
        if True:
            # Refreshing the chosen plot option
            for plot in range(self.plot_count):
                self.y_data_boxes[plot].currentTextChanged.connect(self.y_data_refresher_slots[plot])
                self.x_data_boxes[plot].currentTextChanged.connect(self.x_data_refresher_slots[plot])

                # Refreshing the values for normalized interpolation:
                self.normalization_refresh_buttons[plot].clicked.connect(self.refresh_norm_values_slots[plot])

                self.x_data_boxes[plot].setCurrentIndex(0)

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

        # Setting up the requests for the plot widgets
        if True:
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
            self.close_button.setIcon(self.clos_ic)
            self.maximize_button.setIcon(self.max_ic)
            self.minimize_button.setIcon(self.min_ic)
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
            self.sinSender = SineAudioEmitter(44100, 10, self.freq_number.intValue(), self.volume_slider.value(),
                                              plot_sine_wave=True, plot_mode='')
            # self.start_sound_button.clicked.connect(self.sinSender.start)
            self.start_sound_button.clicked.connect(self.start_audio_player)
            self.volume_slider.valueChanged.connect(self.sinSender.set_volume)
            self.stop_sound_button.clicked.connect(self.stop_audio_player)

            self.sound_range_start = self.sound_bar_start_box.value()
            self.sound_range_stop = self.sound_bar_end_box.value()
            self.sound_button_number = self.button_number_box.value()
            self.first_sound_button = self.first_button_box.value()
            self.sound_range_length = self.sound_range_stop - self.sound_range_start
            self.sound_button_span = self.sound_range_length / (self.sound_button_number - 1)

            self.refresh_sound_values_button.clicked.connect(self.refresh_sound_values)
            self.magic_finder_button.clicked.connect(self.magic_sound_values_refresh)

            self.audio_player_running = False

            self.signal_filter = 1

            self.sine_line = self.graph_sine.plot(np.arange(10), np.zeros(10), pen=pen)
            self.graph_sine.setBackground('w')
            self.start_sine_plot_button.clicked.connect(self.sine_plot_starter)
            self.stop_sine_plot_button.clicked.connect(self.sine_plot_breaker)
            self.only_changes_sine_box.stateChanged.connect(self.only_changes_sine_refresher)

        # Setting up the distance plot calculation
        if True:
            self.distance_values = deque()
            self.distance_time_values = deque()

            # refresh_distance_button
            self.refresh_distance_button.clicked.connect(self.refresh_distance_array)

            self.distance_value_number = 0

        # Setting up the copy to plot x buttons
        for plot in range(self.plot_count):
            self.copy_norm_config_buttons[plot].pressed.connect(self.copy_norm_config_slots[plot])

        # Setting up the animations for the QTabWidget of the MainWindow, should also work if another tab is added
        if True:
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

        # Setting up the fonts for the interface
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
                # print(i)
                i.setFont(flama10u)
                # i.setStyleSheet('color: black')
            for i in self.findChildren(QPushButton):
                i.setFont(flama10)
            for _ in QLabel, QLineEdit, QSpinBox, QComboBox, QCheckBox:
                for i in self.findChildren(_):
                    i.setFont(flama9)

            self.label_31.setFont(QFont('RubFlama Light', 14))
            self.plot_home1.setIcon(QIcon('resources/icons8-home.svg'))
            self.plot_home2.setIcon(QIcon('resources/icons8-home.svg'))

    def plot_signal(self, data, plot: int):
        """
        plots the given data on the given plot

        :param data: a 2-axis set of data
        :param plot: 0 or 1
        :return: an image on the given plot
        """
        if self.log_y_boxes[plot].isChecked():
            self.lines[plot].setData(data[0], np.log10(np.absolute(data[1])))
        else:
            self.lines[plot].setData(data[0], data[1])

        if self.inf_line_boxes[plot].isChecked():
            self.inf_lines[plot].setPos(data[2])

        self.counters_plot[plot] += 1
        if self.plot_home_requests[plot]:
            logging.info(f'autoRange requested on plot: {plot}, autoRanging now')
            self.graphs[plot].autoRange()
            self.plot_home_requests[plot] = False

    def plot_starter(self, _=None, plot: int = None):
        """
        called by the start_plot buttons or to refresh settings of the given plot like this:
        
        self.plot_breaker(plot)
        
        self.plot_starter(plot)

        :param _: unused argument used to intercept the argument of the QPushButton.clicked(bool) signal
        :param plot: 0 or 1
        :return: no return
        """
        logging.info(f'plot_starter on plot: {plot}')
        self.start_plot_buttons[plot].setEnabled(False)
        box = self.y_data_boxes[plot].currentText()
        self.plot_labels[plot].setText(f'Plot {plot}: {box}')
        match box:
            case 'Raw data':
                self.requests[plot] = 1
                self.graphs[plot].setTitle('Raw data')
                self.inf_line_boxes[plot].setEnabled(False)
                self.inf_line_boxes[plot].setChecked(False)
                self.log_y_boxes[plot].setChecked(False)
            case 'IRF':
                self.requests[plot] = 2
                self.graphs[plot].setTitle('IRF data')
                self.inf_line_boxes[plot].setEnabled(False)
                self.inf_line_boxes[plot].setChecked(False)
                self.log_y_boxes[plot].setChecked(False)
            case 'Distance':
                self.requests[plot] = 3
                self.distance_value_number = 0
                self.graphs[plot].setTitle('Distance')
                self.inf_line_boxes[plot].setEnabled(False)
                self.inf_line_boxes[plot].setChecked(False)
                self.log_y_boxes[plot].setChecked(False)
                self.graphs[plot].enableAutoRange()
            case 'Distance Norm':
                self.requests[plot] = 4
                self.distance_value_number = 0
                self.refresh_norm_values(plot=plot)
                self.graphs[plot].enableAutoRange()
                self.inf_line_boxes[plot].setEnabled(False)
                self.inf_line_boxes[plot].setChecked(False)
            case 'IRF Interpolated':
                self.requests[plot] = 5
                self.inf_line_boxes[plot].setEnabled(True)
            case 'IRF Interpolated Norm':
                self.requests[plot] = 6
                self.inf_line_boxes[plot].setEnabled(True)
                self.refresh_norm_values(plot=plot)
        self.data_connector(plot)
        self.plot_connector(self.requests[plot], plot)
        self.stop_plot_buttons[plot].setEnabled(True)

    def plot_breaker(self, _=None, plot: int = None):
        """
        called by the stop_plot buttons or to refresh settings of the given plot like this:
        
        self.plot_breaker(plot)
        
        self.plot_starter(plot)

        :param _: unused argument used to intercept the argument of the QPushButton.clicked(bool) signal
        :param plot: 0 or 1
        :return: no return
        """
        logging.info(f'plot_breaker on plot: {plot}')
        self.stop_plot_buttons[plot].setEnabled(False)
        self.requests[plot] = 0
        self.plot_disconnector(plot)
        self.data_disconnector(plot)
        self.start_plot_buttons[plot].setEnabled(True)

    def data_connector(self, plot: int):
        """
        connects the raw data or the irf data sets of the receiver-class to the requested
        signal processing method of the second data class 
        
        :param plot: 0 or 1
        :return: no return
        """
        logging.info(f'data connector on plot: {plot}, requests[{plot}] = {self.requests[plot]}')
        match self.requests[plot]:
            case 1:
                self.receiver.measurement_ready.connect(self.second_data_classes[plot][0].raw_data)
            case 2:
                self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].irf_data)
            case 3:
                self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].distance)
            case 4:
                self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].distance_norm)
            case 5:
                self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].irf_interp)
            case 6:
                self.receiver.irf_measurement_ready.connect(self.second_data_classes[plot][0].irf_interp_norm)

    def data_disconnector(self, plot: int):
        """
        disconnects the signals of the receiver class from all the slots of the given second_data class to make sure
        there is no double connections as they significantly reduce the speed of the program
        
        :param plot: 0 or 1
        :return: no return
        """
        logging.info(f'data_disconnector on plot: {plot}, requests[{plot}] = {self.requests[plot]}')
        for i in self.second_data_classes[plot][0].return_functions():
            unconnect(self.receiver.irf_measurement_ready, i)

    def plot_connector(self, request, plot: int):
        """
        connects the requested signal of the given second_data class to the given plot. Calls unconnect before to make
        sure there is no double connections. Usually called after self.data_connector()
        
        :param request: requested plot option
        :param plot: 0 or 1
        :return: 
        """
        logging.info(f'plot_connector on plot: {plot}, requests[{plot}] = {self.requests[plot]}')
        match request:
            case 1:
                unconnect(self.second_data_classes[plot][0].measurement_ready, self.plot_signal_slots[plot])
                self.second_data_classes[plot][0].measurement_ready.connect(self.plot_signal_slots[plot])
            case 2:
                unconnect(self.second_data_classes[plot][0].irf_measurement_ready, self.plot_signal_slots[plot])
                self.second_data_classes[plot][0].irf_measurement_ready.connect(self.plot_signal_slots[plot])
            case 3 | 4:
                unconnect(self.second_data_classes[plot][0].distance_ready, self.make_distance_array_slots[plot])
                self.second_data_classes[plot][0].distance_ready.connect(self.make_distance_array_slots[plot])
            case 5 | 6:
                unconnect(self.second_data_classes[plot][0].irf_interp_ready, self.plot_signal_slots[plot])
                self.second_data_classes[plot][0].irf_interp_ready.connect(self.plot_signal_slots[plot])

    def plot_disconnector(self, plot: int):
        """
        disconnects every possible signal from the plot_signal method to make sure no connection slips through

        :param plot: 0 or 1
        :return: no return
        """
        logging.info(f'plot_disconnector on plot: {plot}')
        unconnect(self.second_data_classes[plot][0].measurement_ready, self.plot_signal_slots[plot])
        unconnect(self.second_data_classes[plot][0].irf_measurement_ready, self.plot_signal_slots[plot])
        unconnect(self.second_data_classes[plot][0].distance_ready, self.plot_signal_slots[plot])
        unconnect(self.second_data_classes[plot][0].irf_interp_ready, self.plot_signal_slots[plot])

    def y_data_refresher(self, item, plot: int):
        """
        Called when one of the y_data boxes is changed whether plot is running or not.
        Refreshes the options for the x_data box and restarts the given plot if running.

        :param item: provided by the signal QComboBox.currentTextChanged()
        :param plot: 0 or 1
        :return: no return
        """
        unconnect(self.x_data_boxes[plot].currentTextChanged, self.x_data_refresher_slots[plot])
        unconnect(self.x_data_boxes[plot].currentTextChanged, self.combobox_changed_log)
        self.x_data_boxes[plot].clear()
        match item:
            case 'Raw data' | 'IRF' | 'IRF Interpolated' | 'IRF Interpolated Norm':
                self.x_data_boxes[plot].addItems(['time', 'distance', 'value no.'])
                self.tare_distance_buttons[plot].setEnabled(False)
                self.distance_const_boxes[plot].setEnabled(False)
                self.plot_home_requests[plot] = True
            case 'Distance' | 'Distance Norm':
                self.x_data_boxes[plot].addItems(['duration', 'value no.'])
                self.tare_distance_buttons[plot].setEnabled(True)
                self.distance_const_boxes[plot].setEnabled(True)
        self.x_data_boxes[plot].setCurrentIndex(0)
        self.second_data_classes[plot][0].x_data_request = self.x_data_boxes[plot].currentText()
        self.x_data_boxes[plot].currentTextChanged.connect(self.x_data_refresher_slots[plot])
        self.x_data_boxes[plot].currentTextChanged.connect(self.combobox_changed_log)
        if self.stop_plot_buttons[plot].isEnabled():
            self.plot_breaker(plot=plot)
            self.plot_starter(plot=plot)

    def x_data_refresher(self, item, plot: int):
        """
        Called when one of the x_data boxes is changed whether the plot is running or not.
        Refreshes the x_data_request parameter of the given second_data instance and restarts the plot if running.

        :param item: provided by the signal QComboBox.currentTextChanged()
        :param plot: 0 or 1
        :return:
        """
        logging.info(f'x_data_refresher on plot {plot}')
        self.second_data_classes[plot][0].x_data_request = item
        if self.stop_plot_buttons[plot].isEnabled():
            self.plot_breaker(plot=plot)
            self.plot_starter(plot=plot)
            # if True:
            if self.requests[plot] not in (3, 4):
                self.plot_home_requests[plot] = True
            else:
                self.refresh_distance_array()

    def inf_line_refresher(self, state, plot: int):
        """
        refreshes the red vertical line that cuts through the maximum delivered as second argument of some data-signals
        of the second_data class

        :param state: delivered by the signal QCheckBox.stateChanged()
        :param plot: 0 or 1
        :return: no return
        """
        if state == 2:
            self.graphs[plot].addItem(self.inf_lines[plot])
        else:
            self.graphs[plot].removeItem(self.inf_lines[plot])

    def cable_constant_refresher(self, plot: int):
        """
        Automatically sets a new cable constant as the average of the last 20 values.

        Should only be used when the adjustable short is connected

        :param plot: 0 or 1
        :return: no return
        """
        self.second_data_classes[plot][0].cable_constant += np.average(np.array(self.distance_values)[-20:])
        if plot == 0:
            self.distance_const_box_1.setValue(self.second_data_classes[plot][0].cable_constant)
        else:
            self.distance_const_box_2.setValue(self.second_data_classes[plot][0].cable_constant)

    def make_distance_array(self, data, plot: int):
        """
        Called by the signal SecondData.distance_ready()
        Makes the distance arrays ready for plotting and receives its data from the given second_data instance.
        Only method that calls self.plot_signal() not via a signal

        :param data: provided by the signal SecondData.distance_ready()
        :param plot: 0 or 1
        :return: no return
        """
        self.distance_values.append(data[1])
        match self.x_data_boxes[plot].currentText():
            case 'duration':
                self.distance_time_values.append(data[0])
            case 'value no.':
                self.distance_value_number += 1
                self.distance_time_values.append(self.distance_value_number)
        l_v = self.last_n_values_boxes[plot].value()
        if self.requests[plot] in (3, 4):
            self.plot_signal((np.array(self.distance_time_values)[-l_v:], np.array(self.distance_values)[-l_v:]), plot)

    def refresh_distance_array(self):
        """
        Called by the refresh_distance button. Clears out the distance arrays and resets Receiver.t0 to zero.

        :return: no return
        """
        self.distance_values.clear()
        self.distance_time_values.clear()
        self.receiver.t0 = time.time()

    def refresh_norm_values(self,_=None , plot: int = None):
        """
        Called by the normation_refresh. Refreshes the necessary parameters of the given SecondData instance by
        the one provided in the boxes in the interface. Then connects exactly one irf_measurement to
        SecondData.refresh_y_ref to make or renew the norm array.

        :param _: intercepts
        :param plot: 0 or 1
        :return: no return
        """
        logging.info(f'refresh_norm_values on plot: {plot}')
        self.second_data_classes[plot][0].calibration_start = self.calibration_start_boxes[plot].value()
        self.second_data_classes[plot][0].calibration_end = self.calibration_end_boxes[plot].value()
        self.second_data_classes[plot][0].mes_start = self.norm_mes_start_boxes[plot].value()
        self.second_data_classes[plot][0].mes_end = self.norm_mes_end_boxes[plot].value()
        self.second_data_classes[plot][0].lim_distance = self.lim_distance_boxes[plot].value()
        y_ref = lambda data: self.second_data_classes[plot][0].refresh_y_ref(data)
        self.second_data_classes[plot][0].unconnect_receiver_from_y_ref.connect(
            lambda: unconnect(self.receiver.irf_measurement_ready, y_ref))
        self.receiver.irf_measurement_ready.connect(y_ref)
        self.second_data_classes[plot][0].block_norm_signals = True

    def start_receiver(self):
        """
        starts the udp-package receiver of the Receiver class instance and enables the buttons.

        :return: no return
        """
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
        """
        Called by stop_receive and will be needed when fpga-programming is added.
        Closes and resets the instance of the receiver class.

        :return: no return
        """
        self.plot_breaker(None, 0)
        self.plot_breaker(None, 1)
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
        """
        Refresh the ip and port values and labels in case they are changed.

        :return: no return
        """
        self.ip = self.ip1.text() + '.' + self.ip2.text() + '.' + self.ip3.text() + '.' + self.ip4.text()
        self.port = int(self.recport.text())
        self.sender_port = int(self.senport.text())
        self.ip_label.setText(f' IP:   {self.ip}')
        self.port_label.setText(f' Port: {self.port}')
        self.reconnect_receiver()

    def refresh_configuration(self):
        """
        Called when refresh_config button is clicked. Refreshes the configuration of both the Receiver and the
        SecondData instances

        :return: no return
        """
        self.plot_breaker(None, 0)
        self.plot_breaker(None, 1)
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

    def start_audio_player(self):
        """
        Called by the start_sound_button.

        Starts the sound in the SinSender instance.
        Connects irf_measurement_ready of the Receiver instance to distance_norm of the second SecondData instance.
        Connects the distance signal to self.set_distance_bar and self.set_audio_frequency.

        :return: no return
        """
        self.audio_player_running = True

        self.start_sound_button.setEnabled(False)
        self.plot_breaker(plot=1)
        self.refresh_norm_values(plot=1)
        self.receiver.irf_measurement_ready.connect(self.second_data_classes[1][0].distance_norm)
        self.second_data_classes[1][0].distance_ready.connect(self.set_distance_bar)
        self.second_data_classes[1][0].distance_ready.connect(self.set_audio_frequency)
        self.sinSender.start()
        self.stop_sound_button.setEnabled(True)

    def stop_audio_player(self):
        """
        Called by the stop_sound_button.

        Stops the sound and unconnects the connections from start_audio_player.

        :return: no return
        """
        self.stop_sound_button.setEnabled(False)
        self.sinSender.stop()
        unconnect(self.receiver.irf_measurement_ready, self.second_data_classes[1][0].distance_norm)
        unconnect(self.second_data_classes[1][0].distance_ready, self.set_distance_bar)
        unconnect(self.second_data_classes[1][0].distance_ready, self.set_audio_frequency)
        self.start_sound_button.setEnabled(True)

        self.audio_player_running = False

    def refresh_sound_values(self):
        """
        refreshes the values for the distanceToFrequency calculation in self.set_audio_frequency.

        :return: no return
        """
        self.sound_range_start = self.sound_bar_start_box.value()
        self.sound_range_stop = self.sound_bar_end_box.value()
        self.sound_button_number = self.button_number_box.value()
        self.first_sound_button = self.first_button_box.value()
        self.sound_range_length = self.sound_range_stop - self.sound_range_start
        self.sound_button_span = self.sound_range_length / (self.sound_button_number - 1)

    def magic_sound_values_refresh(self):
        """
        Called by the magic_finder button.

        Opens a dialog window with help of another UI file.
        Helps the user through the steps of determining the different sound options to program a piano keyboard.

        For more see class MagicValuesFinder in pams_functions.py

        :return: no return
        """
        if not self.audio_player_running:
            self.plot_breaker(plot=1)
            self.refresh_norm_values(plot=1)
            self.receiver.irf_measurement_ready.connect(self.second_data_classes[1][0].distance_norm)
        dialog = MagicValuesFinder(self, second_data=self.second_data_classes[1][0])
        dialog.exec()

        self.sound_range_start = dialog.start_value
        self.sound_range_stop = dialog.end_value
        self.sound_button_number = dialog.buttons
        self.first_sound_button = dialog.button0
        self.sound_range_length = self.sound_range_stop - self.sound_range_start
        self.sound_button_span = self.sound_range_length / (self.sound_button_number - 1)
        self.sound_bar_start_box.setValue(self.sound_range_start)
        self.sound_bar_end_box.setValue(self.sound_range_stop)
        self.button_number_box.setValue(self.sound_button_number)
        self.first_button_box.setValue(self.first_sound_button)

        logging.info(f'Magic finder values: \nstart: {dialog.start_value}, end: {dialog.end_value},'
                     f' buttons: {dialog.buttons}, button0: {dialog.button0}')

        if not self.audio_player_running:
            unconnect(self.receiver.irf_measurement_ready, self.second_data_classes[1][0].distance_norm)

    def set_audio_frequency(self, distance):
        """
        Called by signal distance_ready of second SecondData instance.

        Calculates the piano key frequency using the following function:

        https://en.wikipedia.org/wiki/Piano_key_frequencies

        n is determined using the function n = (distance - distanceKey0) / distanceBetweenKeys + keyNumber0.

        self.signal_filter is used so that the frequency is not changed too often.

        :param distance: provided by the signal SecondData.distance_ready()
        :return: no return
        """
        self.signal_filter += 1
        if self.signal_filter == 5:
            dist = distance[1]
            n = (dist - self.sound_range_start) / self.sound_button_span + self.first_sound_button
            freq = int(2**((n - 49) / 12)*440) if dist > 0 else 0
            self.freq_number.display(freq)
            self.sinSender.set_frequency(freq)
            self.dist_number.display(dist)
            self.signal_filter = 0

    def set_distance_bar(self, distance):
        """
        Called by signal SecondData.distanceReady()

        Sets the values of the distance bar in the audio tab

        :param distance: provided by signal SecondData.distanceReady()
        :return: no return
        """
        distance_span = self.sound_range_stop - self.sound_range_start
        self.distance_bar.setValue(int((distance[1]) / distance_span * 10000))

    def plot_sine(self, data):
        """
        Called by signal SineAudioEmitter.sin_ready().

        Sets the sine_wave plot to the sine graph of the audio tab if it is requested.

        :param data: provided by signal SineAudioEmitter.sin_ready()
        :return: no return
        """
        self.sine_line.setData(data[1], data[0])

    def sine_plot_starter(self):
        """
        Called by start_sine_plot_button.

        Refreshes the start and stop buttons and connects signal SineAudioEmitter.sin_ready() to plot.
        :return: no return
        """
        self.start_sine_plot_button.setEnabled(False)
        self.sinSender.sin_ready.connect(self.plot_sine)
        self.stop_sine_plot_button.setEnabled(True)

    def sine_plot_breaker(self):
        """
        Called by stop_sine_plot_button.

        Refreshes the start and stop buttons and disconnects signal SineAudioEmitter.sin_ready() from plot.
        :return: no return
        """
        self.stop_sine_plot_button.setEnabled(False)
        unconnect(self.sinSender.sin_ready, self.plot_sine)
        self.start_sine_plot_button.setEnabled(True)

    def only_changes_sine_refresher(self):
        """
        Called by only_changes_sine_box.

        Refreshes the requested plot mode of SineAudioEmitter
        :return: no return
        """
        if self.only_changes_sine_box.isChecked():
            self.sinSender.plot_mode = 1
        else:
            self.sinSender.plot_mode = 0

    def copy_norm_config(self, plot):
        """
        Called by one of the copy_norm_config buttons.

        Copies the configuration for normalization to the other plot.

        ~plot & 1 makes zero out of one and one out of zero
        :param plot: 0 or 1
        :return: no return
        """
        self.norm_mes_start_boxes[~plot & 1].setValue(self.norm_mes_start_boxes[plot].value())
        self.norm_mes_end_boxes[~plot & 1].setValue(self.norm_mes_end_boxes[plot].value())
        self.calibration_start_boxes[~plot & 1].setValue(self.calibration_start_boxes[plot].value())
        self.calibration_end_boxes[~plot & 1].setValue(self.calibration_end_boxes[plot].value())
        self.lim_distance_boxes[~plot & 1].setValue(self.lim_distance_boxes[plot].value())

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

    def lineedit_changed_log(self):
        if self.sender().objectName() != 'qt_spinbox_lineedit':
            line_edit = self.sender()
            info = line_edit.objectName(), line_edit.text()
            logging.info('')
            logging.info(f'QLineEdit {info[0]} changed to: {info[1]}')

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
        self.only_changes_sine_box.setChecked(True)
        if True:
            for i in self.findChildren(QSpinBox):
                self.settings.setValue(i.objectName(), i.value())
            for i in self.findChildren(QDoubleSpinBox):
                self.settings.setValue(i.objectName(), i.value())
            for i in self.findChildren(QLineEdit):
                self.settings.setValue(i.objectName(), i.text())
            for i in self.findChildren(QCheckBox):
                self.settings.setValue(i.objectName(), i.isChecked())
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
