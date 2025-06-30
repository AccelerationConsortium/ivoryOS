from ivoryos.utils.db_models import User, db


def test_get_signup(client):
    """
    GIVEN a client
    WHEN a GET request is made to /ivoryos/auth/signup
    THEN check that signup page loads with 200 status and contains "Signup" text
    """
    response = client.get("/ivoryos/auth/signup", follow_redirects=True)
    assert response.status_code == 200
    assert b"Signup" in response.data


def test_route_auth_signup(client):
    """
    GIVEN a client
    WHEN a POST request is made to /ivoryos/auth/signup with valid credentials
    THEN check that signup succeeds with 200 status and the user is created in database
    """
    response = client.post("/ivoryos/auth/signup",
                           data={
                               "username": "second_testuser",
                               "password": "password"
                           },
                           follow_redirects=True
                           )
    assert response.status_code == 200
    assert b"Login" in response.data

    # Verify user was created
    with client.application.app_context():
        user = db.session.query(User).filter(User.username == 'second_testuser').first()
        assert user is not None


def test_duplicate_user_signup(client, init_database):
    """
    GIVEN a client and init_database fixture
    WHEN a POST request is made to signup with an existing username
    THEN check that signup fails with 409 status and appropriate error message
    """
    client.post('/ivoryos/auth/signup', data={
        'username': 'existinguser',
        'password': 'anotherpass'
    })
    # Try to create duplicate
    response = client.post('/ivoryos/auth/signup', data={
        'username': 'existinguser',
        'password': 'anotherpass'
    })
    assert response.status_code == 409
    assert b"Signup" in response.data
    assert b"User already exists" in response.data

    # Verify user was created
    users = db.session.query(User).filter(User.username == 'existinguser').all()
    assert len(users) == 1


def test_failed_login(client):
    """
    GIVEN a client and invalid login credentials
    WHEN a POST request is made to /ivoryos/auth/login
    THEN check that login fails with 401 status and the appropriate error message
    """
    response = client.post('/ivoryos/auth/login', data={
        'username': 'nonexistent',
        'password': 'wrongpass'
    })
    assert response.status_code == 401

def test_logout(auth):
    """
    GIVEN an authenticated client
    WHEN a GET request is made to /ivoryos/auth/logout
    THEN check that logout succeeds with 302 status and redirects to login
    """
    response = auth.get('/ivoryos/auth/logout')
    assert response.status_code == 302  # Redirect to login