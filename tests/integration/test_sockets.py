def test_socket_connection(socketio_client):
    """
    Test that a client can successfully connect to the Socket.IO server.
    """
    assert socketio_client.is_connected()
    socketio_client.disconnect()
    assert not socketio_client.is_connected()


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