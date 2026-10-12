# Simple Bank Orderly v3.1 — Browser + Tkinter Desktop

> **GitHub source release:** This repository intentionally excludes all local databases, transaction logs, audit records, exports, backups, and staff/customer information. Run with fictional demonstration accounts only.

## Quick start — clean demo

```powershell
python -m pip install -r requirements.txt
$env:BANK_BACKEND = "sqlite"
python web_app.py
```

Open `http://127.0.0.1:5000` in your browser; create a new administrator on first launch. To use the desktop interface instead, run `python simple_bank.py` in the same shell. SQLite files are created locally and are excluded from Git. MySQL instructions follow below.

## Automated tests

```powershell
$env:BANK_BACKEND = "sqlite"
python -m unittest test_bank test_web -v
```

This is a classroom application, **not a real banking product**. Do not deploy to a public server or use actual customer information.

---


A Python/MySQL classroom banking application with browser and Tkinter interfaces, staff login, customer accounts,
combined searches, deposits/withdrawals/transfers, account editing and closure,
audited actions, CSV reports, external logs, and backup/recovery utilities.

## Browser interface — start here

Version 3.1 adds `web_app.py`, HTML templates and CSS. Both interfaces use the
same `banking.py`, staff logins, database, account numbers, reports and log files.
Tkinter is still available with `python simple_bank.py`.

### Upgrade your existing V3 folder without losing test accounts

1. Stop the desktop app/web server before updating code.
2. Back up your existing V3 `data` folder (SQLite) and your MySQL database if used.
3. Copy the contents of the extracted `Bank_Orderly_v3_1` folder into your existing
   V3 folder. Replace application files; keep your existing `data` folder. No live
   database, sample account store, or credentials are included in this ZIP.
4. In File Explorer, open that V3 folder, click the address bar, type `powershell`,
   and press Enter. Install/update dependencies:

```powershell
python -m pip install -r requirements.txt
```

For an immediate browser demonstration using your local SQLite data:

```powershell
$env:BANK_BACKEND = "sqlite"
python web_app.py
```

Keep that terminal open. Open **http://127.0.0.1:5000** in Edge or Chrome.
If you previously created an Admin in the SAME folder/data directory, sign in
using those credentials. If there are no staff accounts, create the first Admin.
Use Ctrl+C in the terminal to stop the server. Optional `Start_Web_Demo.bat` starts
SQLite mode from its own folder after dependencies are installed.

If you keep v3.1 in a new folder, point it at your existing SQLite directory:

```powershell
$env:BANK_BACKEND = "sqlite"
$env:BANK_DATA_DIR = "C:\FULL\PATH\TO\YOUR\V3\data"
python web_app.py
```

For the assignment's live MySQL verification, follow the MySQL environment setup
below, then run `python web_app.py` instead of `python simple_bank.py`. The browser
interface works with MySQL; SQLite is for independent demonstration/tests.
Changing BANK_BACKEND does NOT move data between databases. SQLite and MySQL
have separate staff/account stores. Select the intended database deliberately.

### Browser workflow

- Overview shows active/closed counts, balances and recent transactions.
- Search Accounts exposes every searchable field, individually or combined with
  AND, and returns every match. Account number links open details and history.
- Create Account requires the existing name/address rules plus simulated identity
  inputs and the opening payment method.
- Account details provide Edit and Close links. Closure requires a reason and
  confirmation; zero-balance policy and preserved history apply as before.
- Deposit, Withdrawal and Transfer use server validation and the same banking rules.
  An overdraft shows a separate confirmation page before posting.
- Reports support the same date/staff/account/action filters and CSV downloads.
- Admins have Staff Accounts, Restricted Reviews and Verify Customer pages.
  Authorization is checked on the server, including direct URL/POST attempts.
- POST forms have CSRF protection and single-use form tokens. Re-submitting the
  same form gets an error, rather than posting the transaction twice.
- Session expiry is enforced after 15 minutes inactivity when the next request
  arrives. Forms opened before expiry/restart must be reloaded.

