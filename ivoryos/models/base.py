import json

import sqlalchemy as sa
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON as PostgresJSON


db = SQLAlchemy()


class JSONType(sa.types.TypeDecorator):
    """JSON column: native ``json`` on PostgreSQL, JSON-encoded text elsewhere.

    Drop-in replacement for ``sqlalchemy_utils.JSONType`` (same storage format),
    which is incompatible with SQLAlchemy 2.1.
    """

    impl = sa.UnicodeText
    hashable = False
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresJSON())
        return dialect.type_descriptor(self.impl)

    def process_bind_param(self, value, dialect):
        if dialect.name == 'postgresql' or value is None:
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if dialect.name == 'postgresql' or value is None:
            return value
        return json.loads(value)
