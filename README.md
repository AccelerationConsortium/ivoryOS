[![Documentation Status](https://readthedocs.org/projects/ivoryos/badge/?version=latest)](https://ivoryos.readthedocs.io/en/latest/?badge=latest)
[![PyPI version](https://img.shields.io/pypi/v/ivoryos)](https://pypi.org/project/ivoryos/)
![License](https://img.shields.io/pypi/l/ivoryos)
[![YouTube](https://img.shields.io/badge/YouTube-video-red?logo=youtube)](https://youtu.be/dFfJv9I2-1g)
[![Published](https://img.shields.io/badge/Nature_Comm.-paper-blue)](https://www.nature.com/articles/s41467-025-60514-w)
[![Discord](https://img.shields.io/discord/1313641159356059770?label=Discord&logo=discord&color=5865F2)](https://discord.gg/AX5P9EdGVX)

![](https://gitlab.com/heingroup/ivoryos/raw/main/docs/source/_static/ivoryos.png)
# ivoryOS: interoperable Web UI for self-driving laboratories (SDLs)
"plug and play" web UI extension for flexible SDLs.

## Table of Contents
- [Description](#description)
- [System requirements](#system-requirements)
- [Installation](#installation)
- [Instructions for use](#instructions-for-use)
- [Demo](#demo)
- [Roadmap](#roadmap)


## Description
Granting SDLs flexibility and modularity makes it almost impossible to design a UI, yet it's a necessity for allowing more people to interact with it (democratisation). 
This web UI aims to ease up the control of any Python-based SDLs by displaying functions and parameters for initialized modules dynamically. 
The modules can be hardware API, high-level functions, or experiment workflow.
With the least modification of the current workflow, user can design, manage and execute their experimental designs and monitor the execution process. 

## System requirements
This software is developed and tested using Windows. This software and its dependencies are compatible across major platforms: Linux, macOS, and Windows. Some dependencies (Flask-SQLAlchemy) may require additional setup.

### Python Version
Python >=3.10 for the best compatibility. Python >=3.7 without Ax.
### Python dependencies
This software is compatible with the latest versions of all dependencies. 
- bcrypt~=4.0
- Flask-Login~=0.6
- Flask-Session~=0.8
- Flask-SocketIO~=5.3
- Flask-SQLAlchemy~=3.1
- SQLAlchemy-Utils~=0.41
- Flask-WTF~=1.2
- python-dotenv==1.0.1
- ax-platform (optional 1.0 for Python>=3.10)
- baybe (optional)


## Installation
```bash
pip install ivoryos
```
or
```bash
git clone https://gitlab.com/heingroup/ivoryos.git
cd ivoryos
pip install .
```

The installation may take 10 to 30 seconds to install. The installation time may vary and take up to several minutes, depending on the network speed, computer performance, and virtual environment settings.

## Instructions for use
### Quick start
In your SDL script, use `ivoryos(__name__)`. 
```python
import ivoryos

ivoryos.run(__name__)
```
### Login
Create an account and login (local database with bcrypt password)
### Features
- **Direct control**: direct function calling _Devices_ tab
- **Workflows**:
  - **Design Editor**: drag/add function to canvas in _Design_ tab. click `Compile and Run` button to go to the execution configuration page
  - **Execution Config**: configure iteration methods and parameters in _Compile/Run_ tab. 
  - **Design Library**: manage workflow scripts in _Library_ tab.
  - **Workflow Data**: Execution records are in _Data_ tab.

[//]: # (![Discord]&#40;https://img.shields.io/discord/1313641159356059770&#41;)

[//]: # (![PyPI - Downloads]&#40;https://img.shields.io/pypi/dm/ivoryos&#41;)


### Additional settings
[//]: # (#### AI assistant)

[//]: # (To streamline the experimental design on SDLs, we also integrate Large Language Models &#40;LLMs&#41; to interpret the inspected functions and generate code according to task descriptions.)

[//]: # ()
[//]: # (#### Enable LLMs with [OpenAI API]&#40;https://github.com/openai/openai-python&#41;)

[//]: # (1. Create a `.env` file for `OPENAI_API_KEY`)

[//]: # (```)

[//]: # (OPENAI_API_KEY="Your API Key")

[//]: # (```)

[//]: # (2. In your SDL script, define model, you can use any GPT models.)

[//]: # ()
[//]: # (```python)

[//]: # (ivoryos.run&#40;__name__, model="gpt-3.5-turbo"&#41;)

[//]: # (```)

[//]: # ()
[//]: # (#### Enable local LLMs with [Ollama]&#40;https://ollama.com/&#41;)

[//]: # (1. Download Ollama.)

[//]: # (2. pull models from Ollama)

[//]: # (3. In your SDL script, define LLM server and model, you can use any models available on Ollama.)

[//]: # ()
[//]: # (```python)

[//]: # (ivoryos.run&#40;__name__, llm_server="localhost", model="llama3.1"&#41;)

[//]: # (```)

#### Add additional logger(s)
```python
ivoryos.run(__name__, logger="logger name")
```
or
```python
ivoryos.run(__name__, logger=["logger 1", "logger 2"])
```
#### Offline (design without hardware connection)
After one successful connection, a blueprint will be automatically saved and made accessible without hardware connection. In a new Python script in the same directory, use `ivoryos.run()` to start offline mode.

```python
ivoryos.run()
```
## Demo
In the [abstract_sdl.py](https://gitlab.com/heingroup/ivoryos/-/blob/main/example/abstract_sdl_example/abstract_sdl.py), where instances of `AbstractSDL` is created as `sdl`,
addresses will be available on terminal.
```Python
ivoryos.run(__name__)
```

 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:8000
 * Running on http://0.0.0.0:8000

### Deck function and web form 
![](https://gitlab.com/heingroup/ivoryos/raw/main/docs/source/_static/demo.gif)


### Directory structure

When you run the application for the first time, it will automatically create the following folders and files in the same directory:

- **`ivoryos_data/`**: Main directory for application-related data.
  - **`ivoryos_data/config_csv/`**: Contains iteration configuration files in CSV format.
  - **`ivoryos_data/llm_output/`**: Stores raw prompt generated for the large language model.
  - **`ivoryos_data/pseudo_deck/`**: Contains pseudo-deck `.pkl` files for offline access.
  - **`ivoryos_data/results/`**: Used for storing results or outputs during workflow execution.
  - **`ivoryos_data/scripts/`**: Holds Python scripts compiled from the visual programming script design.

- **`default.log`**: Log file that captures application logs.
- **`ivoryos.db`**: Database file that stores application data locally.


## Roadmap

- [x] Allow plugin pages ✅  
- [x] pause, resume, abort current and pending workflows ✅
- [x] dropdown input ✅  
- [x] show line number option ✅  
- [ ] snapshot version control
- [ ] optimizer-agnostic
- [ ] check batch-config file compatibility

## Citing

If you find this project useful, please consider citing the following manuscript:

> Zhang, W., Hao, L., Lai, V. et al. [IvoryOS: an interoperable web interface for orchestrating Python-based self-driving laboratories.](https://www.nature.com/articles/s41467-025-60514-w) Nat Commun 16, 5182 (2025).

```bibtex
@article{zhang_et_al_2025,
  author       = {Wenyu Zhang and Lucy Hao and Veronica Lai and Ryan Corkery and Jacob Jessiman and Jiayu Zhang and Junliang Liu and Yusuke Sato and Maria Politi and Matthew E. Reish and Rebekah Greenwood and Noah Depner and Jiyoon Min and Rama El-khawaldeh and Paloma Prieto and Ekaterina Trushina and Jason E. Hein},
  title        = {{IvoryOS}: an interoperable web interface for orchestrating {Python-based} self-driving laboratories},
  journal      = {Nature Communications},
  year         = {2025},
  volume       = {16},
  number       = {1},
  pages        = {5182},
  doi          = {10.1038/s41467-025-60514-w},
  url          = {https://doi.org/10.1038/s41467-025-60514-w}
}
```

For an additional perspective related to the development of the tool, please see:

> Zhang, W., Hein, J. [Behind IvoryOS: Empowering Scientists to Harness Self-Driving Labs for Accelerated Discovery](https://communities.springernature.com/posts/behind-ivoryos-empowering-scientists-to-harness-self-driving-labs-for-accelerated-discovery). Springer Nature Research Communities (2025).

```bibtex
@misc{zhang_hein_2025,
  author       = {Wenyu Zhang and Jason Hein},
  title        = {Behind {IvoryOS}: Empowering Scientists to Harness Self-Driving Labs for Accelerated Discovery},
  howpublished = {Springer Nature Research Communities},
  year         = {2025},
  month        = {Jun},
  day          = {18},
  url          = {https://communities.springernature.com/posts/behind-ivoryos-empowering-scientists-to-harness-self-driving-labs-for-accelerated-discovery}
}
```

## Authors and Acknowledgement
Ivory Zhang, Lucy Hao

Authors acknowledge Telescope Innovations, Hein Lab members for their valuable suggestions and contributions.
