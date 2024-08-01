from serial import Serial


class NeedleWash:
    def __init__(self, wash_port="COM12"):
        self.wash_port = wash_port
        self.needle_wash = Serial(self.wash_port, baudrate=115200, timeout=1)


    def wash_needle(self):
        self.needle_wash.write(str.encode("clear"))



if __name__ == "__main__":
    nw = NeedleWash("COM12")
    print()