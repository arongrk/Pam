import ast
import logging
import pickle
import socket
import time
import inspect
from collections import deque

import numpy as np
from math import trunc, ceil

from PyQt5 import uic
from PyQt5.QtWidgets import QDialog
from scipy.fft import fft, ifft
from scipy.interpolate import BarycentricInterpolator as bary
from scipy.constants import speed_of_light
from scipy.signal.windows import hann
from scipy.signal import argrelmax

import PyQt5
from PyQt5.QtCore import QPointF, QSizeF, QTimer, pyqtSignal, QObject, QThread, Qt
from pyqtgraph import AxisItem


class Handler:

    def __init__(self, receive, package_length=350, shifts=1280,
                 samples_per_sequence=16, sequence_reps=2, marker=b'\xff\xff\xff\xaa'):
        self.sock = receive
        self.pack_len = package_length
        self.shifts = shifts
        self.sps = samples_per_sequence
        self.s_reps = sequence_reps
        self.marker = marker
        self.raw_len = self.shifts * self.sps * self.s_reps

    def assembler(self):
        sock = self.sock
        byte_pack_len = self.pack_len * 4
        byte_raw_len = self.raw_len * 4
        marker = self.marker
        marker_len = len(marker)
        buffer = bytearray()
        t0 = time.time()
        data = bytearray(byte_pack_len)
        while True:
            data = sock.recv(byte_pack_len)
            pos = data.find(marker)
            if pos == -1:
                buffer += data
            else:
                buffer += data[:pos]
                if len(buffer) == byte_raw_len:
                    yield buffer
                else:
                    yield
                buffer = bytearray()
                buffer += data[pos + marker_len:]

    def assembler_2(self):
        sock = self.sock
        byte_pack_len = self.pack_len * 4
        byte_raw_len = self.raw_len * 4
        marker = self.marker
        marker_len = len(marker)
        buffer_len = byte_raw_len * 2
        buffer = bytearray(buffer_len)
        mem_buffer = memoryview(buffer)
        pointer = 0
        while True:
            # WARNING: Did not tested this.
            # receive bytes up to the remaining length of the buffer
            sock.recv_into(mem_buffer[pointer:])
            # optionally: here could be checked if n_received == byte_packLen
            if pointer >= buffer_len - 2 * byte_pack_len:
                # print(f"Buffer overflow, no marker after 200000 bytes received")
                pointer = 0
                continue
            # find the marker if it is there, pos will be relative to pointer
            pos = buffer[pointer:pointer + byte_pack_len].find(marker)
            if pos != -1 and (pointer + pos) / 4 == int((pointer + pos) / 4):
                # marker was found
                # compute the bytes behind the marker
                remaining = byte_pack_len - (pos + marker_len)
                if pointer + pos == byte_raw_len:
                    #  received bytes have correct length up to here, yield 'em
                    yield mem_buffer[0:pointer+pos]
                else:
                    # print a message about discarded bytes
                    # print(f"Discarding {pointer+pos} bytes of data")
                    yield
                # Make sure the marker was not at the end of last received package
                if remaining > 0:
                    # Copy the remaining bytes to the beginning of the buffer
                    mem_buffer[0:remaining] = mem_buffer[pointer + pos + marker_len:pointer + byte_pack_len]
                # set the pointer behind the remaining data
                pointer = remaining
            else:
                # no marker found, simply advance the pointer
                pointer += byte_pack_len


