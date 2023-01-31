import numpy as np
import socket
import matplotlib.pyplot as plt
from ctypes import c_int32

import matlabdata

UDP_IP = '192.168.1.1'
UDP_PORT = 9090
plot_length = 9890
marker = c_int32(0xaaffffff).value
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((UDP_IP, UDP_PORT))
array = np.array([])
package_list = list()

for i in range(3000):
    encoded_package = sock.recvfrom(1400)
    package = np.frombuffer(encoded_package[0], dtype=np.int32)
    package_list.append(package)

print(f'Length of package list: {len(package_list)} arrays')

for i in package_list:
    array = np.append(array, i, axis=0)

with open('resources/test_data2.csv', 'w') as myfile:
    print('Starting export to test_data2.csv')
    np.savetxt(myfile, array)
    print('export complete')


fig, ax = plt.subplots()
ax.plot(np.arange(0, len(array)), array)
plt.show()