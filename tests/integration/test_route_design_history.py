import io
import json
import re

from ivoryos.models import Script, db
from ivoryos.runtime.state import global_state
from ivoryos.services.draft_service import get_script_for_user, post_script_for_user
from tests.conftest import session_draft_id


def _start_draft(client, *actions, **fields):
    """A draft the session already had, which the history does not reach back past."""
    script = Script(author='testuser', deck='test_deck', **fields)
    script.script_dict['script'] = [
        {"id": i, "uuid": 500 + i, "instrument": "deck.dummy", "action": action, "args": {}, "return": ""}
        for i, action in enumerate(actions, start=1)]
    with client.application.app_context():
        post_script_for_user('testuser', script, draft_id=session_draft_id(client), record=False)


def _actions(client):
    with client.application.app_context():
        script = get_script_for_user('testuser', session_draft_id(client))
    return [step['action'] for step in script.script_dict['script']]


def _add_int_method(client, value='5'):
    response = client.post('/ivoryos/draft/instruments/deck.dummy',
                           data={'hidden_name': 'int_method', 'arg': value})
    assert response.get_json()['success'], response.get_json()


def test_adding_a_step_can_be_undone_and_redone(auth, test_deck):
    _start_draft(auth)
    _add_int_method(auth)
    assert _actions(auth) == ['int_method']

    history = auth.get('/ivoryos/draft/history').get_json()
    assert history['undo_label'] == 'Add dummy.int_method'
    assert [entry['label'] for entry in history['entries']] == ['Start', 'Add dummy.int_method']

    undone = auth.post('/ivoryos/draft/history/undo').get_json()
    assert undone['success'] and undone['message'] == 'Undid Add dummy.int_method'
    assert _actions(auth) == []
    # the canvas comes back as it is now, saying redo is possible
    assert 'int_method' not in undone['html'].split('id="draft-history-state"')[0]
    assert 'data-can-redo="true"' in undone['html']

    redone = auth.post('/ivoryos/draft/history/redo').get_json()
    assert redone['success'] and redone['message'] == 'Redid Add dummy.int_method'
    assert _actions(auth) == ['int_method']


def test_there_is_nothing_to_undo_before_the_first_change(auth, test_deck):
    _start_draft(auth)

    response = auth.post('/ivoryos/draft/history/undo').get_json()

    assert response == {'success': False, 'message': 'Nothing to undo',
                        'history': response['history']}
    assert response['history']['can_undo'] is False


def test_deleting_and_editing_steps_can_be_undone(auth, test_deck):
    _start_draft(auth, 'int_method', 'float_method')

    auth.delete('/ivoryos/draft/steps/2')
    assert _actions(auth) == ['int_method']
    auth.post('/ivoryos/draft/steps/501/toggle_comment')

    assert auth.post('/ivoryos/draft/history/undo').get_json()['message'] == 'Undid Disable dummy.int_method'
    assert auth.post('/ivoryos/draft/history/undo').get_json()['message'] == 'Undid Delete dummy.float_method'
    assert _actions(auth) == ['int_method', 'float_method']


def test_a_copy_is_named_a_duplicate_and_a_second_add_is_not(auth, test_deck):
    _start_draft(auth)
    _add_int_method(auth)
    _add_int_method(auth)
    assert auth.get('/ivoryos/draft/history').get_json()['undo_label'] == 'Add dummy.int_method'

    auth.post('/ivoryos/draft/steps/1/duplicate')

    assert auth.get('/ivoryos/draft/history').get_json()['undo_label'] == 'Duplicate dummy.int_method'
    assert _actions(auth) == ['int_method'] * 3


def test_a_new_workflow_starts_its_own_history(auth, test_deck, monkeypatch):
    # clearing names the new draft after the deck's module
    monkeypatch.setattr(global_state._deck, '__name__', 'test_deck', raising=False)
    _start_draft(auth)
    _add_int_method(auth)

    auth.delete('/ivoryos/draft')

    history = auth.get('/ivoryos/draft/history').get_json()
    assert [entry['label'] for entry in history['entries']] == ['New workflow']
    assert auth.post('/ivoryos/draft/history/undo').get_json()['success'] is False
    assert _actions(auth) == []


def test_undo_never_goes_back_past_opening_a_workflow(auth, test_deck):
    """The history belongs to one workflow: opening another from the library starts a new one."""
    _start_draft(auth, name='unsaved_work')
    _add_int_method(auth)
    with auth.application.app_context():
        db.session.add(Script(name='library_flow', deck='test_deck', author='testuser'))
        db.session.commit()

    auth.get('/ivoryos/library/library_flow', headers={'Accept': 'application/json'})
    history = auth.get('/ivoryos/draft/history').get_json()
    assert [entry['label'] for entry in history['entries']] == ['Open “library_flow”']
    assert history['can_undo'] is False

    # changes to the opened workflow undo back to it as it was opened, and no further
    _add_int_method(auth)
    auth.post('/ivoryos/draft/history/undo')
    assert auth.post('/ivoryos/draft/history/undo').get_json()['message'] == 'Nothing to undo'
    with auth.application.app_context():
        script = get_script_for_user('testuser', session_draft_id(auth))
    assert script.name == 'library_flow' and _actions(auth) == []


