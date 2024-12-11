Introduction
===================================

**ivoryOS** is a Python library aiming to ease up the control of any Python-based SDLs
by providing a visual programming and execution interface for initialized modules dynamically.

The modules can be hardware API, high-level functions, or experiment workflow.
With the least modification of the current workflow, user can design,
manage and execute their experimental designs and monitor the execution process.


SDLs workflow execution
---------------------------------
Most autonomous workflows need customized iteration options.
In the meantime, there is the need of pre- and post- experimentation steps.
Taking these into consideration, there are three built in phases in ivoryOS, the preparation, experiment, and clean up phases.

1. Preparation:
    Execute one time before the main experiment

2. Experiment (main workflow)
    Execute multiple times based on the current configration

3. Clean up
    Execute one time after the main experiment


Execution options
--------------------
.. list-table:: Parameter Types and Output Types
   :header-rows: 1
   :widths: 30 35 35

   * - Parameter Type
     - Output Type: Any
     - Output Type: Numerical
   * - Constant
     - Define **repeat** times
     - Define **repeat** times
   * - Configurable
     - Configure **parameters**
     - Configure **optimizer** parameters

1. **Repeat**: available only for workflows without configurable (dynamic) parameters
2. **Parameters**: available for workflows with configurable (dynamic) parameters
3. **Optimizer**: available only for workflows with configurable (dynamic) parameters and numerical output(s)

ivoryOS Output Files Structure
----------------------------------------

When you run the application for the first time, it will automatically create the following folders and files in the same directory:

- **`ivoryos_data/`**: Main directory for application-related data.
- **`ivoryos_data/config_csv/`**: Contains iteration configuration files in CSV format.
- **`ivoryos_data/llm_output/`**: Stores raw prompt generated for the large language model.
- **`ivoryos_data/pseudo_deck/`**: Contains pseudo-deck `.pkl` files for offline access.
- **`ivoryos_data/results/`**: Used for storing results or outputs during workflow execution.
- **`ivoryos_data/scripts/`**: Holds Python scripts compiled from the visual programming script design.

- **`default.log`**: Log file that captures application logs.
- **`ivoryos.db`**: Database file that stores application data locally.

.. code-block:: text

   ivoryos_data/
   ├── config_csv/
   │   ├── example_config.csv
   │   ├── example_config_empty.csv
   ├── llm_output/
   │   ├── prompt.txt
   ├── pseudo_deck/
   │   ├── abstract_sdl.pkl
   ├── results/
   │   ├── example_2024-08-23 23-22.csv
   ├── scripts/
   │   ├── example.json
   │   ├── example.py
   ├── default.log
   ├── ivoryos.db
