"""Full logical backup/restore for classroom recovery testing.
Backups contain confidential data and password hashes; protect the files.
Restore refuses any target with existing staff/accounts.
"""
import json
import os
from pathlib import Path
from banking import Bank, BankError, stamp
from config import DATA_DIR, BACKEND, DB_CONFIG
TABLES=('staff','sequence','customers','accounts','transactions','audit','reviews')

def backup(bank,actor,path):
    with bank.transaction() as con:
        bank.authorize(con,actor,True)
        bank.audit(con,actor,'Full Backup')
        payload={'version':3,'timestamp':stamp(),'tables':{table:bank.rows(con,'SELECT * FROM '+table) for table in TABLES}}
    with Path(path).open('x',encoding='utf-8') as stream:
        json.dump(payload,stream,indent=2); stream.flush(); os.fsync(stream.fileno())
    try: os.chmod(path,0o600)
    except OSError: pass
    bank.flush_logs()

def restore(bank,path):
    payload=json.loads(Path(path).read_text(encoding='utf-8'))
    if payload.get('version')!=3 or set(payload.get('tables',{}))!=set(TABLES): raise BankError('Invalid backup format.')
    with bank.transaction() as con:
        if bank.rows(con,'SELECT id FROM staff') or bank.rows(con,'SELECT account_number FROM accounts'):
            raise BankError('Restore requires a new empty database; existing data will not be overwritten.')
        bank.execute(con,'DELETE FROM sequence').close()
        for table in TABLES:
            cursor=bank.execute(con,'SELECT * FROM '+table+' LIMIT 0')
            allowed=set(cursor.column_names) if bank.backend=='mysql' else set(r[0] for r in cursor.description)
            cursor.fetchall()
            cursor.close()
            for row in payload['tables'][table]:
                if set(row)!=allowed: raise BankError('Backup columns do not match schema.')
                bank.execute(con,'INSERT INTO '+table+' ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')',tuple(row.values())).close()
    bank.flush_logs()

if __name__=='__main__':
    import argparse
    import getpass
    parser=argparse.ArgumentParser(); parser.add_argument('operation',choices=['backup','restore']); parser.add_argument('path'); args=parser.parse_args()
    bank=Bank(DATA_DIR,BACKEND,DB_CONFIG)
    if args.operation=='backup':
        user=bank.login(input('Admin username: '),getpass.getpass('Password: ')); backup(bank,user['id'],args.path)
    else: restore(bank,args.path)
    print(args.operation.title()+' completed.')
