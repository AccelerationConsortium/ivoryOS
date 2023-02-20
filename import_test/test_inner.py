# import repackage
#
# repackage.up()


class TestInner:

    def __init__(self, arg1: str):
        self.a = arg1

    def connect(self):
        print("Connecting", self.a)

