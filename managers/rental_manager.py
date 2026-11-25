
"""Rentals and returns are saved together with book status changes."""

from datetime import date, datetime, timedelta

from managers.student_manager import StudentManager
from managers.receipt_manager import ReceiptManager


class RentalManager:

    # Physical conditions supported by Nu-Mart.
    RETURN_CONDITIONS = ('Good', 'Fair', 'Poor')

    @staticmethod
    def rent_book(conn, student_id, book_ids, due_date, user_id, today=None):
        today = today or date.today()

        if not book_ids:
            raise ValueError('Choose at least one textbook.')

        book_ids = [
            x.strip()
            for x in book_ids
            if x.strip()
        ]

        if not book_ids:
            raise ValueError('Choose at least one textbook.')

        if len(set(book_ids)) != len(book_ids):
            raise ValueError(
                'The same book cannot be selected twice.'
            )

        try:
            due = date.fromisoformat(due_date)
        except (ValueError, TypeError):
            raise ValueError(
                'Enter a valid due date.'
            ) from None

        if due <= today:
            raise ValueError(
                'Due date must be after the rental date.'
            )

        conn.execute('BEGIN IMMEDIATE')

        try:
            # Confirm that the student is enrolled.
            student = StudentManager.verify_student(
                conn,
                student_id
            )

            required_edition = ReceiptManager.get_edition(
                student['grade']
            )

            # Validate every book before saving the rental.
            for book_id in book_ids:

                book = conn.execute(
                    '''
                    SELECT *
                    FROM books
                    WHERE book_id = ?
                    ''',
                    (book_id,)
                ).fetchone()

                if not book:
                    raise ValueError(
                        f'Book {book_id} does not exist.'
                    )

                if book['availability'] != 'Available':
                    raise ValueError(
                        f'Book {book_id} is already rented '
                        'or unavailable.'
                    )

                # Poor-condition books cannot be issued.
                if book['condition'] == 'Poor':
                    raise ValueError(
                        f'Book {book_id} is in Poor condition '
                        'and cannot be rented.'
                    )

                if book['edition'] != required_edition:
                    raise ValueError(
                        f'Book {book_id} is Edition '
                        f'{book["edition"]}; '
                        f'grade {student["grade"]} requires '
                        f'Edition {required_edition}.'
                    )

            rental_ids = []

            for book_id in book_ids:

                # Recheck availability and condition before
                # changing the physical book's rental status.
                updated = conn.execute(
                    '''
                    UPDATE books

                    SET availability = 'Rented'

                    WHERE book_id = ?
                      AND availability = 'Available'
                      AND condition IN ('Good', 'Fair')
                    ''',
                    (book_id,)
                )

                if updated.rowcount != 1:
                    raise ValueError(
                        f'Book {book_id} is no longer '
                        'available for rental.'
                    )

                rental_id = conn.execute(
                    '''
                    INSERT INTO rentals (
                        student_id,
                        book_id,
                        rental_date,
                        due_date,
                        status
                    )

                    VALUES (?, ?, ?, ?, 'Active')
                    ''',
                    (
                        student_id,
                        book_id,
                        today.isoformat(),
                        due.isoformat()
                    )
                ).lastrowid

                rental_ids.append(rental_id)

            issued_at = datetime.now().isoformat(
                timespec='seconds'
            )

            # Record who originally processed the rental.
            receipt_id = ReceiptManager.create_receipt(
                conn,
                student_id,
                rental_ids,
                issued_at,
                user_id
            )

            conn.execute(
                '''
                INSERT INTO audit_logs (
                    user_id,
                    action,
                    details,
                    created_at
                )

                VALUES (?, ?, ?, ?)
                ''',
                (
                    user_id,
                    'RENT',
                    f'Student {student_id}; '
                    f'books {", ".join(book_ids)}',
                    issued_at
                )
            )

            conn.commit()

            return receipt_id

        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def return_book(
        conn,
        rental_id,
        user_id,
        today=None,
        return_condition=None
    ):
        """
        Return a textbook and record its condition
        and the staff member who collected it.

        Conditions:
            Good
            Fair
            Poor
        """

        today = today or date.today()

        # Every new return must explicitly provide a condition.
        if return_condition not in RentalManager.RETURN_CONDITIONS:
            raise ValueError(
                'Choose a valid return condition: '
                'Good, Fair, or Poor.'
            )

        conn.execute('BEGIN IMMEDIATE')

        try:
            rental = conn.execute(
                '''
                SELECT *
                FROM rentals
                WHERE rental_id = ?
                ''',
                (rental_id,)
            ).fetchone()

            if not rental:
                raise ValueError(
                    'Rental record was not found.'
                )

            if rental['status'] != 'Active':
                raise ValueError(
                    'This textbook has already been returned.'
                )

            # Identify the collecting staff member.
            collector = conn.execute(
                '''
                SELECT user_id, username
                FROM users
                WHERE user_id = ?
                ''',
                (user_id,)
            ).fetchone()

            if not collector:
                raise ValueError(
                    'The collecting staff account was not found.'
                )

            # Save the completed rental's condition,
            # collector and actual return date.
            updated = conn.execute(
                '''
                UPDATE rentals

                SET
                    status = 'Returned',
                    return_date = ?,
                    return_condition = ?,
                    returned_to_user_id = ?

                WHERE rental_id = ?
                  AND status = 'Active'
                ''',
                (
                    today.isoformat(),
                    return_condition,
                    user_id,
                    rental_id
                )
            )

            if updated.rowcount != 1:
                raise ValueError(
                    'The rental could not be marked as returned.'
                )

            # The book is no longer rented. Its physical
            # condition is updated to what staff observed.
            #
            # A Poor-condition book will not be rentable
            # because rent_book() checks its condition.
            changed = conn.execute(
                '''
                UPDATE books

                SET
                    availability = 'Available',
                    condition = ?

                WHERE book_id = ?
                  AND availability = 'Rented'
                ''',
                (
                    return_condition,
                    rental['book_id']
                )
            )

            if changed.rowcount != 1:
                raise ValueError(
                    'Book availability could not be updated.'
                )

            created_at = datetime.now().isoformat(
                timespec='seconds'
            )

            # Preserve an audit trail of who accepted the return.
            conn.execute(
                '''
                INSERT INTO audit_logs (
                    user_id,
                    action,
                    details,
                    created_at
                )

                VALUES (?, ?, ?, ?)
                ''',
                (
                    user_id,
                    'RETURN',
                    f'Rental {rental_id}; '
                    f'book {rental["book_id"]}; '
                    f'condition {return_condition}; '
                    f'collected by {collector["username"]}',
                    created_at
                )
            )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

    @staticmethod
    def list_rentals(conn, status='Active'):

        if status not in ('Active', 'Returned', 'All'):
            status = 'Active'

        where = (
            ''
            if status == 'All'
            else 'WHERE r.status = ?'
        )

        args = (
            ()
            if status == 'All'
            else (status,)
        )

        records = conn.execute(
            f'''
            SELECT
                r.*,
                s.first_name,
                s.last_name,
                b.title,
                u.username AS collected_by,
                u.role AS collector_role

            FROM rentals r

            JOIN students s
                ON r.student_id = s.student_id

            JOIN books b
                ON r.book_id = b.book_id

            LEFT JOIN users u
                ON r.returned_to_user_id = u.user_id

            {where}

            ORDER BY r.rental_id DESC

            LIMIT 300
            ''',
            args
        ).fetchall()

        return [
            dict(record)
            for record in records
        ]
