import numpy as np

import matplotlib.pyplot as plt
import random
import time
import numpy as np


def load_ABC():
    file = open('resources/ADCdata.txt')
    data = file.read()
    list_data = data.split("\n")
    int_data = [int(i) for i in list_data]
    numpy_data = np.array(int_data)
    return numpy_data


if __name__ == '__main__':
    plt.ion()

    figure, ax = plt.subplots(figsize=(10, 10))
    line1, = ax.plot(numpy_data, list_data)

    plt.yticks([i * 20000 for i in range(5)])


    st = time.time()
    for i in range(100):
        n = random.randint(0, 1000)
        new_data = [numpy_data[i] + n for i in range(len(numpy_data))]

        # line1.set_xdata(x)
        #line1.set_ydata(new_data)
        #figure.canvas.draw()
        #figure.canvas.flush_events()

    et = time.time()

    t = et - st

    print(t)
