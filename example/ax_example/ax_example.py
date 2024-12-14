import numpy as np

import ivoryos


class BraninFunction:
    def __init__(self):
        self.a = 1
        self.b = 5.1 / (4 * 3.14159**2)
        self.c = 5 / 3.14159
        self.r = 6
        self.s = 10
        self.t = 1 / (8 * 3.14159)

    def evaluate(self, x1:float, x2:float) -> float:
        """Evaluate the Branin function with given parameters x1 and x2."""
        term1 = self.a * (x2 - self.b * x1**2 + self.c * x1 - self.r)**2
        term2 = self.s * (1 - self.t) * np.cos(x1)
        return term1 + term2 + self.s


if __name__ == '__main__':
    bf = BraninFunction()
    ivoryos.run(__name__)