The development server binds only to this computer (`127.0.0.1`), with debug mode
off. It is NOT public hosting. Do not expose it to a network or use real customer
information. This is local HTTP, not encrypted transport. Sessions use a random
signing key on server start; restarting invalidates browser sessions by default.
`BANK_WEB_SECRET` can configure a signing key locally; never commit it. Single-use
form storage is local to one server process, not distributed infrastructure.

## Desktop setup (Windows / PowerShell)

Extract this folder beside your working v2 project. Keep your original database intact.
Python 3.10 or newer with Tkinter is required.

### Quick local demonstration

This uses SQLite, not your MySQL database. It is useful for trying the interface.

```powershell
python -m pip install -r requirements.txt
$env:BANK_BACKEND = "sqlite"
python simple_bank.py
```

On first launch, create an Admin username and password (12+ characters). No default
password is supplied. Choose Staff Accounts to create individual Teller/Admin logins.
Use fictional customer information only.

### MySQL setup (assignment backend)

1. In MySQL Workbench, run `create_database.sql`. It creates `simple_bank_v3`.
2. Create a dedicated local MySQL user with a new password. Grant SELECT, INSERT,
   UPDATE, CREATE, REFERENCES on `simple_bank_v3.*`. Tables are created on first run.
3. Set the connection variables in PowerShell. Replace the placeholders locally:

```powershell
$env:BANK_BACKEND = "mysql"
$env:BANK_DB_HOST = "localhost"
$env:BANK_DB_PORT = "3306"
$env:BANK_DB_USER = "bank_app"
$env:BANK_DB_PASSWORD = "YOUR_NEW_LOCAL_PASSWORD"
$env:BANK_DB_NAME = "simple_bank_v3"
python simple_bank.py
```

Avoid putting passwords in scripts, screenshots, GitHub, or documentation. The
uploaded original configuration contained a password: rotate that credential.
The archived source copy included here has its password replaced with CHANGE_ME.

MySQL must be installed and running on YOUR computer. This package does not
include MySQL Server. The application creates its schema in the selected database.

### Import original v2 data

Make a MySQL backup of `simple_bank` first. Create your first v3 Admin, sign out,
and run the following before creating any v3 customer accounts:

```powershell
$env:BANK_LEGACY_DB_NAME = "simple_bank"
$env:BANK_LEGACY_DB_USER = "YOUR_SOURCE_READ_USER"
$env:BANK_LEGACY_DB_PASSWORD = "YOUR_SOURCE_PASSWORD"
python import_v2.py
```

The import reads v2 accounts and transactions without changing them; the target
must contain no accounts. It preserves numbers, balances, names/addresses,
transaction amounts and timestamps. The next number continues after the largest
imported number. Historical payment methods, staff identities, overdraft consent,
and transfer grouping cannot be established from v2 and are not invented. The
staff ID on imported transactions identifies the importer, NOT the historical teller.

Each imported account receives a separate Pending customer identity. An Admin
must use Verify Customer with fictional identity details before cash transactions
or another account for that identity. The application cannot automatically know
which imported accounts belong to the same real person. Reconcile this before
using imported records for aggregation demonstrations; use newly created accounts
with an Existing Customer ID for the multi-account tests. Historical timestamps
lack original time-zone information and are preserved rather than guessed.

## Desktop workflow

- Search Accounts: choose fields individually, or fill up to six distinct criteria
  to combine with AND. Text supports literal partial matches; all matches appear.
  Amount search fields use integer cents. Double-click a result for details/history.
- Create Account: all original name/address fields remain required. Add a positive
  initial deposit and choose Cash/Electronic. New customers require birth date,
  fictional identification reference and verification checkbox. Existing Customer ID
  reuses a verified identity, enabling aggregation across their accounts.
- Edit Account: select an account first. Changes retain before/after values and actor.
- Deposit / Withdrawal: choose a payment method. Cash conductor defaults to owner;
  enter another verified customer ID when a different person conducts the transaction.
- Transfer: both account updates and history entries commit together. Transfers are
  electronic; differing customer identities at $3,000+ generate record-review notes.
