# Integrator docs

These docs are for people who expose instruments, Python modules, workflow functions, and external systems to IvoryOS.

IvoryOS is Python-native. You do not need decorators, YAML pipelines, a custom workflow language, or hand-written frontend bindings to start integrating a platform. Expose normal Python objects and functions; IvoryOS reads signatures, defaults, type hints, and docstrings to generate controls and workflow actions.

Start with [Quick start](quick-start.md) to install IvoryOS and launch a Python platform. Use [Runtime API reference](usage.rst) for `ivoryos.run(...)` settings, [Python-native integration](python-native-integration.md) for the basic integration model, and [Input types and UI controls](input-types.md) for typed parameters and Enum dropdowns. The client, MCP, and plugin-template pages are generated from the upstream suite READMEs during the Sphinx build.

```{toctree}
:maxdepth: 2

quick-start
usage
python-native-integration
input-types
remote-instrument-proxy
plugins
client-api
mcp-server
```
