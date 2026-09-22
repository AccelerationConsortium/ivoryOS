from ivoryos.models import Script, db
from ivoryos.script import ScriptEditor
from ivoryos.services.draft_service import post_script_for_user


def test_save_list_get_and_delete_library_workflow(auth):
    draft = Script(
        author='testuser',
        deck='demo_deck',
        script_dict={
            'prep': [],
            'script': [{
                'id': 1,
                'uuid': 1,
                'instrument': 'comment',
                'action': 'comment',
                'args': {'statement': 'hello'},
                'return': '',
                'arg_types': {'statement': 'str'},
            }],
            'cleanup': [],
        },
    )
    with auth.application.app_context():
        post_script_for_user('testuser', draft)

    save_response = auth.post(
        '/ivoryos/library/',
        data={
            'run_name': 'saved_workflow',
            'description': 'Saved from tests',
            'register_workflow': 'on',
        },
        headers={'Accept': 'application/json'},
    )

    assert save_response.status_code == 200
    assert save_response.get_json()['success'] is True
    with auth.application.app_context():
        saved = db.session.get(Script, 'saved_workflow')
        assert saved is not None
        assert saved.description == 'Saved from tests'
        assert saved.registered is True

    list_response = auth.get('/ivoryos/library/?keyword=saved', headers={'Accept': 'application/json'})
    assert list_response.status_code == 200
    assert list_response.get_json() == {'workflows': ['saved_workflow']}

    get_response = auth.get('/ivoryos/library/saved_workflow', headers={'Accept': 'application/json'})
    assert get_response.status_code == 200
    payload = get_response.get_json()
    assert payload['script']['name'] == 'saved_workflow'
    assert 'script' in payload['python_script']

    delete_response = auth.delete('/ivoryos/library/saved_workflow')
    assert delete_response.status_code == 200
    assert delete_response.get_json() == {'success': True}

    missing_delete = auth.delete('/ivoryos/library/saved_workflow')
    assert missing_delete.status_code == 200
    assert missing_delete.get_json() == {'success': False}


def test_library_publish_rejects_incomplete_draft(auth):
    draft = Script(author='testuser', deck=None)
    with auth.application.app_context():
        post_script_for_user('testuser', draft)

    response = auth.post(
        '/ivoryos/library/',
        data={'run_name': 'no_deck'},
        headers={'Accept': 'application/json'},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        'success': False,
        'error': 'Deck cannot be empty, try to re-submit deck configuration on the left panel',
    }


def test_library_flags_a_workflow_that_no_longer_fits_the_loaded_deck(auth, test_deck, init_database):
    """
    GIVEN two saved workflows, one stale against the loaded deck and one for another deck
    WHEN the library is listed
    THEN only the stale one for this deck is marked
    """
    from ivoryos.runtime.state import global_state

    global_state._deck.__name__ = 'dummy_deck'
    try:
        stale = Script(name='stale_here', author='testuser', deck='dummy_deck')
        ScriptEditor(stale).add_action({
            'instrument': 'deck.dummy', 'action': 'method_that_was_deleted',
            'args': {}, 'return': '', 'arg_types': {},
        })
        other = Script(name='for_other_platform', author='testuser', deck='some_other_deck')
        ScriptEditor(other).add_action({
            'instrument': 'deck.dummy', 'action': 'method_that_was_deleted',
            'args': {}, 'return': '', 'arg_types': {},
        })
        healthy = Script(name='healthy_here', author='testuser', deck='dummy_deck')
        ScriptEditor(healthy).add_action({
            'instrument': 'deck.dummy', 'action': 'int_method',
            'args': {'arg': 1}, 'return': '', 'arg_types': {'arg': 'int'},
        })

        with auth.application.app_context():
            for script in (stale, other, healthy):
                db.session.add(script)
            db.session.commit()

        body = auth.get('/ivoryos/library/', follow_redirects=True).get_data(as_text=True)
    finally:
        del global_state._deck.__name__

    assert 'stale_here' in body and 'for_other_platform' in body and 'healthy_here' in body
    # one marker only: the other-deck workflow is not broken, just not for this platform
    assert body.count('no longer match the current deck') == 2  # aria-label + title
    assert 'missing method method_that_was_deleted' in body
