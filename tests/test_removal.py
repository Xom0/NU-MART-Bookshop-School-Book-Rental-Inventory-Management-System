
"""Tests for Administrator-only book and student removal.

All tests use the temporary database created by conftest.py.
The live Nu-Mart demonstration database is not modified.
"""

import sqlite3

import pytest

from config import DATABASE
from helpers.database import Database


# ---------------------------------------------------------
# TEST HELPERS
# ---------------------------------------------------------

def get_test_database(client):
    """
    Connect to the temporary database used by the
    current Flask test client, never the live database.
    """
    path = client.application.config['DATABASE']

    assert path != DATABASE, (
        'Removal tests must not use the live database.'
    )

    return Database.connect(path)


def count_records(client, table):
    """Count records in an approved test table."""

    allowed_tables = {
        'books',
        'students',
        'book_classifications',
        'rentals',
        'receipts'
    }

    assert table in allowed_tables

    conn = get_test_database(client)

    try:
        return conn.execute(
            f'SELECT COUNT(*) FROM {table}'
        ).fetchone()[0]

    finally:
        conn.close()


def get_book(client, book_id):
    """Retrieve a physical book from the test database."""

    conn = get_test_database(client)

    try:
        return conn.execute(
            '''
            SELECT *
            FROM books
            WHERE book_id = ?
            ''',
            (book_id,)
        ).fetchone()

    finally:
        conn.close()


def get_student(client, student_id):
    """Retrieve a student from the test database."""

    conn = get_test_database(client)

    try:
        return conn.execute(
            '''
            SELECT *
            FROM students
            WHERE student_id = ?
            ''',
            (student_id,)
        ).fetchone()

    finally:
        conn.close()


