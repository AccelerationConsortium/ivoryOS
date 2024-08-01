from ika import Thermoshaker

from example.abstract_robot_classes.container import Container
from example.kinova_deck.kinova_location import KinovaGridLocation


class Shaker(KinovaGridLocation):
    def __init__(self, name: str, sequence_location_name: str, rows: int, columns: int, spacing_x: float,
                 spacing_y: float, offset_rx: float, offset_ry: float, offset_rz: float):
        super().__init__(name, sequence_location_name, rows, columns, spacing_x, spacing_y, offset_rx, offset_ry,
                         offset_rz)
        self.shaker = Thermoshaker.create(port="dummy", dummy=True)

    def heat(self, container: Container, temperature, duration: int = 10):
        self.shaker.start_tempering()
        self.shaker.set_temperature_duration(duration)

    def stop_heating(self, container: Container):
        self.shaker.stop_tempering()

    def shake(self, container: Container, speed: int = 300, duration=10):
        # self.shaker.set_speed = speed
        # self.shaker.start_shaking()
        print("shaking")

    def stop_shaking(self, container: Container):
        # self.shaker.stop_shaking()
        print("stop shaking")
