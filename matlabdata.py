import numpy as np
import random as rnd
import time as t
import numpy as np


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
    print(value)
    arrays = np.hsplit(array, value)
    for i in range(len(arrays)):
        if arrays[i][0] == split_value:
            arrays[i] = np.delete(arrays[i], 0)
    return arrays


def split_350(array, delete_non_complete=True):
    array_list = np.split(array, [i * 350 for i in range(1, int(len(array) / 350))])
    if not len(array_list[-1]) == 350 and delete_non_complete:
        array_list.pop(-1)
    return array_list



def check_length(array, ref_length):
    pass
