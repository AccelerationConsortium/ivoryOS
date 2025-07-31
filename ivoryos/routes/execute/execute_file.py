import csv
import json
import os
from flask import Blueprint, send_file, request, flash, redirect, url_for, session, current_app
from werkzeug.utils import secure_filename
from ivoryos.utils import utils

files = Blueprint('execute_files', __name__)


@files.route('/files/execution-configs')
def download_empty_config():
    """
    .. :quickref: Workflow Files; download an empty workflow config file (.CSV)

    .. http:get:: /files/execution-configs

    :form file: workflow design CSV file
    :status 302: load pseudo deck and then redirects to :http:get:`/ivoryos/executions/config`
    """
    script = utils.get_script_file()
    run_name = script.name if script.name else "untitled"

    filepath = os.path.join(current_app.config['SCRIPT_FOLDER'], f"{run_name}_config.csv")
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        cfg, cfg_types = script.config("script")
        writer.writerow(cfg)
        writer.writerow(list(cfg_types.values()))
    return send_file(os.path.abspath(filepath), as_attachment=True)

@files.route('/files/batch-configs', methods=['POST'])
def upload():
    """
    .. :quickref: Workflow Files; upload a workflow config file (.CSV)

    .. http:post:: /files/execution-configs

    :form file: workflow CSV config file
    :status 302: save csv file and then redirects to :http:get:`/ivoryos/executions/config`
    """
    if request.method == "POST":
        f = request.files['file']
        if 'file' not in request.files:
            flash('No file part')
        if f.filename.split('.')[-1] == "csv":
            filename = secure_filename(f.filename)
            f.save(os.path.join(current_app.config['CSV_FOLDER'], filename))
            session['config_file'] = filename
            return redirect(url_for("execute.experiment_run"))
        else:
            flash("Config file is in csv format")
            return redirect(url_for("execute.experiment_run"))


@files.route('/files/execution-data', methods=['POST'])
def upload_history():
    """
    .. :quickref: Workflow Files; upload a workflow history file (.CSV)

    .. http:post:: /files/execution-data

    :form file: workflow history CSV file
    :status 302: save csv file and then redirects to :http:get:`/ivoryos/executions/config`
    """
    if request.method == "POST":
        f = request.files['historyfile']
        if 'historyfile' not in request.files:
            flash('No file part')
        if f.filename.split('.')[-1] == "csv":
            filename = secure_filename(f.filename)
            f.save(os.path.join(current_app.config['DATA_FOLDER'], filename))
            return redirect(url_for("execute.experiment_run"))
        else:
            flash("Config file is in csv format")
            return redirect(url_for("execute.experiment_run"))


