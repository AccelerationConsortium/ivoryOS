import time
import serial


# valve = serial.Serial(port="com5", baudrate=115200)


class Valve:
    def __init__(self, port: str, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.valve = serial.Serial(self.port, self.baudrate)
        self.pos = None

    def switch_to_1(self):
        self.valve.write(b"1")
        self.pos = 1

    def switch_to_2(self):
        self.valve.write(b"2")
        self.pos = 2

    def home(self):
        self.valve.write(b"h")
        self.pos = 1

    def wait_and_switch(self, pos: int, wait_min: float = 0):
        time.sleep(wait_min * 60)
        if pos == 1:
            self.switch_to_1()
        elif pos == 2:
            self.switch_to_2()
        else:
            raise ValueError("Invalid Valve Position")

    def toggle(self):
        if self.pos == 1:
            self.switch_to_2()
        elif self.pos == 2:
            self.switch_to_1()
        else:
            self.home()

    def toggle_every_min(self, wait_min: float = 0, duration: int = 1):
        start = time.time()
        while time.time() - start < duration * 60:
            time.sleep(wait_min * 60)
            self.toggle()
