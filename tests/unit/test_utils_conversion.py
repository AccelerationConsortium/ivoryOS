import unittest
from enum import Enum

from ivoryos.parsers.type_conversions import check_config_duplicate, convert_config_type, web_config_entry_wrapper


class MockEnum(Enum):
    OptionA = "OptionA"
    OptionB = "OptionB"

class TestConversion(unittest.TestCase):
    
    def test_basic_primitives(self):
        """Test basic primitive types: int, float, bool, str"""
        # int
        data = {"val": "42"}
        types = {"val": "int"}
        convert_config_type(data, types)
        self.assertEqual(data["val"], 42)
        
        # float
        data = {"val": "3.14"}
        types = {"val": "float"}
        convert_config_type(data, types)
        self.assertEqual(data["val"], 3.14)
        
        # bool
        for truthy in ["True", "true", "True"]: # ast.literal_eval handles True. str conversion?
            data = {"val": "True"}
            types = {"val": "bool"}
            convert_config_type(data, types)
            self.assertTrue(data["val"])
            
        data = {"val": "False"}
        types = {"val": "bool"}
        convert_config_type(data, types)
        self.assertFalse(data["val"])

        # str
        data = {"val": "hello"}
        types = {"val": "str"}
        convert_config_type(data, types)
        self.assertEqual(data["val"], "hello")

    def test_optional_types(self):
        """Test Optional[T] which maps to [T, 'NoneType']"""
        
        # Optional[int]
        types = {"val": ["int", "NoneType"]}
        
        # Case: Value
        data = {"val": "100"}
        convert_config_type(data, types)
        self.assertEqual(data["val"], 100)
        
        # Case: None
        data = {"val": "None"}
        convert_config_type(data, types)
        self.assertIsNone(data["val"])
        
        # Case: Empty string -> None (handled by convert_config_type explicitly)
        data = {"val": ""}
        convert_config_type(data, types)
        self.assertIsNone(data["val"])

        # Optional[str]
        types = {"val": ["str", "NoneType"]}
        
        # Case: Value
        data = {"val": "hello"}
        convert_config_type(data, types)
        self.assertEqual(data["val"], "hello")
        
        # Case: None
        data = {"val": "None"}
        convert_config_type(data, types)
        self.assertIsNone(data["val"])

    def test_union_types(self):
        """Test Union[T1, T2]"""
        types = {"val": ["int", "float"]}
        
        # Case: int
        data = {"val": "42"}
        convert_config_type(data, types)
        self.assertEqual(data["val"], 42)
        
        # Case: float
        data = {"val": "3.14"}
        convert_config_type(data, types)
        self.assertEqual(data["val"], 3.14)

    def test_containers(self):
        """Test list, tuple, etc."""
        # list of ints
        data = {"val": "[1, 2, 3]"}
        types = {"val": "list"}
        convert_config_type(data, types)
        self.assertEqual(data["val"], [1, 2, 3])
        
        # list of strings (using quotes)
        data = {"val": "['a', 'b']"}
        convert_config_type(data, types)
        self.assertEqual(data["val"], ['a', 'b'])

        # tuple
        data = {"val": "(1, 2)"}
        types = {"val": "tuple"}
        convert_config_type(data, types)
        self.assertEqual(data["val"], (1, 2))

    def test_invalid_conversions(self):
        """Test inputs that should fail"""
        data = {"val": "not_a_number"}
        types = {"val": "int"}
        
        # ast.literal_eval will fail or leave it as string.
        # _convert_by_str -> int("not_a_number") -> ValueError -> caught -> TypeError
        
        with self.assertRaises(TypeError):
             convert_config_type(data, types)

    def test_edge_cases(self):
        # Optional[str] with spaces
        data = {"val": "  hello  "}
        types = {"val": ["str", "NoneType"]}
        convert_config_type(data, types)
        self.assertEqual(data["val"], "  hello  ")

        data = {"val": "None"}
        types = {"val": ["int", "NoneType"]}
        convert_config_type(data, types)
        self.assertIsNone(data["val"])

    def test_class_and_enum_conversions(self):
        data = {"val": "42"}
        types = {"val": int}
        convert_config_type(data, types, is_class=True)
        self.assertEqual(data["val"], 42)

        data = {"choice": "OptionB"}
        types = {"choice": "Enum:tests.unit.test_utils_conversion.MockEnum"}
        convert_config_type(data, types)
        self.assertEqual(data["choice"], "OptionB")

    def test_duplicate_and_web_config_helpers(self):
        self.assertTrue(check_config_duplicate([{"x": 1}, {"x": 1}]))
        self.assertFalse(check_config_duplicate([{"x": 1}, {"x": 2}]))

        wrapped = web_config_entry_wrapper(
            {
                "name[0]": "alpha",
                "value[0]": "1",
                "name[1]": "incomplete",
                "value[2]": "",
            },
            ["name", "value"],
        )
        self.assertEqual(wrapped, [{"name": "alpha", "value": "1"}])

if __name__ == "__main__":
    unittest.main()
