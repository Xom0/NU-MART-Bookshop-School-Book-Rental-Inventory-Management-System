"""Web pages and form handling. Business rules live in manager classes."""

import sqlite3
from datetime import date, timedelta
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
    Response
)

from helpers.database import Database
from helpers.file_manager import FileManager

from managers.login_manager import LoginManager
from managers.student_manager import StudentManager
from managers.book_manager import BookManager
from managers.rental_manager import RentalManager
from managers.receipt_manager import ReceiptManager
from managers.reminder_manager import ReminderManager


pages = Blueprint('pages', __name__)


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in first.', 'error')
            return redirect(url_for('pages.login'))

        return func(*args, **kwargs)

    return wrapper


def admin_required(func):
    @wraps(func)
    @login_required
    def wrapper(*args, **kwargs):
        if session.get('role') != 'Admin':
            abort(403)

        return func(*args, **kwargs)

    return wrapper


def db():
    return Database.get()


def actor():
    return session['user_id']


def friendly_error(exc):
    if isinstance(exc, sqlite3.IntegrityError):
        return (
            'This record already exists or its information '
            'conflicts with another record.'
        )

    return str(exc)


@pages.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('pages.login'))

    connection = db()

    stats = {
        'books': connection.execute(
            'SELECT count(*) FROM books'
        ).fetchone()[0],

        'available': connection.execute(
            "SELECT count(*) FROM books WHERE availability='Available'"
        ).fetchone()[0],

        'rentals': connection.execute(
            "SELECT count(*) FROM rentals WHERE status='Active'"
        ).fetchone()[0],

        'students': connection.execute(
            'SELECT count(*) FROM students'
        ).fetchone()[0],

        'overdue': len(
            ReminderManager.find_overdue(connection)
        )
    }

    return render_template('dashboard.html', stats=stats)


@pages.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        access_type = request.form.get('access_type', '')

        # Validate the selected access type against the user's actual role.
        user = LoginManager.authenticate(
            db(),
            username,
            password,
            access_type
        )

        if user:
            # Remove any previous login session information.
            session.clear()

            # Store the authenticated account's actual identity and role.
            session.update(
                user_id=user['user_id'],
                username=user['username'],
                role=user['role'],
                display_name=user['first_name']
            )

            flash(
                'Welcome to Nu-Mart Bookshop.',
                'success'
            )

            return redirect(url_for('pages.index'))

        # Use one error message for invalid credentials or role selection.
        flash(
            'Invalid username, password, or access type.',
            'error'
        )

    return render_template('login.html')


@pages.post('/logout')
@login_required
def logout():
    session.clear()
    flash('You have logged out.', 'success')

    return redirect(url_for('pages.login'))


# INVENTORY UPGRADE:
# Show textbook classifications and individual physical copies.
@pages.route('/books')
@login_required
def books():
    connection = db()

    view = request.args.get('view', 'copies')
    query = request.args.get('q', '').strip()
    mode = request.args.get('mode', 'title')
    classification_id = request.args.get(
        'classification_id',
        ''
    ).strip()
    status = request.args.get('status', 'All')

    if view not in ('catalogue', 'copies'):
        view = 'copies'

    if mode not in ('title', 'id'):
        mode = 'title'

    if status not in (
        'All',
        'Available',
        'Rented',
        'Not Rentable'
    ):
        status = 'All'

    classifications = []
    physical_books = []
    selected_classification = None

    if view == 'catalogue':
        # Search by classification ID, title, or subject.
        classifications = BookManager.search_classifications(
            connection,
            query
        )

    elif classification_id:
        # Look up every physical copy belonging to one textbook.
        selected_classification = BookManager.get_classification(
            connection,
            classification_id
        )

        if selected_classification is None:
            abort(404)

        physical_books = BookManager.get_copies(
            connection,
            classification_id,
            query,
            status
        )

    else:
        # Preserve the original Book ID and partial-title search.
        physical_books = BookManager.search_book(
            connection,
            query,
            mode
        )

    return render_template(
        'books.html',
        view=view,
        query=query,
        mode=mode,
        classification_id=classification_id,
        status=status,
        classifications=classifications,
        books=physical_books,
        selected_classification=selected_classification
    )