class SecondData(QObject):

    # Signals for SecondData
    if True:
        measurement_ready = pyqtSignal(tuple)
        irf_measurement_ready = pyqtSignal(tuple)
        distance_ready = pyqtSignal(tuple)
        irf_interp_ready = pyqtSignal(tuple)
        unconnect_receiver_from_y_ref = pyqtSignal()

    def __init__(self, samples_per_sequence: int, shifts: int, sequence_reps: int, length: int,
                 cable_length_constant: float, norm_measurement_start: float, norm_measurement_end: float,
                 calibration_start: float, calibration_end: float, distance_limit: int, x_data_request: str):

        QObject.__init__(self)

        self.sps = samples_per_sequence
        self.shifts = shifts
        self.sr = sequence_reps
        self.mes_len = length

        self.cable_constant = cable_length_constant

        self.lim_distance = distance_limit

        self.calibration_start = calibration_start
        self.calibration_end = calibration_end

        self.mes_start = norm_measurement_start
        self.mes_end = norm_measurement_end

        self.x_data_request = x_data_request

        self.YRefPos = np.array([])

        self.idx_start, self.idx_stop = None, None

        self.block_norm_signals = False

    def raw_data(self, data):
        match self.x_data_request:
            case 'time':
                self.measurement_ready.emit((data[0], data[1]))
            case 'distance':
                self.measurement_ready.emit((data[0]*speed_of_light/2, data[1]))
            case 'value no.':
                self.measurement_ready.emit((np.arange(len(data[1])), data[1]))

    def irf_data(self, data):
        match self.x_data_request:
            case 'time':
                self.irf_measurement_ready.emit((data[0], data[1]))
            case 'distance':
                self.irf_measurement_ready.emit((data[0]*speed_of_light/2, data[1]))
            case 'value no.':
                self.irf_measurement_ready.emit((np.arange(len(data[1])), data[1]))

    def distance(self, data):
        t = data[2]
        data = zero_padding(data[0], data[1], 2.5e+09, 2**5*self.shifts)
        exact_max = exact_polynom_interp_max(data[0], np.absolute(data[1]), True, self.cable_constant)
        match self.x_data_request:
            case 'duration':
                self.distance_ready.emit((t, exact_max[0], exact_max[1]))
            case 'time' | 'value no.':
                logging.warning(f'when y-data is \"distance\" x-data cannot be {self.x_data_request}')

    def irf_interp(self, data):
        match self.x_data_request:
            case 'time':
                data = zero_padding(data[0], data[1], 2.5e+09, 2**5*self.shifts)
            case 'value no.':
                data = zero_padding(data[0], data[1], 2.5e+09, 2**5*self.shifts, t_data_returned=2)
            case 'distance':
                data = zero_padding(data[0], data[1], 2.5e+09, 2**5*self.shifts, t_data_returned=1)
        exact_max = exact_polynom_interp_max(data[0], np.absolute(data[1]), False)
        self.irf_interp_ready.emit((data[0], data[1], exact_max))

    def irf_interp_norm(self, data):
        if not self.block_norm_signals:
            match self.x_data_request:
                case 'time':
                    data = zero_padding(data[0], data[1], 2.5e+09, 2 ** 5 * self.shifts, True, self.YRefPos, 0)
                    idx_start = np.argwhere(data[0] > self.mes_start/speed_of_light*2)[0][0]
                    idx_stop = np.argwhere(data[0] > self.mes_end/speed_of_light*2)[0][0]
                case 'distance':
                    data = zero_padding(data[0], data[1], 2.5e+09, 2 ** 5 * self.shifts, True, self.YRefPos, 1)
                    idx_start = np.argwhere(data[0] > self.mes_start)[0][0]
                    idx_stop = np.argwhere(data[0] > self.mes_end)[0][0]
                case 'value no.':
                    data = zero_padding(data[0], data[1], 2.5e+09, 2 ** 5 * self.shifts, True, self.YRefPos, 1)
                    idx_start = np.argwhere(data[0] > self.mes_start)[0][0]
                    idx_stop = np.argwhere(data[0] > self.mes_end)[0][0]
                    data = (np.arange(len(data[1])), data[1])
            exact_max = exact_polynom_interp_max(data[0],
                                                 np.absolute(data[1]),
                                                 get_y=True,
                                                 interval=slice(idx_start, idx_stop))
            self.irf_interp_ready.emit((data[0], data[1], exact_max[0], exact_max[1]))

    def distance_norm(self, data):
        if not self.block_norm_signals:
            t = data[2]
            data = zero_padding(data[0], data[1], 2.5e+09, 2 ** 5 * self.shifts, True, self.YRefPos)
            idx_start = np.argwhere(data[0] > self.mes_start/speed_of_light*2)[0][0]
            idx_stop = np.argwhere(data[0] > self.mes_end/speed_of_light*2)[0][0]
            exact_max = exact_polynom_interp_max(data[0],
                                                 np.absolute(data[1]),
                                                 get_distance=True,
                                                 get_y=True,
                                                 interval=slice(idx_start, idx_stop),
                                                 negative_constant=self.mes_start)

            logging.info(f'idx_start: {idx_start}, idx_stop: {idx_stop}')
            if exact_max[1] < self.lim_distance:
                self.distance_ready.emit((t, 0))
            else:
                self.distance_ready.emit((t, exact_max[0]))

    def return_functions(self):
        return self.raw_data, self.irf_data, self.distance, self.irf_interp,  self.irf_interp_norm, self.distance_norm

    def refresh_y_ref(self, data):
        self.unconnect_receiver_from_y_ref.emit()
        self.refresh_idx_lim(data)
        yData = data[1]
        tData = data[0]
        cal_start = np.argwhere(tData > self.calibration_start/speed_of_light*2)[0][0]
        cal_end = np.argwhere(tData > self.calibration_end/speed_of_light*2)[0][0]
        yData[:cal_start] = 0
        yData[cal_start-11:cal_start] = np.linspace(0, yData[cal_start], 11)
        yData[cal_end:cal_end+11] = np.linspace(yData[cal_start], 0, 11)
        yData[cal_end+11:] = 0
        Ly = len(yData)
        YRefTemp = fft(yData, Ly) / Ly
        self.YRefPos = YRefTemp[0:trunc(Ly / 2) + 1]
        self.block_norm_signals = False

    def refresh_idx_lim(self, data):
        self.idx_start = np.argwhere(data[0] > self.mes_start/speed_of_light*2)[0][0]
        self.idx_stop = np.argwhere(data[0] > self.mes_end/speed_of_light*2)[0][0]
        logging.info(f'idx_start: {self.idx_start}, idx_stop: {self.idx_stop}')


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


