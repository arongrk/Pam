import csv
import os
import numpy as np

import definitions
from hacker import Hacker

bytes_plot_len = definitions.PLOT_LENGTH * 4
marker = definitions.MARKER_BYTES
byte_package_len = definitions.PACKAGE_LENGTH * 4


def sender():
    plot = bytearray()
    while True:
        plot += bytearray(os.urandom(bytes_plot_len))
        plot += marker
        while len(plot) >= byte_package_len:
            yield plot[:byte_package_len]
            plot = plot[byte_package_len:]


def real_sender():
    file = open('resources/test_data.csv', newline='')
    data_reader = csv.reader(file, delimiter=' ')
    array = b''
    for i in range(100000):
        array += np.array(float(data_reader.__next__()[0])).tobytes()
    print('array created, markers found at: ', array.find(marker))
    safe = array
    print('array copied')
    while True:
        array += safe
        while len(array) >= byte_package_len:
            yield array[:byte_package_len]
            print('array yielded')
            array = array[byte_package_len:]


def tester():
    g = real_sender()
    for i in range(2000000):
        b = next(g)
        print(len(b))


def create_receive():
    g = sender()

    def receive(*_):
        b = next(g)
        return b

    return receive


def create_real_receive():
    g = real_sender()

    def receive(*_):
        b = next(g)
        return b

    return receive


def test_hacker():
    hacker = Hacker(create_real_receive(), byte_package_len, bytes_plot_len)
    g = hacker.hack()
    for i in range(15):
        r = next(g)
        print(len(r)/4)


if __name__ == '__main__':
    test_hacker()
