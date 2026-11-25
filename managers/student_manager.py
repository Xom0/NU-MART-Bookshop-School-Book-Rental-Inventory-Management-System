
from helpers.database import Database


class StudentManager:

    @staticmethod
    def search_student(conn, query=''):
        """
        Search students using:
        - Student ID
        - First name
        - Last name
        - Full name
        - Part of a name

        Searches ignore capitalization.
        """

        # Remove extra spaces and normalize capitalization.
        q = ' '.join((query or '').split()).casefold()

        # Display all students when the search is empty.
        if not q:
            return Database.rows(conn.execute("""
                SELECT *
                FROM students
                ORDER BY last_name, first_name
                LIMIT 200
            """))

        # Allow partial matching.
        search_term = f'%{q}%'

        # Search both individual names and combined names.
        return Database.rows(conn.execute("""
            SELECT *
            FROM students
            WHERE LOWER(student_id) LIKE ?
               OR LOWER(first_name) LIKE ?
               OR LOWER(last_name) LIKE ?
               OR LOWER(first_name || ' ' || last_name) LIKE ?
               OR LOWER(last_name || ' ' || first_name) LIKE ?
            ORDER BY last_name, first_name
            LIMIT 200
        """, (search_term,) * 5))

    @staticmethod
    def verify_student(conn, student_id):
        student = conn.execute(
            'SELECT * FROM students WHERE student_id=?',
            (student_id,)
        ).fetchone()

        if not student:
            raise ValueError('Student ID was not found.')

        if student['enrolment_status'] != 'Active':
            raise ValueError('Student is not currently enrolled.')

        return dict(student)

    @staticmethod
    def add_student(
        conn,
        student_id,
        first_name,
        last_name,
        grade,
        class_name,
        status
    ):
        try:
            grade = int(grade)
        except (ValueError, TypeError):
            raise ValueError(
                'Grade must be a whole number.'
            ) from None

        if not all((
            student_id.strip(),
            first_name.strip(),
            last_name.strip(),
            class_name.strip()
        )):
            raise ValueError(
                'Complete every required student field.'
            )

        if grade not in range(9, 14) or status not in (
            'Active', 'Inactive'
        ):
            raise ValueError(
                'Grade must be 9–13 and status must be Active or Inactive.'
            )

        conn.execute(
            'INSERT INTO students VALUES(?,?,?,?,?,?)',
            (
                student_id.strip(),
                first_name.strip(),
                last_name.strip(),
                grade,
                class_name.strip(),
                status
            )
        )

    # ---------------------------------------------------------
    # REMOVE STUDENT
    # ---------------------------------------------------------

    @staticmethod
    def remove_student(conn, student_id):
        """
        Remove a student only if no rental or receipt
        history references the student.

        Administrator authorization is enforced by
        the calling Flask route.

        The calling route must use a transaction.
        """

        student_id = str(student_id or '').strip()

        if not student_id:
            raise ValueError(
                'A Student ID is required.'
            )

        # Confirm that the student exists.
        student = conn.execute(
            '''
            SELECT student_id, first_name, last_name
            FROM students
            WHERE student_id = ?
            ''',
            (student_id,)
        ).fetchone()

        if student is None:
            raise ValueError(
                'Student ID was not found.'
            )

        # Protect active and historical rental records.
        rental_exists = conn.execute(
            '''
            SELECT 1
            FROM rentals
            WHERE student_id = ?
            LIMIT 1
            ''',
            (student_id,)
        ).fetchone()

        if rental_exists:
            raise ValueError(
                'This student cannot be removed because '
                'rental history exists. Historical rental '
                'records must be preserved.'
            )

        # Protect receipts even if no rental is currently found.
        receipt_exists = conn.execute(
            '''
            SELECT 1
            FROM receipts
            WHERE student_id = ?
            LIMIT 1
            ''',
            (student_id,)
        ).fetchone()

        if receipt_exists:
            raise ValueError(
                'This student cannot be removed because '
                'receipt history exists. Historical receipt '
                'records must be preserved.'
            )

        # Only an unreferenced student can be deleted.
        result = conn.execute(
            '''
            DELETE FROM students
            WHERE student_id = ?
            ''',
            (student_id,)
        )

        if result.rowcount != 1:
            raise ValueError(
                'Student removal was unsuccessful.'
            )

        return (
            f'{student["first_name"]} '
            f'{student["last_name"]} '
            f'({student_id})'
        )
