
from pathlib import Path
import pytest

from app import create_app
from scripts.setup_database import seed


@pytest.fixture
def client(tmp_path):
    """
    Create a separate temporary Nu-Mart database
    for each automated test.

    The live bookshop database is not modified.
    """

    path = str(tmp_path / 'test_bookshop.db')

    # Create tables and seed demonstration records.
    seed(path)

    # Configure the Flask application for testing.
    app = create_app({
        'TESTING': True,
        'DATABASE': path,
        'SECRET_KEY': 'test-only-secret'
    })

    with app.test_client() as client:
        yield client


@pytest.fixture
def admin(client):
    """
    Authenticate using the Administrator access type.

    The login page submits 'Administrator', which
    LoginManager maps to the database role 'Admin'.
    """

    response = client.post(
        '/login',
        data={
            'access_type': 'Administrator',
            'username': 'Test Administrator',
            'password': 'Admin2026!'
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    # HTTP 200 alone does not prove authentication.
    # Verify that the session contains an authenticated
    # Administrator account.
    with client.session_transaction() as session:

        assert session.get('user_id') is not None

        assert session.get('role') == 'Admin'

        assert session.get('username') == 'Test Administrator'

    return client
