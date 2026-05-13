from datetime import datetime

from ivoryos.models import Script, WorkflowRun, WorkflowStep, WorkflowPhase
from ivoryos import db


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