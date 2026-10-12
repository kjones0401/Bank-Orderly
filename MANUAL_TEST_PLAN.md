# Desktop/MySQL verification — pending on user's computer
Use only fictional data. Record screenshots and actual results; do not label a
manual test Passed until performed. Automated results are in test_results.txt.

| ID | Steps | Expected result | Status |
|---|---|---|---|
| M01 | Launch on MySQL; create first Admin; sign in | Correct staff/role shown | Not run |
| M02 | Create a Teller; sign in as that teller | Admin screens absent | Not run |
| M03 | Create Jane Ann Smith and John Paul Smith | Sequential numbers; records in MySQL | Not run |
| M04 | Search last_name Smith | Both matches appear | Not run |
| M05 | Combine Smith and city; try partial Smi and nonexistent name | All applicable matches; friendly zero count | Not run |
| M06 | Try every search dropdown field, including closed status/reason | Independent fields match correctly | Not run |
| M07 | Edit city and address | Updated details; before/after audit and staff | Not run |
| M08 | Deposit/withdraw; inspect transaction history and MySQL | Correct cents, actor, resulting balance | Not run |
| M09 | Enter zero, negative, text, NaN and extra decimal places | Rejected without financial change | Not run |
| M10 | Withdraw above balance; cancel, then confirm | Cancellation does nothing; confirmation recorded | Not run |
| M11 | Transfer, same-account transfer, invalid destination | Both balances update atomically; invalid attempts rejected | Not run |
| M12 | Attempt closure with positive/negative balance or blank reason | Rejected | Not run |
| M13 | Settle zero balance; close with reason | Closed status, reason, timestamp and staff retained | Not run |
| M14 | Attempt deposit/withdraw/transfer/edit on closed account | Rejected; history remains searchable | Not run |
| M15 | Opening cash deposit 10000, then 0.01 | No initial alert; additional cent triggers review | Not run |
| M16 | Same Customer ID on two accounts; cash 6000 and 5000 through different tellers | Aggregate cash-in alert 11000 | Not run |
| M17 | Cash in 11000, cash out 4000 | Cash-in alert remains 11000 | Not run |
| M18 | Electronic deposit 15000 | No cash CTR alert | Not run |
| M19 | Generate reports by inclusive dates, staff, account and action | Correct intersection of filters | Not run |
| M20 | Export CSV; view in Excel | Headers, cents amounts and safe text | Not run |
| M21 | Review cash alert as Admin; try as Teller | Admin notes retained; teller denied | Not run |
| M22 | Restart app and inspect balances/logs | Persistence and external records agree | Not run |
| M23 | Stop test MySQL server; attempt action; restart | Safe error; no claimed success; reconcile before retry | Not run |
| M24 | Test external export failure on test copy, then Retry Log Export | Financial action not repeated; pending events exported | Not run |
| M25 | Full backup and restore into separate empty target | Balances/history/login restored; existing target refused | Not run |
| M26 | Import v2 into empty v3 account store | Original DB unchanged; balances/history preserved | Not run |
| M27 | Five wrong passwords; valid password during lockout | Locked for 15 minutes | Not run |
| M28 | Leave signed-in GUI inactive 15 minutes | Sign-in required again | Not run |
| M29 | Run two app instances and submit deposits/creates concurrently | No lost balance update or duplicate number | Not run |

Suggested screenshots: login, staff creation, two Smith results, account details,
edit audit, deposit/withdraw/transfer histories, closure reason/status, cash review,
filtered reports, MySQL rows, external logs/snapshot, automated test results and
successful restore. Exclude credentials and real identifying information.
