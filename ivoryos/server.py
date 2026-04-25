import os
import sqlite3
import sys
from typing import Union

from flask import Blueprint

from sqlalchemy import Engine, event

# from ivoryos import BUILDING_BLOCKS
from ivoryos.app import create_app
from ivoryos.config import Config, get_config
from ivoryos.optimizer.registry import OPTIMIZER_REGISTRY
from ivoryos.routes.auth.auth import login_manager
from ivoryos.routes.control.control import global_config
from ivoryos.socket_handlers import socketio
from ivoryos.utils import utils
from ivoryos.utils.db_models import db, User, Script


url_prefix = os.getenv('URL_PREFIX', "/ivoryos")

@event.listens_for(Engine, "connect")
def enforce_sqlite_foreign_keys(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()



@login_manager.user_loader
def load_user(user_id):
    """
    This function is called by Flask-Login on every request to get the
    current user object from the user ID stored in the session.
    """
    # The correct implementation is to fetch the user from the database.
    return db.session.get(User, user_id)


def import_templates_from_dir(dir_path: str):
    """
    Import templates (JSON files) from a directory into the local database.
    """
    import json
    
    if not os.path.exists(dir_path):
        print(f"Directory {dir_path} does not exist.")
        return

    # Check if we are already inside a Flask app context
    from flask import current_app
    app_ctx = None
    if not current_app:
        app = create_app()
        app_ctx = app.app_context()
        app_ctx.push()

    try:
        if sys.argv and sys.argv[0]:
            deck_name = os.path.splitext(os.path.basename(sys.argv[0]))[0]
        else:
            deck_name = "main"

        for filename in os.listdir(dir_path):
            if not filename.endswith(".json"):
                continue

            file_path = os.path.join(dir_path, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON template in {filename}: {e}")
                continue
            except Exception as e:
                print(f"Error reading template {filename}: {e}")
                continue

            name = data.get("name")
            if not name:
                name = os.path.splitext(filename)[0]
                data["name"] = name
                
            data["deck"] = deck_name
            if "author" not in data or not data["author"]:
                data["author"] = "admin"

            try:
                exist_script = db.session.get(Script, name)
                data.pop('_sa_instance_state', None)
                
                if exist_script:
                    for k, v in data.items():
                        if hasattr(exist_script, k):
                            setattr(exist_script, k, v)
                else:
                    new_script = Script()
                    for k, v in data.items():
                        if hasattr(new_script, k):
                            setattr(new_script, k, v)
                    db.session.add(new_script)
                
                db.session.commit()
                # print(f"Successfully imported template: {name}")
            except Exception as db_err:
                db.session.rollback()
                print(f"Database error while importing {name} from {filename}: {db_err}")
                
    except Exception as e:
        print(f"Error importing templates from {dir_path}: {e}")
    finally:
        if app_ctx:
            app_ctx.pop()





def run(module=None, host="0.0.0.0", port=None, debug=None, llm_server=None, model=None,
        config: Config = None,
        logger: Union[str, list] = None,
        logger_output_name: str = None,
        enable_design: bool = True,
        blueprint_plugins: Union[list, Blueprint] = [],
        exclude_names: list = [],
        notification_handler=None,
        optimizer_registry: dict = None,
        templates_dir: str = "templates",
        ):
    """
    Start ivoryOS app server.

    :param module: module name, __name__ for current module
    :param host: host address, defaults to 0.0.0.0
    :param port: port, defaults to None, and will use 8000
    :param debug: debug mode, defaults to None (True)
    :param llm_server: llm server, defaults to None. If None or incorrect, app will run without design-agent feature
    :param model: llm model, defaults to None. If None or incorrect, app will run without design-agent feature
    :param config: config class, defaults to None
    :param logger: logger name of list of logger names, defaults to None
    :param logger_output_name: log file save name of logger, defaults to None, and will use "default.log"
    :param enable_design: enable design canvas, database and workflow execution
    :param blueprint_plugins: Union[list[Blueprint], Blueprint] custom Blueprint pages
    :param exclude_names: list[str] module names to exclude from parsing
    :param notification_handler: notification handler function
    :param templates_dir: directory to import templates from, defaults to "templates"
    """
    # Prevent multiple IvoryOS instances from running simultaneously
    if os.environ.get("IVORYOS_ACTIVE"):
        return
    os.environ["IVORYOS_ACTIVE"] = "1"

    app = create_app(config_class=config or get_config())  # Create app instance using factory function

    if templates_dir:
        resolved_templates_dir = templates_dir
        if module and not os.path.isabs(templates_dir):
            if module in sys.modules and hasattr(sys.modules[module], "__file__"):
                caller_dir = os.path.dirname(os.path.abspath(sys.modules[module].__file__))
                resolved_templates_dir = os.path.join(caller_dir, templates_dir)
        with app.app_context():
            import_templates_from_dir(resolved_templates_dir)

    # plugins = load_installed_plugins(app, socketio)
    plugins = []
    if blueprint_plugins:
        config_plugins = load_plugins(blueprint_plugins, app, socketio)
        plugins.extend(config_plugins)

    def inject_nav_config():
        """Make NAV_CONFIG available globally to all templates."""
        return dict(
            enable_design=enable_design,
            plugins=plugins,
        )

    app.context_processor(inject_nav_config)
    port = port or int(os.environ.get("PORT", 8000))
    debug = debug if debug is not None else app.config.get('DEBUG', True)

    app.config["LOGGERS"] = logger
    app.config["LOGGERS_PATH"] = logger_output_name or app.config["LOGGERS_PATH"]  # default.log
    logger_path = os.path.join(app.config["OUTPUT_FOLDER"], app.config["LOGGERS_PATH"])
    dummy_deck_path = os.path.join(app.config["OUTPUT_FOLDER"], app.config["DUMMY_DECK"])
    if optimizer_registry:
        global_config.optimizers = optimizer_registry
    else:
        global_config.optimizers = OPTIMIZER_REGISTRY
    if module:
        app.config["MODULE"] = module
        app.config["OFF_LINE"] = False
        global_config.deck = sys.modules[module]
        global_config.building_blocks = utils.create_block_snapshot()
        global_config.deck_snapshot = utils.create_deck_snapshot(global_config.deck,
                                                                 output_path=dummy_deck_path,
                                                                 save=True,
                                                                 exclude_names=exclude_names
                                                                 )
        global_config.api_variables = utils.create_module_snapshot(global_config.deck)

    else:
        app.config["OFF_LINE"] = True
    
    # --- Design agent ---
    if model:
        app.config["LLM_MODEL"] = model
        app.config["LLM_SERVER"] = llm_server
        from ivoryos.utils.llm_agent import LlmAgent
        
        try:
            llm_agent = LlmAgent(
                base_url=llm_server, 
                model=model, 
                output_path=app.config["OUTPUT_FOLDER"]
            )
            # lightweight request to verify LLM API connection
            llm_agent.client.models.list() 
            
            global_config.agent = llm_agent
            app.config["ENABLE_AGENT"] = True
            
        except Exception as e:
            print(f"Failed to enable LLM Agent: {e}")
            global_config.agent = None
            app.config["ENABLE_AGENT"] = False
    else:
        app.config["ENABLE_AGENT"] = False


    # --- Logger registration ---
    if logger:
        if isinstance(logger, str):
            logger = [logger]  # convert single logger to list
        elif not isinstance(logger, list):
            raise TypeError("logger must be a string or a list of strings.")

        for log_name in logger:
            utils.start_logger(socketio, log_filename=logger_path, logger_name=log_name)

    # --- Notification handler registration ---
    if notification_handler:

        # make it a list if a single function is passed
        if callable(notification_handler):
            notification_handler = [notification_handler]

        if not isinstance(notification_handler, list):
            raise ValueError("notification_handlers must be a callable or a list of callables.")

        # validate all items are callable
        for handler in notification_handler:
            if not callable(handler):
                raise TypeError(f"Handler {handler} is not callable.")
            global_config.register_notification(handler)

    # always print server
    ip = utils.get_local_ip()
    print(f"Server running at http://localhost:{port}")
    print(f"Server running at http://127.0.0.1:{port}")
    if not ip == "127.0.0.1":
        print(f"Server running at http://{ip}:{port}")
    socketio.run(app, host=host, port=port, debug=debug, use_reloader=False, allow_unsafe_werkzeug=True)
    # return app



def load_plugins(blueprints: Union[list, Blueprint], app, socketio):
    """
    Dynamically load installed plugins and attach Flask-SocketIO.
    :param blueprints: Union[list, Blueprint] list of Blueprint objects or a single Blueprint object
    :param app: Flask application instance
    :param socketio: Flask-SocketIO instance
    :return: list of plugin dicts with name and type
    """
    plugin_list = []
    if not isinstance(blueprints, list):
        blueprints = [blueprints]
    for blueprint in blueprints:
        # If the plugin has an `init_socketio()` function, pass socketio
        if hasattr(blueprint, 'init_socketio'):
            blueprint.init_socketio(socketio)
        
        plugin_info = {
            "name": blueprint.name,
            "type": getattr(blueprint, "plugin_type", "tab")
        }
        plugin_list.append(plugin_info)
        app.register_blueprint(blueprint, url_prefix=f"{url_prefix}/{blueprint.name}")
    return plugin_list

