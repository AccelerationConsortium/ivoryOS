def test_socket_connection(socketio_client):
    """
    Test that a client can successfully connect to the Socket.IO server.
    """
    assert socketio_client.is_connected()
    socketio_client.disconnect()
    assert not socketio_client.is_connected()


def test_socket_handlers(socketio_client, app):
    """
    Test the various socket handlers in socket_handlers.py
    """
    with app.app_context():
        # Connect the client
        if not socketio_client.is_connected():
            socketio_client.connect()
        
        # Check if connect emitted some initial data
        received = socketio_client.get_received()
        assert len(received) > 0
        event_names = [event['name'] for event in received]
        assert 'server_boot_id' in event_names
        assert 'pause_status' in event_names
        
        # Emit pause
        socketio_client.emit('pause')
        received = socketio_client.get_received()
        assert len(received) > 0
        assert 'log' in [event['name'] for event in received]
        
        # Emit retry
        socketio_client.emit('retry')
        received = socketio_client.get_received()
        assert len(received) > 0
        
        # Emit submit_input
        socketio_client.emit('submit_input', {'value': 'test_input'})
        received = socketio_client.get_received()
        assert len(received) > 0
        assert 'log' in [event['name'] for event in received]

        socketio_client.disconnect()


# def test_logger_socket_event(socketio_client):
#     """
#     Test the custom logging event handler.
#     (This assumes you have a handler like `@socketio.on('start_log')`)
#     """
#     # Connect the client
#     socketio_client.connect()
#
#     # Emit an event from the client to the server
#     socketio_client.emit('start_log', {'logger_name': 'my_test_logger'})
#
#     # Check what the server sent back to the client
#     received = socketio_client.get_received()
#
#     assert len(received) > 0
#     assert received[0]['name'] == 'log_message'  # Check for the event name
#     assert 'Logger my_test_logger started' in received[0]['args'][0]['data']

def test_a_page_that_connects_is_sent_where_the_run_is(socketio_client, app, monkeypatch):
    """A page loaded, reloaded or reconnected mid-run is sent the whole picture at once."""
    from types import SimpleNamespace
    from ivoryos.socket_handlers import runner
    from ivoryos.runtime.run_progress import RunProgress

    progress = RunProgress()
    progress.start("task-1", "flow", SimpleNamespace(script_dict={"prep": [{}], "script": [{}, {}]}), iterations=4)
    progress.start_iteration(2)
    progress.at_step("script", 1)
    monkeypatch.setattr(runner, "progress", progress)
    monkeypatch.setattr(runner, "last_execution_section", "script-0")

    with app.app_context():
        socketio_client.get_received()  # what the client's first connect was sent
        socketio_client.disconnect()
        socketio_client.connect()
        received = {event['name']: event['args'][0] for event in socketio_client.get_received()}

    assert received['progress']['uid'] == 'task-1' and received['progress']['state'] == 'running'
    assert (received['progress']['iteration'], received['progress']['iterations'], received['progress']['step']) == (2, 4, 1)
    # the step running now is highlighted again
    assert received['execution'] == {'section': 'script-0'}
    socketio_client.disconnect()


def test_a_page_that_connects_when_nothing_runs_is_told_so(socketio_client, app, monkeypatch):
    from ivoryos.socket_handlers import runner
    from ivoryos.runtime.run_progress import RunProgress

    monkeypatch.setattr(runner, "progress", RunProgress())
    with app.app_context():
        socketio_client.get_received()  # what the client's first connect was sent
        socketio_client.disconnect()
        socketio_client.connect()
        received = socketio_client.get_received()

    [progress] = [event['args'][0] for event in received if event['name'] == 'progress']
    assert progress['state'] == 'idle'
    assert 'execution' not in [event['name'] for event in received]
    socketio_client.disconnect()


def test_the_log_history_goes_only_to_the_page_that_connects(app):
    """A page that connects is sent the last log lines; pages already open are not sent them again."""
    import os
    from ivoryos import socketio

    log_path = os.path.join(app.config["OUTPUT_FOLDER"], app.config["LOGGERS_PATH"])
    with open(log_path, "a") as log_file:
        log_file.write("a line already in the log\n")

    with app.app_context():
        open_page = socketio.test_client(app)
        open_page.get_received()  # what it was sent when it connected

        new_page = socketio.test_client(app)

        new_lines = [event['args'][0]['message'] for event in new_page.get_received() if event['name'] == 'log']
        assert "a line already in the log\n" in new_lines
        assert [event for event in open_page.get_received() if event['name'] == 'log'] == []
        new_page.disconnect()
        open_page.disconnect()