# INVENTORY UPGRADE:
# Create textbook classifications and add physical copies.
@pages.route('/books/add', methods=['GET', 'POST'])
@admin_required
def add_book():
    connection = db()

    if request.method == 'POST':
        try:
            form = request.form

            operation = form.get('operation', '').strip()
            quantity = form.get('quantity', '')
            condition = form.get('condition', 'Good')

            if operation == 'new':

                # Create one classification and its initial copies.
                # The BookManager uses savepoints so failures
                # cannot leave partially created copy batches.
                with connection:
                    result = BookManager.create_textbook_with_copies(
                        connection,
                        form.get('title', ''),
                        form.get('subject', ''),
                        form.get('edition', ''),
                        quantity,
                        condition
                    )

                classification_id = result['classification_id']
                created_count = len(result['copy_ids'])

                flash(
                    f'Textbook {classification_id} created '
                    f'successfully with {created_count} '
                    f'physical copies.',
                    'success'
                )

                return redirect(
                    url_for(
                        'pages.books',
                        view='copies',
                        classification_id=classification_id
                    )
                )

            elif operation == 'existing':

                classification_id = form.get(
                    'classification_id',
                    ''
                ).strip()

                if not classification_id:
                    raise ValueError(
                        'Select an existing textbook classification.'
                    )

                # Add copies to an existing classification.
                # Existing copies and rental records are preserved.
                with connection:
                    copy_ids = BookManager.add_copies(
                        connection,
                        classification_id,
                        quantity,
                        condition
                    )

                flash(
                    f'Added {len(copy_ids)} physical copies '
                    f'to {classification_id}.',
                    'success'
                )

                return redirect(
                    url_for(
                        'pages.books',
                        view='copies',
                        classification_id=classification_id
                    )
                )

            else:
                raise ValueError(
                    'Select a valid inventory operation.'
                )

        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(friendly_error(exc), 'error')

    # Populate the Existing Textbook dropdown.
    classifications = BookManager.search_classifications(
        connection
    )

    return render_template(
        'add_book.html',
        classifications=classifications
    )


# ADMINISTRATOR ONLY:
# Dedicated page for correcting incorrectly added physical
# copies or an entire textbook classification.
@pages.route('/books/remove', methods=['GET', 'POST'])
@admin_required
def remove_book_page():
    connection = db()
    preview = None

    if request.method == 'POST':
        operation = request.form.get('operation', '').strip()
        action = request.form.get('action', 'preview').strip()

        try:
            if action not in ('preview', 'confirm'):
                raise ValueError('Choose a valid removal action.')

            if operation == 'copies':
                raw_ids = request.form.get('book_ids', '')
                book_ids = [
                    value.strip()
                    for value in raw_ids.replace('\n', ',').split(',')
                    if value.strip()
                ]

                if not book_ids:
                    raise ValueError('Enter at least one physical Book ID.')

                if len(book_ids) > 500:
                    raise ValueError('Select no more than 500 physical copies.')

                if len(set(book_ids)) != len(book_ids):
                    raise ValueError('The same Book ID was entered more than once.')

                books_to_remove = []
                for book_id in book_ids:
                    book = connection.execute(
                        'SELECT * FROM books WHERE book_id = ?',
                        (book_id,)
                    ).fetchone()

                    if book is None:
                        raise ValueError(f'Book {book_id} was not found.')

                    has_history = connection.execute(
                        "SELECT 1 FROM rentals WHERE book_id = ? LIMIT 1",
                        (book_id,)
                    ).fetchone()

                    if book['availability'] == 'Rented' or has_history:
                        raise ValueError(
                            f'Book {book_id} is rented or has rental history '
                            'and cannot be removed.'
                        )

                    books_to_remove.append(dict(book))

                if action == 'confirm':
                    with connection:
                        count = BookManager.remove_physical_copies(
                            connection, book_ids
                        )
                    flash(
                        f'Removed {count} physical textbook copies successfully.',
                        'success'
                    )
                    return redirect(url_for('pages.books', view='catalogue'))

                preview = {
                    'operation': 'copies',
                    'book_ids': raw_ids,
                    'books': books_to_remove,
                    'count': len(books_to_remove)
                }

            elif operation == 'classification':
                classification_id = request.form.get(
                    'classification_id', ''
                ).strip()

                classification = BookManager.get_classification(
                    connection, classification_id
                )
                if classification is None:
                    raise ValueError('Textbook classification was not found.')

                has_history = connection.execute(
                    "SELECT 1 FROM rentals r JOIN books b ON b.book_id = r.book_id WHERE b.classification_id = ? LIMIT 1",
                    (classification_id,)
                ).fetchone()
                rented = connection.execute(
                    "SELECT 1 FROM books WHERE classification_id = ? AND availability = 'Rented' LIMIT 1",
                    (classification_id,)
                ).fetchone()
                if has_history or rented:
                    raise ValueError(
                        'This classification includes rented or previously '
                        'rented copies and cannot be removed.'
                    )

                copy_count = connection.execute(
                    'SELECT COUNT(*) FROM books WHERE classification_id = ?',
                    (classification_id,)
                ).fetchone()[0]

                if action == 'confirm':
                    with connection:
                        removed = BookManager.remove_classification(
                            connection, classification_id
                        )
                    flash(
                        f'Classification {classification_id} and {removed} '
                        'copies removed successfully.',
                        'success'
                    )
                    return redirect(url_for('pages.books', view='catalogue'))

                preview = {
                    'operation': 'classification',
                    'classification': classification,
                    'classification_id': classification_id,
                    'count': copy_count
                }
            else:
                raise ValueError('Select a valid removal operation.')

        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(friendly_error(exc), 'error')

    return render_template('remove_book.html', preview=preview)


