from flask_login import UserMixin
from sqlalchemy_utils import JSONType

from ivoryos.models.base import db


class User(db.Model, UserMixin):
    __tablename__ = 'user'
    # id = db.Column(db.Integer)
    username = db.Column(db.String(50), primary_key=True, unique=True, nullable=False)
    # email = db.Column(db.String)
    hashPassword = db.Column(db.String(255))

    # New columns for logo customization
    settings = db.Column(JSONType, nullable=True)

    # password = db.Column()
    def __init__(self, username, password):
        # self.id = id
        self.username = username
        # self.email = email
        self.hashPassword = password

    def get_id(self):
        return self.username
