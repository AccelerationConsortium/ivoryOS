[![Documentation Status](https://readthedocs.org/projects/ivoryos/badge/?version=latest)](https://ivoryos.readthedocs.io/en/latest/?badge=latest)
[![PyPI version](https://img.shields.io/pypi/v/ivoryos)](https://pypi.org/project/ivoryos/)
![License](https://img.shields.io/pypi/l/ivoryos)
[![YouTube](https://img.shields.io/badge/YouTube-tutorial-red?logo=youtube)](https://youtu.be/dFfJv9I2-1g)
[![YouTube](https://img.shields.io/badge/YouTube-demo-red?logo=youtube)](https://youtu.be/flr5ydiE96s)
[![Published](https://img.shields.io/badge/Nature_Comm.-paper-blue)](https://www.nature.com/articles/s41467-025-60514-w)
[![Community](https://img.shields.io/discord/1313641159356059770?label=Discord&logo=discord&color=5865F2)](https://discord.gg/3KdjhUmsYA)

![ivoryos_logo.png](https://gitlab.com/heingroup/ivoryos/raw/main/docs/source/_static/ivoryos_logo.png)

# [IvoryOS](https://ivoryos.ai): interoperable orchestrator for self-driving laboratories (SDLs) 

A **plug-and-play** web interface for flexible, modular SDLs —
you focus on developing protocols, IvoryOS handles the rest.

![code_launch_design.png](https://gitlab.com/heingroup/ivoryos/raw/main/docs/source/_static/code_launch_design.png)

---

## Table of Contents
- [What IvoryOS does](#what-ivoryos-does)
- [System requirements](#system-requirements)
- [Installation](#installation)
- [Features](#features)
- [Demo](#demo)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Acknowledgements](#acknowledgements)

---
## What IvoryOS Does
- Turns Python modules into UIs by dynamically inspecting your hardware APIs, functions, and workflows.
- Standardizes optimization inputs/outputs, making any optimizer plug-and-play.
- Provides a visual workflow builder for designing and running experiments.
- Adds natural-language control for creating and executing workflows, see [IvoryOS MCP](https://gitlab.com/heingroup/ivoryos-suite/ivoryos-mcp) for more details.

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
- pandas

**Optional:**
- ax-platform==1.1.2
- baybe==0.14.0
- nimo
- slack-sdk
</details>

---


## Installation
From PyPI:
```bash
pip install ivoryos
```

[//]: # (From source:)

[//]: # (```bash)

[//]: # (git clone https://gitlab.com/heingroup/ivoryos.git)

[//]: # (cd ivoryos)

[//]: # (pip install -e .)

[//]: # (```)


## Quick start
In your script, where you initialize or import your robot:
```python
my_robot = Robot()

import ivoryos

ivoryos.run(__name__)
```
Then run the script and visit `http://localhost:8000` in your browser.
Use `admin` for both username and password, and start building workflows!

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
Use `pause` in flow control to pause the workflow and send a notification with custom message handler(s). 
When run into `pause`, it will pause, send a message, and wait for human's response. Example of a Slack bot:
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

Created automatically in the same working directory on the first run:
<details>
<summary>click to see the data folder structure</summary>

- **`ivoryos_data/`**: 
  - **`config_csv/`**: Batch configuration `csv`
  - **`pseudo_deck/`**: Offline deck `.pkl`
  - **`results/`**: Execution results
  - **`scripts/`**: Compiled workflows Python scripts
  - **`default.log`**: Application logs
  - **`ivoryos.db`**: Local database
</details>

---

## Demo
Online demo at [demo.ivoryos.ai](https://demo.ivoryos.ai). 
Local version in [abstract_sdl.py](https://gitlab.com/heingroup/ivoryos/-/blob/main/community/examples/abstract_sdl_example/abstract_sdl.py)

---

## Roadmap
- [ ] Python property support (setter/getter)
- [ ] dropdown input 
- [ ] snapshot version control
- [ ] check batch-config file compatibility

---

## Contributing

We welcome all contributions — from core improvements to new drivers, plugins, and real-world use cases.
See `CONTRIBUTING.md` for details and let us know you're interested: https://forms.gle/fPSvw5LEGrweUQUH8

---

## Citing

<details>
<summary>Click to see citations</summary>

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
</details>

---
## Acknowledgements
Authors acknowledge Telescope Innovations Corp., UBC Hein Lab, and Acceleration Consortium members for their valuable suggestions and contributions.
