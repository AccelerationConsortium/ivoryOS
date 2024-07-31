from kinova_deck.chemicals import Liquid
from kinova_deck.kinova_arm import KinovaArm
from kinova_deck.kinova_location import KinovaLocation
from kinova_deck.moveable.europa import EuropaHandling
from kinova_deck.moving.kinova_movable_config import KinovaMoveableConfig, KinovaMoveableSequence

home = KinovaLocation(name='home', sequence_location_name='central_home')
kinova = KinovaArm(name='kinova', home_coordinates='central_home')
europa_base = KinovaLocation(name='europa base', sequence_location_name='liquid_base_xy')
europa = EuropaHandling(name='europa', config=KinovaMoveableConfig(name='europa', safe_moves=[
    KinovaMoveableSequence(location_A='home', location_B=['europa base'], sequence_from_A_to_B=None,
                           sequence_from_B_to_A=None)], grip_open=0, grip_close=0.29), max_volume_ul=1000)
acetone = Liquid(name='acetone', density=0, formula='C3H6O')


class DummyKinovaDeck:
    def __init__(self, arm, liquid_handler, locations):
        self.arm = arm
        self.liquid_handler = liquid_handler
        self.locations = locations


sdl = DummyKinovaDeck(kinova, europa, [home, europa_base])
# gui_functions = ['inner_test1', 'test1', 'test2']


if __name__ == "__main__":
    from ivory_os.app import ivoryos

    ivoryos(__name__)
