from serial import Serial


class Balance:
    def __init__(self, port: str):
        self.port = port
        self.ser = Serial(port)

    def stable_weight(self):
        response = self.send_command("S")
        return self.get_reading(response)

    def weight_immediately(self):
        response = self.send_command("SI")
        return self.get_reading(response)

    def tare(self):
        response = self.send_command("T")
        return self.get_reading(response)

    def zero(self):
        self.send_command("Z")
        return

    def tare_immediately(self):
        response = self.ser.write("TI")
        return self.get_reading(response)

    def zero_immediately(self):
        self.send_command("ZI")

    def send_command(self, command):
        if not command.endswith("\n\r"):
            command += "\n\r"
        self.ser.write(command.encode())
        response = self.ser.readline()
        return response.decode().strip()

    @staticmethod
    def get_reading(response):
        _, _, number, unit = response.split()
        return (float(number))


if __name__ == "__main__":
    b = Balance("COM7")
    w = b.stable_weight()
    print(w)
    print()