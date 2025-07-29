import os
from flask import Blueprint,  request,current_app, send_file
from flask_login import login_required

from ivoryos.utils.client_proxy import export_to_python, create_function
from ivoryos.utils.global_config import GlobalConfig

global_config = GlobalConfig()

control_file = Blueprint('file', __name__)


@control_file.route("/files/proxy", strict_slashes=False)
@login_required
def download_proxy():
    """
    .. :quickref: Direct Control Files; download proxy interface

    download proxy Python interface

    .. http:get:: /files/proxy
    """
    snapshot = global_config.deck_snapshot.copy()
    class_definitions = {}
    # Iterate through each instrument in the snapshot
    for instrument_key, instrument_data in snapshot.items():
        # Iterate through each function associated with the current instrument
        for function_key, function_data in instrument_data.items():
            # Convert the function signature to a string representation
            function_data['signature'] = str(function_data['signature'])
        class_name = instrument_key.split('.')[-1]  # Extracting the class name from the path
        class_definitions[class_name.capitalize()] = create_function(request.url_root, class_name, instrument_data)
    # Export the generated class definitions to a .py script
    export_to_python(class_definitions, current_app.config["OUTPUT_FOLDER"])
    filepath = os.path.join(current_app.config["OUTPUT_FOLDER"], "generated_proxy.py")
    return send_file(os.path.abspath(filepath), as_attachment=True)
