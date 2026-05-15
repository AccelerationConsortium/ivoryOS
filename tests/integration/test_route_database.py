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
