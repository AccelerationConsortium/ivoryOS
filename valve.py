import time

import serial

# valve = serial.Serial(port="com5", baudrate=115200)


class Valve:
    def __init__(self, port: str, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.valve = serial.Serial(self.port, self.baudrate)

    def switch_to_1(self):
        self.valve.write(b"1")

    def switch_to_2(self):
        self.valve.write(b"2")

    def home(self):
        self.valve.write(b"h")

    def wait_and_switch(self, pos: int, wait_min: float = 0):
        time.sleep(wait_min * 60)
        if pos == 1:
            self.switch_to_1()
        elif pos == 2:
            self.switch_to_2()
        else:
            raise ValueError("Invalid Valve Position")
