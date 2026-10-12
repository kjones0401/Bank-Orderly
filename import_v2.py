"""Read-only import of v2 MySQL records into a v3 database with no accounts.
Run after creating the first v3 Admin. Historical identities/methods are unknown.
"""
import os
import secrets
from decimal import Decimal
from banking import Bank, BankError, FIELDS
from config import DATA_DIR, BACKEND, DB_CONFIG

def import_legacy(bank, source, actor):
    cursor=source.cursor(dictionary=True)
    try:
        cursor.execute('SELECT * FROM accounts ORDER BY account_number'); accounts=cursor.fetchall()
        cursor.execute('SELECT * FROM transactions ORDER BY transaction_id'); transactions=cursor.fetchall()
    finally: cursor.close()
    with bank.transaction() as con:
        bank.authorize(con,actor,True)
        if bank.rows(con,'SELECT account_number FROM accounts'): raise BankError('Target must contain no accounts. Import refused.')
        for a in accounts:
            customer=secrets.token_hex(16)
            bank.execute(con,'INSERT INTO customers VALUES (?,?,?,?)',(customer,'Unknown','Legacy: needs verification','Pending')).close()
            columns=('account_number','customer_id')+FIELDS+('account_type','initial_cents','balance_cents','status','created_at')
            values=(a['account_number'],customer)+tuple(a[k] for k in FIELDS)+(a['account_type'],int(Decimal(a['initial_deposit'])*100),int(Decimal(a['current_balance'])*100),'Active',a['created_at'].isoformat())
            bank.execute(con,'INSERT INTO accounts ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',values).close()
        for t in transactions:
            amount=int(Decimal(t['amount'])*100); after=int(Decimal(t['balance_after'])*100)
            increase=t['transaction_type'] in ('Deposit','Initial Deposit','Transfer In')
            before=after-amount if increase else after+amount
            item=dict(id=secrets.token_hex(16),timestamp=t['timestamp'].isoformat(),business_date=t['timestamp'].date().isoformat(),kind=t['transaction_type'],account_number=t['account_number'],related_account=t['related_account'],amount_cents=amount,before_cents=before,after_cents=after,method='Legacy Unknown',conductor_id='Legacy Unknown',staff_id=actor,group_id='Legacy-'+str(t['transaction_id']),overdraft_confirmed=0)
            bank.execute(con,'INSERT INTO transactions ('+','.join(item)+') VALUES ('+','.join('?' for _ in item)+')',tuple(item.values())).close()
            bank.enqueue(con,{'record_type':'transaction','historical_staff_unknown':True,**item})
        bank.execute(con,'UPDATE sequence SET next_number=? WHERE id=1',(max([a['account_number'] for a in accounts],default=999)+1,)).close()
        bank.audit(con,actor,'Import v2',details={'accounts':len(accounts),'transactions':len(transactions),'historical_staff':'unknown; imported transaction staff_id identifies importer only'})
    bank.flush_logs()
    return len(accounts),len(transactions)

if __name__=='__main__':
    import getpass
    import mysql.connector
    bank=Bank(DATA_DIR,BACKEND,DB_CONFIG)
    staff=bank.login(input('v3 admin username: '),getpass.getpass('v3 admin password: '))
    source=mysql.connector.connect(**{**DB_CONFIG,'database':os.getenv('BANK_LEGACY_DB_NAME','simple_bank'),'user':os.getenv('BANK_LEGACY_DB_USER',DB_CONFIG['user']),'password':os.getenv('BANK_LEGACY_DB_PASSWORD',DB_CONFIG['password'])})
    try: print('Imported accounts, transactions:',import_legacy(bank,source,staff['id']))
    finally: source.close()
