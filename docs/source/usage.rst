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


Add Notification Handler(s)
------------------------
To add notification handler(s) that can send out notifications (e.g., email, SMS, Slack, etc.) when using `Pause` in workflows.

.. code-block:: python
  def slack_bot(message: str):
      # send message to slack channel
      pass

  ivoryos.run(__name__, notification_handler=slack_bot)
  ivoryos.run(__name__, notification_handler=[slack_bot, another_notification_handler])


Parameter Type Conversion
-------------------------
The parameter converter supports the following basic types:
`int`, `float`, `str`, `bool`, `list`, `tuple`, `set`

When defining functions for scripting workflows, use these supported types as type hints to ensure automatic parameter conversion.

If a parameter’s type hint is not one of the supported types, IvoryOS will attempt to evaluate it using `ast.literal_eval()`.
If evaluation fails, the parameter will be treated as a `str`.

**Example**

.. code-block:: python

    def example_function(param1: int, param2: float, param3: str, param4: bool, param5: list):
        """
        When calling example_function from the workflow interface:
        param1 will be converted to int
        param2 will be converted to float
        param3 will remain as str
        param4 will be converted to bool
        param5 will be converted to list
        """
        pass

    ivoryos.run(__name__)


Offline Mode
---------------
After one successful connection, a blueprint will be automatically saved and made accessible without hardware connection. In a new Python script in the same directory, use `ivoryos.run()` to start offline mode.

.. code-block:: python

    ivoryos.run()