def averager(data_set, shifts, samples_per_sequence, sequence_reps):
    s = shifts
    t = samples_per_sequence
    u = sequence_reps
    data = np.average(data_set.reshape((s*u, t))[1::u], axis=1)
    return data


def unconnect(signal, old_slot):
    '''

    :param signal:
    :param old_slot:
    :return:
    '''
    while True:
        try:
            signal.disconnect(old_slot)
        except TypeError:
            break


def zero_padding(t, y, fLim, NZP, norm=False, YRef=None, t_data_returned=0):
    '''
    parameters:

    * t:        a t-data array
    * y:        a y-data array with len(t)
    * fLim:     frequency limit
    * NZP
    * norm:     whether a normation should be applied, requires YRef
    * YRef:     Null-measurement for the normation
    * t_data_returned: returns different t-data arrays depending on the number:

      * 0: time
      * 1: distance
      * 2: value number


    '''
    if norm and YRef is None:
        raise ValueError('YRef is required when using norm!')

    Ly = len(y)

    fs = 1/(t[1]-t[0])
    df = fs/Ly
    f = np.arange(0, trunc(Ly/2))*df
    LidxLim = sum(f<=fLim)
    idxLim = np.arange(0, LidxLim)
    fWindCal = f[idxLim]

    # Tp = 1/(2*(LidxLim-1))/df

    Ytemp = fft(y, Ly)/Ly
    YPos = Ytemp[0:trunc(Ly/2)+1]

    window = hann(2*LidxLim-1)

    if norm:
        YPos /= YRef

    YZP = np.zeros(NZP, dtype=np.complex_)
    YPos[1:-1] = 2 * YPos[1:-1]
    YZP[idxLim] = YPos[idxLim] * window[LidxLim-1:]
    yData = np.real(ifft(YZP)*NZP)
    tData = (np.arange(0, NZP) / fs * Ly/NZP + t[0])
    match t_data_returned:
        case 0:
            return tData, yData
        case 1:
            return tData * speed_of_light/2, yData
        case 2:
            return np.arange(len(yData)), yData


def polynom_interp_max(t, y, accuracy: int):
    max_values_index = np.sort(np.argsort(y)[-3:])
    interp = bary(t[max_values_index], y[max_values_index])
    steps = np.arange(t[max_values_index[0]], t[max_values_index[2]], (t[2]-t[1])/accuracy)
    exact_maximum = steps[interp(steps).argmax()]
    return exact_maximum


def exact_polynom_interp_max(t_data,
                             y_data,
                             get_distance: bool = False,
                             get_y: bool = False,
                             cable_constant=0,
                             interval: slice = None,
                             negative_constant: float = 0):

    if np.shape(t_data) != np.shape(y_data):
        raise ValueError('t_data and y_data are not the same shape!')

    if not interval:
        interval = slice(0, len(y_data))
    else:
        if type(interval) != slice:
            raise TypeError('intervall is not type slice')
        elif interval.stop > len(y_data):
            raise ValueError('intervall is out of range')

    t, y = t_data, y_data

    # Get the sorted indexes of the three highest y-Values
    e_i = argrelmax(y[interval])[0] + interval.start
    m = e_i[np.argmax(y[e_i])]
    m_i = [m-1, m, m+1]                                         # if m != 0 else [m, m+1, m+2]


    # load the x and y values into x_ and y_
    x_ = [t[m_i[0]], t[m_i[1]], t[m_i[2]]]
    y_ = [y[m_i[0]], y[m_i[1]], y[m_i[2]]]

    # Create the numpy arrays as basis for the equations
    x_array = np.array(([1, x_[0], x_[0]**2], [1, x_[1], x_[1]**2], [1, x_[2], x_[2]**2]))

    # Solve for the prefactors for 1, x and x²
    factors = np.linalg.solve(x_array, y_)

    # Get the first differentiation
    x = -factors[1]/(factors[2]*2)

    # Return the time if not asked for distance:
    if get_distance:
        x_value = x / 2 * speed_of_light - cable_constant
    else:
        x_value = x

    # Return the y-coordinate of the maximum as a second value
    if get_y:
        return x_value - negative_constant, factors[2]*(x**2)+factors[1]*x+factors[0]
    else:
        return x_value - negative_constant


