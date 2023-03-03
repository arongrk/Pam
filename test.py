import socket
import os
import time


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(('127.0.0.1', 9090))
    plot = bytearray()
    while True:
        plot += os.urandom(40960*4)
        plot += b'\xff\xff\xff\xaa'
        while len(plot) >= 1400:
            sock.send(plot[:1400])
            plot = plot[1400:]
            time.sleep((0.01))


def main2():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('127.0.0.1', 9090))
    while True:
        m = sock.recv(1024)
        print(m)


if __name__ == '__main__':
    main2()
