from sqlalchemy_utils import JSONType

from ivoryos.models.base import db


class SingleStep(db.Model):
    __tablename__ = 'single_steps'

    id = db.Column(db.Integer, primary_key=True)
    method_name = db.Column(db.String(128), nullable=False)
    kwargs = db.Column(JSONType, nullable=False)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    run_error = db.Column(db.String(128))
    output = db.Column(JSONType, nullable=True)

    def as_dict(self):
        dict = self.__dict__.copy()
        dict.pop('_sa_instance_state', None)
        return dict
