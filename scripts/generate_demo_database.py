
"""Generate and safely install the complete Nu-Mart demonstration database."""

"""Generate and safely install the complete Nu-Mart demonstration database."""

import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config import DATABASE, ROOT
from helpers.database import Database
from managers.book_manager import BookManager
from managers.login_manager import LoginManager
from managers.student_manager import StudentManager


LIVE_DB = ROOT / 'instance' / 'bookshop.db'
BUILD_DB = ROOT / 'instance' / 'bookshop-building.db'
BACKUP_DIR = ROOT / 'backups'

STUDENT_COUNT = 100
COPIES_PER_CLASSIFICATION = 200

# The first two fields describe the subject and textbook title.
# The third field is the edition.
TEXTBOOKS = [
    ('Mathematics', 'Mathematics Essentials', 1),
    ('Mathematics', 'Mathematics Essentials', 2),
    ('Mathematics', 'Mathematics Essentials', 3),

    ('English', 'English Language', 1),
    ('English', 'English Language', 2),
    ('English', 'English Language', 3),

    ('Science', 'Integrated Science', 1),
    ('Science', 'Integrated Science', 2),

    ('Biology', 'Biology for Students', 2),
    ('Biology', 'Biology for Students', 3),

    ('Chemistry', 'Chemistry Studies', 2),
    ('Chemistry', 'Chemistry Studies', 3),

    ('Physics', 'Physics Fundamentals', 2),
    ('Physics', 'Physics Fundamentals', 3),

    ('Geography', 'Geography of the Caribbean', 1),
    ('Geography', 'Geography of the Caribbean', 2),

    ('History', 'Caribbean History', 2),
    ('History', 'Caribbean History', 3),

    ('Business', 'Principles of Business', 2),
    ('Information Technology', 'Information Technology', 2)
]

FIRST_NAMES = [
    'Alicia', 'Marcus', 'Shanice', 'Talia', 'Andre',
    'Jada', 'Daniel', 'Brianna', 'Nathan', 'Kayla',
    'Jordan', 'Amara', 'Joshua', 'Naomi', 'David',
    'Leah', 'Malik', 'Chloe', 'Ethan', 'Maya'
]

LAST_NAMES = [
    'Brown', 'James', 'Williams', 'Grant', 'Campbell',
    'Morgan', 'Johnson', 'Clarke', 'Thomas', 'Reid',
    'Smith', 'Davis', 'Robinson', 'Bennett', 'Taylor',
    'Wilson', 'Walker', 'Harris', 'Allen', 'Green'
]


