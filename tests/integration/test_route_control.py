from unittest.mock import patch, Mock

from ivoryos.models import Script
from ivoryos import db

def test_control_panel_redirects_anonymous(client):
    """
    GIVEN an anonymous user
    WHEN the control panel is accessed
    THEN they should be redirected to the login page
    """
    response = client.get('/ivoryos/instruments', follow_redirects=True)
    assert response.status_code == 200
    assert b'Login' in response.data

def test_deck_control_for_auth_user(auth):
    """
    GIVEN an authenticated user
    WHEN the control panel is accessed
    THEN the page should load successfully
    """
    response = auth.get('/ivoryos/instruments/', follow_redirects=True)
    assert response.status_code == 200

def test_new_controller_page(auth):
    """Test new controller page loads"""
    response = auth.get('/ivoryos/instruments/new/', follow_redirects=True)
    assert response.status_code == 200

def test_control_get_json(auth, test_deck):
    """Test that the instruments endpoint returns JSON when Accept header requests it"""
    # Use direct canonical URL and explicit Accept header
    # We need test_deck fixture so it doesn't redirect to /new/
    from ivoryos.runtime.state import global_state
    assert global_state.deck is not None
    
    response = auth.get(
        '/ivoryos/instruments/deck.dummy',
        headers={'Accept': 'application/json'},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b'dummy' in response.data


def test_control_save_order_persists_per_instrument_session(auth):
    response = auth.post(
        '/ivoryos/instruments/deck.dummy/actions/order',
        json={'order': ['float_method', 'int_method']},
    )

    assert response.status_code == 204
    with auth.session_transaction() as session:
        assert session['card_order']['deck.dummy'] == ['float_method', 'int_method']


def test_control_hide_and_show_function_updates_session(auth):
    auth.post(
        '/ivoryos/instruments/deck.dummy/actions/order',
        json={'order': ['float_method', 'int_method']},
    )

    hide_response = auth.patch(
        '/ivoryos/instruments/deck.dummy/actions/int_method',
        json={'hidden': True},
    )

    assert hide_response.status_code == 200
    assert hide_response.get_json()['success'] is True
    with auth.session_transaction() as session:
        assert session['hidden_functions']['deck.dummy'] == ['int_method']
        assert session['card_order']['deck.dummy'] == ['float_method']

    show_response = auth.patch(
        '/ivoryos/instruments/deck.dummy/actions/int_method',
        json={'hidden': False},
    )

    assert show_response.status_code == 200
    with auth.session_transaction() as session:
        assert session['hidden_functions']['deck.dummy'] == []
        assert session['card_order']['deck.dummy'] == ['float_method', 'int_method']
