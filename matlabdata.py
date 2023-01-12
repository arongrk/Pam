import matplotlib.pyplot as plt
import random
import time
'''
file = open('resources/ADCdata.txt')
data = file.read()
list_data = data.split("\n")
int_data = [int(i) for i in list_data]
x = [i for i in range(len(int_data))]

plt.ion()

figure, ax = plt.subplots(figsize=(10, 10))
line1, = ax.plot(x, list_data)

plt.yticks([i * 20000 for i in range(5)])
'''

st = time.time()
for i in range(100):
    n = random.randint(0, 1000)
    new_data = [int_data[i] + n for i in range(len(int_data))]

#    line1.set_xdata(x)
#    line1.set_ydata(new_data)
#    figure.canvas.draw()
#    figure.canvas.flush_events()
et = time.time()

t = et - st

print(t)
