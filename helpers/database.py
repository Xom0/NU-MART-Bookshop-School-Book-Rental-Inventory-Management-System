
"""Database connections and first-time table creation. One SQLite database, nine tables."""

import sqlite3
from pathlib import Path

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL
        CHECK(role IN ('Admin', 'Staff'))
);

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    grade INTEGER NOT NULL
        CHECK(grade BETWEEN 9 AND 13),
    class_name TEXT NOT NULL,
    enrolment_status TEXT NOT NULL
        CHECK(enrolment_status IN ('Active', 'Inactive'))
);

CREATE TABLE IF NOT EXISTS book_classifications (
    classification_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    edition INTEGER NOT NULL
        CHECK(edition IN (1, 2, 3))
);

CREATE TABLE IF NOT EXISTS books (
    book_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    subject TEXT NOT NULL,
    edition INTEGER NOT NULL
        CHECK(edition BETWEEN 1 AND 3),
    condition TEXT NOT NULL
        CHECK(condition IN ('Poor', 'Fair', 'Good')),
    availability TEXT NOT NULL DEFAULT 'Available'
        CHECK(availability IN ('Available', 'Rented')),
    classification_id TEXT
        REFERENCES book_classifications(classification_id)
);

CREATE INDEX IF NOT EXISTS idx_books_classification
    ON books(classification_id);

CREATE TABLE IF NOT EXISTS rentals (
    rental_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL
        REFERENCES students(student_id),
    book_id TEXT NOT NULL
        REFERENCES books(book_id),
    rental_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    return_date TEXT,
    status TEXT NOT NULL
        CHECK(status IN ('Active', 'Returned')),
    return_condition TEXT
        CHECK(
            return_condition IS NULL
            OR return_condition IN ('Good', 'Fair', 'Poor')
        ),
    returned_to_user_id INTEGER
        REFERENCES users(user_id),
    CHECK (
        (status = 'Active' AND return_date IS NULL)
        OR
        (status = 'Returned' AND return_date IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_rental_per_book
    ON rentals(book_id)
    WHERE status = 'Active';

CREATE INDEX IF NOT EXISTS idx_rentals_student
    ON rentals(student_id);

CREATE INDEX IF NOT EXISTS idx_rentals_due
    ON rentals(due_date, status);

CREATE TABLE IF NOT EXISTS receipts (
    receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL
        REFERENCES students(student_id),
    issued_at TEXT NOT NULL,
    user_id INTEGER
        REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS receipt_items (
    receipt_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id INTEGER NOT NULL
        REFERENCES receipts(receipt_id),
    rental_id INTEGER NOT NULL UNIQUE
        REFERENCES rentals(rental_id)
);

CREATE TABLE IF NOT EXISTS reminders (
    reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rental_id INTEGER NOT NULL
        REFERENCES rentals(rental_id),
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK(status IN ('Generated', 'Sent')),
    UNIQUE(rental_id, message)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER
        REFERENCES users(user_id),
    action TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Database:

    @staticmethod
    def connect(path):
        Path(path).parent.mkdir(
            parents=True,
            exist_ok=True
        )

        conn = sqlite3.connect(
            path,
            timeout=10,
            isolation_level=None
        )

        conn.row_factory = sqlite3.Row

        conn.execute(
            'PRAGMA foreign_keys=ON'
        )

        conn.execute(
            'PRAGMA busy_timeout=10000'
        )

        return conn

    @staticmethod
    def initialize(path):
        """
        Create the complete current schema for a new database.

        Existing tables and records are preserved.
        Previously created legacy databases must be
        upgraded using the migration scripts.
        """
        with Database.connect(path) as conn:
            conn.executescript(SCHEMA)

    @staticmethod
    def get():
        if 'db' not in g:
            g.db = Database.connect(
                current_app.config['DATABASE']
            )

        return g.db

    @staticmethod
    def close(_error=None):
        db = g.pop('db', None)

        if db is not None:
            db.close()

    @staticmethod
    def rows(result):
        return [
            dict(r)
            for r in result.fetchall()
        ]
