# ivoryOS: example SDL class
ivoryOS is an open-source Python package enabling SDL interoperability. 


## Python class example
The minimum requirement for achieving the "plug-and-play" feature,
is to use Python class.
```python
class MySDL:
    def __init__(self):
        pass

    def task_1(self, arg_1: int, arg_2: float):
        pass

    def task_2(self):
        pass
```

## Start ivoryOS
in a Python script, import or initialize your SDL module, and run ivoryOS on current script
```python
sdl = MySDL()

import ivoryos
ivoryos.run(__name__)
```

## Integration examples


This directory contains several example projects demonstrating different functionalities.

### Abstract integrations

- [ax_example](#ax_example)
- [sdl_example](#sdl_example)

### ax_example
The `ax_example` aims to demonstrate the optimization feature using Branin Function. 
This demonstration is runnable without hardware connection.

### sdl_example
The `sdl_example` showcases the use of multiple instances in SDL applications.
This demonstration is runnable without hardware connection.

### Platform integrations
- [adc_example](#adc_example)
- [purpose_example](#purpose_example)
- [flow_chem_example](#flow_chem_example)
- [lilie_example](#lilie_example)
- [ti_solubility_example](#ti_solubility_example)
- [ti_derivatization_example](#ti_derivatization_example)


![](../docs/source/_static/platforms.png)


### adc_example
Antibody Drug Conjugation ([ADC](https://gitlab.com/heingroup/adc-automation)) platform

### purpose_example
Purification Platform Optimizing Solubility based Experimentation ([PurPOSE](https://gitlab.com/heingroup/purpose)).

### flow_chem_example
The [Flow Chem](https://github.com/jiayu423/Autonomous-flow-optimizer) code was optimized for ivoryOS ([flow_so_ivoryos](https://github.com/ivoryzh/Autonomous-flow-optimizer/blob/main/single%20objective%20edbo/flow_so_ivoryos.py))

### lilie_example
Liquid-Liquid Extraction ([LiLiE](https://gitlab.com/heingroup/automated-lle)) platform is a work-in-progress platform, aiming to sampling biphasic reaction. The code repository may be unavailable at this moment.

### ti_solubility_example
This example is the solubility platform at Telescope Innovations Corp.


### ti_derivatization_example
This derivatization sampling setup at Telescope Innovations Corp. is using DirectInject system and a [Sielc autosampler](https://gitlab.com/heingroup/sielc_dompser).



