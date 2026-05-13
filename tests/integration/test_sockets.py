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