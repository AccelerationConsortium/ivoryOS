import time
import sys,os
sys.path.append(os.getcwd())
from example.test_inner import TestInner


class MyTest:

    def __init__(self, arg1: TestInner, arg2: int = 0):
        self.inner = arg1
        self.a = arg2

    def test1(self):
        time.sleep(3)
        print("Test1: no arg ", self.inner.a)

    def test2_return_test(self, arg1, arg2: str = "4"):
        print("Test2: Testing for return output", arg1, type(arg1))
        print("Test2: Testing for return output", arg2, type(arg2))
        return arg1
    def test3_arg_required(self, arg1: int):
        print("Test3: Testing required arg", arg1)

    def test4(self, arg1: int = None):
        print("Test4: Testing for None default", arg1)

    def test5(self, arg1:bool= False):
        print("Test5: Testing for boolean input\nValue:", arg1, "   Type: ", type(arg1))

    def test6_another_bool(self, arg_1:bool):
        print("Test6: Testing for boolean input No default\nValue:", arg_1, "   Type: ", type(arg_1))
    def test7_return_test(self, arg1):
        print("Test7: Testing for return output", arg1, type(arg1))