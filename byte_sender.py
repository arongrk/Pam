import csv
import os
import socket

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


def real_sender(sock):
    while True:
        data = sock.recv(1400)
        yield data


def tester():
    g = real_sender()
    for i in range(2000000):
        b = next(g)
        print(len(b))


def create_receive(sender):
    g = sender

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
