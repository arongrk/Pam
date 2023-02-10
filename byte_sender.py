import os

import definitions
from hacker import Hacker

bytes_plot_len = definitions.PLOT_LENGTH
marker = definitions.MARKER_BYTES
byte_package_len = definitions.PACKAGE_LENGTH * 4


def sender():
    plot = bytearray()
    while True:
        plot += bytearray(os.urandom(bytes_plot_len * 4))
        plot += marker
        while len(plot) >= byte_package_len:
            yield plot[:byte_package_len]
            plot = plot[byte_package_len:]


def tester():
    g = sender()
    for i in range(10):
        b = next(g)
        print(len(b))


def create_receive():
    g = sender()

    def receive(*_):
        b = next(g)
        return b

    return receive


def test_hacker():
    hacker = Hacker(create_receive(), byte_package_len, bytes_plot_len)
    g = hacker.hack()
    for i in range(15):
        r = next(g)
        print(len(r))


if __name__ == '__main__':
    test_hacker()
