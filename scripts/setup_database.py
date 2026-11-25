
"""Create tables and sample data for demonstrations. Safe to run more than once."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import DATABASE
from helpers.database import Database
from managers.login_manager import LoginManager
from managers.student_manager import StudentManager
from managers.book_manager import BookManager


def ensure_inventory_schema(conn):
    """
    Ensure the database supports textbook classifications
    and the existing return-tracking enhancements.

    This runs before sample data is inserted.
    Existing records are not deleted or overwritten.
    """

    # One classification represents a textbook title,
    # subject, and edition.
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS book_classifications (
            classification_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            edition INTEGER NOT NULL
                CHECK (edition IN (1, 2, 3))
        )
        '''
    )

    # Check the existing physical-book columns.
    book_columns = {
        row[1]
        for row in conn.execute(
            'PRAGMA table_info(books)'
        )
    }

    # Each physical copy belongs to one classification.
    # Preserve all existing Book IDs.
    if 'classification_id' not in book_columns:
        conn.execute(
            '''
            ALTER TABLE books
            ADD COLUMN classification_id TEXT
            REFERENCES book_classifications(classification_id)
            '''
        )

    # Improve classification-copy searches.
    conn.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_books_classification
        ON books(classification_id)
        '''
    )

    # Check the columns required by the return system.
    rental_columns = {
        row[1]
        for row in conn.execute(
            'PRAGMA table_info(rentals)'
        )
    }

    # Store the physical condition recorded at return.
    if 'return_condition' not in rental_columns:
        conn.execute(
            '''
            ALTER TABLE rentals
            ADD COLUMN return_condition TEXT
            '''
        )

    # Store the staff member who collected the return.
    if 'returned_to_user_id' not in rental_columns:
        conn.execute(
            '''
            ALTER TABLE rentals
            ADD COLUMN returned_to_user_id INTEGER
            REFERENCES users(user_id)
            '''
        )


def seed(path=DATABASE):
    """
    Initialize and seed a Nu-Mart database.

    Automated tests can pass their temporary database path.
    Sample records are only inserted when the corresponding
    table is empty.
    """

    Database.initialize(path)
    conn = Database.connect(path)

    try:
        conn.execute('BEGIN IMMEDIATE')

        # The upgraded BookManager requires these tables
        # and columns before any textbooks are inserted.
        ensure_inventory_schema(conn)

        # Create demonstration users when none exist.
        if not conn.execute(
            'SELECT 1 FROM users LIMIT 1'
        ).fetchone():

            LoginManager.add_user(
                conn,
                'admin',
                'ChangeMe12345!',
                'Demo',
                'Administrator',
                'Admin'
            )

            LoginManager.add_user(
                conn,
                'staff',
                'ChangeMe12345!',
                'Demo',
                'Staff',
                'Staff'
            )

        # Preserve the existing demonstration students.
        if not conn.execute(
            'SELECT 1 FROM students LIMIT 1'
        ).fetchone():

            for student in [
                (
                    'ST001',
                    'Alicia',
                    'Brown',
                    9,
                    '9A',
                    'Active'
                ),
                (
                    'ST002',
                    'Marcus',
                    'James',
                    10,
                    '10B',
                    'Active'
                ),
                (
                    'ST003',
                    'Shanice',
                    'Williams',
                    12,
                    '12A',
                    'Active'
                ),
                (
                    'ST004',
                    'Talia',
                    'Grant',
                    11,
                    '11C',
                    'Inactive'
                )
            ]:
                StudentManager.add_student(
                    conn,
                    *student
                )

        # Create the original demonstration inventory.
        #
        # The previous setup used Great for BK002 and BK005.
        # New textbooks now use Good, Fair, or Poor.
        #
        # BookManager.add_book() automatically creates
        # classifications and links each physical copy.
        if not conn.execute(
            'SELECT 1 FROM books LIMIT 1'
        ).fetchone():

            for book in [
                (
                    'BK001',
                    'Mathematics Essentials',
                    'Mathematics',
                    1,
                    'Good'
                ),
                (
                    'BK002',
                    'Mathematics Essentials',
                    'Mathematics',
                    2,
                    'Good'
                ),
                (
                    'BK003',
                    'English Language',
                    'English',
                    2,
                    'Good'
                ),
                (
                    'BK004',
                    'Caribbean History',
                    'History',
                    3,
                    'Fair'
                ),
                (
                    'BK005',
                    'Chemistry Studies',
                    'Chemistry',
                    3,
                    'Good'
                ),
                (
                    'BK006',
                    'Integrated Science',
                    'Science',
                    1,
                    'Good'
                )
            ]:
                BookManager.add_book(
                    conn,
                    *book
                )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(f'Database ready: {path}')
    print('Demo Admin login: admin / ChangeMe12345!')
    print('Demo Staff login: staff / ChangeMe12345!')
    print(
        'IMPORTANT: These are TEST credentials only. '
        'Change before real deployment.'
    )


if __name__ == '__main__':
    seed()
