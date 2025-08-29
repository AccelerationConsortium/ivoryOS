import os
from flask import Blueprint,  request,current_app, send_file
from flask_login import login_required

from ivoryos.utils.client_proxy import ProxyGenerator
from ivoryos.utils.global_config import GlobalConfig

global_config = GlobalConfig()

control_file = Blueprint('file', __name__)



@control_file.route("/files/proxy", strict_slashes=False)
@login_required
def download_proxy():
    """
    .. :quickref: Direct Control Files; Download proxy Python interface

    download proxy Python interface

    .. http:get:: /files/proxy
    """
    generator = ProxyGenerator(request.url_root)
    snapshot = global_config.deck_snapshot.copy()

    filepath = generator.generate_from_flask_route(
        snapshot,
        request.url_root,
        current_app.config["OUTPUT_FOLDER"]
    )

    return send_file(os.path.abspath(filepath), as_attachment=True)