"""HTTP integration tests: real Flask routes, templates, sessions and SQLite service.
Run all tests: python -m unittest -v. These are not live MySQL tests.
"""
import re
import tempfile
import time
import unittest
from unittest.mock import patch
from banking import Bank
from web_app import create_app
from test_bank import DETAILS

class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.bank=Bank(self.temp.name)
        self.admin=self.bank.create_staff(None,'admin','AdminPassword123!','Admin')
        self.teller=self.bank.create_staff(self.admin,'teller','TellerPassword123!')
        self.app=create_app(self.bank,{'TESTING':True,'SECRET_KEY':'test-key-not-for-deployment'})
        self.client=self.app.test_client(); self.signin()
    def tearDown(self):
        for h in list(self.bank.logger.handlers):h.close();self.bank.logger.removeHandler(h)
        self.temp.cleanup()
    def tokens(self,path):
        page=self.client.get(path,follow_redirects=True).get_data(as_text=True)
        return {key:re.search(r'name="'+key+r'" value="([^"]+)"',page).group(1) for key in ('csrf','nonce')}
    def post(self,path,data=None,follow=True,get_path=None):
        return self.client.post(path,data={**self.tokens(get_path or path),**(data or {})},follow_redirects=follow)
    def signin(self,role='admin'):
        self.client=self.app.test_client()
        self.post('/login',{'username':role,'password':'AdminPassword123!' if role=='admin' else 'TellerPassword123!'},get_path='/login')
    def create(self,amount='100',**extra):
        response=self.post('/accounts/new',{**DETAILS,'amount':amount,'method':'Cash','dob':'1980-01-01','id_reference':'TEST-ID','verified':'yes',**extra})
        self.assertEqual(response.status_code,200,response.get_data(as_text=True))
        return self.bank.search(self.admin)[-1]['account_number']
    def balance(self,n):return self.bank.search(self.admin,{'account_number':n})[0]['balance_cents']
    def test_login_dashboard(self):
        response=self.client.get('/');self.assertEqual(response.status_code,200);self.assertIn(b'Active accounts',response.data)
    def test_anonymous_redirect(self):self.assertEqual(self.app.test_client().get('/accounts').status_code,302)
    def test_csrf_rejects_missing_token(self):self.assertEqual(self.client.post('/accounts/new',data=DETAILS).status_code,400)
    def test_login_failure(self):
        self.client=self.app.test_client();r=self.post('/login',{'username':'admin','password':'wrong'})
        self.assertEqual(r.status_code,400);self.assertIn(b'Invalid login',r.data)
    def test_create_and_search_two_smiths(self):
        a=self.create();b=self.create(first_name='John',middle_name='Paul');r=self.client.get('/accounts?last_name=Smith')
        self.assertIn(b'2 matching accounts',r.data);self.assertIn(f'/accounts/{a}'.encode(),r.data);self.assertIn(f'/accounts/{b}'.encode(),r.data)
    def test_combined_partial_search(self):
        self.create();self.assertIn(b'1 matching account',self.client.get('/accounts?last_name=Smi&city=Owings').data)
        self.assertIn(b'0 matching accounts',self.client.get('/accounts?last_name=Smith&city=Lex').data)
    def test_edit_audit(self):
        a=self.create();r=self.post(f'/accounts/{a}/edit',{**DETAILS,'city':'Lexington'})
        self.assertIn(b'Lexington',r.data);self.assertEqual(len(self.bank.reports(self.admin,'Audit',action='Edit Account')),1)
    def test_deposit_withdraw(self):
        a=self.create();self.post('/transactions/deposit',{'account_number':a,'amount':'20','method':'Cash'})
        self.post('/transactions/withdrawal',{'account_number':a,'amount':'30','method':'Cash'})
        self.assertEqual(self.balance(a),9000)
    def test_invalid_amount(self):
        a=self.create();r=self.post('/transactions/deposit',{'account_number':a,'amount':'NaN','method':'Cash'})
        self.assertEqual(r.status_code,400);self.assertEqual(self.balance(a),10000)
    def test_overdraft_confirmation(self):
        a=self.create();data={'account_number':a,'amount':'101','method':'Cash'}
        r=self.post('/transactions/withdrawal',data);self.assertIn(b'Confirm negative balance',r.data);self.assertEqual(self.balance(a),10000)
        tokens={k:re.findall(r'name="'+k+r'" value="([^"]+)"',r.get_data(as_text=True))[-1] for k in ('csrf','nonce')}
        r=self.client.post('/transactions/withdrawal',data={**data,**tokens,'confirm_overdraft':'yes'},follow_redirects=True)
        self.assertEqual(r.status_code,200);self.assertEqual(self.balance(a),-100)
    def test_transfer(self):
        a=self.create();b=self.create();r=self.post('/transfer',{'source':a,'destination':b,'amount':'25'})
        self.assertEqual(r.status_code,200);self.assertEqual((self.balance(a),self.balance(b)),(7500,12500))
    def test_same_account_transfer(self):
        a=self.create();r=self.post('/transfer',{'source':a,'destination':a,'amount':'1'})
        self.assertEqual(r.status_code,400);self.assertEqual(self.balance(a),10000)
    def test_closure_requires_reason_and_confirmation(self):
        a=self.create();self.post('/transactions/withdrawal',{'account_number':a,'amount':'100','method':'Cash'})
        self.assertEqual(self.post(f'/accounts/{a}/close',{'reason':'','confirm':'yes'}).status_code,400)
        self.assertEqual(self.post(f'/accounts/{a}/close',{'reason':'Requested'}).status_code,400)
    def test_close_and_block(self):
        a=self.create();self.post('/transactions/withdrawal',{'account_number':a,'amount':'100','method':'Cash'})
        r=self.post(f'/accounts/{a}/close',{'reason':'Customer request','confirm':'yes'})
        self.assertIn(b'Customer request',r.data);self.assertIn(b'Closed',r.data)
        self.assertEqual(self.post('/transactions/deposit',{'account_number':a,'amount':'1','method':'Cash'}).status_code,400)
        self.assertIn(b'Initial Deposit',self.client.get(f'/accounts/{a}').data)
    def test_cash_review_and_notes(self):
        self.create('11000');r=self.client.get('/reviews');self.assertIn(b'$11,000.00',r.data)
        review=self.bank.reports(self.admin,'Cash Review')[0]
        r=self.post('/reviews',{'operation':'cash','review_id':review['id'],'notes':'Reviewed simulation'})
        self.assertEqual(r.status_code,200);self.assertIn(b'Reviewed simulation',r.data)
    def test_staff_creation(self):
        r=self.post('/staff',{'username':'new_teller','password':'NewTellerPassword123!','role':'Teller'})
        self.assertIn(b'new_teller',r.data);self.assertEqual(self.bank.login('new_teller','NewTellerPassword123!')['role'],'Teller')
    def test_teller_admin_routes_denied(self):
        self.signin('teller')
        for path in ('/staff','/reviews','/verify'):
            with self.subTest(path=path):self.assertEqual(self.client.get(path).status_code,403)
        self.assertNotIn(b'>Staff accounts</a>',self.client.get('/').data)
    def test_teller_admin_post_denied(self):
        self.signin('teller');tokens=self.tokens('/transactions/deposit')
        r=self.client.post('/staff',data={**tokens,'username':'bad','password':'LongPassword123!','role':'Admin'})
        self.assertEqual(r.status_code,403)
    def test_teller_report_scoped(self):
        a=self.create();self.signin('teller');self.post('/transactions/deposit',{'account_number':a,'amount':'1','method':'Cash'})
        r=self.client.get(f'/reports?report=Transactions&staff={self.admin}')
        self.assertIn(b'Deposit',r.data);self.assertNotIn(b'Initial Deposit</td>',r.data)
        self.assertEqual(self.client.get('/reports?report=Audit').status_code,400)
    def test_csv_download(self):
        a=self.create();r=self.post('/reports',{'report':'Transactions','account':a})
        self.assertEqual(r.status_code,200);self.assertIn('attachment',r.headers['Content-Disposition'])
        self.assertIn(b'amount_cents',r.data);self.assertIn(b'Initial Deposit',r.data)
    def test_duplicate_post_not_replayed(self):
        a=self.create();data={**self.tokens('/transactions/deposit'),'account_number':a,'amount':'5','method':'Cash'}
        first=self.client.post('/transactions/deposit',data=data);second=self.client.post('/transactions/deposit',data=data)
        self.assertEqual(first.status_code,302);self.assertEqual(second.status_code,409);self.assertEqual(self.balance(a),10500)
    def test_session_timeout(self):
        with self.client.session_transaction() as s:s['last_activity']=time.time()-901
        self.assertEqual(self.client.get('/accounts').status_code,302)
    def test_logout(self):
        self.post('/logout',get_path='/');self.assertEqual(self.client.get('/accounts').status_code,302)
    def test_search_xss_escaped(self):
        response=self.client.get('/accounts?last_name=%3Cscript%3Ealert(1)%3C/script%3E')
        self.assertNotIn(b'<script>alert(1)</script>',response.data);self.assertIn(b'&lt;script&gt;',response.data)
    def test_security_headers(self):
        r=self.client.get('/');self.assertEqual(r.headers['Cache-Control'],'no-store');self.assertEqual(r.headers['X-Frame-Options'],'DENY')
    def test_page_renders(self):
        a=self.create()
        for path in ['/accounts/new',f'/accounts/{a}',f'/accounts/{a}/edit',f'/accounts/{a}/close','/transfer','/reports','/staff','/reviews','/verify']:
            with self.subTest(path=path):self.assertEqual(self.client.get(path).status_code,200)
    def test_logs_from_browser_transaction(self):
        a=self.create();self.post('/transactions/deposit',{'account_number':a,'amount':'1','method':'Cash'})
        import json
        rows=[json.loads(line) for line in (self.bank.directory/'transactions.jsonl').read_text().splitlines()]
        self.assertEqual(rows[-1]['after_cents'],10100);self.assertEqual(rows[-1]['staff_id'],self.admin)
    def test_bootstrap(self):
        empty=Bank(self.bank.directory/'new');app=create_app(empty,{'TESTING':True,'SECRET_KEY':'bootstrap-test'});client=app.test_client()
        r=client.get('/setup');html=r.get_data(as_text=True)
        tokens={k:re.search(r'name="'+k+r'" value="([^"]+)"',html).group(1) for k in ('csrf','nonce')}
        r=client.post('/setup',data={**tokens,'username':'first','password':'FirstAdminPassword!'},follow_redirects=True)
        self.assertIn(b'Staff sign in',r.data);self.assertEqual(empty.login('first','FirstAdminPassword!')['role'],'Admin')
        self.assertEqual(client.get('/setup').status_code,302)
        for handler in list(empty.logger.handlers):handler.close();empty.logger.removeHandler(handler)
    def test_bad_account_number(self):
        r=self.post('/transactions/deposit',{'account_number':'abc','amount':'1','method':'Cash'})
        self.assertEqual(r.status_code,400)
    def test_database_outage(self):
        with patch.object(self.bank,'connect',side_effect=OSError('offline')):
            r=self.client.get('/accounts');self.assertEqual(r.status_code,400);self.assertIn(b'Database operation failed',r.data)

if __name__=='__main__':unittest.main(verbosity=2)
