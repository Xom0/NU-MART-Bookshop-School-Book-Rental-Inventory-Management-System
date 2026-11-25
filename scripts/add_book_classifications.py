
"""Add textbook classifications without deleting existing book records."""

import re
import sqlite3
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent

DATABASE_PATH = PROJECT_DIR / 'instance' / 'bookshop.db'


def normalize(value):
    """Standardize text for comparing textbook details."""
    return ' '.join(str(value).strip().split()).casefold()


def subject_code(subject):
    """Generate a three-letter code from the subject."""
    letters = re.sub(r'[^A-Z]', '', subject.upper())

    if not letters:
        return 'GEN'

    return letters[:3].ljust(3, 'X')


def find_classification(conn, title, subject, edition):
    """Find an existing classification with matching book details."""

    rows = conn.execute(
        '''
        SELECT
            classification_id,
            title,
            subject,
            edition
        FROM book_classifications
        '''
    ).fetchall()

    for row in rows:
        if (
            normalize(row['title']) == normalize(title)
            and normalize(row['subject']) == normalize(subject)
            and row['edition'] == edition
        ):
            return row['classification_id']

    return None


def next_classification_id(conn, subject):
    """Generate a unique classification ID for a subject."""

    prefix = f'BK-{subject_code(subject)}-'

    rows = conn.execute(
        '''
        SELECT classification_id
        FROM book_classifications
        WHERE classification_id LIKE ?
        ''',
        (prefix + '%',)
    ).fetchall()

    used_numbers = set()

    for row in rows:
        classification_id = row['classification_id']

        if classification_id.startswith(prefix):
            suffix = classification_id[len(prefix):]

            if suffix.isdigit():
                used_numbers.add(int(suffix))

    number = 1

    while number in used_numbers:
        number += 1

    return f'{prefix}{number:03d}'


def migrate_book_classifications():
    """Create classifications and link existing physical copies."""

    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(
            f'Database not found: {DATABASE_PATH}'
        )

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('BEGIN IMMEDIATE')

        # Create the main textbook classification table.
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

        # Check the columns in the existing books table.
        existing_columns = {
            row['name']
            for row in conn.execute(
                'PRAGMA table_info(books)'
            )
        }

        # Link every physical copy to a textbook classification.
        if 'classification_id' not in existing_columns:
            conn.execute(
                '''
                ALTER TABLE books
                ADD COLUMN classification_id TEXT
                REFERENCES book_classifications(classification_id)
                '''
            )

            print('Added classification_id to books.')

        else:
            print('classification_id already exists.')

        # Improve performance when finding physical copies.
        conn.execute(
            '''
            CREATE INDEX IF NOT EXISTS idx_books_classification
            ON books(classification_id)
            '''
        )

        # Retrieve existing physical books without altering
        # their IDs, condition, status or rental records.
        books = conn.execute(
            '''
            SELECT
                book_id,
                title,
                subject,
                edition,
                classification_id
            FROM books
            ORDER BY book_id
            '''
        ).fetchall()

        created_count = 0
        linked_count = 0

        for book in books:

            # Preserve an existing valid classification link.
            if book['classification_id']:
                existing = conn.execute(
                    '''
                    SELECT classification_id
                    FROM book_classifications
                    WHERE classification_id = ?
                    ''',
                    (book['classification_id'],)
                ).fetchone()

                if existing:
                    continue

                raise ValueError(
                    'Book '
                    f'{book["book_id"]} references a missing '
                    'classification.'
                )

            classification_id = find_classification(
                conn,
                book['title'],
                book['subject'],
                book['edition']
            )

            # Create one classification per distinct
            # title, subject and edition combination.
            if classification_id is None:

                classification_id = next_classification_id(
                    conn,
                    book['subject']
                )

                conn.execute(
                    '''
                    INSERT INTO book_classifications (
                        classification_id,
                        title,
                        subject,
                        edition
                    )
                    VALUES (?, ?, ?, ?)
                    ''',
                    (
                        classification_id,
                        book['title'],
                        book['subject'],
                        book['edition']
                    )
                )

                created_count += 1

            # Connect the physical copy to its classification.
            conn.execute(
                '''
                UPDATE books
                SET classification_id = ?
                WHERE book_id = ?
                ''',
                (
                    classification_id,
                    book['book_id']
                )
            )

            linked_count += 1

        conn.commit()

        print('Migration completed successfully.')
        print('New classifications:', created_count)
        print('Existing copies linked:', linked_count)

        total_books = conn.execute(
            'SELECT COUNT(*) FROM books'
        ).fetchone()[0]

        total_classifications = conn.execute(
            'SELECT COUNT(*) FROM book_classifications'
        ).fetchone()[0]

        unlinked = conn.execute(
            '''
            SELECT COUNT(*)
            FROM books
            WHERE classification_id IS NULL
            '''
        ).fetchone()[0]

        print('Total physical copies:', total_books)
        print('Total classifications:', total_classifications)
        print('Unlinked copies:', unlinked)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == '__main__':
    migrate_book_classifications()
