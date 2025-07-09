from datetime import datetime

from ivoryos.utils.db_models import Script, WorkflowRun, WorkflowStep
from ivoryos import db

def test_database_scripts_page(auth):
    """
    GIVEN an authenticated user
    WHEN they access the script database page
    THEN the page should load and show their scripts
    """
    # First, create a script so the page has something to render
    with auth.application.app_context():
        script = Script(name='test_script', author='testuser')
        db.session.add(script)
        db.session.commit()

    response = auth.get('/ivoryos/database/scripts/', follow_redirects=True)
    assert response.status_code == 200
    # assert b'Scripts Database' in response.data
    assert b'<title>IvoryOS | Design Database</title>' in response.data

def test_database_workflows_page(auth):
    """
    GIVEN an authenticated user
    WHEN they access the workflow database page
    THEN the page should load and show past workflow runs
    """
    # Create a workflow run to display
    with auth.application.app_context():
        run = WorkflowRun(name="untitled", platform="deck",start_time=datetime.now())
        db.session.add(run)
        db.session.commit()
        run_id = run.id

    response = auth.get('/ivoryos/database/workflows/', follow_redirects=True)
    assert response.status_code == 200
    assert b'Workflow ID' in response.data
    # assert b'run_id' in response.data

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

        step = WorkflowStep(method_name='test_step', workflow_id=run_id, phase="main", run_error=False, start_time=datetime.now())
        db.session.add(step)
        db.session.commit()
        # run_id = run.id

    response = auth.get(f'/ivoryos/database/workflows/{run_id}', follow_redirects=True)
    assert response.status_code == 200
    # assert b'test_step' in response.data # Check for a title on the view page
    assert b'test_workflow' in response.data