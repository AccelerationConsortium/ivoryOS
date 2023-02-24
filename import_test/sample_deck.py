import repackage
repackage.up()

from import_test.gui_test import MyTest
from import_test.test_inner import TestInner


a={"a":1,"b":3}
inner_test1 = TestInner("using sample deck")
test1 = MyTest(inner_test1)
