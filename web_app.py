"""Flask browser interface using the SAME Bank service as the Tkinter desktop.
Run locally: python web_app.py, then http://127.0.0.1:5000.
No real financial services or public deployment are supported by this class project.
"""
import csv
import io
import os
import secrets
import threading
import time
from datetime import timedelta
from functools import wraps
from flask import Flask, Response, abort, flash, g, redirect, render_template, request, session, url_for
from banking import Bank, BankError, FIELDS, SEARCH_FIELDS, cents, money
from config import DATA_DIR, BACKEND, DB_CONFIG


def create_app(bank=None, test_config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.getenv('BANK_WEB_SECRET') or secrets.token_hex(32),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                      SESSION_COOKIE_SECURE=False, PERMANENT_SESSION_LIFETIME=timedelta(minutes=15),
                      MAX_CONTENT_LENGTH=65536, TRUSTED_HOSTS=['127.0.0.1', 'localhost'])
    if test_config: app.config.update(test_config)
    app.bank = bank or Bank(DATA_DIR, BACKEND, DB_CONFIG)
    # Single-use forms: a stale form after restart is rejected rather than replayed.
    # Intended for one local Flask process; a distributed deployment needs shared storage.
    forms = {}; forms_lock = threading.Lock()

    def actor():
        return g.staff['id']

    def protected(admin=False):
        def decorator(function):
            @wraps(function)
            def guarded(*args, **kwargs):
                if not g.staff: return redirect(url_for('login'))
                if admin and g.staff['role'] != 'Admin': abort(403)
                return function(*args, **kwargs)
            return guarded
        return decorator

    def new_form():
        nonce = secrets.token_urlsafe(24)
        with forms_lock:
            now = time.time()
            for key in [key for key, item in forms.items() if now - item[1] > 1800]: forms.pop(key, None)
            forms[nonce] = (session['csrf'], now)
        return nonce

    @app.before_request
    def secure_request():
        g.staff = None
        if request.endpoint == 'static': return
        session.setdefault('csrf', secrets.token_urlsafe(32))
        if session.get('staff_id') is not None:
            if time.time() - session.get('last_activity', 0) > 900:
                session.clear(); session['csrf'] = secrets.token_urlsafe(32)
                flash('Your session expired. Please sign in again.', 'warning')
            else:
                with app.bank.transaction() as con:
                    try: row = app.bank.authorize(con, session['staff_id'])
                    except BankError:
                        session.clear(); session['csrf'] = secrets.token_urlsafe(32)
                    else:
                        g.staff = {'id':row['id'], 'username':row['username'], 'role':row['role']}
                        session['last_activity'] = time.time()
        if request.method == 'POST':
            submitted = request.form.get('csrf', '')
            if not secrets.compare_digest(submitted, session['csrf']): abort(400, 'Invalid form security token. Reload the page.')
            with forms_lock: item = forms.pop(request.form.get('nonce', ''), None)
            if not item or item[0] != session['csrf'] or time.time()-item[1]>1800:
                abort(409, 'This form was already submitted or expired. Reload the page; check history before repeating a financial transaction.')

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
        return response

    @app.context_processor
    def context():
        return dict(staff=g.get('staff'), money=money, new_form=new_form,
                    export_pending=app.bank.export_pending, backend=app.bank.backend.upper())

    @app.errorhandler(BankError)
    def bank_error(error):
        return render_template('error.html', title='Action could not be completed', message=str(error)), 400

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(413)
    def http_error(error):
        return render_template('error.html', title=f'Request {error.code}', message=error.description), error.code

    @app.errorhandler(500)
    def server_error(error):
        app.bank.logger.error('Unexpected browser route failure')
        return render_template('error.html', title='Server error', message='Check application.log and transaction history before retrying.'), 500

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if g.staff: return redirect(url_for('dashboard'))
        if app.bank.needs_bootstrap(): return redirect(url_for('setup'))
        if request.method == 'POST':
            user = app.bank.login(request.form.get('username', ''), request.form.get('password', ''))
            session.clear(); session.update(staff_id=user['id'], last_activity=time.time(), csrf=secrets.token_urlsafe(32))
            session.permanent = True
            return redirect(url_for('dashboard'))
        return render_template('login.html', title='Staff sign in', setup=False)

    @app.route('/setup', methods=['GET', 'POST'])
    def setup():
        if not app.bank.needs_bootstrap(): return redirect(url_for('login'))
        if request.method == 'POST':
            app.bank.create_staff(None, request.form.get('username', ''), request.form.get('password', ''), 'Admin')
            flash('Admin created. Sign in with your new credentials.', 'success')
            return redirect(url_for('login'))
        return render_template('login.html', title='Create first Admin', setup=True)

    @app.post('/logout')
    @protected()
    def logout():
        app.bank.logout(actor()); session.clear()
        return redirect(url_for('login'))

    @app.get('/')
    @protected()
    def dashboard():
        accounts = app.bank.search(actor())
        active = [a for a in accounts if a['status'] == 'Active']
        transactions = app.bank.reports(actor(), 'Transactions')
        return render_template('dashboard.html', title='Overview', accounts=accounts,
                               active_count=len(active), total=sum(a['balance_cents'] for a in active),
                               recent=list(reversed(transactions[-8:])))

    @app.get('/accounts')
    @protected()
    def search():
        criteria = {key:request.args[key] for key in SEARCH_FIELDS if request.args.get(key, '').strip()}
        accounts = app.bank.search(actor(), criteria)
        return render_template('search.html', title='Search accounts', accounts=accounts,
                               fields=SEARCH_FIELDS, criteria=criteria)

    @app.route('/accounts/new', methods=['GET', 'POST'])
    @protected()
    def create_account():
        if request.method == 'POST':
            number = app.bank.create_account(actor(), {k:request.form.get(k, '') for k in FIELDS},
                request.form.get('amount', ''), request.form.get('method', ''),
                conductor=request.form.get('conductor', '').strip(),
                customer_id=request.form.get('customer_id', '').strip(),
                dob=request.form.get('dob', ''), id_reference=request.form.get('id_reference', ''),
                verified=request.form.get('verified') == 'yes')
            flash(f'Checking account {number} created.', 'success')
            return redirect(url_for('details', number=number))
        return render_template('account_form.html', title='Create checking account', fields=FIELDS, account=None)

    @app.get('/accounts/<int:number>')
    @protected()
    def details(number):
        accounts = app.bank.search(actor(), {'account_number':number})
        if not accounts: abort(404)
        with app.bank.transaction() as con:
            app.bank.authorize(con, actor())
            history = app.bank.rows(con, 'SELECT * FROM transactions WHERE account_number=? ORDER BY timestamp', (number,))
        return render_template('details.html', title=f'Account {number}', account=accounts[0], history=history)

    @app.route('/accounts/<int:number>/edit', methods=['GET', 'POST'])
    @protected()
    def edit_account(number):
        if request.method == 'POST':
            app.bank.edit(actor(), number, {k:request.form.get(k, '') for k in FIELDS})
            flash('Account updated. Before/after changes recorded in the audit.', 'success')
            return redirect(url_for('details', number=number))
        accounts = app.bank.search(actor(), {'account_number':number})
        if not accounts: abort(404)
        if accounts[0]['status'] != 'Active': raise BankError('Closed accounts cannot be edited.')
        return render_template('account_form.html', title=f'Edit account {number}', fields=FIELDS, account=accounts[0])

    @app.route('/accounts/<int:number>/close', methods=['GET', 'POST'])
    @protected()
    def close_account(number):
        if request.method == 'POST':
            if request.form.get('confirm') != 'yes': raise BankError('Confirm account closure before submitting.')
            app.bank.close_account(actor(), number, request.form.get('reason', ''))
            flash('Account closed. Reason, staff identity and history retained.', 'success')
            return redirect(url_for('details', number=number))
        accounts = app.bank.search(actor(), {'account_number':number})
        if not accounts: abort(404)
        return render_template('close.html', title='Close account', account=accounts[0])

    def integer(name):
        value = request.form.get(name, '').strip()
        if not value.isdigit(): raise BankError(f'{name.replace("_", " ").title()} must be a numeric account number.')
        return int(value)

    @app.route('/transactions/<kind>', methods=['GET', 'POST'])
    @protected()
    def transaction(kind):
        if kind not in ('deposit', 'withdrawal'): abort(404)
        title = kind.title()
        if request.method == 'POST':
            number = integer('account_number'); amount = cents(request.form.get('amount', ''))
            accounts = app.bank.search(actor(), {'account_number':number})
            if not accounts: raise BankError('Account Not Found')
            if kind == 'withdrawal' and amount > accounts[0]['balance_cents'] and request.form.get('confirm_overdraft') != 'yes':
                return render_template('confirm.html', title='Negative balance warning',
                    message=f'This withdrawal would make the balance {money(accounts[0]["balance_cents"] - amount)}.',
                    values={k:request.form.get(k, '') for k in ('account_number','amount','method','conductor')})
            app.bank.transact(actor(), number, title, request.form.get('amount', ''),
                request.form.get('method', ''), request.form.get('conductor', '').strip(),
                confirmed=request.form.get('confirm_overdraft') == 'yes')
            flash(f'{title} completed for account {number}.', 'success')
            return redirect(url_for('details', number=number))
        return render_template('transaction.html', title=title, number=request.args.get('account', ''))

    @app.route('/transfer', methods=['GET', 'POST'])
    @protected()
    def transfer():
        if request.method == 'POST':
            source = integer('source'); destination = integer('destination'); amount = cents(request.form.get('amount', ''))
            if source == destination: raise BankError('Source and destination must be different.')
            accounts = app.bank.search(actor(), {'account_number':source})
            if not accounts: raise BankError('Account Not Found')
            if amount > accounts[0]['balance_cents'] and request.form.get('confirm_overdraft') != 'yes':
                return render_template('confirm.html', title='Negative balance warning',
                    message=f'This transfer would make the source balance {money(accounts[0]["balance_cents"]-amount)}.',
                    values={k:request.form.get(k, '') for k in ('source','destination','amount')})
            app.bank.transfer(actor(), source, destination, request.form.get('amount', ''),
                              confirmed=request.form.get('confirm_overdraft') == 'yes')
            flash('Transfer completed. Both balances and transaction records were saved.', 'success')
            return redirect(url_for('details', number=source))
        return render_template('transfer.html', title='Transfer funds')

    def report_args():
        return {k:request.values.get(k, '').strip() for k in ('start','end','staff','account','action')}

    @app.route('/reports', methods=['GET', 'POST'])
    @protected()
    def reports():
        report = request.values.get('report', 'Transactions')
        args = report_args(); rows = app.bank.reports(actor(), report, **args)
        if request.method == 'POST':
            stream = io.StringIO(newline='')
            if rows:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader()
                for row in rows:
                    writer.writerow({k: ("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
            with app.bank.transaction() as con:
                app.bank.authorize(con, actor()); app.bank.audit(con, actor(), 'Export CSV', details={'report':report,'rows':len(rows),'interface':'browser'})
            app.bank.flush_logs()
            return Response('\ufeff'+stream.getvalue(), mimetype='text/csv',
                            headers={'Content-Disposition':'attachment; filename="bank_report.csv"'})
        return render_template('reports.html', title='Reports', report=report, filters=args, rows=rows,
                               types=['Transactions','Accounts'] + (['Audit','Cash Review','Staff'] if g.staff['role']=='Admin' else []))

    @app.route('/staff', methods=['GET', 'POST'])
    @protected(admin=True)
    def staff_accounts():
        if request.method == 'POST':
            identifier = app.bank.create_staff(actor(), request.form.get('username', ''),
                                               request.form.get('password', ''), request.form.get('role', 'Teller'))
            flash(f'Staff account {identifier} created.', 'success'); return redirect(url_for('staff_accounts'))
        return render_template('staff.html', title='Staff accounts', rows=app.bank.reports(actor(), 'Staff'))

    @app.route('/reviews', methods=['GET', 'POST'])
    @protected(admin=True)
    def reviews():
        if request.method == 'POST':
            if request.form.get('operation') == 'cash':
                app.bank.review(actor(), request.form.get('review_id', ''), request.form.get('notes', ''))
            elif request.form.get('operation') == 'suspicion':
                app.bank.suspicious_flag(actor(), integer('account_number'), request.form.get('notes', ''))
            else: raise BankError('Choose a valid review action.')
            flash('Restricted review saved. No government filing was submitted.', 'success')
            return redirect(url_for('reviews'))
        return render_template('reviews.html', title='Restricted reviews', rows=app.bank.reports(actor(), 'Cash Review'))

    @app.route('/verify', methods=['GET', 'POST'])
    @protected(admin=True)
    def verify():
        if request.method == 'POST':
            app.bank.verify_customer(actor(), request.form.get('customer_id', '').strip(), request.form.get('dob', ''), request.form.get('id_reference', ''))
            flash('Simulated customer verification recorded.', 'success'); return redirect(url_for('verify'))
        return render_template('verify.html', title='Verify imported customer')

    @app.post('/logs/retry')
    @protected()
    def retry_logs():
        success = app.bank.flush_logs()
        flash('Committed records exported.' if success else 'Export is still pending. Check application.log.', 'success' if success else 'warning')
        return redirect(url_for('dashboard'))

    return app

if __name__ == '__main__':
    try: app = create_app()
    except BankError as exc: print('Startup error:', exc); raise SystemExit(1)
    app.run(host='127.0.0.1', port=5000, debug=False)
