from datetime import datetime

from ivoryos.models import Script, WorkflowRun, WorkflowStep, WorkflowPhase
from ivoryos import db


def create_workflow_run_with_phase(app):
    with app.app_context():
        run = WorkflowRun(
            name='test_workflow',
            platform='test_platform',
            start_time=datetime(2026, 5, 14, 12, 0, 0),
            data_path='test_workflow.csv',
        )
        db.session.add(run)
        db.session.commit()

        phase = WorkflowPhase(
            run_id=run.id,
            name='main',
            repeat_index=1,
            parameters=[{'input': 1}],
            outputs=[{'yield': [3, 4], 'status': 'ok'}],
            start_time=datetime(2026, 5, 14, 12, 1, 0),
        )
        db.session.add(phase)
        db.session.commit()

        step = WorkflowStep(
            phase_id=phase.id,
            step_index=1,
            method_name='deck.sensor.read',
            start_time=datetime(2026, 5, 14, 12, 2, 0),
            output={'input': 1, 'yield': 3},
        )
        db.session.add(step)
        db.session.commit()
        return run.id


def test_database_scripts_page(auth):
    """
    GIVEN an authenticated user
    WHEN they access the script library page
    THEN the page should load and show their scripts
    """
    # First, create a script so the page has something to render
    with auth.application.app_context():
        script = Script(name='test_script', author='testuser')
        db.session.add(script)
        db.session.commit()

    response = auth.get('/ivoryos/library/', follow_redirects=True)
    assert response.status_code == 200


def test_database_workflows_page(auth):
    """
    GIVEN an authenticated user
    WHEN they access the workflow records page
    THEN the page should load and show past workflow runs
    """
    # Create a workflow run to display
    with auth.application.app_context():
        run = WorkflowRun(name="untitled", platform="deck", start_time=datetime.now())
        db.session.add(run)
        db.session.commit()

    response = auth.get('/ivoryos/executions/records', follow_redirects=True)
    assert response.status_code == 200


def test_view_specific_workflow(auth):
    """
    GIVEN an authenticated user and an existing workflow run
    WHEN they access the specific URL for that workflow
    THEN the detailed view for that run should be displayed
    """
    with auth.application.app_context():
        run = WorkflowRun(name='test_workflow', platform='test_platform', start_time=datetime.now())
        db.session.add(run)
        db.session.commit()
        run_id = run.id

        phase = WorkflowPhase(run_id=run_id, name="main", start_time=datetime.now())
        db.session.add(phase)
        db.session.commit()

    response = auth.get(f'/ivoryos/executions/records/{run_id}', follow_redirects=True)
    assert response.status_code == 200


def test_database_workflows_json_filters_by_keyword(auth):
    run_id = create_workflow_run_with_phase(auth.application)

    response = auth.get(
        '/ivoryos/executions/records?keyword=test_workflow',
        headers={'Accept': 'application/json'},
    )

    assert response.status_code == 200
    workflow_data = response.get_json()['workflow_data']
    assert str(run_id) in workflow_data
    assert workflow_data[str(run_id)]['workflow_name'] == 'test_workflow'


