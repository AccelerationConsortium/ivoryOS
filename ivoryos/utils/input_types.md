## Supported Input Types

This document outlines the supported input types for configuration parameters and how they are converted from string entries.

### **Primitive Types**

| Type    | Example Input          | Example Conversion                   | Notes |
|---------|------------------------|--------------------------------------|-------|
| `int`   | `"42"`                 | `42`                                 | |
| `float` | `"3.14"`               | `3.14`                               | |
| `str`   | `"hello"`              | `"hello"`                            | |
| `bool`  | `"True"` / `"False"`   | `True` / `False`                     | Case-insensitive for common boolean strings |

### **Container Types**

| Type    | Example Input          | Example Conversion                   | Notes |
|---------|------------------------|--------------------------------------|-------|
| `list`  | `"[1, 2, 3]"`          | `[1, 2, 3]`                          | Supports Python literal syntax |
| `tuple` | `"(1, 'a')"`           | `(1, 'a')`                           | Supports Python literal syntax |
| `set`   | `"{1, 2, 3}"`          | `{1, 2, 3}`                          | Supports Python literal syntax |

### **Complex & Optional Types**

| Type | Example Input | Example Conversion | Notes |
|------|---------------|--------------------|-------|
| `Optional[int]` | `"42"` | `42` | |
| `Optional[int]` | `"None"` / `""` | `None` | Empty string or "None" becomes `None` |
| `Optional[str]` | `"hello"` | `"hello"` | |
| `Union[int, float]` | `"42"` | `42` (int) | Matches `int` |
| `Union[int, float]` | `"3.14"` | `3.14` (float) | Matches `float` |

### **Enum Types**
Enum types are supported via `Enum:<Module>.<ClassName>`.

| Type | Example Input | Example Conversion | Notes |
|------|---------------|--------------------|-------|
| `Enum:chemistry.Solvent` | `"Methanol"` | `Solvent.Methanol.value` | Looks up the Enum member provided string |

### **Any**
| Type | Example Input | Example Conversion |
|------|---------------|--------------------|
| `Any` | `"anything"` | `"anything"` (no conversion applied) |