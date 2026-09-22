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


def test_canvas_flags_a_step_the_deck_no_longer_offers(auth, test_deck):
    """
    GIVEN a draft built against a deck method that has since disappeared
    WHEN the design canvas is rendered
    THEN the step carries a warning and the canvas says how many steps are affected
    """
    script = Script(author='testuser')
    ScriptEditor(script).add_action({
        'instrument': 'deck.dummy',
        'action': 'int_method',
        'args': {'arg': 1},
        'return': '',
        'arg_types': {'arg': 'int'},
    })
    ScriptEditor(script).add_action({
        'instrument': 'deck.dummy',
        'action': 'method_that_was_deleted',
        'args': {},
        'return': '',
        'arg_types': {},
    })

    with auth.application.app_context():
        post_script_for_user('testuser', script)

    response = auth.post('/ivoryos/draft/steps/order', data={'order': '1,2'})
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '1 step' in body and 'no longer match' in body
    # one marker slot per step, but only the stale one carries a reason
    assert body.count('step-issue-marker') == 2
    assert body.count('data-bs-toggle="tooltip"') == 1
    assert "Method &#39;method_that_was_deleted&#39; no longer exists" in body


def test_clean_steps_keep_an_invisible_marker_slot_so_labels_stay_aligned(auth, test_deck):
    script = Script(author='testuser')
    ScriptEditor(script).add_action({
        'instrument': 'deck.dummy',
        'action': 'int_method',
        'args': {'arg': 1},
        'return': '',
        'arg_types': {'arg': 'int'},
    })

    with auth.application.app_context():
        post_script_for_user('testuser', script)

    body = auth.post('/ivoryos/draft/steps/order', data={'order': '1'}).get_data(as_text=True)

    assert 'step-issue-marker me-1 invisible' in body


def test_canvas_has_no_warnings_when_every_step_matches_the_deck(auth, test_deck):
    script = Script(author='testuser')
    ScriptEditor(script).add_action({
        'instrument': 'deck.dummy',
        'action': 'int_method',
        'args': {'arg': 1},
        'return': '',
        'arg_types': {'arg': 'int'},
    })

    with auth.application.app_context():
        post_script_for_user('testuser', script)

    response = auth.post('/ivoryos/draft/steps/order', data={'order': '1'})
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'deck-compatibility-banner' not in body
    assert 'data-bs-toggle="tooltip"' not in body


def test_step_edit_form_explains_why_the_step_no_longer_matches(auth, test_deck):
    script = Script(author='testuser')
    ScriptEditor(script).add_action({
        'instrument': 'deck.dummy',
        'action': 'int_method',
        'args': {'arg': 1, 'dropped_arg': 2},
        'return': '',
        'arg_types': {'arg': 'int', 'dropped_arg': 'int'},
    })

    with auth.application.app_context():
        post_script_for_user('testuser', script)
        uuid = get_script_for_user('testuser').script_dict['script'][0]['uuid']

    response = auth.get(f'/ivoryos/draft/steps/{uuid}')
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Step will fail' in body
    assert 'no longer takes &#39;dropped_arg&#39;' in body


def test_canvas_says_when_the_workflow_belongs_to_another_deck(auth, test_deck):
    from ivoryos.runtime.state import global_state

    # the fixture's stand-in deck carries no module name of its own
    global_state._deck.__name__ = 'current_deck'
    try:
        script = Script(author='testuser', deck='deck_it_was_designed_for')
        ScriptEditor(script).add_action({
            'instrument': 'deck.dummy',
            'action': 'int_method',
            'args': {'arg': 1},
            'return': '',
            'arg_types': {'arg': 'int'},
        })

        with auth.application.app_context():
            post_script_for_user('testuser', script)

        response = auth.post('/ivoryos/draft/steps/order', data={'order': '1'})
        body = response.get_data(as_text=True)
    finally:
        del global_state._deck.__name__

    assert response.status_code == 200
    assert 'deck_it_was_designed_for' in body
    assert 'current_deck' in body


def test_execution_config_page_renders(auth, test_deck):
    """
    GIVEN a draft built against the loaded deck
    WHEN the execution config page is requested
    THEN it renders (it no longer receives the long-unused design_buttons context)
    """
    script = Script(author='testuser')
    ScriptEditor(script).add_action({
        'instrument': 'deck.dummy',
        'action': 'int_method',
        'args': {'arg': 1},
        'return': '',
        'arg_types': {'arg': 'int'},
    })

    with auth.application.app_context():
        post_script_for_user('testuser', script)

    response = auth.get('/ivoryos/executions/config', follow_redirects=True)

    assert response.status_code == 200
    assert 'design_buttons' not in response.get_data(as_text=True)


def test_execution_page_warns_about_steps_that_will_fail(auth, test_deck):
    """
    GIVEN a draft with a step whose deck method is gone, and one that is disabled
    WHEN the execution config page is opened
    THEN it names the failing step and ignores the disabled one, which never runs
    """
    script = Script(author='testuser')
    ScriptEditor(script).add_action({
        'instrument': 'deck.dummy', 'action': 'method_that_was_deleted',
        'args': {}, 'return': '', 'arg_types': {},
    })
    ScriptEditor(script).add_action({
        'instrument': 'deck.dummy', 'action': 'also_deleted',
        'args': {}, 'return': '', 'arg_types': {}, 'disabled': True,
    })

    with auth.application.app_context():
        post_script_for_user('testuser', script)

    body = auth.get('/ivoryos/executions/config', follow_redirects=True).get_data(as_text=True)

    assert 'run-compatibility-warning' in body
    assert '1 step will fail against the current deck' in body
    # the warning lists steps as <code>module.method</code>; the disabled one is
    # absent from that list, though it still shows in the compiled code preview
    assert '<code>dummy.method_that_was_deleted</code>' in body
    assert '<code>dummy.also_deleted</code>' not in body
    # the list is one compact line per step; the full sentence is the hover title
    assert 'missing method method_that_was_deleted' in body
    assert 'Fix these in the workflow designer' not in body


def test_execution_page_is_quiet_when_the_workflow_matches_the_deck(auth, test_deck):
    script = Script(author='testuser')
    ScriptEditor(script).add_action({
        'instrument': 'deck.dummy', 'action': 'int_method',
        'args': {'arg': 1}, 'return': '', 'arg_types': {'arg': 'int'},
    })

    with auth.application.app_context():
        post_script_for_user('testuser', script)

    body = auth.get('/ivoryos/executions/config', follow_redirects=True).get_data(as_text=True)

    assert 'run-compatibility-warning' not in body
