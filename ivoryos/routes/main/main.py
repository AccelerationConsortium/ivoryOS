import os

from flask import Blueprint, render_template, current_app, request, url_for
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename, redirect
from ivoryos.utils.db_models import db
from ivoryos.version import __version__ as ivoryos_version

main = Blueprint('main', __name__, template_folder='templates')

@main.route("/")
@login_required
def index():
    """
    .. :quickref: Home page; ivoryos home page

    Home page for all available routes

    .. http:get:: /

    """
    off_line = current_app.config["OFF_LINE"]
    return render_template('home.html', off_line=off_line, version=ivoryos_version)


@main.route("/help")
def help_info():
    """
    .. :quickref: Help page; ivoryos info page

    static information page

    .. http:get:: /help

    """
    sample_deck = """
    from vapourtec.sf10 import SF10

    # connect SF10 pump
    sf10 = SF10(device_port="com7")

    # start ivoryOS
    from ivoryos.app import ivoryos
    ivoryos(__name__)
    """
    return render_template('help.html', sample_deck=sample_deck)


@main.route('/customize-logo', methods=['POST'])
@login_required
def customize_logo():
    if request.method == 'POST':
        file = request.files.get('logo')
        mode = request.form.get('mode')

        if file and file.filename != '':
            filename = secure_filename(file.filename)

            USER_LOGO_DIR = os.path.join(current_app.static_folder, "user_logos")
            os.makedirs(USER_LOGO_DIR, exist_ok=True)
            filepath = os.path.join(USER_LOGO_DIR, filename)
            file.save(filepath)

            # Save to database
            current_user.settings = {"logo_filename": filename, "logo_mode": mode}
            # current_user.logo_mode = mode
            db.session.commit()

        return redirect(url_for('main.index'))

