import time

from example.dummy_ur.dummy_balance import DummyBalance
from example.dummy_ur.dummy_pump import DummyPump

# some constant values
a = {"a": 1, "b": 3}


class DummySDLDeck:
    def __init__(self, pump: DummyPump, balance: DummyBalance):
        self.pump = pump
        self.balance = balance

    def dose_solvent(self, name: str, amount_in_ml: float = 5, rate_ml_per_minute: float = 1):
        self.pump.dose_liquid(amount_in_ml=amount_in_ml, rate_ml_per_minute=rate_ml_per_minute)
        self.balance.weigh_sample()
        print("dosing solvent")

    def dose_solid(self, amount_in_mg: float = 5, bring_in: bool = False):
        """dose current chemical"""
        self.balance.dose_solid(amount_in_mg=amount_in_mg)
        self.balance.weigh_sample()
        print("dosing solid")

    def equilibrate(self, temp: float, duration: float):
        print("equilibrate")

    def sample(self, sample_volume: float = 10):
        print("sample")

    def dilute(self, solvent: str, factor: float):
        print("dilute")

    def analyze(self):
        print("analyze")

    def filtration(self):
        print("filtration")


balance = DummyBalance("Fake com port 1")
pump = DummyPump("Fake com port 2")
deck = DummySDLDeck(pump, balance)


class DummyExperiment:
    def __init__(self, deck):
        self.deck = deck

    def cooling_crystal(self,
                        low_temp: float,
                        temp_diff: float,
                        cooling_rate: float,
                        mass_mg: float,
                        solvent_A: str,
                        solvent_B: str,
                        solvent_ratio: float
                        ):
        print(type(mass_mg))

    def reslurry(self):
        pass

    def solubility(self,
                   temp: float,
                   temp_time_min: float,
                   duplicates:int,
                   ):
        pass

    def calibration_curve(self,
                          mass_in_mg: float,
                          temp: float,
                          temp_time_min: float,
                          initial_volume_ml: float,
                          sample_volume_ml: float,
                          dilution_factor: int,
                          number_of_dilutions: int,
                          ):
        pass


cryst_co = DummyExperiment(deck)


class ShakerDemo:
    def __init__(self, deck):
        self.deck = deck

    def move_sample_to_shaker(self, location:str="A1"):
        pass

    def shake_for_duration(self, duration: float):
        time.sleep(duration)

    def move_vial_to_tray(self,  location:str="A1"):
        pass

vial_shaker = ShakerDemo(deck)

if __name__ == "__main__":
    from ivoryos.app import ivoryos
    ivoryos(__name__, model="llama3.1", llm_server='localhost',)


    # ivoryos(__name__, model="gpt-3.5-turbo")

"""add 10 mg of acetaminophen, dose 1 ml of methanol, equilibrate for 10 minute at 50 degrees, filter the sample and analyze with HPLC"""
"""i want to run a cooling crystal experiment, with low temperature being 20, and high temperature being 40, cooling rate being 0.1, I want to dose 11 mg of my sample, and use 
water as solvent a and isopropanol for solvent b, the solvent ratio being 0.1"""


