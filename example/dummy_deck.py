from example.dummy_balance import DummyBalance
from example.dummy_pump import DummyPump

# some constant values
a = {"a": 1, "b": 3}


class DummySDLDeck:
    def __init__(self, pump: DummyPump, balance: DummyBalance):
        self.pump = pump
        self.balance = balance

    def pump_and_weigh(self, amount_in_ml: float = 5, rate_ml_per_minute: float = 1):
        self.pump.dose_liquid(amount_in_ml=amount_in_ml, rate_ml_per_minute=rate_ml_per_minute)
        self.balance.weigh_sample()

    def dose_and_weigh(self, amount_in_mg: float = 5):
        self.balance.dose_solid(amount_in_mg=amount_in_mg)
        self.balance.weigh_sample()


balance = DummyBalance("Fake com port 1")
pump = DummyPump("Fake com port 2")
sdl = DummySDLDeck(balance, pump)
# gui_functions = ['inner_test1', 'test1', 'test2']


if __name__ == "__main__":
    from sdl_webui.app import start_gui

    start_gui(__name__)
