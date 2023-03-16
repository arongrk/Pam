import time
from socket import *
import numpy as np
from PyQt5.QtCore import *
from PyQt5.QtGui import *

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
