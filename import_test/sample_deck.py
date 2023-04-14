import repackage

repackage.up()

from import_test.gui_test import MyTest
from import_test.test_inner import TestInner
import ftdi_serial
import numpy
a = {"a": 1, "b": 3}

class SampleDeck:
    def __init__(self):
        self.inner_test1 = TestInner("using sample deck")
        self.test1 = MyTest(self.inner_test1)
        self.test2 = MyTest(self.inner_test1)

    def test_action(self):
        self.test1.test1()
        self.test1.test4()
    def from_a_to_b(self):
        print("testing")
    def _dont_use(self):
        print("not for users")


inner_test1 = TestInner("using sample deck")
test1 = MyTest(inner_test1)
test2 = MyTest(inner_test1)
# gui_functions = ['inner_test1', 'test1', 'test2']


def new_function_test():
    pass
