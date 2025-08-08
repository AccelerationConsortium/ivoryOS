Usage
=====

.. _installation:

Installation
------------

To use ivoryOS, first install it using pip:

.. code-block:: console

   (.venv) $ pip install ivoryos


Quick start
------------

.. code-block:: python


    import ivoryos

    ivoryos.run(__name__)


.. autofunction:: ivoryos.run



Add Additional Logger(s)
------------------------
1. To add additional logger(s),

.. code-block:: python

  ivoryos.run(__name__, logger="logger name")
  ivoryos.run(__name__, logger=["logger 1", "logger 2"])


2. Setting logger file name
By default, all logs will be save to `default.log`. Alternatively, one can create new file for different platforms/dates.

.. code-block:: python

  from datetime import datetime
  ivoryos.run(__name__, logger_output_name =f"log_{datetime.today().strftime("%Y-%m-%d")}.log")


Offline Mode
---------------
After one successful connection, a blueprint will be automatically saved and made accessible without hardware connection. In a new Python script in the same directory, use `ivoryos.run()` to start offline mode.

.. code-block:: python

    ivoryos.run()


