import socket
import numpy as np

import definitions


class Handler:

    def __init__(self, receive:socket.socket, package_length=350, shifts=1280,
                 samples_per_sequence=16, sequence_reps=2, marker=b'\xaa\xff\xff\xff'):
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
        while True:
            data = sock.recv(byte_pack_len)
            pos = data.find(marker)
            if pos == -1:
                buffer += data
            else:
                buffer += data[:pos]
                if len(buffer) == byte_raw_len:
                    yield buffer
                buffer = bytearray()
                buffer += data[pos + marker_len:]


def averager(data: bytes, shifts: int, samples_per_sequence: int, sequence_reps: int):
    data = data
    shifts = shifts
    sps = samples_per_sequence
    sr = sequence_reps
    avg_data = np.zeros(shifts)
    for i in range(shifts):
        avg = 0
        for j in range(sps*(sr*(i+1)-1), (sps*sr*(i+1))):
            avg += data[4*j:4*(j+1)]
        avg_data[i] = avg/sps
    return avg_data
