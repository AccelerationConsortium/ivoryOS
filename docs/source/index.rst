Welcome!
===================================

**ivoryOS** is a Python library aiming to ease up the control of any Python-based SDLs by providing a visual programming and execution interface for initialized modules dynamically.


Introduction and demo video
------------------------------

.. raw:: html

    <iframe width="560" height="315" src="https://www.youtube.com/embed/dFfJv9I2-1g" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>

`Paper <https://www.nature.com/articles/s41467-025-60514-w>`_  | `Code <https://gitlab.com/heingroup/ivoryos>`_ | `Demo <https://demo.ivoryos.ai>`_


Quick start
---------------
.. code-block:: console

   (.venv) $ pip install ivoryos


In a python script, containing the initialized Python modules:

.. code-block:: python

    my_instance = MyClass()

    import ivoryos

    ivoryos.run(__name__)



.. toctree::
   :maxdepth: 2
   :caption: Table of Contents:

   self
   introduction
   usage
   integration
   plugin
   client
   mcp


.. toctree::
   :maxdepth: 2
   :caption: IvoryOS routes docs:

   routes

.. note::

   This project is under active development.