
class Hacker:

    def __init__(self, receive, package_len, total_len, marker=b'\xaa\xff\xff\xff'):
        self.receive = receive
        self.marker = marker
        self.package_len = package_len
        self.total_len = total_len

    def hack(self):
        buffer = bytearray()
        counter = 0
        package_len = self.package_len
        receive = self.receive
        marker = self.marker
        total_len = self.total_len
        marker_len = len(marker)
        while True:
            data = receive(package_len)
            pos = data.find(marker)
            if pos != -1:
                buffer += data
            else:
                buffer += data[:pos]
                if len(buffer) == total_len:
                    yield buffer
                else:
                    pass
                buffer.clear()
                buffer += data[pos + marker_len:]
            # The counter is not really needed anymore as len(buffer) does the job
            # counter += len(data)
            # buffer += data
