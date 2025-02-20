## Supported Input Types
### **Commonly Used Types**
| Type                     | Example Input          | Example Output                       |
|--------------------------|------------------------|--------------------------------------|
| `int`                    | `"42"`                 | `42`                                 |
| `float`                  | `"3.14"`               | `3.14`                               |
| `str`                    | `"hello"`              | `"hello"`                            |
| `bool`                   | `"True"` / `"False"`   | `True` / `False`                     |
| `list[str]`              | `"apple,banana,grape"` | `["apple", "banana", "grape"]`       |
| `list[int]`              | `"1,2,3"`              | `[1, 2, 3]`                          |
| `dict[str, int]`         | `"key1:1,key2:2"`      | `{"key1": 1, "key2": 2}`             |
| `tuple[int, str, float]` | `"1,hello,3.5"`        | `(1, "hello", 3.5)`                  |
| `Optional[int]`          | `""` (empty input)     | `None`                               |
| `Union[int, str]`        | `"42"` or `"hello"`    | `42` or `"hello"`                    |
| `Any`                    | `"anything"`           | `"anything"` (no conversion applied) |

---