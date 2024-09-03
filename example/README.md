# ivoryOS: example SDL class
ivoryOS is an open-source Python package enabling SDL interoperability. 


## Python class example
The minimum requirement for achieving the "plug-and-play" feature,
is to use Python class.
```python
class MySDL:
    def __init__(self):
        pass

    def task_1(self):
        pass

    def task_2(self):
        pass
```

## start ivoryOS
in a Python script, import or initialize your SDL module, and run ivoryOS on current script
```python
sdl = MySDL()

import ivoryos
ivoryos.run(__name__)
```