def create_test_rental(client):
    """
    Create a rental in the temporary database.

    ST001 is Grade 9.
    BK001 is Edition 1.

    This creates a valid historical relationship used
    to test deletion restrictions.
    """

    conn = get_test_database(client)

    try:
        conn.execute('BEGIN IMMEDIATE')

        conn.execute(
            '''
            INSERT INTO rentals (
                student_id,
                book_id,
                rental_date,
                due_date,
                status
            )
            VALUES (?, ?, ?, ?, ?)
            ''',
            (
                'ST001',
                'BK001',
                '2026-11-01',
                '2026-12-01',
                'Active'
            )
        )

        conn.execute(
            '''
            UPDATE books
            SET availability = 'Rented'
            WHERE book_id = ?
            ''',
            ('BK001',)
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def login_as_staff(client):
    """Authenticate as Staff using the login form."""

    response = client.post(
        '/login',
        data={
            'access_type': 'Staff',
            'username': 'Removal Test Staff',
            'password': 'Staff2026!'
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    with client.session_transaction() as session:
        assert session.get('role') == 'Staff'

    return client


# ---------------------------------------------------------
# ADMINISTRATOR PAGE ACCESS
# ---------------------------------------------------------

def test_admin_can_open_removal_pages(admin):
    """Administrators can access both removal pages."""

    book_response = admin.get('/books/remove')
    student_response = admin.get('/students/remove')

    assert book_response.status_code == 200
    assert student_response.status_code == 200

    assert b'Remove Book' in book_response.data
    assert b'Remove Student' in student_response.data


def test_staff_cannot_access_removal_pages(client):
    """Staff must not access removal pages or submit deletions."""

    login_as_staff(client)

    assert client.get('/books/remove').status_code == 403
    assert client.get('/students/remove').status_code == 403

    book_count = count_records(client, 'books')
    student_count = count_records(client, 'students')

    book_response = client.post(
        '/books/remove',
        data={
            'operation': 'copies',
            'action': 'confirm',
            'book_ids': 'BK006'
        }
    )

    student_response = client.post(
        '/students/remove',
        data={
            'action': 'confirm',
            'student_id': 'ST004'
        }
    )

    assert book_response.status_code == 403
    assert student_response.status_code == 403

    assert count_records(client, 'books') == book_count
    assert count_records(client, 'students') == student_count


def test_guest_cannot_access_removal_pages(client):
    """Guests must authenticate before accessing removal pages."""

    book_response = client.get('/books/remove')
    student_response = client.get('/students/remove')

    assert book_response.status_code == 302
    assert student_response.status_code == 302

    assert '/login' in book_response.location
    assert '/login' in student_response.location


# ---------------------------------------------------------
# PHYSICAL BOOK REMOVAL
# ---------------------------------------------------------

def test_book_preview_does_not_delete(admin):
    """Previewing a book must not modify inventory."""

    before = count_records(admin, 'books')

    response = admin.post(
        '/books/remove',
        data={
            'operation': 'copies',
            'action': 'preview',
            'book_ids': 'BK006'
        }
    )

    assert response.status_code == 200
    assert b'BK006' in response.data
    assert b'Confirm Removal' in response.data

    assert count_records(admin, 'books') == before
    assert get_book(admin, 'BK006') is not None


def test_admin_can_remove_unused_physical_copy(admin):
    """An unused physical book can be removed by an Admin."""

    before = count_records(admin, 'books')

    response = admin.post(
        '/books/remove',
        data={
            'operation': 'copies',
            'action': 'confirm',
            'book_ids': 'BK006'
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    assert count_records(admin, 'books') == before - 1
    assert get_book(admin, 'BK006') is None

    # Removing a copy must not remove its classification.
    assert count_records(admin, 'book_classifications') > 0


def test_admin_can_remove_multiple_unused_copies(admin):
    """Multiple unused physical copies can be removed together."""

    before = count_records(admin, 'books')

    response = admin.post(
        '/books/remove',
        data={
            'operation': 'copies',
            'action': 'confirm',
            'book_ids': 'BK004, BK006'
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    assert count_records(admin, 'books') == before - 2

    assert get_book(admin, 'BK004') is None
    assert get_book(admin, 'BK006') is None


def test_rented_book_cannot_be_removed(admin):
    """An actively rented physical copy must be protected."""

    create_test_rental(admin)

    before = count_records(admin, 'books')

    response = admin.post(
        '/books/remove',
        data={
            'operation': 'copies',
            'action': 'confirm',
            'book_ids': 'BK001'
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    assert count_records(admin, 'books') == before
    assert get_book(admin, 'BK001') is not None

    assert b'cannot be removed' in response.data.lower() or (
        b'rental history' in response.data.lower()
    )


def test_batch_removal_is_atomic(admin):
    """
    If one selected book has rental history,
    no books in the batch may be deleted.
    """

    create_test_rental(admin)

    before = count_records(admin, 'books')

    response = admin.post(
        '/books/remove',
        data={
            'operation': 'copies',
            'action': 'confirm',
            'book_ids': 'BK006, BK001'
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    # BK001 has history and must remain.
    assert get_book(admin, 'BK001') is not None

    # BK006 must also remain because the batch failed.
    assert get_book(admin, 'BK006') is not None

    assert count_records(admin, 'books') == before


# ---------------------------------------------------------
# CLASSIFICATION REMOVAL
# ---------------------------------------------------------

def test_admin_can_remove_unused_classification(admin):
    """Remove an unused classification and its physical copies."""

    conn = get_test_database(admin)

    try:
        classification_id = conn.execute(
            '''
            SELECT classification_id
            FROM books
            WHERE book_id = ?
            ''',
            ('BK006',)
        ).fetchone()['classification_id']

    finally:
        conn.close()

    before_books = count_records(admin, 'books')
    before_classes = count_records(
        admin,
        'book_classifications'
    )

    response = admin.post(
        '/books/remove',
        data={
            'operation': 'classification',
            'action': 'confirm',
            'classification_id': classification_id
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    assert get_book(admin, 'BK006') is None
    assert count_records(admin, 'books') == before_books - 1

    assert count_records(
        admin,
        'book_classifications'
    ) == before_classes - 1


def test_classification_with_rental_history_is_protected(admin):
    """A classification with rented copies cannot be removed."""

    create_test_rental(admin)

    conn = get_test_database(admin)

    try:
        classification_id = conn.execute(
            '''
            SELECT classification_id
            FROM books
            WHERE book_id = ?
            ''',
            ('BK001',)
        ).fetchone()['classification_id']

    finally:
        conn.close()

    before_books = count_records(admin, 'books')
    before_classes = count_records(
        admin,
        'book_classifications'
    )

    response = admin.post(
        '/books/remove',
        data={
            'operation': 'classification',
            'action': 'confirm',
            'classification_id': classification_id
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    assert get_book(admin, 'BK001') is not None

    assert count_records(admin, 'books') == before_books
    assert count_records(
        admin,
        'book_classifications'
    ) == before_classes


# ---------------------------------------------------------
# STUDENT REMOVAL
# ---------------------------------------------------------

def test_student_preview_does_not_delete(admin):
    """Previewing a student must not remove the record."""

    before = count_records(admin, 'students')

    response = admin.post(
        '/students/remove',
        data={
            'action': 'preview',
            'student_id': 'ST004'
        }
    )

    assert response.status_code == 200
    assert b'ST004' in response.data
    assert b'Confirm Removal' in response.data

    assert count_records(admin, 'students') == before
    assert get_student(admin, 'ST004') is not None


def test_admin_can_remove_unused_student(admin):
    """An Administrator may remove a student without history."""

    before = count_records(admin, 'students')

    response = admin.post(
        '/students/remove',
        data={
            'action': 'confirm',
            'student_id': 'ST004'
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    assert count_records(admin, 'students') == before - 1
    assert get_student(admin, 'ST004') is None


def test_student_with_rental_history_is_protected(admin):
    """A student with rental history must not be removed."""

    create_test_rental(admin)

    before = count_records(admin, 'students')

    response = admin.post(
        '/students/remove',
        data={
            'action': 'confirm',
            'student_id': 'ST001'
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    assert count_records(admin, 'students') == before
    assert get_student(admin, 'ST001') is not None


def test_student_with_receipt_history_is_protected(admin):
    """A student with receipt history must not be removed."""

    conn = get_test_database(admin)

    try:
        conn.execute(
            '''
            INSERT INTO receipts (
                student_id,
                issued_at,
                user_id
            )
            VALUES (?, ?, ?)
            ''',
            (
                'ST004',
                '2026-11-24T12:00:00',
                None
            )
        )

    finally:
        conn.close()

    before = count_records(admin, 'students')

    response = admin.post(
        '/students/remove',
        data={
            'action': 'confirm',
            'student_id': 'ST004'
        },
        follow_redirects=True
    )

    assert response.status_code == 200

    assert count_records(admin, 'students') == before
    assert get_student(admin, 'ST004') is not None
