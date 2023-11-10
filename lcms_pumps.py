import os
import sys

import serial

sys.path.insert(1, os.getcwd())

from new_era.peristaltic_pump_network import PeristalticPumpNetwork, NetworkedPeristalticPump
from vapourtec.sf10 import SF10
import time


class MultiPumps:
    def __init__(self, sf10: SF10, new_era: NetworkedPeristalticPump):
        self.sf10 = sf10
        self.new_era = new_era

    def sf10_dispense(self, duration: int, speed_ml_min: float = None):
        if speed_ml_min is not None:
            self.sf10.set_flow_rate(speed_ml_min)
        self.sf10.start()
        time.sleep(duration)
        self.sf10.stop()

    def new_era_dispense(self, duration: int, speed: float = None, direction=None):
        if speed is not None:
            self.new_era.set_rate(speed)
        if direction in ["withdraw", "dispense", "reverse"]:
            self.new_era.set_direction(direction)
        self.new_era.start()
        time.sleep(duration)
        self.new_era.stop()


# # --------------------new_era---------------------------
# pump_network = PeristalticPumpNetwork('com5')
# new_era = pump_network.add_pump(address=0, baudrate=9600)
#
# # --------------------  SF10  --------------------------
# sf10 = SF10(device_port="com1")


new_era = None

# --------------------  SF10  --------------------------
# sf10 = None
# creating multi pumps
multi_pumps = MultiPumps(sf10=serial.Serial(), new_era=new_era)
gui_functions = ['multi_pumps', 'sf10', 'new_era']



import config
config.deck = multi_pumps
# print("config",config.deck)
from app import socketio, app
socketio.run(app, host="0.0.0.0", port=8000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)

