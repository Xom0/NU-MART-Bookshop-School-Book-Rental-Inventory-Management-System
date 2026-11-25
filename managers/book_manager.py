"""Manage textbook classifications and individual physical copies."""

import re
import sqlite3

from helpers.database import Database


class BookManager:

    # Only these physical conditions are used for new records.
    BOOK_CONDITIONS = ('Good', 'Fair', 'Poor')

    # A maximum per operation prevents accidental bulk creation.
    MAX_COPIES_PER_BATCH = 500

    @staticmethod
    def normalize(value):
        """Normalize text when comparing textbook information."""
        return ' '.join(str(value or '').strip().split()).casefold()

    @staticmethod
    def subject_code(subject):
        """Create a three-letter subject code for classification IDs."""
        letters = re.sub(
            r'[^A-Z]',
            '',
            str(subject).upper()
        )

        if not letters:
            return 'GEN'

        return letters[:3].ljust(3, 'X')

    @staticmethod
    def validate_edition(edition):
        """Ensure the edition follows the existing grade mapping."""
        try:
            edition = int(edition)

        except (ValueError, TypeError):
            raise ValueError(
                'Edition must be 1, 2 or 3.'
            ) from None

        if edition not in (1, 2, 3):
            raise ValueError(
                'Edition must be 1, 2 or 3.'
            )

        return edition

    @staticmethod
    def validate_condition(condition):
        """Check the physical condition of a book."""
        condition = str(condition or '').strip()

        if condition not in BookManager.BOOK_CONDITIONS:
            raise ValueError(
                'Condition must be Good, Fair, or Poor.'
            )

        return condition

    # ---------------------------------------------------------
    # EXISTING BOOK SEARCH
    # ---------------------------------------------------------

    @staticmethod
    def search_book(conn, query='', mode='title'):
        """
        Search individual physical books.

        This method preserves the original interface used
        by the existing website and automated tests.
        """
        query = str(query or '').strip()

        if mode == 'id':

            if query:
                return Database.rows(
                    conn.execute(
                        '''
                        SELECT *
                        FROM books
                        WHERE book_id = ?
                        ORDER BY book_id
                        ''',
                        (query,)
                    )
                )

            return Database.rows(
                conn.execute(
                    '''
                    SELECT *
                    FROM books
                    ORDER BY book_id
                    LIMIT 250
                    '''
                )
            )

        if mode != 'title':
            raise ValueError(
                'Search must use Book ID or title.'
            )

        return Database.rows(
            conn.execute(
                '''
                SELECT *
                FROM books
                WHERE title LIKE ?
                ORDER BY title, book_id
                LIMIT 250
                ''',
                (f'%{query}%',)
            )
        )

    # ---------------------------------------------------------
    # AVAILABILITY
    # ---------------------------------------------------------

    @staticmethod
    def check_availability(conn, book_id):
        """
        A physical copy is rentable only when:
        1. Its availability is Available.
        2. Its condition is Good or Fair.
        """
        book = conn.execute(
            '''
            SELECT *
            FROM books
            WHERE book_id = ?
            ''',
            (book_id,)
        ).fetchone()

        if book is None:
            raise ValueError(
                'Book ID was not found.'
            )

        return (
            book['availability'] == 'Available'
            and book['condition'] in ('Good', 'Fair')
        )


    # ---------------------------------------------------------
    # REMOVE PHYSICAL TEXTBOOK
    # ---------------------------------------------------------

    @staticmethod
    def remove_book(conn, book_id):
        """
        Remove one physical textbook only when it has
        no active or historical rental records.

        The textbook classification is preserved.
        Administrator authorization is enforced by
        the calling Flask route.

        The calling route must use a transaction.
        """

        book_id = str(book_id or '').strip()

        if not book_id:
            raise ValueError(
                'A physical Book ID is required.'
            )

        # Confirm that the physical textbook exists.
        book = conn.execute(
            '''
            SELECT book_id, title, availability
            FROM books
            WHERE book_id = ?
            ''',
            (book_id,)
        ).fetchone()

        if book is None:
            raise ValueError(
                'Book ID was not found.'
            )

        # An actively rented textbook must not be deleted.
        if book['availability'] == 'Rented':
            raise ValueError(
                'This textbook is currently rented '
                'and cannot be removed.'
            )

        # Keep all rental history, including returned rentals.
        rental_exists = conn.execute(
            '''
            SELECT 1
            FROM rentals
            WHERE book_id = ?
            LIMIT 1
            ''',
            (book_id,)
        ).fetchone()

        if rental_exists:
            raise ValueError(
                'This textbook cannot be removed because '
                'rental history exists. Historical records '
                'must be preserved.'
            )

        # Delete only this physical copy.
        # Do not delete its textbook classification.
        result = conn.execute(
            '''
            DELETE FROM books
            WHERE book_id = ?
            ''',
            (book_id,)
        )

        if result.rowcount != 1:
            raise ValueError(
                'Textbook removal was unsuccessful.'
            )

        return book_id


    # ---------------------------------------------------------
    # CLASSIFICATION LOOKUP
    # ---------------------------------------------------------

    @staticmethod
    def find_classification(conn, title, subject, edition):
        """
        Find the classification for a matching textbook
        title, subject and edition.
        """
        edition = BookManager.validate_edition(edition)

        rows = conn.execute(
            '''
            SELECT
                classification_id,
                title,
                subject,
                edition
            FROM book_classifications
            WHERE edition = ?
            ''',
            (edition,)
        ).fetchall()

        for row in rows:

            if (
                BookManager.normalize(row['title'])
                == BookManager.normalize(title)
                and
                BookManager.normalize(row['subject'])
                == BookManager.normalize(subject)
            ):
                return dict(row)

        return None

    @staticmethod
    def get_classification(conn, classification_id):
        """Retrieve one textbook classification by ID."""
        row = conn.execute(
            '''
            SELECT *
            FROM book_classifications
            WHERE classification_id = ?
            ''',
            (classification_id,)
        ).fetchone()

        return dict(row) if row else None

    @staticmethod
    def search_classifications(conn, query=''):
        """
        Search the textbook catalogue.

        Counts refer to physical copies, not classifications.
        """
        query = str(query or '').strip()

        search_term = f'%{query}%'

        rows = conn.execute(
            '''
            SELECT
                c.classification_id,
                c.title,
                c.subject,
                c.edition,

                COUNT(b.book_id) AS total_copies,

                SUM(
                    CASE
                        WHEN b.availability = 'Available'
                         AND b.condition IN ('Good', 'Fair')
                        THEN 1
                        ELSE 0
                    END
                ) AS rentable_copies,

                SUM(
                    CASE
                        WHEN b.availability = 'Rented'
                        THEN 1
                        ELSE 0
                    END
                ) AS rented_copies,

                SUM(
                    CASE
                        WHEN b.condition = 'Poor'
                        THEN 1
                        ELSE 0
                    END
                ) AS poor_copies

            FROM book_classifications c

            LEFT JOIN books b
                ON b.classification_id = c.classification_id

            WHERE
                c.classification_id LIKE ?
                OR c.title LIKE ?
                OR c.subject LIKE ?

            GROUP BY
                c.classification_id,
                c.title,
                c.subject,
                c.edition

            ORDER BY
                c.subject,
                c.title,
                c.edition
            ''',
            (
                search_term,
                search_term,
                search_term
            )
        ).fetchall()

        return [dict(row) for row in rows]

    # ---------------------------------------------------------
    # INDIVIDUAL COPY LOOKUP
    # ---------------------------------------------------------

    @staticmethod
    def get_copies(
        conn,
        classification_id,
        query='',
        status='All'
    ):
        """
        Find physical copies of one textbook classification.

        status:
            All
            Available
            Rented
            Not Rentable
        """
        classification = BookManager.get_classification(
            conn,
            classification_id
        )

        if not classification:
            raise ValueError(
                'Textbook classification was not found.'
            )

        if status not in (
            'All',
            'Available',
            'Rented',
            'Not Rentable'
        ):
            raise ValueError(
                'Choose a valid copy status.'
            )

        query = str(query or '').strip()

        sql = '''
            SELECT
                b.*,

                CASE
                    WHEN b.condition = 'Poor'
                    THEN 'Not Rentable'

                    WHEN b.availability = 'Rented'
                    THEN 'Rented'

                    WHEN b.availability = 'Available'
                     AND b.condition IN ('Good', 'Fair')
                    THEN 'Available'

                    ELSE 'Not Rentable'
                END AS rental_eligibility

            FROM books b

            WHERE b.classification_id = ?
              AND b.book_id LIKE ?
        '''

        parameters = [
            classification_id,
            f'%{query}%'
        ]

        if status == 'Available':
            sql += '''
                AND b.availability = 'Available'
                AND b.condition IN ('Good', 'Fair')
            '''

        elif status == 'Rented':
            sql += '''
                AND b.availability = 'Rented'
            '''

        elif status == 'Not Rentable':
            sql += '''
                AND (
                    b.condition NOT IN ('Good', 'Fair')
                    OR b.availability NOT IN ('Available', 'Rented')
                )
            '''

        sql += '''
            ORDER BY b.book_id
            LIMIT 2000
        '''

        return Database.rows(
            conn.execute(sql, parameters)
        )

    # ---------------------------------------------------------
    # CLASSIFICATION ID GENERATION
    # ---------------------------------------------------------

    @staticmethod
    def generate_classification_id(conn, subject):
        """
        Generate IDs such as:
            BK-MAT-001
            BK-ENG-001
            BK-SCI-001
        """
        prefix = f'BK-{BookManager.subject_code(subject)}-'

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
            current_id = row['classification_id']

            if current_id.startswith(prefix):

                suffix = current_id[len(prefix):]

                if suffix.isdigit():
                    used_numbers.add(int(suffix))

        number = 1

        while number in used_numbers:
            number += 1

        return f'{prefix}{number:03d}'

    # ---------------------------------------------------------
    # CREATE TEXTBOOK CLASSIFICATION
    # ---------------------------------------------------------

    @staticmethod
    def create_classification(
        conn,
        title,
        subject,
        edition
    ):
        """
        Create one textbook classification.

        Duplicate classifications are rejected.
        """
        title = ' '.join(str(title or '').strip().split())
        subject = ' '.join(str(subject or '').strip().split())

        if not title or not subject:
            raise ValueError(
                'Textbook title and subject are required.'
            )

        edition = BookManager.validate_edition(edition)

        existing = BookManager.find_classification(
            conn,
            title,
            subject,
            edition
        )

        if existing:
            raise ValueError(
                'This textbook classification already exists. '
                'Choose Add Copies to add more physical books.'
            )

        classification_id = BookManager.generate_classification_id(
            conn,
            subject
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
                title,
                subject,
                edition
            )
        )

        return classification_id

    # ---------------------------------------------------------
    # GENERATE PHYSICAL COPY IDS
    # ---------------------------------------------------------

    @staticmethod
    def generate_copy_ids(conn, classification_id, quantity):
        """
        Generate unique IDs for copies of a classification.

        Example:
            BK-MAT-001-001
            BK-MAT-001-002
            BK-MAT-001-003
        """
        try:
            quantity = int(quantity)

        except (ValueError, TypeError):
            raise ValueError(
                'Enter a valid number of copies.'
            ) from None

        if not 1 <= quantity <= BookManager.MAX_COPIES_PER_BATCH:
            raise ValueError(
                'Number of copies must be between 1 and 500.'
            )

        if not BookManager.get_classification(
            conn,
            classification_id
        ):
            raise ValueError(
                'Textbook classification was not found.'
            )

        prefix = classification_id + '-'

        rows = conn.execute(
            '''
            SELECT book_id
            FROM books
            WHERE book_id LIKE ?
            ''',
            (prefix + '%',)
        ).fetchall()

        used_numbers = set()

        for row in rows:
            current_id = row['book_id']

            if current_id.startswith(prefix):

                suffix = current_id[len(prefix):]

                if suffix.isdigit():
                    used_numbers.add(int(suffix))

        next_number = max(used_numbers, default=0) + 1

        copy_ids = []

        for _ in range(quantity):

            while next_number in used_numbers:
                next_number += 1

            copy_id = f'{prefix}{next_number:03d}'

            copy_ids.append(copy_id)
            used_numbers.add(next_number)

            next_number += 1

        return copy_ids

    # ---------------------------------------------------------
    # ADD COPIES TO AN EXISTING CLASSIFICATION
    # ---------------------------------------------------------

    @staticmethod
    def add_copies(
        conn,
        classification_id,
        quantity,
        condition='Good'
    ):
        """
        Add physical copies to an existing classification.

        All copies in a batch receive the chosen initial
        condition and have unique physical Book IDs.
        """
        condition = BookManager.validate_condition(condition)

        classification = BookManager.get_classification(
            conn,
            classification_id
        )

        if not classification:
            raise ValueError(
                'Textbook classification was not found.'
            )

        # Generate IDs before inserting the physical copies.
        copy_ids = BookManager.generate_copy_ids(
            conn,
            classification_id,
            quantity
        )

        # A savepoint prevents partial copy creation.
        conn.execute('SAVEPOINT add_book_copies')

        try:
            for book_id in copy_ids:

                conn.execute(
                    '''
                    INSERT INTO books (
                        book_id,
                        title,
                        subject,
                        edition,
                        condition,
                        availability,
                        classification_id
                    )

                    VALUES (?, ?, ?, ?, ?, 'Available', ?)
                    ''',
                    (
                        book_id,
                        classification['title'],
                        classification['subject'],
                        classification['edition'],
                        condition,
                        classification_id
                    )
                )

            conn.execute('RELEASE SAVEPOINT add_book_copies')

            return copy_ids

        except Exception:
            conn.execute('ROLLBACK TO SAVEPOINT add_book_copies')
            conn.execute('RELEASE SAVEPOINT add_book_copies')
            raise

    # ---------------------------------------------------------
    # CREATE A CLASSIFICATION WITH ITS FIRST COPIES
    # ---------------------------------------------------------

    @staticmethod
    def create_textbook_with_copies(
        conn,
        title,
        subject,
        edition,
        quantity,
        condition='Good'
    ):
        """
        Create a new classification and its physical copies.

        If any step fails, the entire operation is rolled back.
        """
        conn.execute('SAVEPOINT create_textbook_copies')

        try:
            classification_id = BookManager.create_classification(
                conn,
                title,
                subject,
                edition
            )

            copy_ids = BookManager.add_copies(
                conn,
                classification_id,
                quantity,
                condition
            )

            conn.execute(
                'RELEASE SAVEPOINT create_textbook_copies'
            )

            return {
                'classification_id': classification_id,
                'copy_ids': copy_ids
            }

        except Exception:
            conn.execute(
                'ROLLBACK TO SAVEPOINT create_textbook_copies'
            )
            conn.execute(
                'RELEASE SAVEPOINT create_textbook_copies'
            )
            raise

    # ---------------------------------------------------------
    # EXISTING ADD BOOK FUNCTION
    # ---------------------------------------------------------

    @staticmethod
    def add_book(
        conn,
        book_id,
        title,
        subject,
        edition,
        condition
    ):
        """
        Preserve the original Add Book method.

        A physical book added through the legacy interface
        is automatically linked to its classification.
        """
        book_id = str(book_id or '').strip()
        title = ' '.join(str(title or '').strip().split())
        subject = ' '.join(str(subject or '').strip().split())

        if not all((book_id, title, subject)):
            raise ValueError(
                'Book ID, title and subject are required.'
            )

        edition = BookManager.validate_edition(edition)
        condition = BookManager.validate_condition(condition)

        conn.execute('SAVEPOINT add_single_book')

        try:
            existing = BookManager.find_classification(
                conn,
                title,
                subject,
                edition
            )

            if existing:
                classification_id = existing['classification_id']

            else:
                classification_id = BookManager.create_classification(
                    conn,
                    title,
                    subject,
                    edition
                )

            conn.execute(
                '''
                INSERT INTO books (
                    book_id,
                    title,
                    subject,
                    edition,
                    condition,
                    classification_id
                )

                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    book_id,
                    title,
                    subject,
                    edition,
                    condition,
                    classification_id
                )
            )

            conn.execute('RELEASE SAVEPOINT add_single_book')

        except Exception:
            conn.execute('ROLLBACK TO SAVEPOINT add_single_book')
            conn.execute('RELEASE SAVEPOINT add_single_book')
            raise

    # ---------------------------------------------------------
    # REMOVE MULTIPLE PHYSICAL COPIES
    # ---------------------------------------------------------

    @staticmethod
    def remove_physical_copies(conn, book_ids):
        """
        Remove physical copies entered incorrectly.

        The classification remains intact. Reject the whole
        operation when any selected copy has rental history.
        The caller must enforce Administrator authorization.
        """
        if isinstance(book_ids, str):
            book_ids = book_ids.replace('\\r', '\\n').replace('\\n', ',').split(',')

        try:
            book_ids = [str(book_id).strip() for book_id in book_ids]
        except TypeError:
            raise ValueError('Enter physical Book IDs to remove.') from None

        if not book_ids or any(not book_id for book_id in book_ids):
            raise ValueError('Enter at least one valid physical Book ID.')

        if len(book_ids) > BookManager.MAX_COPIES_PER_BATCH:
            raise ValueError('Remove no more than 500 copies at once.')

        if len(set(book_ids)) != len(book_ids):
            raise ValueError('Duplicate Book IDs were selected.')

        # Validate every copy before deleting anything.
        for book_id in book_ids:
            book = conn.execute(
                'SELECT availability FROM books WHERE book_id = ?',
                (book_id,)
            ).fetchone()
            if book is None:
                raise ValueError(f'Book {book_id} was not found.')
            if book['availability'] == 'Rented':
                raise ValueError(f'Book {book_id} is currently rented.')
            if conn.execute(
                'SELECT 1 FROM rentals WHERE book_id = ? LIMIT 1',
                (book_id,)
            ).fetchone():
                raise ValueError(
                    f'Book {book_id} has rental history and cannot be removed.'
                )

        conn.execute('SAVEPOINT remove_physical_copies')
        try:
            for book_id in book_ids:
                result = conn.execute(
                    '''
                    DELETE FROM books
                    WHERE book_id = ?
                      AND availability != 'Rented'
                      AND NOT EXISTS (
                          SELECT 1 FROM rentals
                          WHERE rentals.book_id = books.book_id
                      )
                    ''',
                    (book_id,)
                )
                if result.rowcount != 1:
                    raise ValueError(f'Could not remove book {book_id}.')
            conn.execute('RELEASE SAVEPOINT remove_physical_copies')
        except Exception:
            conn.execute('ROLLBACK TO SAVEPOINT remove_physical_copies')
            conn.execute('RELEASE SAVEPOINT remove_physical_copies')
            raise

        return len(book_ids)

    # ---------------------------------------------------------
    # REMOVE TEXTBOOK CLASSIFICATION
    # ---------------------------------------------------------

    @staticmethod
    def remove_classification(conn, classification_id):
        """
        Remove an incorrectly added textbook classification
        and its physical copies, only if none has rental history.

        The entire operation is atomic. The caller must enforce
        Administrator authorization and request confirmation.
        """
        classification_id = str(classification_id or '').strip()
        classification = BookManager.get_classification(
            conn, classification_id
        )
        if classification is None:
            raise ValueError('Textbook classification was not found.')

        if conn.execute(
            '''
            SELECT 1 FROM rentals r
            JOIN books b ON b.book_id = r.book_id
            WHERE b.classification_id = ? LIMIT 1
            ''',
            (classification_id,)
        ).fetchone():
            raise ValueError(
                'This classification has rental history and cannot be removed.'
            )

        if conn.execute(
            '''
            SELECT 1 FROM books
            WHERE classification_id = ? AND availability = 'Rented'
            LIMIT 1
            ''',
            (classification_id,)
        ).fetchone():
            raise ValueError(
                'This classification contains a currently rented book.'
            )

        conn.execute('SAVEPOINT remove_classification')
        try:
            count = conn.execute(
                'SELECT COUNT(*) FROM books WHERE classification_id = ?',
                (classification_id,)
            ).fetchone()[0]
            deleted = conn.execute(
                '''
                DELETE FROM books
                WHERE classification_id = ?
                  AND availability != 'Rented'
                  AND NOT EXISTS (
                      SELECT 1 FROM rentals
                      WHERE rentals.book_id = books.book_id
                  )
                ''',
                (classification_id,)
            ).rowcount
            if deleted != count:
                raise ValueError(
                    'Some copies are protected. No records were removed.'
                )

            result = conn.execute(
                'DELETE FROM book_classifications WHERE classification_id = ?',
                (classification_id,)
            )
            if result.rowcount != 1:
                raise ValueError('Classification removal was unsuccessful.')
            conn.execute('RELEASE SAVEPOINT remove_classification')
        except Exception:
            conn.execute('ROLLBACK TO SAVEPOINT remove_classification')
            conn.execute('RELEASE SAVEPOINT remove_classification')
            raise

        return count
