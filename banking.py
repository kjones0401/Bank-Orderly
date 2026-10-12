"""Audited classroom banking service. All mutations use one DB transaction.
SQLite is a local demonstration/test backend; MySQL is the assignment backend.
Financial records use integer cents, never binary floating point.
"""
import csv
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

class BankError(Exception):
    """A safe user-facing validation or processing error."""

FIELDS = ('first_name', 'middle_name', 'last_name', 'street_number', 'street_name',
          'city', 'state', 'zip_code')
SEARCH_FIELDS = FIELDS + ('account_number', 'customer_id', 'account_type', 'status',
                          'initial_cents', 'balance_cents', 'dob', 'id_reference',
                          'verification_status', 'created_at', 'closed_at', 'closure_reason')
MAX_CENTS = 999999999999  # Original DECIMAL(12,2) storage range.

def cents(value):
    """Accept positive finite monetary input with at most two decimal places."""
    try:
        amount = Decimal(str(value).strip().replace(',', '').replace('$', ''))
    except InvalidOperation as exc:
        raise BankError('Amount must be numeric.') from exc
    if not amount.is_finite() or amount <= 0:
        raise BankError('Amount must be finite and greater than zero.')
    if amount.as_tuple().exponent < -2:
        raise BankError('Amount cannot contain more than two decimal places.')
    if amount > Decimal(MAX_CENTS) / 100:
        raise BankError('Amount exceeds the supported storage range.')
    return int(amount * 100)

def money(value):
    return f'${Decimal(value) / 100:,.2f}'

def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')

def business_day():
    return datetime.now(ZoneInfo('America/New_York')).date().isoformat()

def password_hash(password, salt=None):
    if len(password) < 12:
        raise BankError('Use a password of at least 12 characters.')
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 300000).hex()
    return salt + ':' + digest

def password_matches(password, stored):
    salt, digest = stored.split(':')
    actual = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 300000).hex()
    return hmac.compare_digest(actual, digest)

SCHEMA = [
'''CREATE TABLE IF NOT EXISTS staff (id INTEGER PRIMARY KEY, username VARCHAR(80) UNIQUE NOT NULL,
 password_hash VARCHAR(200) NOT NULL, role VARCHAR(20) NOT NULL, active INTEGER NOT NULL,
 failures INTEGER NOT NULL DEFAULT 0, locked_until VARCHAR(40), created_at VARCHAR(40) NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS sequence (id INTEGER PRIMARY KEY, next_number INTEGER NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS customers (id VARCHAR(40) PRIMARY KEY, dob VARCHAR(10) NOT NULL,
 id_reference VARCHAR(100) NOT NULL, verification_status VARCHAR(20) NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS accounts (account_number INTEGER PRIMARY KEY, customer_id VARCHAR(40) NOT NULL,
 first_name VARCHAR(50) NOT NULL, middle_name VARCHAR(50) NOT NULL, last_name VARCHAR(50) NOT NULL,
 street_number VARCHAR(10) NOT NULL, street_name VARCHAR(100) NOT NULL, city VARCHAR(75) NOT NULL,
 state VARCHAR(2) NOT NULL, zip_code VARCHAR(5) NOT NULL, account_type VARCHAR(20) NOT NULL,
 initial_cents BIGINT NOT NULL, balance_cents BIGINT NOT NULL, status VARCHAR(20) NOT NULL,
 created_at VARCHAR(40) NOT NULL, closed_at VARCHAR(40), closure_reason TEXT,
 FOREIGN KEY(customer_id) REFERENCES customers(id))''',
'''CREATE TABLE IF NOT EXISTS transactions (id VARCHAR(40) PRIMARY KEY, timestamp VARCHAR(40) NOT NULL,
 business_date VARCHAR(10) NOT NULL, kind VARCHAR(30) NOT NULL, account_number INTEGER NOT NULL,
 related_account INTEGER, amount_cents BIGINT NOT NULL, before_cents BIGINT NOT NULL,
 after_cents BIGINT NOT NULL, method VARCHAR(20) NOT NULL, conductor_id VARCHAR(40) NOT NULL,
 staff_id INTEGER NOT NULL, group_id VARCHAR(40) NOT NULL, overdraft_confirmed INTEGER NOT NULL,
 FOREIGN KEY(account_number) REFERENCES accounts(account_number), FOREIGN KEY(staff_id) REFERENCES staff(id))''',
'''CREATE TABLE IF NOT EXISTS audit (id VARCHAR(40) PRIMARY KEY, timestamp VARCHAR(40) NOT NULL,
 staff_id INTEGER, action VARCHAR(40) NOT NULL, account_number INTEGER, details TEXT NOT NULL)''',
'''CREATE TABLE IF NOT EXISTS reviews (id VARCHAR(40) PRIMARY KEY, business_date VARCHAR(10) NOT NULL,
 person_id VARCHAR(40) NOT NULL, direction VARCHAR(10) NOT NULL, total_cents BIGINT NOT NULL,
 due_date VARCHAR(10) NOT NULL, status VARCHAR(30) NOT NULL, reviewer INTEGER, notes TEXT,
 UNIQUE(business_date, person_id, direction))''',
'''CREATE TABLE IF NOT EXISTS outbox (id VARCHAR(40) PRIMARY KEY, payload TEXT NOT NULL, exported INTEGER NOT NULL)'''
]

