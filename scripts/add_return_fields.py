
"""Add return-condition and collecting-staff fields to existing rentals."""

import sqlite3
from pathlib import Path


# Find the database relative to the project folder.
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_DIR / 'instance' / 'bookshop.db'


def add_return_fields():
    if not DATABASE_PATH.is_file():
        raise FileNotFoundError(
            f'Database not found: {DATABASE_PATH}'
        )

    conn = sqlite3.connect(DATABASE_PATH)

    try:
        # Read the existing rental columns.
        existing_columns = {
            row[1]
            for row in conn.execute(
                'PRAGMA table_info(rentals)'
            )
        }

        # Add the return condition without removing old records.
        if 'return_condition' not in existing_columns:
            conn.execute(
                '''
                ALTER TABLE rentals
                ADD COLUMN return_condition TEXT
                '''
            )

            print('Added: return_condition')
        else:
            print('Already exists: return_condition')

        # Store the ID of the person accepting the return.
        if 'returned_to_user_id' not in existing_columns:
            conn.execute(
                '''
                ALTER TABLE rentals
                ADD COLUMN returned_to_user_id INTEGER
                REFERENCES users(user_id)
                '''
            )

            print('Added: returned_to_user_id')
        else:
            print('Already exists: returned_to_user_id')

        conn.commit()

        print('Return fields migration completed successfully.')

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == '__main__':
    add_return_fields()
