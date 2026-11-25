
class ReceiptManager:

    @staticmethod
    def get_edition(grade):
        grade = int(grade)

        if grade == 9:
            return 1

        if grade in (10, 11):
            return 2

        if grade in (12, 13):
            return 3

        raise ValueError('Grade must be from 9 to 13.')

    @staticmethod
    def create_receipt(conn, student_id, rental_ids, issued_at, user_id):
        if not rental_ids:
            raise ValueError('A receipt requires at least one rental.')

        # Store the original processor's user ID.
        receipt_id = conn.execute(
            '''
            INSERT INTO receipts (
                student_id,
                issued_at,
                user_id
            )
            VALUES (?, ?, ?)
            ''',
            (
                student_id,
                issued_at,
                user_id
            )
        ).lastrowid

        # Link all rented copies to the same receipt.
        for rental_id in rental_ids:
            conn.execute(
                '''
                INSERT INTO receipt_items (
                    receipt_id,
                    rental_id
                )
                VALUES (?, ?)
                ''',
                (
                    receipt_id,
                    rental_id
                )
            )

        return receipt_id

    @staticmethod
    def get_receipt(conn, receipt_id):
        # Retrieve student and original processor information.
        header = conn.execute(
            '''
            SELECT
                r.*,
                s.first_name,
                s.last_name,
                s.grade,
                s.class_name,
                u.username AS processed_by,
                u.role AS processed_by_role

            FROM receipts r

            JOIN students s
                ON s.student_id = r.student_id

            LEFT JOIN users u
                ON u.user_id = r.user_id

            WHERE r.receipt_id = ?
            ''',
            (receipt_id,)
        ).fetchone()

        if not header:
            raise ValueError('Receipt was not found.')

        # Retrieve all textbooks included on the receipt.
        items = conn.execute(
            '''
            SELECT
                b.book_id,
                b.title,
                b.edition,
                b.subject,
                b.condition,
                t.due_date,
                t.rental_id

            FROM receipt_items ri

            JOIN rentals t
                ON ri.rental_id = t.rental_id

            JOIN books b
                ON t.book_id = b.book_id

            WHERE ri.receipt_id = ?

            ORDER BY ri.receipt_item_id
            ''',
            (receipt_id,)
        ).fetchall()

        return (
            dict(header),
            [dict(item) for item in items]
        )

    @staticmethod
    def list_receipts(conn, query=''):
        # Search existing receipts without changing any records.
        query = str(query or '').strip()

        # A blank search returns the most recent receipts.
        if not query:
            rows = conn.execute(
                '''
                SELECT
                    r.receipt_id,
                    r.student_id,
                    r.issued_at,
                    s.first_name,
                    s.last_name,
                    s.grade,
                    s.class_name,
                    u.username AS processed_by,
                    u.role AS processed_by_role,
                    COUNT(ri.receipt_item_id) AS book_count

                FROM receipts r

                JOIN students s
                    ON s.student_id = r.student_id

                LEFT JOIN users u
                    ON u.user_id = r.user_id

                LEFT JOIN receipt_items ri
                    ON ri.receipt_id = r.receipt_id

                GROUP BY r.receipt_id

                ORDER BY r.receipt_id DESC

                LIMIT 300
                '''
            ).fetchall()

        else:
            search_term = f'%{query}%'

            rows = conn.execute(
                '''
                SELECT
                    r.receipt_id,
                    r.student_id,
                    r.issued_at,
                    s.first_name,
                    s.last_name,
                    s.grade,
                    s.class_name,
                    u.username AS processed_by,
                    u.role AS processed_by_role,
                    COUNT(ri.receipt_item_id) AS book_count

                FROM receipts r

                JOIN students s
                    ON s.student_id = r.student_id

                LEFT JOIN users u
                    ON u.user_id = r.user_id

                LEFT JOIN receipt_items ri
                    ON ri.receipt_id = r.receipt_id

                WHERE
                    CAST(r.receipt_id AS TEXT) = ?
                    OR r.student_id LIKE ?
                    OR LOWER(
                        s.first_name || ' ' || s.last_name
                    ) LIKE LOWER(?)
                    OR LOWER(COALESCE(u.username, ''))
                        LIKE LOWER(?)

                GROUP BY r.receipt_id

                ORDER BY r.receipt_id DESC

                LIMIT 300
                ''',
                (
                    query,
                    search_term,
                    search_term,
                    search_term
                )
            ).fetchall()

        return [dict(row) for row in rows]
