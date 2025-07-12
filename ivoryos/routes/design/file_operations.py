import csv
import json
import os
from flask import Blueprint, send_file, request, flash, redirect, url_for, session, current_app
from werkzeug.utils import secure_filename
from ivoryos.utils import utils

files = Blueprint('design_files', __name__)

@files.route('/design/uploads', methods=['POST'])
def upload():
    """Upload a workflow config file (.CSV)"""
    if request.method == "POST":
        f = request.files['file']
        if 'file' not in request.files:
            flash('No file part')
        if f.filename.split('.')[-1] == "csv":
            filename = secure_filename(f.filename)
            f.save(os.path.join(current_app.config['CSV_FOLDER'], filename))
            session['config_file'] = filename
            return redirect(url_for("design.experiment_run"))
        else:
            flash("Config file is in csv format")
            return redirect(url_for("design.experiment_run"))

@files.route('/design/workflow/download/<filename>')
def download_results(filename):
    """Download a workflow data file"""
    filepath = os.path.join(current_app.config["DATA_FOLDER"], filename)
    return send_file(os.path.abspath(filepath), as_attachment=True)

@files.route('/design/load_json', methods=['POST'])
def load_json():
    """Upload a workflow design file (.JSON)"""
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

@files.route('/design/script/download/<filetype>')
def download(filetype):
    """Download a workflow design file"""
    script = utils.get_script_file()
    run_name = script.name if script.name else "untitled"
    
    if filetype == "configure":
        filepath = os.path.join(current_app.config['SCRIPT_FOLDER'], f"{run_name}_config.csv")
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            cfg, cfg_types = script.config("script")
            writer.writerow(cfg)
            writer.writerow(list(cfg_types.values()))
    elif filetype == "script":
        script.sort_actions()
        json_object = json.dumps(script.as_dict())
        filepath = os.path.join(current_app.config['SCRIPT_FOLDER'], f"{run_name}.json")
        with open(filepath, "w") as outfile:
            outfile.write(json_object)
    elif filetype == "python":
        filepath = os.path.join(current_app.config["SCRIPT_FOLDER"], f"{run_name}.py")
    else:
        return "Unsupported file type", 400
    return send_file(os.path.abspath(filepath), as_attachment=True)


@files.route('/design/upload_history', methods=['POST'])
def upload_history():
    """Upload a workflow history file (.CSV)"""
    if request.method == "POST":
        f = request.files['historyfile']
        if 'historyfile' not in request.files:
            flash('No file part')
        if f.filename.split('.')[-1] == "csv":
            filename = secure_filename(f.filename)
            f.save(os.path.join(current_app.config['DATA_FOLDER'], filename))
            return redirect(url_for("design.experiment_run"))
        else:
            flash("Config file is in csv format")
            return redirect(url_for("design.experiment_run")) 