@pages.get('/books/export')
@admin_required
def export_books():
    return Response(
        FileManager.export_csv(db()),
        mimetype='text/csv',
        headers={
            'Content-Disposition': 'attachment;filename=books_export.csv'
        }
    )


@pages.post('/books/import')
@admin_required
def import_books():
    file = request.files.get('csv_file')

    if not file or not file.filename.lower().endswith('.csv'):
        flash('Choose a CSV file.', 'error')

    else:
        try:
            count = FileManager.import_csv(db(), file)
            flash(f'Imported {count} textbooks.', 'success')

        except (
            ValueError,
            sqlite3.IntegrityError,
            UnicodeError
        ) as exc:
            flash(friendly_error(exc), 'error')

    return redirect(url_for('pages.books'))


@pages.route('/students')
@login_required
def students():
    query = request.args.get('q', '')

    return render_template(
        'students.html',
        students=StudentManager.search_student(db(), query),
        query=query
    )


@pages.route('/students/add', methods=['GET', 'POST'])
@admin_required
def add_student():
    if request.method == 'POST':
        try:
            f = request.form

            with db():
                StudentManager.add_student(
                    db(),
                    f.get('student_id', ''),
                    f.get('first_name', ''),
                    f.get('last_name', ''),
                    f.get('grade', ''),
                    f.get('class_name', ''),
                    f.get('enrolment_status', 'Active')
                )

            flash('Student added successfully.', 'success')
            return redirect(url_for('pages.students'))

        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(friendly_error(exc), 'error')

    return render_template('add_student.html')


# ADMINISTRATOR ONLY:
# Dedicated page for removing an incorrectly added student.
@pages.route('/students/remove', methods=['GET', 'POST'])
@admin_required
def remove_student_page():
    connection = db()
    preview = None

    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        action = request.form.get('action', 'preview').strip()

        try:
            if action not in ('preview', 'confirm'):
                raise ValueError('Choose a valid removal action.')

            student = connection.execute(
                'SELECT * FROM students WHERE student_id = ?',
                (student_id,)
            ).fetchone()
            if student is None:
                raise ValueError('Student ID was not found.')

            has_rentals = connection.execute(
                'SELECT 1 FROM rentals WHERE student_id = ? LIMIT 1',
                (student_id,)
            ).fetchone()
            has_receipts = connection.execute(
                'SELECT 1 FROM receipts WHERE student_id = ? LIMIT 1',
                (student_id,)
            ).fetchone()
            if has_rentals or has_receipts:
                raise ValueError(
                    'This student has rental or receipt history '
                    'and cannot be removed.'
                )

            if action == 'confirm':
                with connection:
                    removed = StudentManager.remove_student(
                        connection, student_id
                    )
                flash(f'Student {removed} removed successfully.', 'success')
                return redirect(url_for('pages.students'))

            preview = dict(student)

        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(friendly_error(exc), 'error')

    return render_template('remove_student.html', preview=preview)


# FIX-01: Show all rental records by default.
@pages.route('/rentals')
@login_required
def rentals():
    status = request.args.get('status', 'All')

    if status not in ('All', 'Active', 'Returned'):
        status = 'All'

    rental_records = RentalManager.list_rentals(
        db(),
        status
    )

    return render_template(
        'rentals.html',
        rentals=rental_records,
        status=status
    )


