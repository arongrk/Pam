import numpy as np
import random as rnd
import time as t
import numpy as np
import socket


def load_adc():
    file = open('resources/ADCdata.txt')
    data = file.read()
    list_data = data.split("\n")
    int_data = [int(i) for i in list_data]
    numpy_data = np.array(int_data)
    return numpy_data


def load_fpga():
    file = open('resources/FPGAdata.txt')
    data = file.read()
    list_data = data.split("\n")
    int_data = [int(i) for i in list_data]
    numpy_data = np.array(int_data)
    return numpy_data


def split_data(array, split_value):
    value = np.where(array == split_value)[0]
    arrays = np.hsplit(array, value)
    for i in range(len(arrays)):
        try:
            if arrays[i][0] == split_value:
                arrays[i] = np.delete(arrays[i], 0)
        except IndexError:
            if arrays[1][0] == split_value:
                arrays[1] = np.delete(arrays[1], 0)
    return arrays


def split_350(array, delete_non_complete=True):
    array_list = np.split(array, [i * 350 for i in range(1, int(len(array) / 350))])
    if not len(array_list[-1]) == 350 and delete_non_complete:
        array_list.pop(-1)
    return array_list



def check_length(array, ref_length):
    pass


# def socket_receiver(UDP_IP : str, UDP_PORT : int)
#     sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     sock.bind((UDP_IP, UDP_PORT))
#     while True:
#         data, addr = sock.recvfrom(1400)
#         package = np.frombuffer(data, dtype=np.int32)
#         yield package