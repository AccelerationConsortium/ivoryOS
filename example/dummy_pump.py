class DummyPump:

    def __init__(self, com_port: str):
        self.com_port = com_port

    def dose_liquid(self, amount_in_ml: float, rate_ml_per_minute:float):
        print(f"pretending dosing {amount_in_ml} at {rate_ml_per_minute} ml/min")

