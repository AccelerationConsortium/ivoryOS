class DummyBalance:

    def __init__(self, com_port: str):
        self.com_port = com_port

    def weigh_sample(self):
        print(f"Weighing sample using {self.com_port}")

    def dose_solid(self, amount_in_mg: float):
        print(f"Dosing {amount_in_mg} mg using {self.com_port}")
