import ast
import pickle
import time
import inspect
import numpy as np
from math import trunc

from scipy.fft import fft, ifft
from scipy.interpolate import BarycentricInterpolator as bary
from scipy.constants import speed_of_light
from scipy.signal.windows import hann

import PyQt5
from PyQt5.QtCore import QPointF
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


def averager(data_set, shifts, samples_per_sequence, sequence_reps):
    s = shifts
    t = samples_per_sequence
    u = sequence_reps
    data = np.average(data_set.reshape((s*u, t))[1::u], axis=1)
    return data


def unconnect(signal, old_slot):
    try:
        while True:
            signal.disconnect(old_slot)
    except TypeError:
        pass


def zero_padding(t, y, fLim, NZP, norm=False, YRef=None, return_distance=False):
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
    if return_distance:
        tData *= speed_of_light/2
    return tData, yData


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
                             interval: slice=None):

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
    m = np.argmax(y[interval]) + interval.start
    m_i = [m-1, m, m+1]


    # load the x and y values into x_ and y_
    x_ = [t[m_i[0]], t[m_i[1]], t[m_i[2]]]
    y_ = [y[m_i[0]], y[m_i[1]], y[m_i[2]]]

    # Create the numpy arrays as basis for the equations
    x_array = np.array(([1, x_[0], x_[0]**2], [1, x_[1], x_[1]**2], [1, x_[2], x_[2]**2]))

    # Solve for the prefactors for 1, x and x²
    factors = np.linalg.solve(x_array, y_)

    # Get the first differentiation
    x = -factors[1]/(factors[2]*2)

    # Return the time if not asked for speed:
    if get_distance:
        x_value = x / 2 * speed_of_light - cable_constant
    else:
        x_value = x
    if get_y:
        return x_value, factors[2]*(x**2)+factors[1]*x+factors[0]
    else:
        return x_value


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


    pass