@pages.route('/rentals/new', methods=['GET', 'POST'])
@login_required
def new_rental():
    connection = db()

    if request.method == 'POST':
        try:
            f = request.form

            # Staff may choose multiple physical book IDs,
            # one per line or separated by commas.
            book_ids = [
                x.strip()
                for x in f.get('book_ids', '').replace(
                    '\n', ','
                ).split(',')
                if x.strip()
            ]

            receipt_id = RentalManager.rent_book(
                connection,
                f.get('student_id', '').strip(),
                book_ids,
                f.get('due_date', ''),
                actor()
            )

            flash(
                'Rental saved and receipt generated.',
                'success'
            )

            return redirect(
                url_for(
                    'pages.receipt',
                    receipt_id=receipt_id
                )
            )

        except (ValueError, sqlite3.IntegrityError) as exc:
            flash(friendly_error(exc), 'error')

    return render_template(
        'new_rental.html',
        default_due=(
            date.today() + timedelta(days=14)
        ).isoformat(),
        students=StudentManager.search_student(connection),
        books=BookManager.search_book(connection)
    )


# FIX-01: Keep returned books visible after processing.
@pages.post('/rentals/<int:rental_id>/return')
@login_required
def return_rental(rental_id):
    try:
        # A condition is required for every new return.
        return_condition = request.form.get(
            'return_condition',
            ''
        ).strip()

        # Reject missing, unknown, or modified form values.
        if return_condition not in RentalManager.RETURN_CONDITIONS:
            raise ValueError(
                'Please select a valid return condition: '
                'Good, Fair, or Poor.'
            )

        # The authenticated user is the person collecting
        # the returned textbook. Never trust a submitted
        # username for this field.
        RentalManager.return_book(
            db(),
            rental_id,
            actor(),
            return_condition=return_condition
        )

        flash(
            'Textbook returned successfully. '
            f'Recorded condition: {return_condition}. '
            'The return is visible in Rental History.',
            'success'
        )

    except (ValueError, sqlite3.IntegrityError) as exc:
        flash(friendly_error(exc), 'error')

    return redirect(
        url_for('pages.rentals', status='All')
    )


# NEW FEATURE: Browse and search previously issued rental receipts.
@pages.route('/receipts')
@login_required
def receipts():
    # Read the search query entered on the Receipt History page.
    query = request.args.get('q', '').strip()

    # Retrieve saved receipts with student and processor information.
    saved_receipts = ReceiptManager.list_receipts(
        db(),
        query
    )

    # Display the searchable list of existing receipts.
    return render_template(
        'receipts.html',
        receipts=saved_receipts,
        query=query
    )


@pages.route('/receipts/<int:receipt_id>')
@login_required
def receipt(receipt_id):
    try:
        header, items = ReceiptManager.get_receipt(
            db(),
            receipt_id
        )

    except ValueError:
        abort(404)

    return render_template(
        'receipt.html',
        receipt=header,
        items=items
    )


@pages.route('/reminders')
@login_required
def reminders():
    conn = db()

    items = ReminderManager.check_due_dates(conn)

    saved = [
        dict(x)
        for x in conn.execute("""
            SELECT
                m.*,
                r.book_id,
                s.first_name,
                s.last_name
            FROM reminders m
            JOIN rentals r
                ON r.rental_id = m.rental_id
            JOIN students s
                ON s.student_id = r.student_id
            ORDER BY m.created_at DESC
            LIMIT 150
        """)
    ]

    return render_template(
        'reminders.html',
        items=items,
        saved=saved
    )


@pages.post('/reminders/<int:rental_id>/generate')
@login_required
def generate_reminder(rental_id):
    try:
        with db():
            message = ReminderManager.create_reminder(
                db(),
                rental_id
            )

        flash(message, 'success')

    except ValueError as exc:
        flash(str(exc), 'error')

    return redirect(url_for('pages.reminders'))


@pages.app_errorhandler(403)
def forbidden(error):
    return render_template(
        'error.html',
        message='You need administrator access to use this page.'
    ), 403


@pages.app_errorhandler(404)
def not_found(error):
    return render_template(
        'error.html',
        message='The requested record was not found.'
    ), 404
