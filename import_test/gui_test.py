import repackage
repackage.up()
from import_test.test_inner import TestInner


class MyTest:

    def __init__(self, arg1: TestInner, arg2: int = 0):
        self.inner = arg1
        self.a = arg2

    def test1(self):
        print(self.inner)
        print("Test1: no arg ", self.inner.a)

    def test2(self, arg1: int = 2, arg2: str = "4"):
        print("Test2: Testing for None default", arg1)

    def test3(self, arg1: int = 2):
        print(arg1)

    def test4(self, arg1: int = None):
        print("Test4: Testing for None default", arg1)

    def test5(self, arg1: bool):
        print("Test5: Testing for boolean input\nValue:", arg1, "   Type: ", type(arg1))
