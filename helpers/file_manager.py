
"""Import and export books in CSV format (not a separate primary database)."""

import csv
from io import StringIO

from managers.book_manager import BookManager


class FileManager:

    REQUIRED_COLUMNS = (
        'book_id',
        'title',
        'subject',
        'edition',
        'condition'
    )

    OPTIONAL_COLUMNS = (
        'availability',
        'classification_id'
    )

    EXPORT_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

    @staticmethod
    def export_csv(conn):
        """
        Export physical books with their classifications.

        Preserve the original CSV fields and include
        classification_id as an additional column.
        """
        out = StringIO()
        writer = csv.writer(out)

        writer.writerow(FileManager.EXPORT_COLUMNS)

        rows = conn.execute(
            '''
            SELECT
                book_id,
                title,
                subject,
                edition,
                condition,
                availability,
                classification_id
            FROM books
            ORDER BY book_id
            '''
        )

        for row in rows:
            writer.writerow(tuple(row))

        return out.getvalue()

    @staticmethod
    def import_csv(conn, file):
        """
        Import new physical textbooks safely.

        - Supports the original five required columns.
        - Accepts optional availability and classification_id.
        - Links new books through BookManager.add_book().
        - Rejects duplicate Book IDs.
        - Rejects invalid or inconsistent data.
        - Prevents partially imported CSV batches.
        - Preserves existing records and rental history.
        """
        reader = csv.DictReader(
            (
                line.decode('utf-8-sig')
                for line in file.stream
            )
        )

        fieldnames = reader.fieldnames or []

        if len(fieldnames) != len(set(fieldnames)):
            raise ValueError(
                'CSV contains duplicate column headings.'
            )

        missing = [
            column
            for column in FileManager.REQUIRED_COLUMNS
            if column not in fieldnames
        ]

        if missing:
            raise ValueError(
                'CSV is missing required columns: '
                + ', '.join(missing)
            )

        # Read and validate all records before writing
        # anything to the database.
        rows = list(reader)

        if not rows:
            raise ValueError(
                'The CSV file contains no textbook records.'
            )

        prepared_rows = []
        seen_ids = set()

        for line_number, row in enumerate(rows, start=2):

            # A malformed row may contain unexpected
            # extra values under the None key.
            if None in row:
                raise ValueError(
                    f'CSV row {line_number} contains '
                    'more values than its headings.'
                )

            book_id = str(
                row.get('book_id') or ''
            ).strip()

            title = str(
                row.get('title') or ''
            ).strip()

            subject = str(
                row.get('subject') or ''
            ).strip()

            edition = row.get('edition')

            condition = str(
                row.get('condition') or ''
            ).strip()

            availability = str(
                row.get('availability') or 'Available'
            ).strip()

            supplied_classification = str(
                row.get('classification_id') or ''
            ).strip()

            if not book_id or not title or not subject:
                raise ValueError(
                    f'CSV row {line_number}: '
                    'Book ID, title and subject are required.'
                )

            if len(book_id) > 60:
                raise ValueError(
                    f'CSV row {line_number}: '
                    'Book ID exceeds 60 characters.'
                )

            if len(title) > 200 or len(subject) > 120:
                raise ValueError(
                    f'CSV row {line_number}: '
                    'Title or subject is too long.'
                )

            # Apply the same edition validation
            # used throughout the inventory system.
            try:
                edition = BookManager.validate_edition(
                    edition
                )
            except ValueError as exc:
                raise ValueError(
                    f'CSV row {line_number}: {exc}'
                ) from exc

            # New imports use Good, Fair and Poor.
            try:
                condition = BookManager.validate_condition(
                    condition
                )
            except ValueError as exc:
                raise ValueError(
                    f'CSV row {line_number}: {exc}'
                ) from exc

            # A CSV must not create a rented book without
            # an associated rental transaction.
            if availability != 'Available':
                raise ValueError(
                    f'CSV row {line_number}: '
                    'Only Available copies can be imported. '
                    'Historical rentals must remain in '
                    'the database.'
                )

            if book_id in seen_ids:
                raise ValueError(
                    f'CSV row {line_number}: '
                    f'Duplicate Book ID {book_id} '
                    'within the CSV file.'
                )

            seen_ids.add(book_id)

            prepared_rows.append(
                {
                    'line_number': line_number,
                    'book_id': book_id,
                    'title': title,
                    'subject': subject,
                    'edition': edition,
                    'condition': condition,
                    'classification_id': supplied_classification
                }
            )

        # Reject existing Book IDs before making changes.
        # This prevents imports from overwriting old books.
        for row in prepared_rows:

            existing = conn.execute(
                '''
                SELECT book_id
                FROM books
                WHERE book_id = ?
                ''',
                (row['book_id'],)
            ).fetchone()

            if existing:
                raise ValueError(
                    f'CSV row {row["line_number"]}: '
                    f'Book ID {row["book_id"]} '
                    'already exists in inventory.'
                )

        # Perform the import as one atomic database
        # operation using an SQLite savepoint.
        #
        # If a row fails, all changes made by this
        # particular CSV import are undone.
        previous_transaction = conn.in_transaction

        conn.execute(
            'SAVEPOINT csv_import_batch'
        )

        try:

            for row in prepared_rows:

                # The upgraded BookManager automatically
                # finds or creates a textbook classification.
                BookManager.add_book(
                    conn,
                    row['book_id'],
                    row['title'],
                    row['subject'],
                    row['edition'],
                    row['condition']
                )

                # If the file supplied a classification
                # ID, verify it matches the actual link.
                #
                # Do not silently associate the imported
                # book with an unrelated classification.
                supplied_id = row['classification_id']

                if supplied_id:

                    saved = conn.execute(
                        '''
                        SELECT classification_id
                        FROM books
                        WHERE book_id = ?
                        ''',
                        (row['book_id'],)
                    ).fetchone()

                    actual_id = saved[0]

                    if actual_id != supplied_id:
                        raise ValueError(
                            f'CSV row {row["line_number"]}: '
                            f'Classification {supplied_id} '
                            'does not match the classification '
                            f'generated for this book '
                            f'({actual_id}). '
                            'Check the source catalogue '
                            'before importing.'
                        )

            conn.execute(
                'RELEASE SAVEPOINT csv_import_batch'
            )

            # A standalone import must be persisted.
            # If the caller already had a transaction,
            # leave the final commit to that caller.
            if not previous_transaction:
                conn.commit()

        except Exception:

            conn.execute(
                'ROLLBACK TO SAVEPOINT csv_import_batch'
            )

            conn.execute(
                'RELEASE SAVEPOINT csv_import_batch'
            )

            raise

        return len(prepared_rows)
