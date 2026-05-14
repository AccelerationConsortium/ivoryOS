import json
from datetime import datetime

from sqlalchemy_utils import JSONType

from ivoryos.models.base import db


class Script(db.Model):
    __tablename__ = 'script'
    # id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), primary_key=True, unique=True)
    deck = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    script_dict = db.Column(JSONType, nullable=True)
    time_created = db.Column(db.String(50), nullable=True)
    last_modified = db.Column(db.String(50), nullable=True)
    id_order = db.Column(JSONType, nullable=True)
    editing_type = db.Column(db.String(50), nullable=True)
    author = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    registered = db.Column(db.Boolean, nullable=True, default=False)
    return_values = db.Column(JSONType, default=[])
    uuid = db.Column(db.String(36), unique=True, nullable=True)
    

    def __init__(self, name=None, deck=None, status=None, script_dict: dict = None, id_order: dict = None,
                 time_created=None, last_modified=None, editing_type=None, author: str = None,
                 registered:bool=False, return_values: list = None,
                 description: str = None,
                 python_script: str = None,
                 uuid: str = None,
                 ):
        if script_dict is None:
            script_dict = {"prep": [], "script": [], "cleanup": []}
        elif type(script_dict) is not dict:
            script_dict = json.loads(script_dict)
        if id_order is None:
            id_order = {"prep": [], "script": [], "cleanup": []}
        elif type(id_order) is not dict:
            id_order = json.loads(id_order)
        if status is None:
            status = 'editing'
        if time_created is None:
            time_created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if last_modified is None:
            last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if editing_type is None:
            editing_type = "script"
        if description is None:
            description = ""
        self.name = name
        self.deck = deck
        self.status = status
        self.script_dict = script_dict
        self.time_created = time_created
        self.last_modified = last_modified
        self.id_order = id_order
        self.editing_type = editing_type
        self.author = author
        self.python_script = python_script
        self.description = description
        self.registered = registered
        self.return_values = return_values
        self.uuid = uuid

    def as_dict(self):
        data = dict(self.__dict__)  # shallow copy
        data.pop('_sa_instance_state', None)
        return data

    @classmethod
    def from_dict(cls, data):
        """Build a Script from serialized draft or database data."""
        data = dict(data or {})
        data.pop('_sa_instance_state', None)
        init_fields = {
            "name",
            "deck",
            "status",
            "script_dict",
            "id_order",
            "time_created",
            "last_modified",
            "editing_type",
            "author",
            "registered",
            "return_values",
            "description",
            "python_script",
            "uuid",
        }
        kwargs = {key: value for key, value in data.items() if key in init_fields}
        return cls(**kwargs)

    def get(self):
        workflows = db.session.query(Script).all()
        return workflows

    def __getattr__(self, name):
        """Delegate missing attributes/methods to ScriptEditor."""
        # Avoid recursion for standard attributes
        if name in ("script_dict", "id_order", "editing_type"):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
            
        try:
            from ivoryos.script.editor import ScriptEditor
            editor = ScriptEditor(self)
            if hasattr(editor, name):
                return getattr(editor, name)
        except (ImportError, AttributeError):
            pass
            
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    @property
    def stypes(self):
        return list(self.script_dict.keys())

    def update_time_stamp(self):
        self.last_modified = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_script(self, stype: str):
        return self.script_dict[stype]

    def isEmpty(self) -> bool:
        if not (self.script_dict['script'] or self.script_dict['prep'] or self.script_dict['cleanup']):
            return True
        return False

    def finalize(self):
        """finalize script, disable editing"""
        self.status = "finalized"
        self.update_time_stamp()

    def save_as(self, name):
        """resave script, enable editing"""
        self.name = name
        self.status = "editing"
        self.update_time_stamp()
