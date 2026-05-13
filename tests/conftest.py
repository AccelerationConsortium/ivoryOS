from enum import Enum

import bcrypt
import pytest
from ivoryos.config import get_config

from ivoryos import create_app, socketio, db as _db
from ivoryos.models import User
from ivoryos.runtime.state import global_state
from ivoryos.parsers.introspection import generate_interface_schema


@pytest.fixture(scope='session')
def app():
    """Create a new app instance for the test session."""
    _app = create_app(get_config('testing'))
    return _app

@pytest.fixture(scope='function')
def client(app):
    """A fresh Flask test client for every test."""
    return app.test_client()

@pytest.fixture(scope='function')
def init_database(app):
    """Ensure a clean database and seed the default user for each test."""
    with app.app_context():
        _db.drop_all()
        _db.create_all()
        
        # Seed test user
        password = 'password'
        bcrypt_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        user = User(username='testuser', password=bcrypt_password)
        _db.session.add(user)
        _db.session.commit()
        
        yield _db
        
        _db.session.rollback()
        _db.session.remove()
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
    login_response = client.post('/ivoryos/auth/login', data={
        'username': 'testuser',
        'password': 'password'
    }, follow_redirects=True)
    assert login_response.status_code == 200
    # Also check that we are actually logged in (optional but good)
    # assert b'Logout' in login_response.data

    yield client  # this is where the testing happens!

    # Log out the user after the test is done
    client.get('/ivoryos/auth/logout', follow_redirects=True)


@pytest.fixture
def socketio_client(app):
    """A test client for Socket.IO."""
    return socketio.test_client(app)


class MockEnum(Enum):
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

    def enum_method(self, arg: MockEnum = MockEnum.OPTION_A):
        return arg

    def str_method(self) -> dict:
        return {'status': 'OK'}


@pytest.fixture
def test_deck(app):
    """
    A fixture that creates and loads a predictable 'deck' of dummy instruments
    for testing the dynamic control routes.
    """
    dummy_instrument = DummyModule()
    from ivoryos.parsers.introspection import _inspect_class
    snapshot = {"deck.dummy": _inspect_class(dummy_instrument)}

    # Mock the deck as an object with a 'dummy' attribute
    class MockDeck:
        def __init__(self, dummy):
            self.dummy = dummy
    
    global_state._interface_schema = snapshot
    global_state._deck = MockDeck(dummy_instrument)

    yield dummy_instrument

    global_state._interface_schema = {}
    global_state._deck = None