def change_dict(dictionary: dict, *args):
    d = dictionary
    k_list = list(d.keys())
    if len(d) != len(args):
        raise ValueError(f'Dictionary length and argument count must be the same, found: {len(d), len(args)}')
    else:
        for i in range(len(args)):
            d[k_list[i]] = args[i]
        return d


def compare_sender(sender: PyQt5.QtCore.QObject, names: tuple, print_sender_if_none: bool = False):
    name = sender.sender().objectName()
    n = 0
    for i in names:
        if type(i) is not str:
            # print(f'i: {i}, type(i): {type(i)}, n: {n}')
            raise ValueError(f'expected tuple of strings, got {names} with type {type(names)} instead.')
        if i == name:
            return n
        n += 1
    if print_sender_if_none:
        print(f'real sender was: {name}')
    return None


def change_pickled_data(location='resources/configurations.bin',
                        values=None):
    if values is None:
        values = dict(shifts=0, samples_per_sequence=0, sequence_reps=0, length=0, last_values1=0,
                      last_values2=0, cable_length_constant=0)
    new_values = None
    with open(location, 'r+b') as file:
        try:
            values = pickle.load(file)
        except EOFError:
            values = values
        keys = values.keys()
        print('Leave empty to keep the current value')
        for key in keys:
            new = input(f'{key}({values[key]}):')
            if len(new) > 0:
                new = ast.literal_eval(new)
                match new:
                    case str():
                        values[key] = int(new)
                    case _:
                        values[key] = new
        add_keys =  input('Do you want to add any keys? (y/n): ')
        if add_keys == 'y' or add_keys == 'Y':
            while True:
                key = input('Key: ')
                if len(key) == 0:
                    break
                value = ast.literal_eval(input('Value: '))
                values[key] = value
        keys = values.keys()
        change_keys = input('Do you want to change any keywords? (y/n): ')
        if change_keys == 'y' or change_keys == 'Y':
            print('Leave empty to keep the current key')
            addables = list()
            deletables = list()
            for key in keys:
                new = input(f'{key}: ')
                if len(new) > 0:
                    addables.append(new)
                    deletables.append(key)
            for i in range(len(addables)):
                values[addables[i]] = values[deletables[i]]
                del values[deletables[i]]
        delete_keys = input('Do you want to delete any keys? (y/n): ')
        if delete_keys == 'y' or delete_keys == 'Y':
            print('Leave empty to skip')
            while True:
                key = input('Enter the keyword to delete from the dict: ')
                if len(key) == 0:
                    break
                del values[key]
        new_values = values
    with open(location, 'wb') as file:
        pickle.dump(new_values, file)


def check_args(func, arg, return_other_args=False, removable_item=None):
    args = inspect.getfullargspec(func).args
    try:
        args.remove(removable_item)
    except ValueError:
        pass
    try:
        args.remove(arg)
        return (True, args) if return_other_args else True
    except ValueError:
        return (False, None) if return_other_args else False


