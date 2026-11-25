
import pytest

from datetime import date, timedelta

from helpers.database import Database
from managers.rental_manager import RentalManager
from managers.receipt_manager import ReceiptManager


def test_rent_receipt_return_and_prevent_double_rental(client):
    conn = Database.connect(
        client.application.config['DATABASE']
    )

    try:
        user = conn.execute(
            "SELECT user_id FROM users WHERE username='admin'"
        ).fetchone()[0]

        due = (
            date.today() + timedelta(days=14)
        ).isoformat()

        # Rent two textbooks to the same student.
        receipt_id = RentalManager.rent_book(
            conn,
            'ST002',
            ['BK002', 'BK003'],
            due,
            user
        )

        # Verify the generated receipt.
        header, items = ReceiptManager.get_receipt(
            conn,
            receipt_id
        )

        assert header['student_id'] == 'ST002'
        assert len(items) == 2

        # The physical copy must be marked as rented.
        assert conn.execute(
            """
            SELECT availability
            FROM books
            WHERE book_id = 'BK002'
            """
        ).fetchone()[0] == 'Rented'

        # Prevent renting an already rented copy.
        with pytest.raises(
            ValueError,
            match='already rented'
        ):
            RentalManager.rent_book(
                conn,
                'ST002',
                ['BK002'],
                due,
                user
            )

        # Identify the first rental on the receipt.
        rental_id = items[0]['rental_id']

        # Record the return condition and collecting staff.
        RentalManager.return_book(
            conn,
            rental_id,
            user,
            return_condition='Good'
        )

        # Verify the rental was returned.
        rental = conn.execute(
            """
            SELECT
                status,
                return_condition,
                returned_to_user_id
            FROM rentals
            WHERE rental_id = ?
            """,
            (rental_id,)
        ).fetchone()

        assert rental['status'] == 'Returned'
        assert rental['return_condition'] == 'Good'
        assert rental['returned_to_user_id'] == user

        # Verify the individual physical book is available.
        book = conn.execute(
            """
            SELECT
                condition,
                availability
            FROM books
            WHERE book_id = 'BK002'
            """
        ).fetchone()

        assert book['condition'] == 'Good'
        assert book['availability'] == 'Available'

        # Prevent returning the same rental twice.
        with pytest.raises(
            ValueError,
            match='already been returned'
        ):
            RentalManager.return_book(
                conn,
                rental_id,
                user,
                return_condition='Good'
            )

    finally:
        conn.close()


def test_invalid_edition_rolls_back_everything(client):
    conn = Database.connect(
        client.application.config['DATABASE']
    )

    try:
        user = conn.execute(
            "SELECT user_id FROM users WHERE username='admin'"
        ).fetchone()[0]

        # Grade 10 requires Edition 2.
        # BK002 is Edition 2 but BK001 is Edition 1.
        # The entire transaction must be rejected.
        with pytest.raises(
            ValueError,
            match='requires Edition 2'
        ):
            RentalManager.rent_book(
                conn,
                'ST002',
                ['BK002', 'BK001'],
                (
                    date.today() + timedelta(days=7)
                ).isoformat(),
                user
            )

        # The first book must still be available.
        assert conn.execute(
            """
            SELECT availability
            FROM books
            WHERE book_id = 'BK002'
            """
        ).fetchone()[0] == 'Available'

        # No partial rental should have been saved.
        assert conn.execute(
            'SELECT count(*) FROM rentals'
        ).fetchone()[0] == 0

    finally:
        conn.close()
