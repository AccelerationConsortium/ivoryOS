import time

from serial import Serial
from ika.vacuum_pump import VacuumPump

"""
a1 : close left
a0 : open left
b1 : close right
b0 : open right
"""


class Solenoid(object):
    def __init__(self, valve_port="COM4", pump_port="COM3"):
        self.valve_port = valve_port
        self.pump_port = pump_port
        self.solenoid = Serial(self.valve_port, baudrate=115200, timeout=1)
        self.vacuum = VacuumPump(self.pump_port)

    def start_right_vacuum(self, pressure: int = 1050):
        self.solenoid.write(b'a1')
        time.sleep(1)
        self.solenoid.write(b'b0')
        time.sleep(1)
        self.vacuum.start()
        self.vacuum.set_pressure = pressure
        time.sleep(60)
        self.stop_vacuum()


    def start_left_vacuum(self, pressure: int = 1050):
        self.solenoid.write(b'b1')
        time.sleep(1)
        self.solenoid.write(b'a0')
        time.sleep(1)
        self.vacuum.start()
        self.vacuum.set_pressure = pressure
        time.sleep(60)
        self.stop_vacuum()

    def stop_vacuum(self):
        self.vacuum.set_pressure = 1050
        time.sleep(5)
        self.vacuum.stop()


if __name__ == "__main__":
    solenoid = Solenoid()
    solenoid.start_left_vacuum(pressure=900)
    solenoid.start_right_vacuum(pressure=900)
    solenoid.stop_vacuum()
