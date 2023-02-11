import time

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
        expecting_marker = True
        receive = self.receive
        marker = self.marker
        marker_len = len(marker)
        t0 = time.process_time_ns()
        while True:
            tr0 = time.process_time_ns()
            data = receive(package_len)
            trd = time.process_time_ns() - tr0
            match data.find(marker), expecting_marker:
                case -1, True:
                    continue
                case -1, False:
                    counter += len(data)
                    buffer += data
                case position, True:
                    tail = data[position+marker_len:]
                    counter += len(tail)
                    buffer += tail
                    expecting_marker = False
                case position, False:
                    if counter + position == self.total_len:
                        buffer += data[:position]
                        t1 = time.process_time_ns()
                        print(f"Package decode time ms: {(t1-t0-trd)/1000000.0}")
                        yield buffer
                        t0 = time.process_time_ns()
                    buffer.clear()
                    buffer += data[position+marker_len:]
                    counter = len(buffer)

