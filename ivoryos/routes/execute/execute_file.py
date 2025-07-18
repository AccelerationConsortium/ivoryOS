import csv
import json
import os
from flask import Blueprint, send_file, request, flash, redirect, url_for, session, current_app
from werkzeug.utils import secure_filename
from ivoryos.utils import utils

files = Blueprint('execute_files', __name__)



@files.route('/upload/config', methods=['POST'])
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
            return redirect(url_for("execute.experiment_run"))
        else:
            flash("Config file is in csv format")
            return redirect(url_for("execute.experiment_run"))


@files.route('/upload/history', methods=['POST'])
def upload_history():
    """Upload a workflow history file (.CSV)"""
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