class MagicValuesFinder(QDialog):
    timer_ready = pyqtSignal()

    def __init__(self, parent=None, second_data: SecondData = None):
        super().__init__(parent)
        uic.loadUi('resources/magic_finder_dialogue.ui', self)

        self.maximum_page = 0

        self.timer = QTimer()
        self.remaining_time = 0
        self.timer.timeout.connect(self.update_timer)

        self.next_button.clicked.connect(self.next_page)
        self.previous_button.clicked.connect(self.previous_page)
        self.start_button.clicked.connect(self.start)
        self.start_next_button1.clicked.connect(self.start)
        self.confirm_button.clicked.connect(self.confirm_buttons)
        self.confirm_and_exit_button.clicked.connect(self.confirm_exit)

        self.second_data = second_data
        self.data_array = deque()

        self.start_value = 0
        self.end_value = 0
        self.buttons = 0
        self.button0 = 0

        self.stacked_widget.currentChanged.connect(self.change_page_number)

    def collect_data(self, data):
        self.data_array.append(data[1])

    def start(self):
        page = self.stacked_widget.currentIndex()

        self.stacked_widget.setCurrentIndex(page + 1)
        self.maximum_page = page + 1

        self.remaining_time = 3
        self.timer.start(1000)
        self.timer.timeout.connect(self.time_label_text)
        self.timer_ready.connect(lambda: unconnect(self.timer.timeout, self.time_label_text))
        self.timer_ready.connect(self.mes_start)

    def mes_start(self):
        unconnect(self.timer_ready, self.mes_start)

        page = self.stacked_widget.currentIndex()

        match page:
            case 1:
                self.p1_label1.setText('')
                self.p1_label2.setText('Hold!')
            case 4:
                self.p3_label1.setText('')
                self.p3_label2.setText('Hold!')

        self.second_data.distance_ready.connect(self.collect_data)

        self.remaining_time = 1
        self.timer.start(1000)
        self.timer_ready.connect(self.mes_end)

    def mes_end(self):
        unconnect(self.second_data.distance_ready, self.collect_data)
        unconnect(self.timer_ready, self.mes_end)

        page = self.stacked_widget.currentIndex()

        array = np.array(self.data_array)
        self.data_array.clear()

        match page:
            case 1:
                self.stacked_widget.setCurrentIndex(2)

                self.start_value = np.average(np.average(array))
                self.start_value_box.setValue(self.start_value)

                self.maximum_page = 3
                self.previous_button.setEnabled(True)
                self.next_button.setEnabled(True)
            case 4:
                self.stacked_widget.setCurrentIndex(5)

                self.end_value = np.average(np.average(array))
                self.end_value_box.setValue(self.end_value)

                self.maximum_page = 6
                self.next_button.setEnabled(True)

    def time_label_text(self):
        page = self.stacked_widget.currentIndex()
        if page == 1:
            self.p1_label2.setText(str(self.remaining_time))
        if page == 4:
            self.p3_label2.setText(str(self.remaining_time))

    def confirm_buttons(self):
        if round(self.start_value, 2) != self.start_value_box.value():
            self.start_value = self.start_value_box.value()
        if round(self.end_value, 2) != self.end_value_box.value():
            self.end_value = self.end_value_box.value()

        self.start_value_box2.setValue(self.start_value_box.value())
        self.end_value_box2.setValue(self.end_value_box.value())
        self.button_number_box2.setValue(self.button_number_box.value()+2)
        self.null_button_box2.setValue(self.null_button_box.value())

        self.stacked_widget.setCurrentIndex(7)
        self.maximum_page = 7

    def confirm_exit(self):
        if round(self.start_value, 2) != self.start_value_box2.value():
            self.start_value = self.start_value_box2.value()
        if round(self.end_value, 2) != self.end_value_box2.value():
            self.end_value = self.end_value_box2.value()
        self.buttons = self.null_button_box2.value()
        self.button0 = self.button_number_box2.value()
        self.accept()
        # self.close()

    def next_page(self):
        self.previous_button.setEnabled(True)
        index = self.stacked_widget.currentIndex()

        match index:
            case 0:
                self.stacked_widget.setCurrentIndex(2)
            case 3:
                self.stacked_widget.setCurrentIndex(5)
            case _:
                self.stacked_widget.setCurrentIndex(index + 1)

        if self.stacked_widget.currentIndex() in (self.stacked_widget.count()-1, self.maximum_page):
            self.next_button.setEnabled(False)

    def previous_page(self):
        self.next_button.setEnabled(True)
        index = self.stacked_widget.currentIndex()

        match index:
            case 2:
                self.stacked_widget.setCurrentIndex(0)
            case 5:
                self.stacked_widget.setCurrentIndex(3)
            case _:
                self.stacked_widget.setCurrentIndex(index - 1)

        if self.stacked_widget.currentIndex() == 0:
            self.previous_button.setEnabled(False)

    def change_page_number(self):
        index = self.stacked_widget.currentIndex()
        if index not in (1, 4):
            self.page_number.setText(f'{index+1}/{self.stacked_widget.count()}')
        else:
            self.page_number.setText('')

    def update_timer(self):
        self.remaining_time -= 1
        if self.remaining_time == 0:
            self.timer.stop()
            self.timer_ready.emit()

    def close(self):
        super().close()
        return 'the values are here to come'


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


if __name__ == '__main__':
    # tries = 1000
    # t0 = time.time()
    # for i in range(tries):
    #     maximum = polynomial_interpolation([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1],
    #                                        [1, 1, 1, 6, 8, 7, 1, 1, 1, 1])
    # print((time.time()-t0) / tries * 1000, maximum)
    test_dict = {'name': 'bron', 'age': 18, 'height': 195}
    test_dict_c = change_dict(test_dict, 1, 2, 3)
    print(test_dict_c)
