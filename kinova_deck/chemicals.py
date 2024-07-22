from abstract_robot_classes.chemical import Chemical


class Liquid(Chemical):
    def __init__(self, name: str, formula: str, density: float = -1):
        self.name = name
        self.formula = formula
        self.density: float = density


class Solid(Chemical):
    def __init__(self, name: str, formula: str, density: float = -1):
        self.name = name
        self.formula = formula
        self.density: float = density