- Overdraft: explicit confirmation is required when a withdrawal/transfer makes the
  source balance negative. This preserves the classroom workflow, not a real overdraft
  product or compliance disclosure system.
- Close Account: requires a reason, confirmation, and zero balance (project policy).
  History and identifying records remain; transactions and edits are blocked.
- Reports: Transactions and Accounts for tellers; Audit, Staff and Cash Review for
  admins. Transaction reports for tellers are restricted to their own staff ID.
  Account history intentionally includes all staff transactions on that account.
  Dates are YYYY-MM-DD and the end date is inclusive. Staff/account/action filters
  apply to transaction/audit reports. Account reports support account number.
- CSV export neutralizes formula-like text. CSV money fields are cents; table views
  show dollars. Staff reports exclude passwords/hashes.
- Cash Review: Admin-only simulated cash review notes and restricted suspicion notes.
- Sessions sign out after 15 minutes inactivity; five failed logins lock for 15 minutes.

## External records and recovery

Files under `data/` (or BANK_DATA_DIR):

- `application.log`: failures without raw credentials or database error text.
- `transactions.jsonl`: successful committed transactions, timestamps, actor, balances.
- `audit.jsonl`: account changes, closure reason, logins, searches and report actions.
- `balance_snapshot.json`: current balances/statuses, regenerated atomically.
- `bank.sqlite`: present only for SQLite mode.

A database outbox is written in the same transaction as financial changes. File
export occurs after commit; failures remain pending for retry. Never repeat a
financial transaction just because export failed. Retry Log Export instead.
Export is at-least-once: interrupted exports may duplicate event IDs; deduplicate
by ID. A snapshot/log is not a full backup, and a failure before file export can
leave external files behind the database. Copies on the same disk do not protect
against disk loss. Use full backups and separate protected storage.

### Full backup and restore

```powershell
python recovery.py backup backup_2026_10_07.json
```

Prompts for Admin login. Choose a new filename; existing backups are not overwritten.
Backups include customer details and password hashes. Restrict file access, protect
storage, and keep a copy separately. Backups are NOT encrypted by this utility.

To verify restoration, set BANK_DATA_DIR to a new directory (SQLite) or BANK_DB_NAME
to a new empty database (MySQL), then:

```powershell
python recovery.py restore backup_2026_10_07.json
```

Run on the new empty target before creating a first Admin. Restore refuses an
existing staff/account store. Staff logins from the backup are restored. Do not
restore files from an untrusted source. Full backups restore the backup point;
this utility does not automatically replay later external events. Compare those
by ID and reconcile before posting any corrections. For real MySQL operations,
also use native backups and point-in-time recovery with binary logs.

## Verify

```powershell
python -m unittest -v
```

See `docs/test_results_web.txt` for the current 78-test combined run (48 service
+ 30 HTTP tests), `docs/test_results.txt` for the earlier 48-test run, and
`docs/MANUAL_TEST_PLAN.md` for required desktop/MySQL checks.
Automated tests exercise the SQLite service and Flask request/response routes; they do NOT establish
that MySQL or the GUI has been validated on your machine.

## Files

- `simple_bank.py`: Tkinter interface and entry point.
- `web_app.py`, `templates/`, `static/`: Flask browser interface.
- `test_web.py`: 30 HTTP integration tests.
- `Start_Web_Demo.bat`: optional Windows SQLite browser launcher.
- `banking.py`: rules, authentication, data access, transactions, reports, audit/export.
- `config.py`: environment-based configuration.
- `create_database.sql`: separate v3 database setup.
- `import_v2.py`: non-destructive v2 import.
- `recovery.py`: full logical backup/restore.
- `test_bank.py`: automated tests without third-party test runner dependency.
- `original_v2/`: source reference with database password removed.
- `docs/`: testing, requirements, development record and regulatory scope.

This is a classroom simulation, not a certified or production banking platform.
Read `docs/REGULATORY_SCOPE.md` for exactly what is and is not implemented.
