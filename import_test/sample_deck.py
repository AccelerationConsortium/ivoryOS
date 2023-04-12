import repackage

repackage.up()

from import_test.gui_test import MyTest
from import_test.test_inner import TestInner
import ftdi_serial
import numpy
a = {"a": 1, "b": 3}
inner_test1 = TestInner("using sample deck")
test1 = MyTest(inner_test1)

test2 = MyTest(inner_test1)
# gui_functions = ['inner_test1', 'test1', 'test2']


def new_function_test():
    pass
