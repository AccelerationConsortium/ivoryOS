import os
from copy import deepcopy

from flask import Blueprint,  request,current_app, send_file
from flask_login import login_required

from ivoryos.services.client_proxy import ProxyGenerator
from ivoryos.runtime.state import GlobalState

global_state = GlobalState()

control_file = Blueprint('file', __name__)



@control_file.route("/files/proxy", strict_slashes=False)
@login_required
def download_proxy():
    """
    .. :quickref: Direct Control Files; Download proxy Python interface

    download proxy Python interface

    .. http:get:: /instruments/files/proxy
    """
    generator = ProxyGenerator(request.url_root)
    interface_schema = deepcopy(global_state.interface_schema)
    filepath = generator.generate_from_flask_route(
        interface_schema,
        request.url_root,
        current_app.config["OUTPUT_FOLDER"]
    )
    return send_file(os.path.abspath(filepath), as_attachment=True)
