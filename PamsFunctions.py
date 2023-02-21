import time
from socket import *
import numpy as np

import definitions


class Handler:

    def __init__(self, receive: socket, package_length=350, shifts=1280,
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
        data = bytearray(1400)
        while True:
            data = sock.recv(1400)
            pos = data.find(marker)
            if pos == -1:
                buffer += data
            else:
                buffer += data[:pos]
                if len(buffer) == byte_raw_len:
                    yield buffer
                else:
                    print(len(buffer))
                buffer = bytearray()
                buffer += data[pos + marker_len:]

    def assembler_2(self):
        sock = self.sock
        byte_pack_len = self.pack_len * 4
        byte_raw_len = self.raw_len * 4
        marker = self.marker
        marker_len = len(marker)
        buf = bytearray()
        buffer = memoryview(buf)
        t0 = time.time()
        pointer = 0
        while True:
            length = sock.recv_into(buffer[pointer:])
            if length != 1400:
                print('False Package!')
            pointer += byte_pack_len
            pos = buf[pointer:pointer+byte_pack_len].find(marker)
            if pos != -1:
                expected_pos = pos + byte_raw_len + 4


def averager(data_set: bytes):
    data = np.average(np.frombuffer(data_set, np.int32).reshape((2560, 16))[1::2], axis=1)
    return data


def create_receive(receiver):
    sock = receiver
    def receive(*_):
        data = sock.recv(1400)
        yield data


