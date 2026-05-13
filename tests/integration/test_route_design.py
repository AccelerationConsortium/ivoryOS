def test_design_page_loads_for_auth_user(auth):
    """
    GIVEN an authenticated user
    WHEN the design page is accessed
    THEN the page should load successfully
    """
    response = auth.get('/ivoryos/draft/instruments', follow_redirects=True)
    assert response.status_code == 200


def test_clear_canvas(auth):
    """
    Tests clearing the design canvas (deleting the current draft).
    """
    response = auth.delete('/ivoryos/draft', follow_redirects=True)
    assert response.status_code == 200


def test_experiment_campaign_page(auth):
    """
    Tests the experiment campaign/run page.
    """
    response = auth.get('/ivoryos/executions/queue', follow_redirects=True)
    assert response.status_code == 200


def test_draft_instruments_list(auth):
    """
    Tests the design instruments list endpoint.
    """
    response = auth.get('/ivoryos/draft/instruments', follow_redirects=True)
    assert response.status_code == 200


def test_code_preview(auth):
    """
    Tests the code preview endpoint.
    """
    response = auth.get('/ivoryos/draft/code_preview', follow_redirects=True)
    assert response.status_code == 200