def test_workflow_logs_json_and_missing_record(auth):
    run_id = create_workflow_run_with_phase(auth.application)

    response = auth.get(
        f'/ivoryos/executions/records/{run_id}',
        headers={'Accept': 'application/json'},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['workflow_info']['name'] == 'test_workflow'
    assert payload['csv_file_name'] == 'test_workflow.csv'
    assert payload['phases']['script']['1'][0]['steps'][0]['method_name'] == 'deck.sensor.read'

    missing = auth.get('/ivoryos/executions/records/999999', headers={'Accept': 'application/json'})
    assert missing.status_code == 404
    assert missing.get_json() == {'error': 'Workflow not found'}


def test_workflow_phase_data_csv_logs_and_delete(auth):
    run_id = create_workflow_run_with_phase(auth.application)

    phase_data = auth.get(f'/ivoryos/executions/data/{run_id}')
    assert phase_data.status_code == 200
    assert phase_data.get_json() == {'1': {'yield': [{'x': 1, 'y': 3}, {'x': 1, 'y': 4}]}}

    csv_response = auth.get(f'/ivoryos/executions/records/{run_id}/steps_data_csv')
    assert csv_response.status_code == 200
    assert 'deck.sensor.read' in csv_response.get_data(as_text=True)
    assert 'test_workflow_steps.csv' in csv_response.headers['Content-disposition']

    missing_log = auth.get(f'/ivoryos/executions/records/{run_id}/logs')
    assert missing_log.status_code == 404
    assert missing_log.get_json() == {'error': 'Log file not found on disk'}

    delete_response = auth.delete(f'/ivoryos/executions/records/{run_id}')
    assert delete_response.status_code == 200
    assert delete_response.get_json() == {'success': True}
    with auth.application.app_context():
        assert db.session.get(WorkflowRun, run_id) is None

    missing_delete = auth.delete(f'/ivoryos/executions/records/{run_id}')
    assert missing_delete.status_code == 404
    assert missing_delete.get_json() == {'error': 'Workflow run not found', 'success': False}


def test_existing_database_gets_the_new_run_columns(app, tmp_path):
    """
    GIVEN a database from before runs kept their config table, outcome and events
    WHEN the app checks the schema at start
    THEN the columns are added, so queries on runs keep working
    """
    from sqlalchemy import create_engine, inspect, text
    from ivoryos.app import reset_old_schema

    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE workflow_runs (id INTEGER PRIMARY KEY, name VARCHAR(128), platform VARCHAR(128))"))
        conn.execute(text("CREATE TABLE workflow_phases (id INTEGER PRIMARY KEY, run_id INTEGER)"))

    with app.app_context():
        reset_old_schema(engine, str(tmp_path))

    columns = {column['name'] for column in inspect(engine).get_columns('workflow_runs')}
    assert {'config_history', 'status', 'events'} <= columns


def test_workflow_view_shows_the_config_table_results_outcome_and_events(auth):
    """
    GIVEN a config run that was edited, skipped a row and was stopped early
    WHEN its page is opened
    THEN it shows how it ended, every row with its status and outputs, the
    changes tucked away, and the user's stop on the timeline
    """
    history = {
        'initial': [{'temperature': '25'}, {'temperature': 'hot'}, {'temperature': '60'}],
        'final': [{'row': 1, 'status': 'done', 'iteration': 1, 'values': {'temperature': 30.0}, 'outputs': {'yield_pct': 0.93}},
                  {'row': 2, 'status': 'skipped', 'iteration': None, 'values': {'temperature': 'hot'}, 'outputs': {},
                   'reason': "cannot convert 'hot'", 'invalid': {'temperature': "cannot convert 'hot'"}},
                  {'row': 3, 'status': 'pending', 'iteration': None, 'values': {'temperature': '60'}, 'outputs': {}}],
        'changes': [{'time': '2026-10-06T10:00:00', 'row': 1, 'action': 'edit', 'field': 'temperature',
                     'from': '25', 'to': '30', 'while_running': True, 'used': True}],
    }
    events = [{'time': '2026-10-06T10:00:05', 'kind': 'stop_after_iteration', 'detail': None}]
    with auth.application.app_context():
        run = WorkflowRun(name='edited', platform='deck', start_time=datetime.now(), config_history=history,
                          status='stopped', events=events)
        db.session.add(run)
        db.session.commit()
        run_id = run.id

    body = auth.get(f'/ivoryos/executions/records/{run_id}').get_data(as_text=True)

    assert 'Stopped early' in body
    assert 'Config table results' in body
    assert '0.93' in body and 'href="#card-iter1"' in body
    # the value that could not run is marked in red, its reason on hover rather than spelled out
    assert '<td class="text-danger fw-semibold" title="cannot convert &#39;hot&#39;">hot</td>' in body
    assert '<div class="text-danger">' not in body
    assert 'not run' in body
    assert 'Changed during the run (1)' in body
    assert "Row 1: &#39;temperature&#39; changed from &#39;25&#39; to &#39;30&#39; while it was running" in body
    assert '"Stop after this iteration"' in body and "group: 'events'" in body
    assert 'Stopped early' in auth.get('/ivoryos/executions/records').get_data(as_text=True)


def test_run_list_tells_running_and_unfinished_runs_apart(auth):
    """
    GIVEN a run in progress, one that never finished, and one from before outcomes were kept
    WHEN the run list is opened
    THEN the running one shows as running, the unfinished one as not finished,
    and the old one shows no outcome
    """
    from ivoryos.runtime.state import GlobalState

    with auth.application.app_context():
        running = WorkflowRun(name='now', platform='deck', start_time=datetime.now())
        unfinished = WorkflowRun(name='crashed', platform='deck', start_time=datetime.now())
        old = WorkflowRun(name='old', platform='deck', start_time=datetime.now(), end_time=datetime.now())
        db.session.add_all([running, unfinished, old])
        db.session.commit()
        running_id = running.id

    state = GlobalState()
    previous = state.runner_status
    state.runner_status = {'id': running_id, 'type': 'workflow'}
    state.runner_lock.acquire()
    try:
        body = auth.get('/ivoryos/executions/records').get_data(as_text=True)
    finally:
        state.runner_lock.release()
        state.runner_status = previous

    assert body.count('title="Running"') == 1
    assert body.count('title="Did not finish"') == 1
    assert 'bg-teal-subtle' not in body
