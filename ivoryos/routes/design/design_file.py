
import json
import os
from flask import Blueprint, send_file, request, flash, redirect, url_for, current_app
from werkzeug.utils import secure_filename
from ivoryos.utils import utils

files = Blueprint('design_files', __name__)



@files.route('/files/script-json', methods=['POST'])
def load_json():
    """
    .. :quickref: Workflow Design Ext; upload a workflow design file (.JSON)

    .. http:post:: /files/script-json

    :form file: workflow design JSON file
    :status 302: load script json and then redirects to :http:get:`/ivoryos/draft`
    """

    if request.method == "POST":
        f = request.files['file']
        if 'file' not in request.files:
            flash('No file part')
        if f.filename.endswith("json"):
            script_dict = json.load(f)
            utils.post_script_file(script_dict, is_dict=True)
        else:
            flash("Script file need to be JSON file")
    return redirect(url_for("design.experiment_builder"))

@files.route('/files/script-python')
def download_python():
    """
    .. :quickref: Workflow Design Ext; export a workflow design file (.py)

    .. http:post:: /files/script-python

    :status 302: redirects to :http:get:`/ivoryos/draft`
    """
    script = utils.get_script_file()
    run_name = script.name if script.name else "untitled"
    filepath = os.path.join(current_app.config["SCRIPT_FOLDER"], f"{run_name}.py")
    return send_file(os.path.abspath(filepath), as_attachment=True)


@files.route('/files/script-json')
def download_json():
    """
    .. :quickref: Workflow Design Ext; export a workflow design file (.JSON)

    .. http:post:: /files/script-json

    :status 302: redirects to :http:get:`/ivoryos/draft`
    """
    script = utils.get_script_file()
    run_name = script.name if script.name else "untitled"

    script.sort_actions()
    json_object = json.dumps(script.as_dict())
    filepath = os.path.join(current_app.config['SCRIPT_FOLDER'], f"{run_name}.json")
    with open(filepath, "w") as outfile:
        outfile.write(json_object)
    return send_file(os.path.abspath(filepath), as_attachment=True)


