from flask import Blueprint, render_template, current_app
from flask_login import login_required
from ivoryos.version import __version__ as ivoryos_version

main = Blueprint('main', __name__, template_folder='templates/main')

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
