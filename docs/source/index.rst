IvoryOS documentation
=====================

**IvoryOS** is an open-source orchestration platform and runtime for self-driving laboratories and scientific automation.

IvoryOS turns existing Python automation code into an interactive control panel, a visual workflow designer, an execution runtime, and an optimization-ready experimentation interface. It is Python-native, hardware-agnostic, and designed for rapidly changing research environments.

.. raw:: html

   <iframe width="560" height="315" src="https://www.youtube.com/embed/dFfJv9I2-1g" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

`Paper <https://www.nature.com/articles/s41467-025-60514-w>`_ | `Code <https://gitlab.com/heingroup/ivoryos>`_ | `Demo <https://demo.ivoryos.ai>`_

Choose a path
-------------

- `Users <users/index.html>`_: operate the browser UI, design workflows, run experiments, and review output data.
- `Examples <examples/index.html>`_: browse platform examples, community integrations, templates, and gallery links.
- `Integrators <integrators/index.html>`_: expose instruments and Python modules, configure IvoryOS, define input types, and connect plugins, clients, MCP tools, or remote instruments.
- `Developers <developers/index.html>`_: work on the IvoryOS codebase, runtime internals, HTTP routes, releases, and documentation structure.

Core idea
---------

IvoryOS introspects live Python modules and initialized objects. Function names, signatures, type hints, defaults, and docstrings become UI controls and workflow actions without requiring a separate workflow language.

Where to start
--------------

- If you are operating an existing IvoryOS platform, start with `Using the UI <users/using-the-ui.html>`_.
- If you want examples of IvoryOS in practice, start with `Examples <examples/index.html>`_.
- If you are launching or integrating a Python platform, start with `Integrator quick start <integrators/quick-start.html>`_.
- If you are changing IvoryOS itself, start with `Architecture notes <developers/architecture.html>`_.

.. toctree::
   :maxdepth: 2
   :caption: Documentation
   :hidden:

   users/index
   integrators/index
   developers/index
   examples/index

.. note::

   This project is under active development.
