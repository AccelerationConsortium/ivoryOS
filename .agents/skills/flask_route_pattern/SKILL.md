---
name: flask_route_pattern
description: How to create and register a new route, Blueprint, or plugin page in the IvoryOS Flask app
---

# IvoryOS Flask Route & Blueprint Pattern

> **Building an external plugin page?** Use the `plugin_page_pattern` skill in the
> [IvoryOS Plugin Template repo](https://github.com/ivoryos-ai/IvoryOS-plugin-template)
> (`.agents/skills/plugin_page_pattern/SKILL.md`). That skill covers the `base.html`
> integration trick, standalone dev mode, and SocketIO registration.
> This skill covers adding routes **inside** the IvoryOS core package.

IvoryOS uses Flask Blueprints organised by feature area. Read this skill whenever you are
adding a new page, API endpoint, or plugin tab.

---

## 1. Understand the Blueprint Map

All Blueprints are imported and registered in `ivoryos/app.py` at **module level** (before `create_app()`):

```python
# app.py lines 27-33
app.register_blueprint(main,    url_prefix=url_prefix)             # /ivoryos
app.register_blueprint(auth,    url_prefix=f'{url_prefix}/auth')
app.register_blueprint(library, url_prefix=f'{url_prefix}/library')
app.register_blueprint(control, url_prefix=f'{url_prefix}/instruments')
app.register_blueprint(design,  url_prefix=f'{url_prefix}')       # shares root!
app.register_blueprint(execute, url_prefix=f'{url_prefix}')       # shares root!
app.register_blueprint(data,    url_prefix=f'{url_prefix}')       # shares root!
```

> **Warning**: `design`, `execute`, and `data` share `url_prefix=url_prefix`. Be careful about
> route name collisions when adding routes to any of these blueprints.

`url_prefix` is read from the `URL_PREFIX` environment variable (default `/ivoryos`).

---

## 2. Adding a Route to an Existing Blueprint

**Example**: adding a route to the `data` blueprint.

```
ivoryos/routes/data/
  data.py          ← add your @data.route() here
  templates/       ← add your .html template here
```

```python
# ivoryos/routes/data/data.py
from flask import Blueprint, render_template, jsonify
from flask_login import login_required

data = Blueprint('data', __name__, template_folder='templates')

@data.route('/my-new-page', methods=['GET'])
@login_required
def my_new_page():
    return render_template('my_new_page.html', ivoryos_version=ivoryos_version)
```

**Template convention**: always `{% extends "base.html" %}` and pass any required context
variables (especially `ivoryos_version` if the template displays it).

---

## 3. Creating a Brand-New Blueprint (new feature area)

```
ivoryos/routes/myfeature/
  __init__.py       ← empty
  myfeature.py      ← Blueprint definition + routes
  templates/
    myfeature/
      index.html
```

```python
# ivoryos/routes/myfeature/myfeature.py
from flask import Blueprint, render_template
from flask_login import login_required

myfeature = Blueprint('myfeature', __name__, template_folder='templates')

@myfeature.route('/', strict_slashes=False)
@login_required
def index():
    return render_template('myfeature/index.html')
```

Then register it in `app.py`:

```python
# ivoryos/app.py  — add near line 20 (imports)
from ivoryos.routes.myfeature.myfeature import myfeature

# and near line 33 (registrations)
app.register_blueprint(myfeature, url_prefix=f'{url_prefix}/myfeature')
```

---

## 4. Plugin Blueprints (preferred for extensions)

If the feature is an **optional extension** (not part of the IvoryOS core), use the plugin
system instead of modifying `app.py`:

```python
# my_plugin.py  (in user's project, not inside ivoryos/)
from flask import Blueprint, render_template

my_plugin = Blueprint('my_plugin', __name__, template_folder='templates')
my_plugin.plugin_type = "tab"  # "tab" | "modal" | "sidebar"

@my_plugin.route('/', strict_slashes=False)
def index():
    return render_template('my_plugin/index.html')

def init_socketio(socketio):
    """Called automatically by ivoryos.server if present."""
    @socketio.on('my_event')
    def handle_my_event(data):
        pass
```

Then pass it to `run()`:

```python
import ivoryos
ivoryos.run(module=__name__, blueprint_plugins=[my_plugin])
```

The plugin will be mounted at `/ivoryos/my_plugin` and appear in the nav automatically.

---

## 5. Static Files

- JS: `ivoryos/static/js/my_feature.js`
- CSS: `ivoryos/static/css/my_feature.css`

Reference them in templates using:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/my_feature.css') }}">
<script src="{{ url_for('static', filename='js/my_feature.js') }}"></script>
```

The static URL path is configured in `app.py` as `static_url_path=f'{url_prefix}/static'`.

---

## 6. Template Context & Base Template

Standard context variables available in all templates via `@app.before_request` and
`@app.context_processor`:

| Variable | Source | Purpose |
|---|---|---|
| `g.logger` | `before_request` | GUI logger |
| `g.socketio` | `before_request` | SocketIO instance |
| `enable_design` | context_processor | Whether the design canvas is enabled |
| `plugins` | context_processor | List of registered plugin dicts |
| `ivoryos_version` | pass explicitly | Version string from `ivoryos.version` |

Always `{% extends "base.html" %}` unless the page is a standalone (e.g. login page).

---

## 7. API / JSON Endpoints

For JSON APIs used by the frontend JS:

```python
from flask import jsonify, request

@myfeature.route('/api/data', methods=['GET'])
@login_required
def api_data():
    return jsonify({'status': 'ok', 'data': []})
```

For SocketIO interactions (preferred for real-time), register handlers in `socket_handlers.py`
or use `init_socketio()` in your plugin blueprint.

---

## 8. Authentication

- Use `@login_required` from `flask_login` on all protected routes.
- Demo mode (`DemoConfig`) uses a fake `SessionDemoUser`; never check `current_user.id` for data isolation in demo mode.
- The login view is `auth.login`.

---

## 9. Checklist Before Finishing

- [ ] Blueprint imported and registered in `app.py` (or passed as plugin)
- [ ] `url_prefix` uses the `url_prefix` variable, not a hardcoded string
- [ ] Template extends `base.html` and uses correct block names
- [ ] All protected routes decorated with `@login_required`
- [ ] Static assets in `ivoryos/static/js` or `ivoryos/static/css`
- [ ] No new route names conflict with existing ones in shared-prefix blueprints
