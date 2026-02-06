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


Design Agent
------------
The design agent simplifies the workflow creation process by allowing users to generate experimental actions using natural language. Instead of manually searching through available methods, you can describe your intent, and the agent will extract the most likely actions from all instruments on your current deck configuration. It also supports the flow control functions "wait" and "comment".

.. raw:: html

    <iframe width="495" height="315" src="https://www.youtube.com/embed/MopfBnEOlK0?autoplay=1&mute=1&loop=1&playlist=MopfBnEOlK0&controls=0"  frameborder="0"  allow="autoplay; encrypted-media"  allowfullscreen> </iframe>


*Natural language input in offline mode with the abstract_sdl deck, using the qwen3-30b-a3b-instruct-2507 model.*


Configuration
~~~~~~~~~~~~~
The design agent supports any Large Language Model (LLM) compatible with the OpenAI's Chat Completions API V1. If ``OPENAI_API_KEY``, ``model``, or ``llm_server`` is missing or incorrect, IvoryOS will start without the design agent feature.

**1. API Key Setup**
Define your API key as an environment variable or create a ``.env`` file in your project root directory:

.. code-block:: text

    OPENAI_API_KEY=<your_key_here>

**2. Initialization**
Pass the ``model`` name and the ``llm_server`` (OpenAI base_url) to the ``ivoryos.run`` command.

Examples
~~~~~~~~~~~~~

**Cloud LLM Provider with On-Line Connected Devices**
Use this configuration to connect to remote providers such as OpenAI, Anthropic, and Alphabet. The ``__name__`` keyword in the beginning initialises IvoryOS in online mode.

.. code-block:: python

    import ivoryos

    if __name__ == "__main__":
        ivoryos.run(__name__, model="gpt-4o", llm_server="https://api.openai.com/v1")

**Off-Line Mode and Local LLM**
The design agent works with the actively selected offline deck. Furthermore, the implementation via OpenAI API enables the use of locally hosted LLMs.

.. code-block:: python

    import ivoryos

    if __name__ == "__main__":
        ivoryos.run(model="qwen3-30b-a3b-instruct-2507", llm_server="http://localhost:11434/v1/")

.. note::
    For every request, the agent saves the full prompt and the raw JSON response to the ``ivoryos_data/llm_output/`` directory for debugging and transparency.

Tips for Model Selection and Daily Use
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **Minimum Model Requirement**: For consistent JSON output, a model equivalent to ``meta-llama-3.1-8b-instruct`` or better is recommended.
* **Model Size**: Modern models and those with >8B parameters perform more reliably but require more compute.
* **Avoid "Thinking" Models**: Reasoning models are not recommended due to their increased output time.
* **Improvement via Documentation**: Accuracy is significantly improved by providing rigorous method and class documentation, as these are extracted and used as context for the LLM. The class docstring is only extracted in online mode.
* **Prompt Clarity**: The shorter and more direct the user prompt, the more reliable the design agent becomes.