import socket
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from pyqtgraph import *
from ctypes import c_int32
import numpy as np
import random as rnd



UDP_IP = '192.168.1.1'
UDP_PORT = 9090

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))

while True:
    data, addr = sock.recvfrom(10000)
    print(data)