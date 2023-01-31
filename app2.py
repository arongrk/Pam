import socket
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from pyqtgraph import *
from ctypes import c_int32
import numpy as np
import random as rnd
import time as t


UDP_IP = '192.168.1.1'
UDP_PORT = 9090

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
a=0
time = t.time()

while True:
    st = t.time()
    data, addr = sock.recvfrom(1400)
    # encoded_data = data.decode('utf32-sig')
    # print(type(data))
    # print(1)
    package = np.frombuffer(data, dtype=np.int32)
    marker = np.where(package == c_int32(0xaaffffff).value)
    if len(marker[0]) == 0:
        a += 1
    else:
        print(f'marker at position {marker[0]} after {a} packages/ {t.time() - time} seconds')
        a = 0
        time = t.time()
        print(package)
        break