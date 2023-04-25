import time
from socket import *
import numpy as np
from math import trunc
from scipy.fft import fft, ifft
from scipy.interpolate import BarycentricInterpolator as bary
from scipy.constants import speed_of_light
from PyQt5.QtNetwork import QUdpSocket

import definitions


class Handler:

    def __init__(self, receive: QUdpSocket, package_length=350, shifts=1280,
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


def zero_padding(t, y, fLim, NZP):
    Ly = len(y)
    fs = 1/(t[1]-t[0])
    df = fs/Ly
    f = np.arange(0, trunc(Ly/2))*df
    LidxLim = sum(f <= fLim)
    idxLim = np.arange(0, LidxLim)
    fWindCal = f[idxLim]

    # Tp = 1/(2*(LidxLim-1))/df


    Ytemp = np.real(fft(y, Ly))/Ly
    YPos = Ytemp[0:trunc(Ly/2)+1]

    YZP = np.zeros(np.real(NZP))
    YPos[1:-1] = 2 * YPos[1:-1]
    YZP[idxLim] = YPos[idxLim]

    yData = np.real(ifft(YZP)*NZP)
    tData = (np.arange(0, NZP) / fs * Ly/NZP + t[1])

    return tData, yData


def polynom_interp_max(t, y, accuracy: int):
    max_values_index = np.sort(np.argsort(y)[-3:])
    interp = bary(t[max_values_index], y[max_values_index])
    steps = np.arange(t[max_values_index[0]], t[max_values_index[2]], (t[2]-t[1])/accuracy)
    exact_maximum = steps[interp(steps).argmax()]
    return exact_maximum


def exact_polynom_interp_max(t_data, y_data):
    if np.shape(t_data) != np.shape(y_data):
        raise ValueError('t_data and y_data are not the same shape!')

    t, y = t_data, y_data

    # Get the sorted indexes of the three highest y-Values
    m_i = np.sort(np.argsort(y)[-3:])

    # load the x and y values into x_ and y_
    x_ = [t[m_i[0]], t[m_i[1]], t[m_i[2]]]
    y_ = [y[m_i[0]], y[m_i[1]], y[m_i[2]]]

    # Create the numpy arrays as basis for the equations
    x_array = np.array(([1, x_[0], x_[0]**2], [1, x_[1], x_[1]**2], [1, x_[2], x_[2]**2]))

    # Solve for the prefactors for 1, x and x²
    factors = np.linalg.solve(x_array, y_)

    # Get the first differentiation
    x = -factors[1]/(factors[2]*2)
    x = x/2 * speed_of_light - 2.9011
    return x


def change_dict(dictionary: dict, *args):
    d = dictionary
    k_list = list(d.keys())
    if len(d) != len(args):
        raise ValueError(f'Dictionary length and args must be the same, found: {len(d), len(args)}')
    for i in range(len(args)):
        d[k_list[i]] = args[i]
    return d



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
