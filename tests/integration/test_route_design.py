def test_design_page_loads_for_auth_user(auth):
    """
    GIVEN an authenticated user
    WHEN the design page is accessed
    THEN the page should load successfully
    """
    response = auth.get('/ivoryos/design/script/', follow_redirects=True)
    assert response.status_code == 200
    assert b'<title>IvoryOS | Design</title>' in response.data # Assuming this text exists


def test_clear_canvas(auth):
    """
    Tests clearing the design canvas.
    """
    response = auth.get('/ivoryos/design/clear', follow_redirects=True)
    assert response.status_code == 200
    # assert b'Operations' in response.data

# def test_add_action(auth, test_deck):
#     """
#     Tests adding an action to the design canvas.
#     """
#     response = auth.post('/ivoryos/design/script/deck.dummy/', data={
#         'hidden_name': 'int_method',
#         'arg': '10'
#     }, follow_redirects=True)
#     assert response.status_code == 200

def test_experiment_run_page(auth):
    """
    Tests the experiment run page.
    """
    response = auth.get('/ivoryos/design/campaign')
    assert response.status_code == 200
    assert b'Run Panel' in response.data