class Bank:
    def __init__(self, directory, backend='sqlite', db_config=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.backend = backend
        self.db_config = db_config or {}
        self._export_lock = threading.Lock()
        self.export_pending = False
        self.logger = logging.getLogger('bank.' + str(self.directory))
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.FileHandler(self.directory / 'application.log', encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
            self.logger.addHandler(handler)
        self._initialize()
        self.flush_logs()

    def connect(self):
        if self.backend == 'sqlite':
            con = sqlite3.connect(self.directory / 'bank.sqlite', timeout=30)
            con.row_factory = sqlite3.Row
            con.execute('PRAGMA foreign_keys=ON')
            return con
        if self.backend != 'mysql':
            raise BankError('BANK_BACKEND must be mysql or sqlite.')
        import mysql.connector
        return mysql.connector.connect(**self.db_config)

    def execute(self, con, sql, parameters=()):
        cursor = con.cursor(dictionary=True) if self.backend == 'mysql' else con.cursor()
        cursor.execute(sql.replace('?', '%s') if self.backend == 'mysql' else sql, parameters)
        return cursor

    def rows(self, con, sql, parameters=()):
        cur = self.execute(con, sql, parameters)
        result = [dict(row) for row in cur.fetchall()]
        cur.close()
        return result

    @contextmanager
    def transaction(self):
        con = None
        try:
            con = self.connect()
            if self.backend == 'sqlite':
                con.execute('BEGIN IMMEDIATE')
            else:
                con.start_transaction()
                # Serialize writers on the sequence row: simple and safe for a class project.
                self.rows(con, 'SELECT * FROM sequence WHERE id=1 FOR UPDATE')
            yield con
            con.commit()
        except BankError:
            if con: con.rollback()
            raise
        except Exception as exc:
            if con: con.rollback()
            self.logger.error('Database operation failed: %s', type(exc).__name__)
            raise BankError('Database operation failed. Check application.log; no success is assumed.') from exc
        finally:
            if con: con.close()

    def _initialize(self):
        con = None
        try:
            con = self.connect()
            for sql in SCHEMA:
                if self.backend == 'mysql': sql += ' ENGINE=InnoDB'
                self.execute(con, sql).close()
            if not self.rows(con, 'SELECT * FROM sequence WHERE id=1'):
                self.execute(con, 'INSERT INTO sequence VALUES (1,1000)').close()
            con.commit()
        except Exception as exc:
            raise BankError('Cannot initialize database. Check environment settings and create the v3 database.') from exc
        finally:
            if con: con.close()

    def audit(self, con, staff_id, action, account=None, details=None):
        item = dict(id=secrets.token_hex(16), timestamp=stamp(), staff_id=staff_id,
                    action=action, account_number=account, details=details or {})
        self.execute(con, 'INSERT INTO audit VALUES (?,?,?,?,?,?)',
                     (item['id'], item['timestamp'], staff_id, action, account, json.dumps(item['details']))).close()
        self.enqueue(con, {'record_type': 'audit', **item})

    def enqueue(self, con, record):
        self.execute(con, 'INSERT INTO outbox VALUES (?,?,0)',
                     (secrets.token_hex(16), json.dumps(record))).close()

    def flush_logs(self):
        """Export committed outbox events; retries can repeat IDs, never invent transactions."""
        with self._export_lock:
            try:
                with self.transaction() as con:
                    for row in self.rows(con, 'SELECT * FROM outbox WHERE exported=0'):
                        record = json.loads(row['payload'])
                        filename = 'transactions.jsonl' if record['record_type'] == 'transaction' else 'audit.jsonl'
                        with (self.directory / filename).open('a', encoding='utf-8') as stream:
                            stream.write(json.dumps(record) + '\n'); stream.flush(); os.fsync(stream.fileno())
                        self.execute(con, 'UPDATE outbox SET exported=1 WHERE id=?', (row['id'],)).close()
                    accounts = self.rows(con, 'SELECT account_number,customer_id,balance_cents,status FROM accounts ORDER BY account_number')
                    temporary = self.directory / 'balances.tmp'
                    with temporary.open('w', encoding='utf-8') as stream:
                        json.dump({'timestamp': stamp(), 'accounts': accounts}, stream, indent=2)
                        stream.flush(); os.fsync(stream.fileno())
                    os.replace(temporary, self.directory / 'balance_snapshot.json')
                self.export_pending = False
                return True
            except Exception:
                self.export_pending = True
                self.logger.error('External export pending; committed records remain in database outbox.')
                return False

    def needs_bootstrap(self):
        with self.transaction() as con:
            return not self.rows(con, 'SELECT id FROM staff')

    def authorize(self, con, actor, admin=False):
        rows = self.rows(con, 'SELECT * FROM staff WHERE id=? AND active=1', (actor,))
        if not rows or (admin and rows[0]['role'] != 'Admin'):
            raise BankError('Access denied. An authorized staff login is required.')
        return rows[0]

    def create_staff(self, actor, username, password, role='Teller'):
        username = username.strip()
        if not username or len(username)>80 or role not in ('Admin', 'Teller'):
            raise BankError('Enter a username and valid staff role.')
        hashed = password_hash(password)
        with self.transaction() as con:
            existing = self.rows(con, 'SELECT id FROM staff')
            if existing: self.authorize(con, actor, True)
            elif role != 'Admin': raise BankError('The first staff account must be an Admin.')
            if self.rows(con, 'SELECT id FROM staff WHERE username=?', (username,)):
                raise BankError('Username already exists.')
            identifier = max([r['id'] for r in existing], default=0) + 1
            self.execute(con, 'INSERT INTO staff (id,username,password_hash,role,active,created_at) VALUES (?,?,?,?,1,?)',
                         (identifier, username, hashed, role, stamp())).close()
            self.audit(con, actor or identifier, 'Create Staff', details={'username':username,'role':role})
        self.flush_logs()
        return identifier

    def login(self, username, password):
        failure = None; staff = None
        with self.transaction() as con:
            found = self.rows(con, 'SELECT * FROM staff WHERE username=?', (username.strip(),))
            staff = found[0] if found else None
            locked = staff and staff['locked_until'] and staff['locked_until'] > stamp()
            if not staff or not staff['active'] or locked or not password_matches(password, staff['password_hash']):
                if staff and not locked:
                    count = staff['failures'] + 1
                    until = (datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat() if count>=5 else None
                    self.execute(con, 'UPDATE staff SET failures=?,locked_until=? WHERE id=?', (count,until,staff['id'])).close()
                self.audit(con, None, 'Failed Login', details={'username':username.strip()})
                failure = 'Invalid login or account temporarily locked.'
            else:
                self.execute(con, 'UPDATE staff SET failures=0,locked_until=NULL WHERE id=?', (staff['id'],)).close()
                self.audit(con, staff['id'], 'Login')
        self.flush_logs()
        if failure: raise BankError(failure)
        return {'id':staff['id'], 'username':staff['username'], 'role':staff['role']}

    def logout(self, actor):
        with self.transaction() as con:
            self.authorize(con, actor); self.audit(con, actor, 'Logout')
        self.flush_logs()

    def validate_details(self, details):
        result = {key: str(details.get(key, '')).strip() for key in FIELDS}
        if not all(result.values()): raise BankError('All name and address fields are required.')
        for key in FIELDS[:3]:
            if len(result[key])>50 or not all(c.isalpha() or c in " '-" for c in result[key]):
                raise BankError('Names may contain letters, spaces, apostrophes, and hyphens only (maximum 50 characters).')
        if not result['street_number'].isdigit() or len(result['street_number'])>10:
            raise BankError('Street number must be numeric (maximum 10 digits).')
        if len(result['street_name'])>100 or not all(c.isalnum() or c in " .'-" for c in result['street_name']):
            raise BankError('Invalid street name.')
        if len(result['city'])>75 or not all(c.isalpha() or c in " .'-" for c in result['city']):
            raise BankError('Invalid city.')
        result['state'] = result['state'].upper()
        if len(result['state'])!=2 or not result['state'].isalpha(): raise BankError('State requires two letters.')
        if len(result['zip_code'])!=5 or not result['zip_code'].isdigit(): raise BankError('ZIP requires five digits.')
        return result

    def account(self, con, number, active=False):
        rows = self.rows(con, 'SELECT a.*,c.dob,c.id_reference,c.verification_status FROM accounts a JOIN customers c ON c.id=a.customer_id WHERE account_number=?', (number,))
        if not rows: raise BankError('Account Not Found')
        if active and rows[0]['status'] != 'Active': raise BankError('Closed accounts cannot receive transactions or edits.')
        return rows[0]

    def create_account(self, actor, details, amount, method='Cash', conductor='', customer_id='', dob='', id_reference='', verified=False):
        details = self.validate_details(details); amount = cents(amount)
        self.validate_method(method)
        with self.transaction() as con:
            self.authorize(con, actor)
            if customer_id:
                customers = self.rows(con, 'SELECT * FROM customers WHERE id=?', (customer_id,))
                if not customers: raise BankError('Existing customer ID not found.')
                if customers[0]['verification_status'] != 'Verified': raise BankError('Verify the imported customer before opening another account.')
            else:
                try:
                    parsed = datetime.strptime(dob, '%Y-%m-%d').date()
                    if parsed > datetime.now().date(): raise ValueError()
                except ValueError: raise BankError('Enter a valid birth date as YYYY-MM-DD.')
                if not id_reference.strip() or len(id_reference)>100 or not verified:
                    raise BankError('A fictional identification reference and verification confirmation are required.')
                customer_id = secrets.token_hex(16)
                self.execute(con, 'INSERT INTO customers VALUES (?,?,?,?)',
                             (customer_id, dob, id_reference.strip(), 'Verified')).close()
            number = self.rows(con, 'SELECT next_number FROM sequence WHERE id=1')[0]['next_number']
            self.execute(con, 'UPDATE sequence SET next_number=next_number+1 WHERE id=1').close()
            columns = ('account_number','customer_id') + FIELDS + ('account_type','initial_cents','balance_cents','status','created_at')
            values = (number,customer_id) + tuple(details[k] for k in FIELDS) + ('Checking',amount,0,'Active',stamp())
            self.execute(con, 'INSERT INTO accounts ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')', values).close()
            account = self.account(con, number)
            self.record(con, actor, account, 'Initial Deposit', amount, method, conductor or customer_id)
            self.audit(con, actor, 'Create Account', number, {'customer_id':customer_id})
        self.flush_logs()
        return number

    def validate_method(self, method):
        if method not in ('Cash', 'Electronic'): raise BankError('Select Cash or Electronic. Check deposits are not implemented.')

    def record(self, con, actor, account, kind, amount, method, conductor, related=None, group=None, confirmed=False):
        if method=='Cash' and not self.rows(con, "SELECT id FROM customers WHERE id=? AND verification_status='Verified'", (conductor,)):
            raise BankError('Cash conductor must be an existing verified customer ID; register the person first.')
        increase = kind in ('Deposit','Initial Deposit','Transfer In')
        before = account['balance_cents']; after = before + (amount if increase else -amount)
        if abs(after)>MAX_CENTS: raise BankError('Resulting balance exceeds the supported range.')
        item = dict(id=secrets.token_hex(16),timestamp=stamp(),business_date=business_day(),kind=kind,
                    account_number=account['account_number'],related_account=related,amount_cents=amount,
                    before_cents=before,after_cents=after,method=method,conductor_id=conductor,
                    staff_id=actor,group_id=group or secrets.token_hex(16),overdraft_confirmed=int(confirmed))
        self.execute(con, 'UPDATE accounts SET balance_cents=? WHERE account_number=?', (after,account['account_number'])).close()
        self.execute(con, 'INSERT INTO transactions ('+','.join(item)+') VALUES ('+','.join('?' for _ in item)+')', tuple(item.values())).close()
        self.enqueue(con, {'record_type':'transaction',**item})
        self.audit(con, actor, kind, account['account_number'], {'transaction_id':item['id'],'before_cents':before,'after_cents':after,'overdraft_confirmed':confirmed})
        if method=='Cash': self.refresh_reviews(con, item['business_date'])

    def refresh_reviews(self, con, day):
        """Aggregate both conductor and beneficiary identities, without double counting."""
        transactions = self.rows(con, '''SELECT t.*,a.customer_id FROM transactions t JOIN accounts a
             ON t.account_number=a.account_number WHERE t.business_date=? AND t.method='Cash' ''', (day,))
        totals = {}
        for t in transactions:
            direction = 'In' if t['kind'] in ('Deposit','Initial Deposit') else 'Out'
            for person in {t['conductor_id'],t['customer_id']}:
                totals[(person,direction)] = totals.get((person,direction),0)+t['amount_cents']
        for (person,direction),total in totals.items():
            if total<=1000000: continue
            existing = self.rows(con, 'SELECT id,total_cents FROM reviews WHERE business_date=? AND person_id=? AND direction=?', (day,person,direction))
            if existing:
                if existing[0]['total_cents'] != total:
                    self.execute(con, "UPDATE reviews SET total_cents=?,status='Pending simulation',reviewer=NULL,notes=NULL WHERE id=?", (total,existing[0]['id'])).close()
            else:
                due = (datetime.strptime(day,'%Y-%m-%d')+timedelta(days=15)).date().isoformat()
                self.execute(con, 'INSERT INTO reviews VALUES (?,?,?,?,?,?,?,NULL,NULL)',
                             (secrets.token_hex(16),day,person,direction,total,due,'Pending simulation')).close()

    def transact(self, actor, number, kind, amount, method='Cash', conductor='', confirmed=False):
        amount=cents(amount); self.validate_method(method)
        if kind not in ('Deposit','Withdrawal'): raise BankError('Invalid transaction type.')
        with self.transaction() as con:
            self.authorize(con, actor); account=self.account(con,number,True)
            if kind=='Withdrawal' and amount>account['balance_cents'] and not confirmed:
                raise BankError('Explicit negative-balance confirmation is required.')
            self.record(con,actor,account,kind,amount,method,conductor or account['customer_id'],confirmed=confirmed)
        self.flush_logs()

    def transfer(self, actor, source, destination, amount, confirmed=False):
        amount=cents(amount)
        if source==destination: raise BankError('Source and destination must be different.')
        with self.transaction() as con:
            self.authorize(con,actor); a=self.account(con,source,True); b=self.account(con,destination,True)
            if amount>a['balance_cents'] and not confirmed: raise BankError('Explicit negative-balance confirmation is required.')
            group=secrets.token_hex(16)
            if amount >= 300000 and a['customer_id'] != b['customer_id']:
                self.audit(con,actor,'Transfer Record Review',source,{'group_id':group,'destination':destination,'amount_cents':amount,'simulation':True,'note':'Review applicable $3,000 funds-transfer recordkeeping requirements and exceptions.'})
            self.record(con,actor,a,'Transfer Out',amount,'Electronic',a['customer_id'],destination,group,confirmed)
            self.record(con,actor,b,'Transfer In',amount,'Electronic',a['customer_id'],source,group)
        self.flush_logs()

    def edit(self, actor, number, details):
        details=self.validate_details(details)
        with self.transaction() as con:
            self.authorize(con,actor); old=self.account(con,number,True)
            self.execute(con,'UPDATE accounts SET '+','.join(k+'=?' for k in FIELDS)+' WHERE account_number=?',
                         tuple(details[k] for k in FIELDS)+(number,)).close()
            self.audit(con,actor,'Edit Account',number,{'before':{k:old[k] for k in FIELDS},'after':details})
        self.flush_logs()

    def close_account(self, actor, number, reason):
        if not reason.strip(): raise BankError('Reason for Account Closure is required.')
        with self.transaction() as con:
            self.authorize(con,actor); account=self.account(con,number,True)
            if account['balance_cents']!=0: raise BankError('Project policy: settle the account to a zero balance before closure.')
            self.execute(con,"UPDATE accounts SET status='Closed',closed_at=?,closure_reason=? WHERE account_number=?",
                         (stamp(),reason.strip(),number)).close()
            self.audit(con,actor,'Close Account',number,{'reason':reason.strip()})
        self.flush_logs()

    def search(self, actor, criteria=None):
        criteria=criteria or {}; sql='SELECT a.*,c.dob,c.id_reference,c.verification_status FROM accounts a JOIN customers c ON c.id=a.customer_id WHERE 1=1'; params=[]
        for key,value in criteria.items():
            if key not in SEARCH_FIELDS: raise BankError('Unsupported search field.')
            if str(value).strip()=='': continue
            prefix='c.' if key in ('dob','id_reference','verification_status') else 'a.'
            if key in ('account_number','initial_cents','balance_cents'):
                try: value=int(value)
                except ValueError: raise BankError('Numeric search field requires an integer (balances use cents).')
                sql+=' AND '+prefix+key+'=?'; params.append(value)
            else:
                # Literal substring matching; wildcard characters are escaped.
                value=str(value).replace('!','!!').replace('%','!%').replace('_','!_')
                sql+=' AND '+prefix+key+" LIKE ? ESCAPE '!'"; params.append('%'+value+'%')
        with self.transaction() as con:
            self.authorize(con,actor); result=self.rows(con,sql+' ORDER BY a.account_number',params)
            self.audit(con,actor,'Search Accounts',details={'fields':list(criteria),'matches':len(result)})
        self.flush_logs(); return result

    def reports(self, actor, report='Transactions', start='', end='', staff='', account='', action=''):
        if report not in ('Transactions','Audit','Accounts','Cash Review','Staff'): raise BankError('Invalid report.')
        for value in (start,end):
            if value:
                try: datetime.strptime(value,'%Y-%m-%d')
                except ValueError: raise BankError('Report dates must be YYYY-MM-DD.')
        if start and end and start>end: raise BankError('Start date must not follow end date.')
        with self.transaction() as con:
            user=self.authorize(con,actor,report in ('Audit','Cash Review','Staff'))
            if report=='Accounts': sql='SELECT * FROM accounts WHERE 1=1'; date_field='created_at'
            elif report=='Staff': sql='SELECT id,username,role,active,created_at FROM staff WHERE 1=1'; date_field='created_at'
            elif report=='Cash Review': sql='SELECT * FROM reviews WHERE 1=1'; date_field='business_date'
            else:
                table='transactions' if report=='Transactions' else 'audit'
                sql='SELECT * FROM '+table+' WHERE 1=1'; date_field='timestamp'
            params=[]
            if start: sql+=' AND '+date_field+'>=?'; params.append(start)
            if end: sql+=' AND '+date_field+'<?'; params.append((datetime.strptime(end,'%Y-%m-%d')+timedelta(days=1)).date().isoformat())
            if report in ('Transactions','Audit'):
                if user['role']=='Teller': staff=actor
                if staff:
                    try: staff=int(staff)
                    except ValueError: raise BankError('Staff ID must be numeric.')
                    sql+=' AND staff_id=?'; params.append(staff)
                if account:
                    try: account=int(account)
                    except ValueError: raise BankError('Account number must be numeric.')
                    sql+=' AND account_number=?'; params.append(account)
                if action: sql+=' AND '+('kind' if report=='Transactions' else 'action')+'=?'; params.append(action)
            elif account and report=='Accounts': sql+=' AND account_number=?'; params.append(account)
            result=self.rows(con,sql+' ORDER BY '+date_field,params)
            self.audit(con,actor,'Generate Report',details={'report':report,'start':start,'end':end,'staff':staff,'account':account,'action':action,'rows':len(result)})
        self.flush_logs(); return result

    def review(self, actor, review_id, notes):
        if not notes.strip(): raise BankError('Review notes are required.')
        with self.transaction() as con:
            self.authorize(con,actor,True)
            if not self.rows(con,'SELECT id FROM reviews WHERE id=?',(review_id,)): raise BankError('Review not found.')
            self.execute(con,"UPDATE reviews SET status='Reviewed simulation',reviewer=?,notes=? WHERE id=?",(actor,notes.strip(),review_id)).close()
            self.audit(con,actor,'Review Cash Alert',details={'review_id':review_id,'notes':notes.strip()})
        self.flush_logs()

    def suspicious_flag(self, actor, number, notes):
        if not notes.strip(): raise BankError('Restricted review notes are required.')
        with self.transaction() as con:
            self.authorize(con,actor,True); self.account(con,number)
            self.audit(con,actor,'Restricted Suspicion Review',number,{'notes':notes.strip(),'simulation':True})
        self.flush_logs()

    def export_csv(self, actor, rows, path):
        """Neutralize spreadsheet formulas in user-controlled cells."""
        with self.transaction() as con:
            self.authorize(con,actor)
            self.audit(con,actor,'Export CSV',details={'rows':len(rows)})
        with open(path,'w',newline='',encoding='utf-8-sig') as stream:
            if rows:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader()
                for row in rows:
                    writer.writerow({k: ("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v) for k,v in row.items()})
        self.flush_logs()

    def verify_customer(self, actor, customer_id, dob, reference):
        try:
            date = datetime.strptime(dob, '%Y-%m-%d').date()
            if date > datetime.now().date(): raise ValueError()
        except ValueError: raise BankError('Enter a valid birth date YYYY-MM-DD.')
        if not reference.strip() or len(reference)>100: raise BankError('A fictional ID reference is required.')
        with self.transaction() as con:
            self.authorize(con,actor,True)
            if not self.rows(con,'SELECT id FROM customers WHERE id=?',(customer_id,)): raise BankError('Customer not found.')
            self.execute(con,"UPDATE customers SET dob=?,id_reference=?,verification_status='Verified' WHERE id=?",(dob,reference.strip(),customer_id)).close()
            self.audit(con,actor,'Verify Customer',details={'customer_id':customer_id,'simulation':True})
        self.flush_logs()
