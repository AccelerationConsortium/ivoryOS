from enum import Enum

import bcrypt
import pytest
from ivoryos.config import get_config

from ivoryos import create_app, socketio, db as _db, utils, global_config
from ivoryos.utils.db_models import User


@pytest.fixture(scope='session')
def app():
    """Create a new app instance for the test session."""
    _app = create_app(get_config('testing'))
    return _app

@pytest.fixture
def client(app):
    """A test client for the app."""
    with app.test_client() as client:
        with app.app_context():
            _db.create_all()
        yield client
        with app.app_context():
            _db.drop_all()

# @pytest.fixture(scope='session')
# def db(app):
#     """Session-wide test database."""
#     with app.app_context():
#         _db.create_all()
#         yield _db
#         _db.drop_all()

@pytest.fixture(scope='module')
def init_database(app):
    """
    Creates the database tables and seeds it with a default test user.
    This runs once per test module.
    """
    with app.app_context():
        # Drop everything first to ensure a clean slate
        _db.drop_all()
        # Create the database tables
        _db.create_all()

        # Insert a default user for authentication tests
        # Note: In a real app with password hashing, you'd call a hash function here.
        password = 'password'
        bcrypt_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        default_user = User(username='testuser', password=bcrypt_password)
        _db.session.add(default_user)
        _db.session.commit()

        yield _db  # this is where the testing happens!

        # Teardown: drop all tables after the tests in the module are done
        _db.drop_all()


# ---------------------
# Authentication Fixture
# ---------------------

@pytest.fixture(scope='function')
def auth(client, init_database):
    """
    Logs in the default user for a single test function.
    Depends on `init_database` to ensure the user exists.
    Handles logout as part of teardown.
    """
    # Log in the default user
    client.post('/ivoryos/auth/login', data={
        'username': 'testuser',
        'password': 'password'
    }, follow_redirects=True)

    yield client  # this is where the testing happens!

    # Log out the user after the test is done
    client.get('/ivoryos/auth/logout', follow_redirects=True)


@pytest.fixture
def socketio_client(app):
    """A test client for Socket.IO."""
    return socketio.test_client(app)


class TestEnum(Enum):
    """An example Enum for testing type conversion."""
    OPTION_A = 'A'
    OPTION_B = 'B'

class DummyModule:
    """A more comprehensive dummy instrument for testing."""
    def int_method(self, arg: int = 1):
        return arg

    def float_method(self, arg: float = 1.0):
        return arg

    def bool_method(self, arg: bool = False):
        return arg

    def list_method(self, arg: list = None):
        return arg or []

    def enum_method(self, arg: TestEnum = TestEnum.OPTION_A):
        return arg

    def str_method(self) -> dict:
        return {'status': 'OK'}


@pytest.fixture
def test_deck(app):
    """
    A fixture that creates and loads a predictable 'deck' of dummy instruments
    for testing the dynamic control routes.
    """
    dummy_module = DummyModule()
    snapshot = utils.create_deck_snapshot(dummy_module)

    with app.app_context():
        global_config.deck_snapshot = snapshot
        global_config.deck = dummy_module # instantiate the class

    yield DummyModule

    with app.app_context():
        global_config.deck_snapshot = {}
        global_config.deck = {}