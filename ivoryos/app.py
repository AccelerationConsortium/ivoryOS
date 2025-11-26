import os
import uuid

import bcrypt
from flask import Flask, session, g, redirect, url_for
from flask_login import AnonymousUserMixin

from ivoryos.utils import utils
from ivoryos.utils.db_models import db, User
from ivoryos.routes.auth.auth import auth, login_manager
from ivoryos.routes.control.control import control
from ivoryos.routes.data.data import data
from ivoryos.routes.library.library import library
from ivoryos.routes.design.design import design
from ivoryos.routes.execute.execute import execute
from ivoryos.socket_handlers import socketio
from ivoryos.routes.main.main import main
from ivoryos.version import __version__ as ivoryos_version
from sqlalchemy import inspect, text

url_prefix = os.getenv('URL_PREFIX', "/ivoryos")
app = Flask(__name__, static_url_path=f'{url_prefix}/static', static_folder='static')
app.register_blueprint(main, url_prefix=url_prefix)
app.register_blueprint(auth, url_prefix=f'{url_prefix}/{auth.name}')
app.register_blueprint(library, url_prefix=f'{url_prefix}/{library.name}')
app.register_blueprint(control, url_prefix=f'{url_prefix}/instruments')
app.register_blueprint(design, url_prefix=f'{url_prefix}')
app.register_blueprint(execute, url_prefix=f'{url_prefix}')
app.register_blueprint(data, url_prefix=f'{url_prefix}')
# app.register_blueprint(api, url_prefix=f'{url_prefix}/{api.name}')

def reset_old_schema(engine, db_dir):
    inspector = inspect(engine)
    tables = inspector.get_table_names()


    # Check if old tables exist (no workflow_phases table)
    has_workflow_phase = 'workflow_phases' in tables
    old_workflow_run = 'workflow_runs' in tables
    old_workflow_step = 'workflow_steps' in tables

    # v1.3.4 only delete and backup when there is runs but no phases
    if not has_workflow_phase and old_workflow_run:
        print("⚠️ Old workflow database detected! All previous workflows have been reset to support the new schema.")
        # Backup old DB
        db_path = os.path.join(db_dir, "ivoryos.db")
        if os.path.exists(db_path):
            # os.makedirs(backup_dir, exist_ok=True)
            from datetime import datetime
            import shutil
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(db_dir, f"ivoryos_backup_{ts}.db")
            shutil.copy(db_path, backup_path)
            print(f"Backup created at {backup_path}")
        with engine.begin() as conn:
            # Drop old tables
            if old_workflow_step:
                conn.execute(text("DROP TABLE IF EXISTS workflow_steps"))
            if old_workflow_run:
                conn.execute(text("DROP TABLE IF EXISTS workflow_runs"))
    with engine.begin() as conn:
        try:
            conn.execute(
                text("ALTER TABLE user ADD COLUMN settings TEXT")
            )
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE script ADD COLUMN description TEXT"))
        except Exception:
            pass
    # Recreate new schema
    db.create_all()  # creates workflow_runs, workflow_phases, workflow_steps


def create_admin():
    """
    Create an admin user with username 'admin' and password 'admin' if it doesn't exist.
    """
    with app.app_context():
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            print("Creating default admin user...")
            admin_user = User(
                username='admin',
                password=bcrypt.hashpw("admin".encode('utf-8'), bcrypt.gensalt()),
            )
            db.session.add(admin_user)
            db.session.commit()
        else:
            print("Admin user already exists.")


def create_app(config_class=None):
    """
    create app, init database
    """

    app.config.from_object(config_class or 'config.get_config()')
    os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)
    # Initialize extensions
    socketio.init_app(app, cors_allowed_origins="*", cookie=None)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    db.init_app(app)

    # Create database tables
    with app.app_context():
        # db.create_all()
        reset_old_schema(db.engine, app.config['OUTPUT_FOLDER'])
        create_admin()

    # Additional setup
    utils.create_gui_dir(app.config['OUTPUT_FOLDER'])

    # logger_list = app.config["LOGGERS"]
    logger_path = os.path.join(app.config["OUTPUT_FOLDER"], app.config["LOGGERS_PATH"])
    logger = utils.start_logger(socketio, 'gui_logger', logger_path)

    @app.before_request
    def before_request():
        """
        Called before

        """
        g.logger = logger
        g.socketio = socketio
        session.permanent = False
        # DEMO_MODE: Simulate logged-in user per session
        if app.config.get("DEMO_MODE", False):
            if "demo_user_id" not in session:
                session["demo_user_id"] = f"demo_{str(uuid.uuid4())[:8]}"

            class SessionDemoUser(AnonymousUserMixin):
                @property
                def is_authenticated(self):
                    return True

                def get_id(self):
                    return session.get("demo_user_id")

            login_manager.anonymous_user = SessionDemoUser



    @app.route('/')
    def redirect_to_prefix():
        return redirect(url_for('main.index', version=ivoryos_version))  # Assuming 'index' is a route in your blueprint

    @app.template_filter('format_name')
    def format_name(name):
        name = name.split(".")[-1]
        text = ' '.join(word for word in name.split('_'))
        return text.capitalize()

    # app.config.setdefault("DEMO_MODE", False)
    return app