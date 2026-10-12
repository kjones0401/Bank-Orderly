# Browser / MySQL checks for assignment submission

Automated HTTP tests are in test_web.py. All current tests run with SQLite.
Use live MySQL on your computer and record actual outcomes for these steps.

| ID | Browser check | Expected evidence | Live MySQL status |
|---|---|---|---|
| W01 | Launch web_app.py and sign in in Edge/Chrome | Address bar shows local web URL; staff/role visible | Not Run |
| W02 | Create Jane Ann Smith and John Paul Smith with fictional identities | Success pages; two MySQL accounts; sequential numbers | Not Run |
| W03 | Search last_name Smith, then Smi | BOTH Smith accounts in the results screenshot | Not Run |
| W04 | Combine last name and city, then try every independent field | Correct intersection or zero-match message | Not Run |
| W05 | Edit name/address | Updated page; before/after audit and staff ID | Not Run |
| W06 | Deposit/withdraw and transfer | Balances agree with MySQL and transaction/log records | Not Run |
| W07 | Try invalid/negative/zero amounts and same-account transfer | Error page; no unintended financial changes | Not Run |
| W08 | Attempt overdraft; cancel, then confirm | Confirmation page; cancel posts nothing; consent recorded | Not Run |
| W09 | Settle an account to zero; close with a required reason | Closed status/reason/timestamp and retained history | Not Run |
| W10 | Try a transaction on a closed account | Server rejects it | Not Run |
| W11 | Create Teller as Admin; sign in as Teller | Admin links absent; direct restricted URLs denied | Not Run |
| W12 | Generate reports using dates/staff/account/actions; download CSV | Filtered rows and valid CSV with cents columns | Not Run |
| W13 | Test >$10,000 cash and two-account same-person aggregation | Restricted simulated review; no fake filing confirmation | Not Run |
| W14 | Compare transactions.jsonl and balance_snapshot.json to MySQL | Matching committed IDs, staff and balances | Not Run |
| W15 | Test duplicate form submission and session expiry | No duplicate posting; expired session requires login | Not Run |
| W16 | Stop test database; attempt browser action; restore connection | Safe error; inspect history before retry | Not Run |
| W17 | Backup and restore into empty target | Restored accounts, balances, history and staff logins | Not Run |
| W18 | Open same data through Tkinter and browser | A committed change appears in both interfaces | Not Run |

Save prompts, intermediate versions, exact AI/model label, test output, observed
results, screenshots and problems/solutions in CherryTree. Export the complete
node to PDF and check that code/text/screenshots are legible before submitting.
Account closure preserves history; confirm your instructor accepts it as the
assignment's delete operation. No public deployment is needed to use a web interface.
