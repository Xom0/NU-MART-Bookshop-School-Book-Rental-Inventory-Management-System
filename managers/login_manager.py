
import os
import hmac
import sqlite3

from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)


class LoginManager:

    # Default passwords for the local demonstration.
    # Environment variables can override these values.
    STAFF_PASSWORD = os.environ.get(
        'NUMART_STAFF_PASSWORD',
        'Staff2026!'
    )

    ADMIN_PASSWORD = os.environ.get(
        'NUMART_ADMIN_PASSWORD',
        'Admin2026!'
    )

    @staticmethod
    def authenticate(conn, username, password, access_type=None):
        # Remove unnecessary spaces from the entered name.
        username = ' '.join(username.strip().split())

        if not username or len(username) > 80 or not password:
            return None

        # Look for an existing user with this name.
        user = conn.execute(
            '''
            SELECT *
            FROM users
            WHERE LOWER(username) = LOWER(?)
            ''',
            (username,)
        ).fetchone()

        # Preserve compatibility with existing internal
        # authentication calls that do not specify access type.
        if access_type is None:
            if user and check_password_hash(
                user['password_hash'],
                password
            ):
                return dict(user)

            return None

        # Convert the login-page selection to the database role.
        role_mapping = {
            'Administrator': 'Admin',
            'Staff': 'Staff'
        }

        selected_role = role_mapping.get(access_type)

        if selected_role is None:
            return None

        # Determine the password for the selected access type.
        required_password = (
            LoginManager.ADMIN_PASSWORD
            if selected_role == 'Admin'
            else LoginManager.STAFF_PASSWORD
        )

        # The selected role's shared password must be correct.
        if not hmac.compare_digest(
            password.encode('utf-8'),
            required_password.encode('utf-8')
        ):
            return None

        # Existing names keep their original role.
        # A Staff account cannot become an administrator
        # simply by changing the access type.
        if user:
            if user['role'] != selected_role:
                return None

            return dict(user)

        # The name is new, so create a user record.
        # This gives each entered name a persistent user ID
        # for rental, receipt and return records.
        name_parts = username.split(' ', 1)

        first_name = name_parts[0]

        last_name = (
            name_parts[1]
            if len(name_parts) > 1
            else ''
        )

        try:
            with conn:
                conn.execute(
                    '''
                    INSERT INTO users (
                        username,
                        password_hash,
                        first_name,
                        last_name,
                        role
                    )
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (
                        username,
                        generate_password_hash(required_password),
                        first_name,
                        last_name,
                        selected_role
                    )
                )

        except sqlite3.IntegrityError:
            # Reject conflicting registrations rather than
            # changing another account's identity or role.
            return None

        # Retrieve the newly created account.
        user = conn.execute(
            '''
            SELECT *
            FROM users
            WHERE LOWER(username) = LOWER(?)
            ''',
            (username,)
        ).fetchone()

        return dict(user) if user else None

    @staticmethod
    def add_user(
        conn,
        username,
        password,
        first_name,
        last_name,
        role='Staff'
    ):
        if role not in ('Admin', 'Staff') or len(password) < 10:
            raise ValueError(
                'Choose a valid role and a password '
                'of at least 10 characters.'
            )

        return conn.execute(
            '''
            INSERT INTO users(
                username,
                password_hash,
                first_name,
                last_name,
                role
            )
            VALUES (?, ?, ?, ?, ?)
            ''',
            (
                username,
                generate_password_hash(password),
                first_name,
                last_name,
                role
            )
        ).lastrowid

    @staticmethod
    def check_permission(user, required='Staff'):
        return (
            bool(user)
            and (
                required == 'Staff'
                or user['role'] == 'Admin'
            )
        )
