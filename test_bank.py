"""Service/integration tests using a real isolated SQLite database, not a fake repo."""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from banking import Bank, BankError, cents

DETAILS=dict(first_name='Jane',middle_name='Ann',last_name='Smith',street_number='123',street_name='Main Street',city='Owingsville',state='KY',zip_code='40360')

class BankingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.bank=Bank(self.temp.name)
        self.admin=self.bank.create_staff(None,'admin','AdminPassword123!','Admin')
        self.teller=self.bank.create_staff(self.admin,'teller','TellerPassword123!')
    def tearDown(self):
        for h in list(self.bank.logger.handlers):h.close(); self.bank.logger.removeHandler(h)
        self.temp.cleanup()
    def create(self,amount='100',**options):
        return self.bank.create_account(self.admin,DETAILS,amount,dob='1980-01-01',id_reference='TEST-ID',verified=True,**options)
    def get(self,number):return self.bank.search(self.admin,{'account_number':number})[0]
    def test_sequential_numbers(self):self.assertEqual((self.create(),self.create()),(1000,1001))
    def test_search_all_matches(self):self.create(); self.create(); self.assertEqual(len(self.bank.search(self.admin,{'last_name':'Smi'})),2)
    def test_combined_search(self):self.create(); self.assertEqual(len(self.bank.search(self.admin,{'last_name':'Smith','city':'Lex'})),0)
    def test_search_each_field(self):
        n=self.create(); account=self.get(n)
        for field in ('first_name','middle_name','last_name','street_number','street_name','city','state','zip_code','account_number','customer_id','account_type','status','initial_cents','balance_cents','dob','id_reference','verification_status','created_at'):
            with self.subTest(field=field): self.assertEqual(len(self.bank.search(self.admin,{field:account[field]})),1)
    def test_literal_sql_injection_search(self):self.create(); self.assertEqual(self.bank.search(self.admin,{'last_name':"' OR 1=1 --"}),[])
    def test_literal_wildcard(self):self.create(); self.assertEqual(self.bank.search(self.admin,{'last_name':'%'}),[])
    def test_edit_audit(self):
        n=self.create(); self.bank.edit(self.admin,n,{**DETAILS,'city':'Lexington'})
        self.assertEqual(self.get(n)['city'],'Lexington')
        rows=self.bank.reports(self.admin,'Audit',action='Edit Account'); self.assertIn('Owingsville',rows[0]['details'])
    def test_deposit_withdraw(self):
        n=self.create(); self.bank.transact(self.teller,n,'Deposit','20'); self.bank.transact(self.teller,n,'Withdrawal','30')
        self.assertEqual(self.get(n)['balance_cents'],9000)
    def test_overdraft_requires_confirmation(self):
        n=self.create()
        with self.assertRaises(BankError):self.bank.transact(self.teller,n,'Withdrawal','101')
        self.assertEqual(self.get(n)['balance_cents'],10000)
        self.bank.transact(self.teller,n,'Withdrawal','101',confirmed=True); self.assertEqual(self.get(n)['balance_cents'],-100)
    def test_transfer(self):
        a=self.create(); b=self.create(); self.bank.transfer(self.teller,a,b,'25')
        self.assertEqual((self.get(a)['balance_cents'],self.get(b)['balance_cents']),(7500,12500))
        rows=self.bank.reports(self.admin,'Transactions',action='Transfer Out'); self.assertEqual(rows[0]['staff_id'],self.teller)
    def test_transfer_same_account(self):
        a=self.create()
        with self.assertRaises(BankError):self.bank.transfer(self.admin,a,a,'1')
    def test_transfer_rollback(self):
        a=self.create(); b=self.create(); original=self.bank.record
        def fail_second(con,actor,account,kind,*args,**kwargs):
            if kind=='Transfer In': raise BankError('Injected failure')
            return original(con,actor,account,kind,*args,**kwargs)
        with patch.object(self.bank,'record',side_effect=fail_second):
            with self.assertRaises(BankError):self.bank.transfer(self.admin,a,b,'25')
        self.assertEqual((self.get(a)['balance_cents'],self.get(b)['balance_cents']),(10000,10000))
        self.assertEqual(self.bank.reports(self.admin,'Transactions',action='Transfer Out'),[])
    def test_closure_reason_required(self):
        a=self.create()
        with self.assertRaises(BankError):self.bank.close_account(self.admin,a,' ')
    def test_closure_zero_policy(self):
        a=self.create()
        with self.assertRaises(BankError):self.bank.close_account(self.admin,a,'Requested')
    def test_closed_account_preserved_and_blocked(self):
        a=self.create(); self.bank.transact(self.admin,a,'Withdrawal','100'); self.bank.close_account(self.teller,a,'Customer request')
        self.assertEqual(self.get(a)['closure_reason'],'Customer request')
        for action in ('Deposit','Withdrawal'):
            with self.assertRaises(BankError):self.bank.transact(self.admin,a,action,'1')
        with self.assertRaises(BankError):self.bank.edit(self.admin,a,DETAILS)
        self.assertEqual(len(self.bank.reports(self.admin,'Transactions',account=a)),2)
    def test_transfer_closed(self):
        a=self.create(); b=self.create(); self.bank.transact(self.admin,b,'Withdrawal','100'); self.bank.close_account(self.admin,b,'Request')
        with self.assertRaises(BankError):self.bank.transfer(self.admin,a,b,'1')
    def test_invalid_money(self):
        for value in ('','abc','0','-1','1.999','NaN','Infinity','1e999'):
            with self.subTest(value=value),self.assertRaises(BankError):cents(value)
    def test_valid_money(self):self.assertEqual(cents('$1,234.50'),123450)
    def test_service_validation(self):
        for updates in ({'middle_name':''},{'zip_code':'1234'},{'street_number':'abc'},{'state':'KYY'},{'first_name':'123'}):
            with self.subTest(updates=updates),self.assertRaises(BankError):
                self.bank.create_account(self.admin,{**DETAILS,**updates},'100',dob='1980-01-01',id_reference='TEST',verified=True)
    def test_identity_required(self):
        with self.assertRaises(BankError):self.bank.create_account(self.admin,DETAILS,'100')
    def test_ctr_exact_boundary(self):
        self.create('10000'); self.assertEqual(self.bank.reports(self.admin,'Cash Review'),[])
    def test_ctr_over_boundary(self):
        self.create('10000.01'); rows=self.bank.reports(self.admin,'Cash Review'); self.assertEqual(len(rows),1); self.assertEqual(rows[0]['total_cents'],1000001)
    def test_ctr_multiple_accounts_and_tellers(self):
        a=self.create('6000'); customer=self.get(a)['customer_id']; b=self.create('1',customer_id=customer,method='Electronic')
        self.bank.transact(self.teller,b,'Deposit','5000'); rows=self.bank.reports(self.admin,'Cash Review'); self.assertEqual(rows[0]['total_cents'],1100000)
    def test_cash_not_net(self):
        a=self.create('11000'); self.bank.transact(self.admin,a,'Withdrawal','4000')
        self.assertEqual(self.bank.reports(self.admin,'Cash Review')[0]['total_cents'],1100000)
    def test_electronic_not_cash(self):self.create('15000',method='Electronic'); self.assertEqual(self.bank.reports(self.admin,'Cash Review'),[])
    def test_cash_conductor_cross_owners(self):
        a=self.create('1',method='Electronic'); b=self.create('1',method='Electronic'); c=self.get(a)['customer_id']
        self.bank.transact(self.admin,a,'Deposit','6000',conductor=c); self.bank.transact(self.teller,b,'Deposit','5000',conductor=c)
        rows=self.bank.reports(self.admin,'Cash Review'); match=[r for r in rows if r['person_id']==c]; self.assertEqual(match[0]['total_cents'],1100000)
    def test_invalid_conductor_rolls_back(self):
        a=self.create()
        with self.assertRaises(BankError):self.bank.transact(self.admin,a,'Deposit','1',conductor='missing')
        self.assertEqual(self.get(a)['balance_cents'],10000)
    def test_login(self):self.assertEqual(self.bank.login('teller','TellerPassword123!')['role'],'Teller')
    def test_failed_login_persisted(self):
        with self.assertRaises(BankError):self.bank.login('admin','bad')
        self.assertEqual(len(self.bank.reports(self.admin,'Audit',action='Failed Login')),1)
    def test_lockout(self):
        for i in range(5):
            with self.assertRaises(BankError):self.bank.login('teller','bad')
        with self.assertRaises(BankError):self.bank.login('teller','TellerPassword123!')
    def test_password_not_plaintext(self):
        with self.bank.transaction() as con:staff=self.bank.rows(con,'SELECT password_hash FROM staff WHERE id=?',(self.admin,))[0]
        self.assertNotIn('AdminPassword',staff['password_hash'])
    def test_admin_permissions(self):
        with self.assertRaises(BankError):self.bank.create_staff(self.teller,'evil','PasswordLong123!','Admin')
        for report in ('Audit','Cash Review','Staff'):
            with self.assertRaises(BankError):self.bank.reports(self.teller,report)
    def test_unauthorized_mutation(self):
        a=self.create()
        with self.assertRaises(BankError):self.bank.transact(999,a,'Deposit','5')
    def test_teller_report_scoped(self):
        a=self.create(); self.bank.transact(self.teller,a,'Deposit','1')
        rows=self.bank.reports(self.teller,'Transactions',staff=self.admin); self.assertEqual(len(rows),1); self.assertEqual(rows[0]['staff_id'],self.teller)
    def test_report_date_validation(self):
        with self.assertRaises(BankError):self.bank.reports(self.admin,start='not a date')
        with self.assertRaises(BankError):self.bank.reports(self.admin,start='2026-10-08',end='2026-10-07')
    def test_report_filters(self):
        a=self.create(); self.bank.transact(self.teller,a,'Deposit','1'); self.assertEqual(len(self.bank.reports(self.admin,staff=self.teller,account=a,action='Deposit')),1)
    def test_review(self):
        self.create('11000'); r=self.bank.reports(self.admin,'Cash Review')[0]; self.bank.review(self.admin,r['id'],'Checked simulation')
        self.assertEqual(self.bank.reports(self.admin,'Cash Review')[0]['reviewer'],self.admin)
    def test_logs_snapshot(self):
        a=self.create(); self.bank.transact(self.admin,a,'Deposit','1')
        records=[json.loads(line) for line in (self.bank.directory/'transactions.jsonl').read_text().splitlines()]
        self.assertEqual(records[-1]['after_cents'],10100)
        snapshot=json.loads((self.bank.directory/'balance_snapshot.json').read_text()); self.assertEqual(snapshot['accounts'][0]['balance_cents'],10100)
    def test_export_failure_retry(self):
        a=self.create()
        with patch('banking.os.fsync',side_effect=OSError('disk full')):self.bank.transact(self.admin,a,'Deposit','1')
        self.assertEqual(self.get(a)['balance_cents'],10100); self.assertTrue(self.bank.flush_logs())
    def test_restart_persistence(self):
        a=self.create(); other=Bank(self.temp.name); self.assertEqual(other.search(self.admin,{'account_number':a})[0]['balance_cents'],10000)
    def test_concurrent_deposits(self):
        a=self.create()
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda _:self.bank.transact(self.teller,a,'Deposit','1'),range(10)))
        self.assertEqual(self.get(a)['balance_cents'],11000)
    def test_concurrent_number_allocation(self):
        with ThreadPoolExecutor(max_workers=3) as pool: numbers=list(pool.map(lambda _:self.create(),range(6)))
        self.assertEqual(sorted(numbers),list(range(1000,1006)))
    def test_csv_formula_safe(self):
        path=self.bank.directory/'report.csv'; self.bank.export_csv(self.admin,[{'note':'=1+1'}],path)
        self.assertIn("'=1+1",path.read_text(encoding='utf-8-sig'))
    def test_database_outage(self):
        with patch.object(self.bank,'connect',side_effect=OSError('offline')):
            with self.assertRaises(BankError):self.bank.search(self.admin)

    def test_backup_restore(self):
        from recovery import backup,restore
        a=self.create(); path=self.bank.directory/'backup.json'; backup(self.bank,self.admin,path)
        other=Bank(self.bank.directory/'restored'); restore(other,path)
        self.assertEqual(other.search(self.admin,{'account_number':a})[0]['balance_cents'],10000)
        for handler in list(other.logger.handlers):handler.close();other.logger.removeHandler(handler)
        with self.assertRaises(BankError):restore(self.bank,path)
    def test_transfer_record_review(self):
        a=self.create('4000',method='Electronic');b=self.create('100',method='Electronic')
        self.bank.transfer(self.admin,a,b,'3000')
        self.assertEqual(len(self.bank.reports(self.admin,'Audit',action='Transfer Record Review')),1)
    def test_reopens_cash_review_after_more_cash(self):
        a=self.create('11000');r=self.bank.reports(self.admin,'Cash Review')[0]
        self.bank.review(self.admin,r['id'],'Reviewed');self.bank.transact(self.admin,a,'Deposit','1')
        self.assertEqual(self.bank.reports(self.admin,'Cash Review')[0]['status'],'Pending simulation')
    def test_legacy_import(self):
        from import_v2 import import_legacy
        from datetime import datetime
        class Cursor:
            def execute(inner,sql):inner.sql=sql
            def fetchall(inner):
                if 'FROM accounts' in inner.sql:
                    return [{**DETAILS,'account_number':1010,'initial_deposit':'100.00','current_balance':'120.00','account_type':'Checking','created_at':datetime(2026,1,1)}]
                return [{'transaction_id':1,'timestamp':datetime(2026,1,1),'transaction_type':'Initial Deposit','account_number':1010,'related_account':None,'amount':'100.00','balance_after':'100.00'},
                        {'transaction_id':2,'timestamp':datetime(2026,1,2),'transaction_type':'Deposit','account_number':1010,'related_account':None,'amount':'20.00','balance_after':'120.00'}]
            def close(inner):pass
        class Source:
            def cursor(inner,**kw):return Cursor()
        self.assertEqual(import_legacy(self.bank,Source(),self.admin),(1,2))
        self.assertEqual(self.get(1010)['balance_cents'],12000)
        with self.assertRaises(BankError):self.bank.transact(self.admin,1010,'Deposit','1')
        customer=self.get(1010)['customer_id'];self.bank.verify_customer(self.admin,customer,'1980-01-01','TEST-REVERIFY')
        self.bank.transact(self.admin,1010,'Deposit','1');self.assertEqual(self.create(),1011)
        with self.assertRaises(BankError):import_legacy(self.bank,Source(),self.admin)

if __name__=='__main__':unittest.main(verbosity=2)
