from unittest.mock import patch

from tests.conftest import TestEnum


def test_int_conversion(auth, test_deck):
    """Tests that a string from a form is converted to an integer."""
    with patch('ivoryos.control.routes.global_config.deck_instance.deck_dummy.int_method') as mock_method:
        auth.post('/ivoryos/control/deck.dummy/call/int_method', data={'arg': '123'})
        # Check that the mock was called with an integer
        mock_method.assert_called_with(arg=123)

def test_float_conversion(auth, test_deck):
    """Tests that a string from a form is converted to a float."""
    with patch('ivoryos.control.routes.global_config.deck_instance.deck_dummy.float_method') as mock_method:
        auth.post('/ivoryos/control/deck.dummy/call/float_method', data={'arg': '123.45'})
        # Check that the mock was called with a float
        mock_method.assert_called_with(arg=123.45)

def test_bool_conversion(auth, test_deck):
    """Tests that a string from a form is converted to a boolean."""
    with patch('ivoryos.control.routes.global_config.deck_instance.deck_dummy.bool_method') as mock_method:
        # Test with 'true'
        auth.post('/ivoryos/control/deck.dummy/call/bool_method', data={'arg': 'true'})
        mock_method.assert_called_with(arg=True)
        # Test with 'false'
        auth.post('/ivoryos/control/deck.dummy/call/bool_method', data={'arg': 'false'})
        mock_method.assert_called_with(arg=False)

def test_list_conversion(auth, test_deck):
    """Tests that a comma-separated string from a form is converted to a list."""
    with patch('ivoryos.control.routes.global_config.deck_instance.deck_dummy.list_method') as mock_method:
        auth.post('/ivoryos/control/deck.dummy/call/list_method', data={'arg': 'a,b,c'})
        # Check that the mock was called with a list of strings
        mock_method.assert_called_with(arg=['a', 'b', 'c'])

def test_enum_conversion(auth, test_deck):
    """Tests that a string from a form is converted to an Enum member."""
    with patch('ivoryos.control.routes.global_config.deck_instance.deck_dummy.enum_method') as mock_method:
        auth.post('/ivoryos/control/deck.dummy/call/enum_method', data={'arg': 'OPTION_B'})
        # Check that the mock was called with the correct Enum member
        mock_method.assert_called_with(arg=TestEnum.OPTION_B)