def generate_students(conn):
    """Create 100 fictional students across Grades 9 to 13."""

    for index in range(STUDENT_COUNT):
        number = index + 1

        student_id = f'ST{number:03d}'
        first_name = FIRST_NAMES[index % len(FIRST_NAMES)]

        last_name = LAST_NAMES[
            (index * 7 + index // 20) % len(LAST_NAMES)
        ]

        grade = 9 + (index % 5)
        class_letter = chr(ord('A') + (index // 5) % 4)
        class_name = f'{grade}{class_letter}'

        # Ten students are Inactive to test enrolment rules.
        enrolment_status = (
            'Inactive' if number % 10 == 0 else 'Active'
        )

        StudentManager.add_student(
            conn,
            student_id,
            first_name,
            last_name,
            grade,
            class_name,
            enrolment_status
        )


def generate_users(conn):
    """Create the demonstration Administrator and Staff accounts."""

    LoginManager.add_user(
        conn,
        'Demo Administrator',
        LoginManager.ADMIN_PASSWORD,
        'Demo',
        'Administrator',
        'Admin'
    )

    LoginManager.add_user(
        conn,
        'Demo Staff',
        LoginManager.STAFF_PASSWORD,
        'Demo',
        'Staff',
        'Staff'
    )


def generate_inventory(conn):
    """Create 20 classifications with 200 physical copies each."""

    for subject, title, edition in TEXTBOOKS:

        # Create the classification and the first 170 copies.
        result = BookManager.create_textbook_with_copies(
            conn,
            title,
            subject,
            edition,
            170,
            'Good'
        )

        classification_id = result['classification_id']

        # Add 25 Fair-condition copies.
        BookManager.add_copies(
            conn,
            classification_id,
            25,
            'Fair'
        )

        # Add 5 Poor-condition copies.
        # These remain in inventory but cannot be rented.
        BookManager.add_copies(
            conn,
            classification_id,
            5,
            'Poor'
        )

        print(
            f'{classification_id}: '
            f'{title}, Edition {edition} — '
            f'{COPIES_PER_CLASSIFICATION} copies'
        )


def verify_database(path):
    """Verify record counts, relationships, and SQLite integrity."""

    conn = sqlite3.connect(path)

    try:
        conn.execute('PRAGMA foreign_keys=ON')

        counts = {
            'students': conn.execute(
                'SELECT COUNT(*) FROM students'
            ).fetchone()[0],

            'classifications': conn.execute(
                'SELECT COUNT(*) FROM book_classifications'
            ).fetchone()[0],

            'books': conn.execute(
                'SELECT COUNT(*) FROM books'
            ).fetchone()[0],

            'users': conn.execute(
                'SELECT COUNT(*) FROM users'
            ).fetchone()[0]
        }

        expected = {
            'students': 100,
            'classifications': 20,
            'books': 4000,
            'users': 2
        }

        for table, expected_count in expected.items():
            if counts[table] != expected_count:
                raise ValueError(
                    f'{table}: expected {expected_count}, '
                    f'found {counts[table]}'
                )

        # Every physical copy must have a classification.
        unlinked = conn.execute(
            '''
            SELECT COUNT(*)
            FROM books b
            LEFT JOIN book_classifications c
                ON b.classification_id = c.classification_id
            WHERE c.classification_id IS NULL
            '''
        ).fetchone()[0]

        if unlinked:
            raise ValueError(
                f'{unlinked} physical copies are unclassified.'
            )

        # Every classification must contain exactly 200 copies.
        groups = conn.execute(
            '''
            SELECT classification_id, COUNT(*)
            FROM books
            GROUP BY classification_id
            '''
        ).fetchall()

        if len(groups) != 20 or any(
            count != COPIES_PER_CLASSIFICATION
            for _, count in groups
        ):
            raise ValueError(
                'One or more classifications have incorrect copy counts.'
            )

        # Test SQLite database integrity.
        integrity = conn.execute(
            'PRAGMA integrity_check'
        ).fetchone()[0]

        if integrity != 'ok':
            raise ValueError(
                f'Database integrity check failed: {integrity}'
            )

        # Check foreign-key relationships.
        violations = conn.execute(
            'PRAGMA foreign_key_check'
        ).fetchall()

        if violations:
            raise ValueError(
                f'Foreign-key violations: {violations}'
            )

        print('\nDATABASE VERIFICATION PASSED')

        for table, count in counts.items():
            print(f'{table}: {count}')

        print('Unclassified books:', unlinked)
        print('SQLite integrity:', integrity)
        print('Foreign-key violations:', len(violations))

    finally:
        conn.close()


def backup_existing_database():
    """Create a consistent backup of the previous active database."""

    if not LIVE_DB.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime(
        '%Y%m%d-%H%M%S-%f'
    )

    backup_path = (
        BACKUP_DIR / f'bookshop-before-demo-{timestamp}.db'
    )

    source = sqlite3.connect(LIVE_DB)
    destination = sqlite3.connect(backup_path)

    try:
        source.backup(destination)

    finally:
        destination.close()
        source.close()

    # Confirm the backup is a valid SQLite database.
    verify_backup = sqlite3.connect(backup_path)

    try:
        result = verify_backup.execute(
            'PRAGMA integrity_check'
        ).fetchone()[0]

        if result != 'ok':
            raise ValueError(
                'Previous database backup failed integrity verification.'
            )

    finally:
        verify_backup.close()

    print('Previous database backed up:', backup_path)

    return backup_path


def main():
    """Build, verify, back up, and install the database."""

    # Prevent accidental replacement of a different
    # database selected through an environment variable.
    if Path(DATABASE).resolve() != LIVE_DB.resolve():
        raise RuntimeError(
            'NUMART_DATABASE points to a different database. '
            'Resolve this before generating the demo database.'
        )

    # A leftover building database must be investigated,
    # rather than silently deleted or overwritten.
    if BUILD_DB.exists():
        raise FileExistsError(
            f'A building database already exists: {BUILD_DB}'
        )

    # Check that the new master schema is available.
    Database.initialize(BUILD_DB)

    conn = Database.connect(BUILD_DB)

    try:
        conn.execute('BEGIN IMMEDIATE')

        generate_users(conn)
        generate_students(conn)
        generate_inventory(conn)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    # Do not replace the current database if validation fails.
    verify_database(BUILD_DB)

    # Preserve the previous database before replacement.
    backup_existing_database()

    # All connections to the active Flask application
    # must be closed before this replacement.
    os.replace(BUILD_DB, LIVE_DB)

    print('\nNEW DEMONSTRATION DATABASE INSTALLED')
    print('Active database:', LIVE_DB)

    # Confirm the installed database matches the validated one.
    verify_database(LIVE_DB)

    print('\nAdministrator: Demo Administrator')
    print('Staff: Demo Staff')
    print('Use the configured shared access-type passwords.')


if __name__ == '__main__':
    main()
