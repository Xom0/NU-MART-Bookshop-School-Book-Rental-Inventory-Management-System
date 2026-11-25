
from datetime import date, timedelta


def test_guest_redirected(client):
    # Guests must not access protected inventory pages.
    assert client.get('/books').status_code == 302


def test_admin_pages_and_auth(admin):
    # The admin fixture performs the new role-based login.
    # Verify that all required pages remain accessible.
    for page in [
        '/',
        '/books',
        '/books/add',
        '/students',
        '/rentals',
        '/rentals/new',
        '/reminders'
    ]:
        response = admin.get(page)

        assert response.status_code == 200, (
            page,
            response.status_code
        )


def test_rent_via_web(admin):
    # An authenticated Administrator creates a rental
    # using the physical Book ID.
    response = admin.post(
        '/rentals/new',
        data={
            'student_id': 'ST002',
            'book_ids': 'BK002',
            'due_date': (
                date.today() + timedelta(days=14)
            ).isoformat()
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    # The response should show the generated receipt.
    assert b'Receipt #' in response.data

    # The receipt should reference the physical Book ID.
    assert b'BK002' in response.data


def test_staff_cannot_add_books(client):
    # Sign in using the updated Staff access type.
    response = client.post(
        '/login',
        data={
            'access_type': 'Staff',
            'username': 'Test Staff',
            'password': 'Staff2026!'
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    # Confirm that the user is actually logged in as Staff.
    with client.session_transaction() as session:
        assert session.get('user_id') is not None
        assert session.get('role') == 'Staff'
        assert session.get('username') == 'Test Staff'

    # Staff must not be able to access Administrator-only
    # inventory creation functionality.
    assert client.get('/books/add').status_code == 403
