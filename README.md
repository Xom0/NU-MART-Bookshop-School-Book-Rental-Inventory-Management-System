# Nu-Mart Bookshop Management System

A Python and Flask-based Bookshop Management System developed for the COMP2140 Software Engineering group project at The University of the West Indies, Mona.

Nu-Mart provides textbook inventory management, student record searching, rental and return processing, receipt generation, due-date tracking, and overdue reminders.

The application uses **Python, Flask, and SQLite**, with nine related database tables. The submitted ZIP includes a fully populated demonstration database, allowing anyone to test the system without manually creating records.

## 1. System Requirements

### Prerequisites

- Windows 10 or Windows 11
- Python 3.12 or newer
- Visual Studio Code (recommended) or another suitable code editor
- A modern web browser, such as Google Chrome, Microsoft Edge, or Firefox
- Internet access for the initial Python dependency installation

**No MySQL, PostgreSQL, or separate database server is required.**

The application uses a local SQLite database included in the project.

## 2. Installation and Setup (Windows PowerShell)

### Step 1: Extract the ZIP File

Extract the submitted ZIP file to a suitable location on your computer.

Example:

`C:\Users\YourName\Documents\numart-bookshop`

Open the extracted `numart-bookshop` folder in Visual Studio Code.

### Step 2: Open the Terminal

In Visual Studio Code, select:

**Terminal → New Terminal**

Ensure the terminal is running from the project root directory containing `app.py`.

### Step 3: Create a Python Virtual Environment

Run:

```powershell
py -3.12 -m venv .venv
```

If Python 3.12 is unavailable but a compatible newer version is installed, use:

```powershell
py -m venv .venv
```

### Step 4: Install Dependencies

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

This installs the Python libraries required by the application.

### Step 5: Start the Application

Run:

```powershell
.\.venv\Scripts\python.exe app.py
```

### Step 6: Open Nu-Mart

Open a web browser and visit:

**http://127.0.0.1:5000**

The Nu-Mart login page should appear.

### Step 7: Sign In

Choose the appropriate access type and enter the corresponding demonstration credentials.

| Access Type | Name | Password |
|---|---|---|
| Administrator | Demo Administrator | `Admin2026!` |
| Staff | Demo Staff | `Staff2026!` |

These are the default demonstration credentials. Environment variables can override the shared passwords.

The Administrator has access to inventory and student management features, while Staff users can perform permitted day-to-day bookshop operations.

**Important:** These credentials are for local demonstration and testing only.

### Step 8: Stop the Application

Press **Ctrl + C** in the terminal running Flask.

## 3. Demonstration Database

The project includes a fully populated SQLite database located at:

`instance/bookshop.db`

The database is automatically accessed when the application starts.



### Included Demonstration Data

| Record Type | Quantity |
|---|---:|
| Students | 100 |
| Active Students | 90 |
| Inactive Students | 10 |
| Textbook Classifications | 20 |
| Physical Textbook Copies | 4,000 |
| Good-condition Copies | 3,400 |
| Fair-condition Copies | 500 |
| Poor-condition Copies | 100 |
| Demonstration Login Accounts | 2 |

Students are distributed across Grades 9–13, with 20 students per grade.

Each textbook classification initially contains 200 individual physical copies, each identified by a unique Book ID.

The original demonstration dataset contains no rental transactions. Rental, receipt, return, and reminder records can be created while testing the application.

The numbers above describe the generated starting dataset. Counts may change as testers add, rent, return, import, or remove records.

### Book Identification

Each textbook classification has its own classification ID.

Example:

`BK-MAT-001`

Individual physical copies are identified separately.

Examples:

- `BK-MAT-001-001`
- `BK-MAT-001-002`
- `BK-MAT-001-200`

This allows Nu-Mart to track the condition, availability, and rental history of each physical textbook independently.


## 4. Administrator and Staff Permissions

Nu-Mart uses two access types.

