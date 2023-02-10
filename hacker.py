
class Hacker:

    def __init__(self, receive, package_len, total_len, marker=b'\xaa\xff\xff\xff'):
        self.receive = receive
        self.marker = marker
        self.package_len = package_len
        self.total_len = total_len

    def hack(self):
        buffer = bytearray()
        counter = 0
        while True:
            data = self.receive()
            counter += len(data)
            buffer += data

