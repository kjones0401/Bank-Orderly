"""Expanded Tkinter teller desktop, v3.0. Run: python simple_bank.py."""
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from banking import Bank, BankError, FIELDS, SEARCH_FIELDS, money, cents
from config import APP_NAME, APP_VERSION, DATA_DIR, BACKEND, DB_CONFIG

class BankApplication(tk.Tk):
    def __init__(self, bank):
        super().__init__()
        self.bank=bank; self.user=None; self.selected=None; self.last_activity=time.monotonic()
        self.title(f'{APP_NAME} v{APP_VERSION} — {BACKEND.upper()}'); self.geometry('1180x850'); self.minsize(950,700)
        self.configure(bg='#eef2f6')
        style=ttk.Style(self); style.theme_use('clam')
        style.configure('TButton',padding=8); style.configure('Title.TLabel',font=('Segoe UI',18,'bold'))
        self.bind_all('<KeyPress>',self.activity); self.bind_all('<ButtonPress>',self.activity)
        self.after(30000,self.check_session)
        self.protocol('WM_DELETE_WINDOW',self.exit_app)
        self.login_page()

    def exit_app(self):
        if self.user: self.call(lambda:self.bank.logout(self.user['id']))
        self.destroy()

    def activity(self,event=None): self.last_activity=time.monotonic()
    def check_session(self):
        if self.user and time.monotonic()-self.last_activity>900:
            self.logout(); messagebox.showinfo('Session expired','Please sign in again after 15 minutes of inactivity.')
        self.after(30000,self.check_session)

    def call(self, function):
        try:
            result = function()
            if self.bank.export_pending: messagebox.showwarning('Log Export Pending','Database changes committed, but external log export is pending. Retry Log Export; do not repeat a transaction.')
            return result
        except BankError as exc: messagebox.showerror('Bank Orderly',str(exc)); return None
        except (ValueError,TypeError): messagebox.showerror('Bank Orderly','Enter valid numeric account/staff numbers.'); return None
        except OSError: messagebox.showerror('Bank Orderly','Unable to write file. Check destination permissions.'); return None

    def clear(self):
        for widget in self.winfo_children(): widget.destroy()

    def login_page(self):
        self.configure(menu='')
        self.clear(); self.user=None
        frame=ttk.Frame(self,padding=40); frame.pack(expand=True)
        bootstrap=self.bank.needs_bootstrap()
        ttk.Label(frame,text='Create First Admin' if bootstrap else 'Staff Login',style='Title.TLabel').pack(pady=15)
        ttk.Label(frame,text='Classroom simulation • Use fictional customer data').pack(pady=8)
        entries={}
        for label,key in [('Username','username'),('Password','password')]:
            ttk.Label(frame,text=label).pack(anchor='w'); entry=ttk.Entry(frame,width=36,show='*' if key=='password' else '')
            entry.pack(pady=5); entries[key]=entry
        if bootstrap: ttk.Label(frame,text='Choose a password with at least 12 characters.').pack()
        def submit():
            def operation():
                if bootstrap: self.bank.create_staff(None,entries['username'].get(),entries['password'].get(),'Admin')
                self.user=self.bank.login(entries['username'].get(),entries['password'].get())
                self.activity(); self.workspace(); self.search_page()
            self.call(operation)
        ttk.Button(frame,text='Create Admin & Sign In' if bootstrap else 'Sign In',command=submit).pack(pady=15)
        entries['password'].bind('<Return>',lambda e:submit()); entries['username'].focus_set()

    def workspace(self):
        self.clear()
        header=tk.Label(self,text=f'{APP_NAME} v{APP_VERSION}   |   {self.user["username"]} ({self.user["role"]})',
                        bg='#17365d',fg='white',font=('Segoe UI',17,'bold'),pady=15)
        header.pack(fill='x')
        body=ttk.Frame(self); body.pack(fill='both',expand=True)
        nav=tk.Frame(body,bg='#17365d',width=210); nav.pack(side='left',fill='y'); nav.pack_propagate(False)
        commands=[('Search Accounts',self.search_page),('Create Account',lambda:self.account_form()),
                  ('Edit Account',self.edit_page),('Deposit',lambda:self.transaction_page('Deposit')),
                  ('Withdrawal',lambda:self.transaction_page('Withdrawal')),('Transfer',self.transfer_page),
                  ('Close Account',self.closure_page),('Reports',self.reports_page)]
        if self.user['role']=='Admin': commands += [('Staff Accounts',self.staff_page),('Cash Review',self.review_page),('Verify Customer',self.verification_page)]
        commands += [('Retry Log Export',self.retry_export),('Sign Out',self.logout)]
        menu_bar=tk.Menu(self); teller_menu=tk.Menu(menu_bar,tearoff=False)
        for label,command in commands: teller_menu.add_command(label=label,command=command)
        teller_menu.add_separator(); teller_menu.add_command(label='Exit',command=self.exit_app)
        menu_bar.add_cascade(label='Teller Menu',menu=teller_menu); self.configure(menu=menu_bar)
        for label,command in commands:
            tk.Button(nav,text=label,command=command,bg='white',fg='#17365d',relief='flat',anchor='w',
                      font=('Segoe UI',10,'bold'),padx=12,pady=8).pack(fill='x',padx=10,pady=4)
        self.content=ttk.Frame(body,padding=20); self.content.pack(side='left',fill='both',expand=True)

    def page(self,title):
        for widget in self.content.winfo_children(): widget.destroy()
        ttk.Label(self.content,text=title,style='Title.TLabel').pack(anchor='w',pady=(0,12))

    def form(self, labels, parent=None, values=None):
        frame=ttk.Frame(parent or self.content); frame.pack(anchor='w',fill='x')
        entries={}; values=values or {}
        for row,(key,label) in enumerate(labels):
            ttk.Label(frame,text=label).grid(row=row,column=0,sticky='w',padx=4,pady=3)
            entry=ttk.Entry(frame,width=43); entry.grid(row=row,column=1,sticky='w',padx=12,pady=3)
            entry.insert(0,str(values.get(key,'') or '')); entries[key]=entry
        return entries

    def table(self,rows,columns=None,parent=None,height=12):
        frame=ttk.Frame(parent or self.content); frame.pack(fill='both',expand=True,pady=10)
        columns=columns or (list(rows[0]) if rows else ['result'])
        tree=ttk.Treeview(frame,columns=columns,show='headings',height=height)
        for col in columns:
            tree.heading(col,text=col.replace('_',' ').title()); tree.column(col,width=145,minwidth=80)
        for row in rows:
            tree.insert('', 'end',values=[money(row.get(c,0)) if c.endswith('_cents') else str(row.get(c,'') or '') for c in columns])
        vertical=ttk.Scrollbar(frame,orient='vertical',command=tree.yview)
        horizontal=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        tree.grid(row=0,column=0,sticky='nsew'); vertical.grid(row=0,column=1,sticky='ns'); horizontal.grid(row=1,column=0,sticky='ew')
        frame.columnconfigure(0,weight=1); frame.rowconfigure(0,weight=1)
        return tree

    def selected_number(self): return str(self.selected or '')

    def search_page(self):
        self.page('Search Accounts')
        ttk.Label(self.content,text='Choose any fields. Filled criteria are combined with AND. Text searches match partial values.').pack(anchor='w')
        ttk.Label(self.content,text='Balance/initial deposit searches use integer cents (10000 = $100.00). Blank criteria return all accounts.').pack(anchor='w')
        criteria_frame=ttk.Frame(self.content); criteria_frame.pack(fill='x',pady=8)
        pairs=[]
        for index in range(6):
            field=ttk.Combobox(criteria_frame,values=SEARCH_FIELDS,state='readonly',width=22)
            field.grid(row=index//2,column=(index%2)*2,padx=4,pady=3)
            value=ttk.Entry(criteria_frame,width=20); value.grid(row=index//2,column=(index%2)*2+1,padx=4,pady=3)
            pairs.append((field,value))
        pairs[0][0].set('last_name')
        result_frame=ttk.Frame(self.content); result_frame.pack(fill='both',expand=True)
        def search():
            def operation():
                criteria={}
                for field,value in pairs:
                    if value.get().strip():
                        if not field.get(): raise BankError('Choose a field for each entered search value.')
                        if field.get() in criteria: raise BankError('Choose each search field only once.')
                        criteria[field.get()]=value.get()
                rows=self.bank.search(self.user['id'],criteria)
                for widget in result_frame.winfo_children(): widget.destroy()
                ttk.Label(result_frame,text=f'{len(rows)} matching account(s). Double-click an account for details.').pack(anchor='w')
                tree=self.table(rows,['account_number','first_name','middle_name','last_name','city','status','balance_cents','customer_id'],result_frame)
                def choose(event):
                    selected=tree.selection()
                    if selected: self.selected=int(tree.item(selected[0],'values')[0]); self.details_page()
                tree.bind('<Double-1>',choose)
            self.call(operation)
        ttk.Button(criteria_frame,text='Search',command=search).grid(row=3,column=0,pady=6)
        search()

    def details_page(self):
        def operation():
            rows=self.bank.search(self.user['id'],{'account_number':self.selected}); account=rows[0]
            self.page(f'Account {self.selected} — {account["status"]}')
            details='\n'.join(f'{k.replace("_"," ").title()}: {money(v) if k.endswith("_cents") else v}' for k,v in account.items())
            text=tk.Text(self.content,height=14,wrap='word'); text.insert('1.0',details); text.configure(state='disabled'); text.pack(fill='x')
            buttons=ttk.Frame(self.content); buttons.pack(fill='x')
            for label,command in [('Edit',self.edit_page),('Deposit',lambda:self.transaction_page('Deposit')),('Withdrawal',lambda:self.transaction_page('Withdrawal')),('Close',self.closure_page)]:
                ttk.Button(buttons,text=label,command=command).pack(side='left',padx=4)
            # Account history includes all tellers; ordinary teller activity reports remain scoped.
            with self.bank.transaction() as con:
                self.bank.authorize(con,self.user['id'])
                history=self.bank.rows(con,'SELECT timestamp,kind,staff_id,amount_cents,after_cents,method FROM transactions WHERE account_number=? ORDER BY timestamp',(self.selected,))
            self.table(history)
        self.call(operation)

    def edit_page(self):
        if not self.selected:
            messagebox.showinfo('Edit Account','Search and double-click an account first.'); self.search_page(); return
        self.call(lambda:self.account_form(self.bank.search(self.user['id'],{'account_number':self.selected})[0]))

    def account_form(self,existing=None):
        self.page('Edit Account' if existing else 'Create Checking Account')
        entries=self.form([(k,k.replace('_',' ').title()) for k in FIELDS],values=existing)
        extra={}; verified=tk.BooleanVar()
        if not existing:
            ttk.Label(self.content,text='Identification notice: account opening requires identity information and verification. Use fictional data only.').pack(anchor='w',pady=6)
            extra=self.form([('amount','Initial Deposit'),('customer_id','Existing Customer ID (optional)'),('dob','New Customer Birth Date (YYYY-MM-DD)'),('id_reference','Fictional ID Reference')])
            ttk.Checkbutton(self.content,text='Identity verification completed (simulation)',variable=verified).pack(anchor='w')
            method=ttk.Combobox(self.content,values=['Cash','Electronic'],state='readonly'); method.set('Cash'); method.pack(anchor='w',pady=5)
        def save():
            def operation():
                details={k:e.get() for k,e in entries.items()}
                if existing: self.bank.edit(self.user['id'],existing['account_number'],details)
                else:
                    self.selected=self.bank.create_account(self.user['id'],details,extra['amount'].get(),method.get(),
                        customer_id=extra['customer_id'].get().strip(),dob=extra['dob'].get(),id_reference=extra['id_reference'].get(),verified=verified.get())
                messagebox.showinfo('Account Saved',f'Account {self.selected} saved.'); self.details_page()
            self.call(operation)
        ttk.Button(self.content,text='Save Account',command=save).pack(anchor='w',pady=10)

    def transaction_page(self,kind):
        self.page(kind)
        entries=self.form([('number','Account Number'),('amount','Amount'),('conductor','Cash Conductor Customer ID (blank = owner)')],values={'number':self.selected_number()})
        method=ttk.Combobox(self.content,values=['Cash','Electronic'],state='readonly'); method.set('Cash'); method.pack(anchor='w',pady=8)
        def submit():
            def operation():
                number=int(entries['number'].get()); amount=cents(entries['amount'].get())
                rows=self.bank.search(self.user['id'],{'account_number':number})
                if not rows: raise BankError('Account Not Found')
                confirmed=False
                if kind=='Withdrawal' and amount>rows[0]['balance_cents']:
                    confirmed=messagebox.askyesno('Negative Balance Warning',f'Balance will become {money(rows[0]["balance_cents"]-amount)}. Proceed?')
                    if not confirmed:return
                self.bank.transact(self.user['id'],number,kind,entries['amount'].get(),method.get(),entries['conductor'].get().strip(),confirmed)
                messagebox.showinfo('Transaction Complete',f'{kind} saved.'); self.selected=None; self.transaction_page(kind)
            self.call(operation)
        ttk.Button(self.content,text=f'Complete {kind}',command=submit).pack(anchor='w',pady=10)

    def transfer_page(self):
        self.page('Transfer')
        entries=self.form([('source','From Account'),('destination','To Account'),('amount','Amount')],values={'source':self.selected_number()})
        def submit():
            def operation():
                source=int(entries['source'].get()); destination=int(entries['destination'].get()); amount=cents(entries['amount'].get())
                rows=self.bank.search(self.user['id'],{'account_number':source})
                if not rows: raise BankError('Account Not Found')
                confirmed=False
                if amount>rows[0]['balance_cents']:
                    confirmed=messagebox.askyesno('Negative Balance Warning',f'Source balance will become {money(rows[0]["balance_cents"]-amount)}. Proceed?')
                    if not confirmed:return
                self.bank.transfer(self.user['id'],source,destination,entries['amount'].get(),confirmed)
                messagebox.showinfo('Transfer Complete','Both account balances and transaction records saved.'); self.selected=None; self.transfer_page()
            self.call(operation)
        ttk.Button(self.content,text='Complete Transfer',command=submit).pack(anchor='w',pady=10)

    def closure_page(self):
        self.page('Close Account')
        ttk.Label(self.content,text='Project policy: balance must be zero. Customer and transaction history will be retained.').pack(anchor='w')
        entries=self.form([('number','Account Number'),('reason','Reason for Account Closure (required)')],values={'number':self.selected_number()})
        def submit():
            def operation():
                number=int(entries['number'].get()); reason=entries['reason'].get()
                if not reason.strip(): raise BankError('Reason for Account Closure is required.')
                if not messagebox.askyesno('Confirm Closure',f'Close account {number}?\nReason: {reason}'): return
                self.bank.close_account(self.user['id'],number,reason); self.selected=number
                messagebox.showinfo('Account Closed','Closure reason and staff identity recorded.'); self.details_page()
            self.call(operation)
        ttk.Button(self.content,text='Close Account',command=submit).pack(anchor='w',pady=10)

    def reports_page(self):
        self.page('Reports')
        types=['Transactions','Accounts'] + (['Audit','Cash Review','Staff'] if self.user['role']=='Admin' else [])
        report=ttk.Combobox(self.content,values=types,state='readonly'); report.set('Transactions'); report.pack(anchor='w')
        entries=self.form([('start','Start Date YYYY-MM-DD'),('end','End Date YYYY-MM-DD'),('staff','Staff ID'),('account','Account Number'),('action','Exact Action / Transaction Type')])
        ttk.Label(self.content,text='Staff/account/action filters apply to Transactions and Audit. Account reports also allow account number.').pack(anchor='w')
        result=ttk.Frame(self.content); result.pack(fill='both',expand=True); current=[]
        def generate():
            def operation():
                rows=self.bank.reports(self.user['id'],report.get(),**{k:e.get().strip() for k,e in entries.items()})
                current.clear(); current.extend(rows)
                for child in result.winfo_children(): child.destroy()
                ttk.Label(result,text=f'{len(rows)} row(s). Monetary columns are displayed in dollars; CSV stores cents.').pack(anchor='w')
                self.table(rows,parent=result)
            self.call(operation)
        def export():
            path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')])
            if path:self.call(lambda:self.bank.export_csv(self.user['id'],current,path))
        buttons=ttk.Frame(self.content); buttons.pack(anchor='w')
        ttk.Button(buttons,text='Generate',command=generate).pack(side='left'); ttk.Button(buttons,text='Export CSV',command=export).pack(side='left',padx=6)
        generate()

    def staff_page(self):
        self.page('Create Staff Account')
        entries=self.form([('username','Username'),('password','Password (12+ characters)')]); entries['password'].configure(show='*')
        role=ttk.Combobox(self.content,values=['Teller','Admin'],state='readonly'); role.set('Teller'); role.pack(anchor='w',pady=8)
        def save():
            def operation():
                identifier=self.bank.create_staff(self.user['id'],entries['username'].get(),entries['password'].get(),role.get())
                messagebox.showinfo('Staff Created',f'Staff ID: {identifier}'); self.staff_page()
            self.call(operation)
        ttk.Button(self.content,text='Create Staff',command=save).pack(anchor='w')
        self.call(lambda:self.table(self.bank.reports(self.user['id'],'Staff')))

    def review_page(self):
        self.page('Restricted Cash / Suspicion Review — Simulation')
        ttk.Label(self.content,text='No government filing is performed. Cash alerts are review records, not declarations of wrongdoing.').pack(anchor='w')
        rows=self.call(lambda:self.bank.reports(self.user['id'],'Cash Review')) or []
        self.table(rows,height=7)
        entries=self.form([('review','Cash Review ID'),('account','Account Number (suspicion review)'),('notes','Restricted Review Notes')])
        def review(): self.call(lambda:self.bank.review(self.user['id'],entries['review'].get().strip(),entries['notes'].get()))
        def flag(): self.call(lambda:self.bank.suspicious_flag(self.user['id'],int(entries['account'].get()),entries['notes'].get()))
        ttk.Button(self.content,text='Save Cash Review Notes',command=review).pack(anchor='w',pady=4)
        ttk.Button(self.content,text='Record Suspicion Review',command=flag).pack(anchor='w')

    def verification_page(self):
        self.page('Verify Imported Customer — Simulation')
        entries=self.form([('customer','Customer ID'),('dob','Birth Date YYYY-MM-DD'),('reference','Fictional Identification Reference')])
        def submit():
            def operation():
                self.bank.verify_customer(self.user['id'],entries['customer'].get().strip(),entries['dob'].get(),entries['reference'].get())
                messagebox.showinfo('Verification Saved','Customer verification recorded.')
            self.call(operation)
        ttk.Button(self.content,text='Confirm Verification',command=submit).pack(anchor='w',pady=10)

    def retry_export(self):
        success=self.bank.flush_logs()
        messagebox.showinfo('Log Export','Committed records exported.' if success else 'Export remains pending. Check application.log.')

    def logout(self):
        if self.user:self.call(lambda:self.bank.logout(self.user['id']))
        self.selected=None; self.login_page()

def main():
    try: bank=Bank(DATA_DIR,BACKEND,DB_CONFIG)
    except BankError as exc:
        root=tk.Tk(); root.withdraw(); messagebox.showerror('Startup',str(exc)); root.destroy(); return
    BankApplication(bank).mainloop()

if __name__=='__main__': main()
