Hello World Plugin for IvoryOS
================================

This is a template plugin for extending IvoryOS with standalone pages. It demonstrates how to structure a plugin using Flask's Blueprint system and integrate with IvoryOS through an entry point.

Features
--------

- Uses Flask's ``Blueprint`` to modularize the plugin.
- Includes a WebSocket (``SocketIO``) integration.
- Can function as a standalone page or as part of the IvoryOS ecosystem.
- Requires an entry point in ``setup.py`` for automatic discovery.

.. image:: docs/img.png
   :alt: Plugin Structure Image

Plugin Structure
----------------

.. code-block::

    ivoryos_plugin/
    ├── templates/
    │   ├── example.html    # Template file for the plugin
    ├── __init__.py
    ├── hello_world.py      # Main plugin file
    MANIFEST.in             # installation include/exclude
    setup.py                # Plugin installation file
    README.md

Main Plugin File: ``hello_world.py``
------------------------------------

The plugin must define a ``main`` function inside a Flask ``Blueprint``. This function serves as the main route of the plugin (quick access in the navigation panel).

.. code-block:: python

    from flask import render_template, Blueprint, current_app
    import os

    plugin = Blueprint("plugin", __name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))

    @plugin.route('/')
    def main():
        base_exists = "base.html" in current_app.jinja_loader.list_templates()
        return render_template('example.html', base_exists=base_exists)

Blueprint in Flask
------------------

Flask's ``Blueprint`` is used to organize routes and views into separate modules. This makes it easy to create modular and reusable components.

- ``Blueprint("plugin", __name__, template_folder=...)`` defines a new component that can be registered in a Flask app.
- The ``@plugin.route('/')`` decorator sets up a route for the plugin.
- When used inside IvoryOS, the ``Blueprint`` is registered dynamically, allowing for extension without modifying the core application.

Plugin Registration in ``setup.py``
-----------------------------------

Each plugin must define an entry point under ``ivoryos.plugins`` so that it can be discovered by IvoryOS.

.. code-block:: python

    from setuptools import setup, find_packages

    setup(
        ...,
        entry_points={
            "ivoryos.plugins": [
                "plugin = ivoryos_plugin.hello_world",  # Plugin entry point
            ],
        },
        ...
    )

Keynotes
--------

1. Attribute name matches the Blueprint name (e.g. both named ``plugin`` in the example)

.. code-block:: python

    plugin = Blueprint("plugin", __name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"))

2. Include ``main()`` as the main route for the plugin.
3. Entry point includes ``ivoryos.plugins`` in ``setup.py`` with the attribute name included (e.g. named ``plugin`` in the example).

Running the Plugin Standalone
-----------------------------

This plugin can also run as a standalone Flask app by executing:

.. code-block:: python

    if __name__ == '__main__':
        app = Flask(__name__)
        app.register_blueprint(plugin)
        app.run()

        # ------------------------------------------
        # ---- Option 2 - run with websocket -------
        # ------------------------------------------
        # socketio = SocketIO(app)
        # init_socketio(socketio)
        # socketio.run(app, debug=True, allow_unsafe_werkzeug=True)

This initializes the Flask app and runs the ``Blueprint`` independently.

Installing the Plugin
---------------------

To install the plugin in a Python environment:

.. code-block:: sh

    pip install .

Once installed, IvoryOS will automatically detect and load the plugin based on the entry point.

