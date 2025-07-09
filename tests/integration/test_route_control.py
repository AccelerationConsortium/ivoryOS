from unittest.mock import patch, Mock

from ivoryos.utils.db_models import Script
from ivoryos import db

def test_control_panel_redirects_anonymous(client):
    """
    GIVEN an anonymous user
    WHEN the control panel is accessed
    THEN they should be redirected to the login page
    """
    response = client.get('/ivoryos/control/home/deck', follow_redirects=True)
    assert response.status_code == 200
    assert b'Login' in response.data

def test_deck_control_for_auth_user(auth):
    """
    GIVEN an authenticated user
    WHEN the control panel is accessed
    THEN the page should load successfully
    """
    response = auth.get('/ivoryos/control/home/deck', follow_redirects=True)
    assert response.status_code == 200
    assert b'<title>IvoryOS | Devices</title>' in response.data # Assuming this text exists on the page

def test_temp_control_for_auth_user(auth):
    """
    GIVEN an authenticated user
    WHEN the control panel is accessed
    THEN the page should load successfully
    """
    response = auth.get('/ivoryos/control/home/temp', follow_redirects=True)
    assert response.status_code == 200
    # assert b'<title>IvoryOS | Devices</title>' in response.data # Assuming this text exists on the page

def test_new_controller_page(auth):
    """Test new controller page loads"""
    response = auth.get('/ivoryos/control/new/')
    assert response.status_code == 200

def test_download_proxy(self, auth_headers):
    """Test proxy download functionality"""
    with patch('ivoryos.routes.control.control.global_config') as mock_config:
        mock_config.deck_snapshot = {'test_instrument': {'test_method': {'signature': 'test()'}}}
        response = auth_headers.get('/ivoryos/control/download')
        assert response.status_code == 200
        assert response.headers['Content-Disposition'].startswith('attachment')

def test_backend_control_get(self, auth_headers):
    """Test backend control GET endpoint"""
    with patch('ivoryos.routes.control.control.global_config') as mock_config:
        mock_config.deck_snapshot = {'test_instrument': {'test_method': {'signature': 'test()'}}}
        response = auth_headers.get('/ivoryos/api/control/')
        assert response.status_code == 200
        assert response.is_json

@patch('ivoryos.routes.control.control.runner')
@patch('ivoryos.routes.control.control.find_instrument_by_name')
@patch('ivoryos.routes.control.control.create_form_from_module')
def test_backend_control_post(self, mock_form, mock_find, mock_runner, auth_headers):
    """Test backend control POST endpoint"""
    # Setup mocks
    mock_instrument = Mock()
    mock_find.return_value = mock_instrument
    mock_field = Mock()
    mock_field.name = 'test_param'
    mock_field.data = 'test_value'
    mock_form_instance = Mock()
    mock_form_instance.__iter__ = Mock(return_value=iter([mock_field]))
    mock_form.return_value = {'test_method': mock_form_instance}
    mock_runner.run_single_step.return_value = 'success'
    response = auth_headers.post('/ivoryos/api/control/test_instrument', data={
        'hidden_name': 'test_method',
        'hidden_wait': 'true'
    })
    assert response.status_code == 200

# def test_control(auth, app):
#     """
#     GIVEN an authenticated user and an existing script
#     WHEN a POST request is made to run the script
#     THEN the user should be redirected and a success message shown
#     """
#     # We need to create a script in the database first
#     with app.app_context():
#         script = Script(name='My Test Script', author='testuser', content='print("hello")')
#         db.session.add(script)
#         db.session.commit()
#         script_id = script.id
#
#     # Simulate running the script
#     response = auth.post(f'/ivoryos/control/run/{script_id}', follow_redirects=True)
#     assert response.status_code == 200
#     assert b'has been initiated' in response.data # Check for a flash message