import time

class Hacker:

    def __init__(self, receive, package_len, total_len, marker=b'\xaa\xff\xff\xff'):
        self.receive = receive
        self.marker = marker
        self.package_len = package_len
        self.total_len = total_len

    def hack(self):
        buffer = bytearray()
        package_len = self.package_len
        receive = self.receive
        marker = self.marker
        marker_len = len(marker)
        t0 = time.process_time_ns()
        while True:
            tr0 = time.process_time_ns()
            data = receive(package_len)
            trd = time.process_time_ns() - tr0
            match data.find(marker):
                case -1:
                    buffer += data
                case position:
                    if len(buffer) + position == self.total_len:
                        buffer += data[:position]
                        t1 = time.process_time_ns()
                        print(f"Package decode time ms: {(t1-t0-trd)/1000000.0}")
                        yield buffer
                        t0 = time.process_time_ns()
                    buffer.clear()
                    buffer += data[position+marker_len:]

