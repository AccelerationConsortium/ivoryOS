![logo](ivoryos.png)
# ivoryOS: interoperable Web UI for SDLs
ivoryOS is an open-source Python package enabling SDL interoperability. Add a web UI to SDLs anytime.
## Description
Granting SDLs flexibility and modularity makes it almost impossible to design a UI, yet it's a necessity for allowing more people to interact with it (democratisation). 
This web UI aims to ease up the control of any Python-based SDLs by displaying functions and parameters for initialized modules dynamically. 
The modules can be hardware API, high-level functions, or experiment workflow.
With the least modification of the current workflow, user can design, save and run their experiment and monitor the process. 
## AI assistant
To streamline the experimental design on SDLs, we also integrate Large Language Models (LLMs) to interpret the inspected functions and generate code according to task descriptions.

## Installation
```
pip install ivoryos
```

## Usage
In your SDL script, use `ivoryos(__name__)`. Example in [abstract_sdl.py](https://gitlab.com/heingroup/ivoryos/-/blob/main/example/dummy_ur/dummy_deck.py)

```python
from ivoryos import ivoryos

ivoryos(__name__)
```


## Enable LLMs with [OpenAI API](https://github.com/openai/openai-python)
1. Create a `.env` file for `OPENAI_API_KEY`
```
OPENAI_API_KEY="Your API Key"
```
2. In your SDL script, define model, you can use any GPT models.

```python
from ivoryos import ivoryos

ivoryos(__name__, model="gpt-3.5-turbo")
```

## Enable local LLMs with [Ollama](https://ollama.com/)
1. Download Ollama.
2. pull models from Ollama
3. In your SDL script, define LLM server and model, you can use any models available on Ollama.

```python
from ivoryos import ivoryos

ivoryos(__name__, llm_server="localhost", model="llama3.1")
```

## Developing
This is a wip project. Here are some future actions.
1. Support @setter decorator.
2. Documentation: white paper wip
3. Compatibility: compatability report to open-source lab hardware APIs will soon be added. As of now, due to the limitation of web form, the usability of APIs with object inputs (e.g. Opentron Python API) is very limited.


## Authors and Acknowledgement
Ivory Zhang, Lucy Hao

Authors acknowledge all former and current Hein Lab members for their valuable suggestions. 

## License
[LICENSE](LICENSE)