def test_importing_a_workflow_starts_its_own_history(auth, test_deck):
    _start_draft(auth)
    _add_int_method(auth)
    imported = Script(name='from_file', deck='test_deck', author='testuser').as_dict()

    auth.post('/ivoryos/files/script-json', data={'file': (io.BytesIO(json.dumps(imported).encode()), 'flow.json')},
              content_type='multipart/form-data')

    history = auth.get('/ivoryos/draft/history').get_json()
    assert [entry['label'] for entry in history['entries']] == ['Import “from_file”']
    assert history['can_undo'] is False


def test_going_back_to_a_point_in_the_history(auth, test_deck):
    _start_draft(auth)
    _add_int_method(auth, '1')
    _add_int_method(auth, '2')

    response = auth.post('/ivoryos/draft/history/0').get_json()
    assert response['message'] == 'Undid 2 changes'
    assert _actions(auth) == []

    response = auth.post('/ivoryos/draft/history/2').get_json()
    assert response['message'] == 'Redid 2 changes'
    assert _actions(auth) == ['int_method', 'int_method']


def test_an_undo_shows_the_tab_it_changes(auth, test_deck):
    _start_draft(auth)
    auth.patch('/ivoryos/draft/ui-state', json={'editing_type': 'prep'})
    _add_int_method(auth)
    auth.patch('/ivoryos/draft/ui-state', json={'editing_type': 'script'})
    # switching tabs is not a change to undo
    assert auth.get('/ivoryos/draft/history').get_json()['undo_label'] == 'Add dummy.int_method (Prep)'

    auth.post('/ivoryos/draft/history/undo')

    with auth.application.app_context():
        script = get_script_for_user('testuser', session_draft_id(auth))
    assert script.editing_type == 'prep' and script.script_dict['prep'] == []


def test_each_session_has_its_own_history(app, auth, test_deck):
    _start_draft(auth)
    _add_int_method(auth)

    python_client = app.test_client()
    python_client.post('/ivoryos/auth/login', data={'username': 'testuser', 'password': 'password'})

    assert python_client.post('/ivoryos/draft/history/undo').get_json()['success'] is False
    assert _actions(auth) == ['int_method']


def test_the_designer_has_undo_redo_and_history_controls(auth, test_deck):
    _start_draft(auth)
    page = auth.get('/ivoryos/draft').get_data(as_text=True)

    assert 'id="draftUndoButton"' in page and 'id="draftRedoButton"' in page
    assert 'id="draftHistoryButton"' in page and 'id="draftHistoryMenu"' in page
    assert 'js/draft_history.js' in page
    # nothing to undo yet, and the page says so before any script runs
    assert re.search(r'onclick="undoDraft\(\)"\s+aria-label="Undo" title="Undo" disabled', page)
    assert 'data-can-undo="false"' in page
    # opening the designer fills in the deck, which is not a change to undo
    assert auth.get('/ivoryos/draft/history').get_json()['can_undo'] is False


def test_the_toolbar_is_one_row_with_import_and_export_under_more(auth, test_deck):
    _start_draft(auth)
    page = auth.get('/ivoryos/draft').get_data(as_text=True)
    toolbar = page[page.index('role="toolbar"'):page.index('Tabs for Info/Prep/Experiment/Cleanup')]
    tabs_row = page[page.index('Tabs for Info/Prep/Experiment/Cleanup'):page.index('showPythonCodeSwitch')]

    # New, Save As, then undo, redo and the history, then More
    assert toolbar.index('> New') < toolbar.index('> Save As') < toolbar.index('id="draftUndoButton"') \
        < toolbar.index('id="draftRedoButton"') < toolbar.index('id="draftHistoryButton"') < toolbar.index('More')
    # Import and Export are items of More, not buttons of their own
    more = toolbar[toolbar.index('More'):]
    assert 'data-bs-target="#jsonModal"' in more and 'script-json?filetype=script' in more
    assert 'class="dropdown-item" data-bs-toggle="modal" data-bs-target="#jsonModal"' in more
    # the row under it holds the tabs and the code preview only
    assert 'btn-group' not in tabs_row


def test_every_canvas_update_carries_what_undo_would_do(auth, test_deck):
    _start_draft(auth, 'int_method', 'float_method')

    html = auth.delete('/ivoryos/draft/steps/2').get_data(as_text=True)

    assert 'data-can-undo="true"' in html
    assert 'data-undo-label="Delete dummy.float_method"' in html
