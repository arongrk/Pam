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
                    yield
                buffer = bytearray()
                buffer += data[pos + marker_len:]

    def assembler_2(self):
        sock = self.sock
        byte_pack_len = self.pack_len * 4
        byte_raw_len = self.raw_len * 4
        marker = self.marker
        marker_len = len(marker)
        buffer = bytearray(200000)
        mem_buffer = memoryview(buffer)
        pointer = 0
        while True:
            # WARNING: Did not tested this.
            # receive bytes up to the remaining length of the buffer
            n_received = sock.recv_into(mem_buffer[pointer:])
            # optionally: here could be checked if n_received == byte_packLen
            if pointer + n_received == 200000:
                print(f"Buffer overflow, no marker after 200000 bytes received")
                pointer = 0
                continue
            # find the marker if it is there, pos will be relative to pointer
            pos = buffer[pointer:pointer + n_received].find(marker)
            if pos != -1:
                # marker was found
                # compute the bytes behind the marker
                remaining = n_received - (pos + marker_len)
                if pointer + pos == byte_raw_len:
                    #  received bytes have correct length up to here, yield 'em
                    yield mem_buffer[0:pointer+pos]
                else:
                    # print a message about discarded bytes
                    print(f"Discarding {pointer+pos} bytes of data")
                # Make sure the marker was not at the end of last received package
                if remaining > 0:
                    # Copy the remaining bytes to the beginning of the buffer
                    mem_buffer[0:remaining] = mem_buffer[pointer + pos + marker_len:pointer + n_received]
                # set the pointer behind the remaining data
                pointer = remaining
            else:
                # no marker found, simply advance the pointer
                pointer += n_received


def averager(data_set: bytes, shifts, samples_per_sequence, sequence_reps):
    s = shifts
    t = samples_per_sequence
    u = sequence_reps
    data = np.average(data_set.reshape((s*u, t))[1::u], axis=1)
    return data


def create_receive(receiver):
    sock = receiver
    def receive(*_):
        data = sock.recv(1400)
        yield data


