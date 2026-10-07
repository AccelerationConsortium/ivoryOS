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


def test_run_names_skip_queued_tasks_not_yet_in_the_database(app, init_database, monkeypatch):
    """
    GIVEN one finished run named 'flow' and another task already queued as 'flow_1'
    WHEN a name is picked for the next task
    THEN it skips both, rather than reusing the queued task's name
    """
    from datetime import datetime

    from ivoryos.models import WorkflowRun
    from ivoryos.routes.execute import execute as execute_module

    monkeypatch.setattr(execute_module.runner, "execution_queue", [{"run_name": "flow_1"}])
    monkeypatch.setattr(execute_module.runner, "current_task", None)

    with app.app_context():
        db.session.add(WorkflowRun(name='flow', platform='deck', start_time=datetime.now()))
        db.session.commit()

        assert execute_module._unique_run_name('flow') == 'flow_2'


def test_queued_task_conditions_can_be_read_and_edited(auth, monkeypatch):
    """
    GIVEN a config task waiting in the queue
    WHEN its conditions are read, then edited with a bad and a good value
    THEN the bad edit is refused with a reason and the good one is applied
    """
    from ivoryos.routes.execute import execute as execute_module

    script = Script(author='testuser')
    script.script_dict['script'] = [{
        'id': 1, 'uuid': 1, 'instrument': 'deck.reactor', 'action': 'run',
        'args': {'temperature': '#temperature'}, 'return': '', 'arg_types': {'temperature': 'float'},
    }]
    task = {'uid': 'abc', 'script': script, 'run_name': 'flow', 'repeat_count': None,
            'batch_size': 1, 'compiled': False, 'config': [{'temperature': '25'}]}
    monkeypatch.setattr(execute_module.runner, 'execution_queue', [task])
    monkeypatch.setattr(execute_module.runner, 'socketio', None)
    url = '/ivoryos/executions/queue/task/abc/conditions'

    assert auth.get(url).get_json()['rows'] == [['25']]

    refused = auth.post(url, json={'config': [{'temperature': 'hot'}]})
    assert refused.status_code == 400
    assert 'Entry 1' in refused.get_json()['error']
    assert task['config'] == [{'temperature': '25'}]

    assert auth.post(url, json={'config': [{'temperature': '30'}, {'temperature': '35'}]}).status_code == 200
    assert task['config'] == [{'temperature': '30'}, {'temperature': '35'}]

    assert auth.get('/ivoryos/executions/queue/task/gone/conditions').status_code == 404
    assert auth.post('/ivoryos/executions/queue/task/gone/conditions', json={}).status_code == 404


def test_renaming_a_queued_task_keeps_run_names_unique(auth, monkeypatch):
    """
    GIVEN two queued tasks, 'flow' and 'other'
    WHEN 'other' is renamed to 'flow', and then to 'flow 1', which cleans up to its own name
    THEN it becomes 'flow_1', and stays 'flow_1' rather than clashing with itself
    """
    from ivoryos.routes.execute import execute as execute_module

    first = {'uid': 'a', 'script': Script(author='testuser'), 'run_name': 'flow', 'repeat_count': 2, 'config': None}
    second = {'uid': 'b', 'script': Script(author='testuser'), 'run_name': 'other', 'repeat_count': 2,
              'config': None, 'display_name': 'Other'}
    monkeypatch.setattr(execute_module.runner, 'execution_queue', [first, second])
    monkeypatch.setattr(execute_module.runner, 'current_task', None)
    monkeypatch.setattr(execute_module.runner, 'socketio', None)
    url = '/ivoryos/executions/queue/task/b/conditions'

    assert auth.post(url, json={'name': 'flow'}).status_code == 200
    assert (second['run_name'], second['display_name']) == ('flow_1', None)

    assert auth.post(url, json={'name': 'flow 1'}).status_code == 200
    assert second['run_name'] == 'flow_1'


def test_running_config_table_can_be_read_and_edited(auth, monkeypatch):
    """
    GIVEN a config run in progress, with its first row running
    WHEN its table is read, then edited with a bad and a good value
    THEN the bad edit is refused, the good one applied, and another task's uid is turned away
    """
    from ivoryos.routes.execute import execute as execute_module
    from ivoryos.runtime.live_config import LiveConfig

    url = '/ivoryos/executions/current_task/config'
    monkeypatch.setattr(execute_module.runner, 'live_config', None)
    assert auth.get(url).status_code == 404

    live = LiveConfig([{'temperature': '25'}, {'temperature': '40'}], {'temperature': 'float'})
    live.start_batch(1)
    monkeypatch.setattr(execute_module.runner, 'live_config', live)
    monkeypatch.setattr(execute_module.runner, 'current_task', {'uid': 'abc', 'run_name': 'flow', 'batch_size': 1})

    table = auth.get(url).get_json()
    assert [(row['status'], row['values']) for row in table['rows']] == [('running', ['25']), ('pending', ['40'])]
    rows = [{'id': row['id'], 'values': {'temperature': row['values'][0]}, 'number': n}
            for n, row in enumerate(table['rows'], start=1)]

    rows[1]['values'] = {'temperature': 'warm'}
    refused = auth.post(url, json={'uid': 'abc', 'rows': rows})
    assert refused.status_code == 400 and 'Row 2' in refused.get_json()['error']

    rows[1]['values'] = {'temperature': '45'}
    saved = auth.post(url, json={'uid': 'abc', 'rows': rows + [{'id': None, 'values': {'temperature': '60'}, 'number': 3}]})
    assert saved.get_json() == {'status': 'ok', 'notes': []}
    assert [row['values'] for row in auth.get(url).get_json()['rows']] == [['25'], ['45'], ['60']]

    assert auth.post(url, json={'uid': 'other', 'rows': rows}).status_code == 404
