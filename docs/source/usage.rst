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


Enable text-to-code with LLMs
------------------------------------

The LLM agent used openai Python API that support both using OpenAI API key or local models that are powered by Ollama

1. Example of using Llama3.1
    - Download and install `Ollama`.
    - Pull models from `Ollama`.
    - In your SDL script, define the LLM server and model. You can use any model available on `Ollama`:
    - Note that the full url of using Ollama localhost is "http://localhost:11434/v1/"

.. code-block:: python

   ivoryos.run(__name__, llm_server="localhost", model="llama3.1")

2. Example of using gpt-3.5-turbo. You can use any model available:
    - Create a `.env` file for `OPENAI_API_KEY`.
    - In your SDL script, define the modeul, but no need to define the LLM server. You can use any model available from OpenAI:

.. code-block:: python

   ivoryos.run(__name__, model="gpt-3.5-turbo")


Add Additional Logger(s)
------------------------
To add additional logger(s), you can specify them in your script:

1. For a single logger:

.. code-block:: python

  ivoryos.run(__name__, logger="logger name")

2. For multiple loggers:

.. code-block:: python

  ivoryos.run(__name__, logger=["logger 1", "logger 2"])

3. Setting logger file name
By default, all logs will be save to `default.log`. Alternatively, one can create new file for different platforms/dates.

.. code-block:: python

  from datetime import datetime
  ivoryos.run(__name__, logger_output_name =f"log_{datetime.today().strftime("%Y-%m-%d")}.log")


Offline Mode
---------------
After one successful connection, a blueprint will be automatically saved and made accessible without hardware connection. In a new Python script in the same directory, use `ivoryos.run()` to start offline mode.

.. code-block:: python

    ivoryos.run()


