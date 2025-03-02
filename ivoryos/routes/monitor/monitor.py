from flask import Blueprint, flash, render_template
from flask_login import login_required

from ivoryos.utils.global_config import GlobalConfig

global_config = GlobalConfig()

monitor = Blueprint('monitor', __name__, template_folder='templates/monitor')


@monitor.route("/stream_feed")
@login_required
def stream_feed():
    """
    .. :quickref: Monitor; stream feed

    display feed by ip address
    e.g. HeinSight output feed
    .. http:get:: /my_deck
    """
    return render_template('monitor.html', stream_address="http://127.0.0.1:8001/frame")
