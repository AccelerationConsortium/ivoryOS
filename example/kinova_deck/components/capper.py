from ftdi_serial import Serial

"""
decapper
"""

class Capper:
    def __init__(self, port, baud=115200, bytesize=8, timeout=20):
        # self.somatic = serial_.Serial(port=port, baudrate=baud, bytesize=bytesize,
        #                             timeout=timeout, stopbits=serial_.STOPBITS_ONE)
        self.capper = Serial(device_port=port, baudrate=baud, data_bits=bytesize, read_timeout=timeout)

        print(f"Established connection with {self.capper} at {port}")

    def connect(self):
        self.capper.__init__()

    def disconnect(self):
        # put capper in its default state of "closed" before closing connection
        # self.home()
        self.capper.close()
        print("Disconnected capper")

    def open(self):
        cmd = f"open"
        self._execute(cmd)

    def close(self):
        cmd = "close"
        self._execute(cmd)

    def tighten(self):
        cmd = "tighten"
        self._execute(cmd)

    def loosen(self):
        cmd = "loosen"
        self._execute(cmd)

    def home(self):
        cmd = "home"
        self._execute(cmd)


    def _execute(self, cmd, wait=True):
        ans = None
        self.capper.write(cmd.encode())

        # Serial device returns "-4" when action complete
        while True:
            # ans = self.somatic.readline().decode("ascii").strip()
            ans = self.capper.read_line().decode("ascii").strip()
            if ans == "1":
                break
        return ans


if __name__ == "__main__":
    capper = Capper("COM9")
    capper.home()
    capper.open()
    capper.close()
    # x.loosen()
    # x.tighten()
    # time.sleep(3)
    # x.home()


