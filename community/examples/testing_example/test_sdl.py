from typing import List
import sys
import os

from community.examples.testing_example.utils import TestEnum

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

class Test:
    def list_example(self, l: List[int]):
        print(f'list values: {l}')

    def enum_example(self, e: TestEnum):
        print(f'enum: {e}')

    # def list_enum_example(self, l: List[TestEnum]):
    #     print(f'list enums: {l}')


testing = Test()

if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
    import ivoryos

    ivoryos.run(__name__)