| Operation | Administrator | Staff |
|---|---|---|
| View Dashboard | Yes | Yes |
| Search Inventory | Yes | Yes |
| View Student Records | Yes | Yes |
| Add Books | Yes | No |
| Remove Physical Copies | Yes | No |
| Remove Classifications | Yes | No |
| Add Students | Yes | No |
| Remove Students | Yes | No |
| Process Rentals | Yes | Yes |
| Process Returns | Yes | Yes |
| View and Print Receipts | Yes | Yes |
| View and Generate Reminders | Yes | Yes |
| Import and Export Inventory CSV | Yes | No |

Removal operations require Administrator authentication and confirmation.

Records associated with active or historical rental transactions are protected from deletion.

## 6. Demonstration Walkthrough

The following walkthrough can be used to evaluate the application's main features.

### 1. Login and Dashboard

Sign in using the Administrator demonstration account.

Examine the dashboard, which displays inventory totals, student counts, active rentals, and overdue information.

### 2. Textbook Catalogue

Open **Books → Textbook Catalogue**.

Verify that the initial database contains 20 classifications.

Open classification `BK-MAT-001` and examine its 200 physical copies.

### 3. Inventory Search

Open **Books → Physical Copies**.

Search for:

`BK-MAT-001-001`

Select **Exact Book ID**.

Verify that the matching Mathematics Essentials copy is displayed.

Search by title using:

`Mathematics Essentials`

Observe matching textbook records.

### 4. Add Textbooks

Open **Books → Add Book** as Administrator.

Create a new demonstration classification with a valid title, subject, edition, condition, and number of physical copies.

Verify that the system generates the new classification ID and physical-copy IDs.

Alternatively, add copies to an existing classification.

## 5. Automated Testing

Nu-Mart includes automated tests using pytest.

The test suite verifies:

- Inventory searching
- Duplicate textbook prevention
- Grade-to-edition mapping
- Receipt generation
- Student searching and enrolment validation
- Rental processing and return restrictions
- Due-date reminders
- Authentication and authorization
- Administrator-only removal operations
- Physical-copy and classification deletion
- Protection of rental and receipt history
- Transaction consistency and rollback

### Run the Tests

Open a separate terminal in the project root and execute:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

### Latest Verified Results

| Result | Value |
|---|---|
| Total Automated Tests | 30 |
| Tests Passed | 30 |
| Tests Failed | 0 |
| Pass Rate | 100% |
| Execution Time | 9.02 seconds |

The automated tests use temporary SQLite databases.

**Running pytest does not delete or reset the populated demonstration database.**

Manual system test cases and supporting documentation are maintained separately where included in the submission.

## 8. Main Classes and Components

The system includes record classes, management classes, database utilities, and website routes.

### Record Classes

- `User`
- `Student`
- `Book`
- `Rental`
- `Receipt`
- `Reminder`

### Management Classes

- `LoginManager` — authentication and access permissions
- `StudentManager` — student searches, enrolment verification, addition, and removal
- `BookManager` — textbook classifications, physical copies, searching, addition, and removal
- `RentalManager` — rental and return processing
- `ReceiptManager` — receipt generation, retrieval, and grade-to-edition mapping
- `ReminderManager` — due-date checks and reminder management

### Supporting Components

- `Database` — SQLite connections and database initialization
- `FileManager` — CSV inventory import and export
- `EmailSender` — optional email functionality, not enabled for live delivery by default
- `routes/web.py` — Flask routes and user-interface operations

## 9. Database Structure

Nu-Mart uses one SQLite database with **nine tables**.

| Table | Purpose |
|---|---|
| `users` | Stores login accounts and access roles |
| `students` | Stores student records |
| `book_classifications` | Stores textbook classifications |
| `books` | Stores individual physical textbook copies |
| `rentals` | Stores rental and return information |
| `receipts` | Stores receipt headers |
| `receipt_items` | Links rental records to receipts |
