[![Documentation Status](https://readthedocs.org/projects/ivoryos/badge/?version=latest)](https://ivoryos.readthedocs.io/en/latest/?badge=latest)
[![PyPI version](https://img.shields.io/pypi/v/ivoryos)](https://pypi.org/project/ivoryos/)
![License](https://img.shields.io/pypi/l/ivoryos)
[![YouTube](https://img.shields.io/badge/YouTube-tutorial-red?logo=youtube)](https://youtu.be/dFfJv9I2-1g)
[![YouTube](https://img.shields.io/badge/YouTube-demo-red?logo=youtube)](https://youtu.be/flr5ydiE96s)
[![Published](https://img.shields.io/badge/Nature_Comm.-paper-blue)](https://www.nature.com/articles/s41467-025-60514-w)

[//]: # ([![Discord]&#40;https://img.shields.io/discord/1313641159356059770?label=Discord&logo=discord&color=5865F2&#41;]&#40;https://discord.gg/AX5P9EdGVX&#41;)

![](https://gitlab.com/heingroup/ivoryos/raw/main/docs/source/_static/ivoryos.png)
# ivoryOS: interoperable Web UI for self-driving laboratories (SDLs)
A **plug-and-play** web interface for flexible SDLs 

---

## Table of Contents
- [Description](#description)
- [System requirements](#system-requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Features](#features)
- [Demo](#demo)
- [Roadmap](#roadmap)
- [Acknowledgements](#acknowledgements)

---
## Description
Building UIs for SDLs is challenging because flexibility and modularity make them unpredictable — yet accessibility is essential for **democratisation** of AI-driven scientific discovery.

**IvoryOS** bridges the gap by:
- Dynamically inspecting initialized Python modules (hardware APIs, high-level functions, or workflows)
- Automatically displaying functions and parameters in a web UI
- Allowing users to **design**, **manage**, and **execute** experimental workflows with minimal changes to existing scripts
- Providing natural language support for workflow design and execution, check [IvoryOS MCP](https://gitlab.com/heingroup/ivoryos-suite/ivoryos-mcp) for more details.

----
## System Requirements

**Platforms:** Compatible with Linux, macOS, and Windows (developed/tested on Windows).  
**Python:**  
- Recommended: Python ≥3.10  
- Minimum: Python ≥3.7 (without Ax optimizer support) 

**Core Dependencies:**
<details>
<summary>Click to expand</summary>

- bcrypt~=4.0  
- Flask-Login~=0.6  
- Flask-Session~=0.8  
- Flask-SocketIO~=5.3  
- Flask-SQLAlchemy~=3.1  
- SQLAlchemy-Utils~=0.41  
- Flask-WTF~=1.2  
- python-dotenv==1.0.1  

**Optional:**
- ax-platform (≥1.0, Python≥3.10)
- baybe
</details>

---


## Installation
From PyPI:
```bash
pip install ivoryos
```
From source:
```bash
git clone https://gitlab.com/heingroup/ivoryos.git
cd ivoryos
pip install -e .
```


## Quick start
In your SDL script, 
```python
my_robot = Robot()

import ivoryos

ivoryos.run(__name__)
```
You can now access the web UI at http://127.0.0.1:8000,
create an account, login, and start designing workflows!

----
## Features
### Direct control: 
direct function calling _Devices_ tab
### Workflows
  - **Design Editor**: drag/add function to canvas in _Design_ tab. click `Compile and Run` button to go to the execution configuration page
  - **Execution Config**: configure iteration methods and parameters in _Compile/Run_ tab. 
  - **Design Library**: manage workflow scripts in _Library_ tab.
  - **Workflow Data**: Execution records are in _Data_ tab.
### Offline mode
after one successful connection, a blueprint will be automatically saved and made accessible without hardware connection. In a new Python script in the same directory, use `ivoryos.run()` to start offline mode.



### Logging
Add single or multiple loggers:
```python
ivoryos.run(__name__, logger="logger name")
ivoryos.run(__name__, logger=["logger 1", "logger 2"])
```
### Human-in-the-loop
Add single or multiple notification handlers for `pause` feature in flow control:
```python

def slack_bot(msg: str = "Hi"):
    """
    a function that can be used as a notification handler function("msg")
    :param msg: message to send
    """
    from slack_sdk import WebClient

    slack_token = "your slack token"
    client = WebClient(token=slack_token)

    my_user_id = "your user id"  # replace with your actual Slack user ID

    client.chat_postMessage(channel=my_user_id, text=msg)

import ivoryos
ivoryos.run(__name__, notification_handler=slack_bot)
```

### Directory Structure

Created automatically on first run:
- **`ivoryos_data/`**: 
  - **`ivoryos_data/config_csv/`**: Batch configuration `csv`
  - **`ivoryos_data/pseudo_deck/`**: Offline deck `.pkl`
  - **`ivoryos_data/results/`**: Execution results
  - **`ivoryos_data/scripts/`**: Compiled workflows Python scripts
- **`default.log`**: Application logs
- **`ivoryos.db`**: Local database
---
## Demo
In the [abstract_sdl.py](https://gitlab.com/heingroup/ivoryos/-/blob/main/example/abstract_sdl_example/abstract_sdl.py)
```Python
ivoryos.run(__name__)
```

 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:8000
 * Running on http://0.0.0.0:8000

---

## Roadmap

- [ ] dropdown input 
- [ ] snapshot version control
- [ ] optimizer-agnostic
- [ ] prefect compatibility
- [ ] check batch-config file compatibility

---

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
---
## Acknowledgements
Authors acknowledge Telescope Innovations Corp., UBC Hein Lab, and Acceleration Consortium members for their valuable suggestions and contributions.
