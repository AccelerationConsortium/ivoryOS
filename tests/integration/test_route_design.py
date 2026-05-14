import io

from ivoryos.models import Script, db
from ivoryos.script import ScriptEditor
from ivoryos.services.draft_service import get_script_for_user, post_script_for_user


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
    assert "code" in response.get_json()


def test_update_ui_state_show_code_and_invalid_request(auth):
    response = auth.patch('/ivoryos/draft/ui-state', json={'show_code': True})

    assert response.status_code == 200
    assert response.get_json() == {'success': True}
    with auth.session_transaction() as session:
        assert session['show_code'] is True

    invalid = auth.patch('/ivoryos/draft/ui-state', json={'unknown': True})
    assert invalid.status_code == 400
    assert invalid.get_json() == {'error': 'Invalid request'}


def test_get_available_variables_reads_current_user_draft(auth):
    script = Script(author='testuser')
    ScriptEditor(script).add_variable('5', 'sample_count', 'int')
    ScriptEditor(script).add_action({
        'instrument': 'deck.sensor',
        'action': 'read',
        'args': {},
        'return': 'measurement',
        'arg_types': {},
    })

    with auth.application.app_context():
        post_script_for_user('testuser', script)

    response = auth.get('/ivoryos/draft/variables')

    assert response.status_code == 200
    assert set(response.get_json()['variables']) >= {'sample_count', 'measurement'}


def test_reorder_steps_updates_current_draft_order(auth):
    script = Script(author='testuser')
    ScriptEditor(script).add_action({
        'instrument': 'comment',
        'action': 'comment',
        'args': {'statement': 'first'},
        'return': '',
        'arg_types': {'statement': 'str'},
    })
    ScriptEditor(script).add_action({
        'instrument': 'comment',
        'action': 'comment',
        'args': {'statement': 'second'},
        'return': '',
        'arg_types': {'statement': 'str'},
    })
    ScriptEditor(script).add_action({
        'instrument': 'comment',
        'action': 'comment',
        'args': {'statement': 'third'},
        'return': '',
        'arg_types': {'statement': 'str'},
    })

    with auth.application.app_context():
        post_script_for_user('testuser', script)

    response = auth.post('/ivoryos/draft/steps/order', data={'order': '3,1,2'})

    assert response.status_code == 200
    with auth.application.app_context():
        draft = get_script_for_user('testuser')
    assert [action['args']['statement'] for action in draft.script_dict['script']] == ['third', 'first', 'second']
    assert [action['id'] for action in draft.script_dict['script']] == [1, 2, 3]


def test_import_python_file_reports_missing_or_empty_upload(auth):
    no_file = auth.post('/ivoryos/draft/import_python_file', data={})
    assert no_file.status_code == 200
    assert no_file.get_json() == {'success': False, 'error': 'No file part'}

    no_functions = auth.post(
        '/ivoryos/draft/import_python_file',
        data={'file': (io.BytesIO(b'x = 1\n'), 'workflow.py')},
        content_type='multipart/form-data',
    )
    assert no_functions.status_code == 200
    assert no_functions.get_json() == {'success': False, 'error': 'No functions found in file'}


def test_confirm_import_python_creates_workflow_script(auth):
    payload = {
        'workflows': {
            'imported_workflow': {
                'cards': [{
                    'id': 1,
                    'uuid': 1,
                    'instrument': 'comment',
                    'action': 'comment',
                    'args': {'statement': 'hello'},
                    'return': '',
                    'arg_types': {'statement': 'str'},
                }],
                'source': 'def imported_workflow():\n    pass\n',
            }
        },
        'overwrite': [],
    }

    response = auth.post('/ivoryos/draft/confirm_import_python', json=payload)

    assert response.status_code == 200
    assert response.get_json() == {
        'success': True,
        'results': {'imported_workflow': 'created'},
    }
    with auth.application.app_context():
        saved = db.session.get(Script, 'imported_workflow')
        assert saved is not None
        assert saved.author == 'testuser'
        assert saved.script_dict['script'][0]['action'] == 'comment'
