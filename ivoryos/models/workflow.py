from datetime import datetime

from sqlalchemy_utils import JSONType

from ivoryos.models.base import db


class WorkflowRun(db.Model):
    """Represents the entire experiment"""
    __tablename__ = 'workflow_runs'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    platform = db.Column(db.String(128), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.now())
    end_time = db.Column(db.DateTime)
    data_path = db.Column(db.String(256))
    repeat_mode = db.Column(db.String(64), default="none")  # static_repeat, sweep, optimizer

    # A run contains multiple iterations
    phases = db.relationship(
        'WorkflowPhase',
        backref='workflow_runs', # Clearer back-reference name
        cascade='all, delete-orphan',
        lazy='dynamic' # Good for handling many iterations
    )
    def as_dict(self):
        dict = self.__dict__
        dict.pop('_sa_instance_state', None)
        return dict

class WorkflowPhase(db.Model):
    """Represents a single function call within a WorkflowRun."""
    __tablename__ = 'workflow_phases'

    id = db.Column(db.Integer, primary_key=True)
    # Foreign key to link this iteration to its parent run
    run_id = db.Column(db.Integer, db.ForeignKey('workflow_runs.id', ondelete='CASCADE'), nullable=False)

    # NEW: Store iteration-specific parameters here
    name = db.Column(db.String(64), nullable=False)  # 'prep', 'main', 'cleanup'
    repeat_index = db.Column(db.Integer, default=0)

    parameters = db.Column(JSONType)  # Use db.JSON for general support
    outputs = db.Column(JSONType)
    start_time = db.Column(db.DateTime, default=datetime.now)
    end_time = db.Column(db.DateTime)

    # An iteration contains multiple steps
    steps = db.relationship(
        'WorkflowStep',
        backref='workflow_phases',  # Clearer back-reference name
        cascade='all, delete-orphan'
    )

    def as_dict(self):
        dict = self.__dict__.copy()
        dict.pop('_sa_instance_state', None)
        return dict

class WorkflowStep(db.Model):
    __tablename__ = 'workflow_steps'

    id = db.Column(db.Integer, primary_key=True)
    # workflow_id = db.Column(db.Integer, db.ForeignKey('workflow_runs.id', ondelete='CASCADE'), nullable=True)
    phase_id = db.Column(db.Integer, db.ForeignKey('workflow_phases.id', ondelete='CASCADE'), nullable=True)

    # phase = db.Column(db.String(64), nullable=False)  # 'prep', 'main', 'cleanup'
    # repeat_index = db.Column(db.Integer, default=0)   # Only applies to 'main' phase
    step_index = db.Column(db.Integer, default=0)
    method_name = db.Column(db.String(128), nullable=False)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    run_error = db.Column(db.Boolean, default=False)
    output = db.Column(JSONType, default={})
    # Using as_dict method from ModelBase

    def as_dict(self):
        dict = self.__dict__.copy()
        dict.pop('_sa_instance_state', None)
        return dict
