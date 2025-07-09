from flask_login import current_user


def test_home_page_authenticated(auth, app):
    """
    GIVEN an authenticated user (using the 'auth' fixture)
    WHEN the home page is accessed
    THEN check that they see the main application page
    """
    with auth.application.test_request_context('/ivoryos/'):
        # Manually trigger the before_request functions that Flask-Login uses
        app.preprocess_request()

        # Assert that the `current_user` proxy is now populated and authenticated
        assert current_user.is_authenticated
        assert current_user.username == 'testuser'

def test_help_page(client):
    """
    GIVEN an unauthenticated user
    WHEN they access the help page
    THEN check that the page loads successfully and contains documentation content
    """
    response = client.get('/ivoryos/help')
    assert response.status_code == 200
    assert b'Documentations' in response.data

def test_prefix_redirect(auth):
    """
    GIVEN an authenticated user (using the 'auth' fixture)
    WHEN the home page is accessed without prefix
    THEN check that they see the main application page
    """
    response = auth.get('/', follow_redirects=True)
    assert response.status_code == 200