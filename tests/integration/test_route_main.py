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

def test_the_home_page_says_what_to_do_first(auth, app, monkeypatch):
    monkeypatch.setitem(app.config, "OFF_LINE", False)
    page = auth.get('/ivoryos/').get_data(as_text=True)

    # the steps, in the order a lab goes through them, each a link to where it happens
    steps = ['Try Your Instruments', 'Build a Workflow', 'Run It', 'Review the Results']
    assert [page.index(step) for step in steps] == sorted(page.index(step) for step in steps)
    for url in ('/ivoryos/instruments', '/ivoryos/draft', '/ivoryos/executions', '/ivoryos/executions/records'):
        assert f'href="{url}' in page
    # and the designer's tips, a click away
    assert 'data-bs-target="#tipsModal"' in page and 'id="tipsModal"' in page


def test_offline_there_are_no_instruments_to_try(auth):
    page = auth.get('/ivoryos/').get_data(as_text=True)

    assert 'Try Your Instruments' not in page
    # the steps are numbered from one all the same
    assert '<span class="getting-started-number">1</span>' in page and '>Build a Workflow<' in page
