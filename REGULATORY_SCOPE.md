# Regulatory scope — U.S. classroom simulation
Reviewed October 7, 2026. These controls illustrate selected requirements; they
are not a complete legal-compliance determination. Federal/state requirements,
bank charter, customer type, products, exceptions and bank policies all affect
real deployment. No real funds or actual government submissions are supported.

## Implemented demonstrations

1. Cash reporting: flag MORE THAN $10,000 cash in OR cash out per person per
   business day, separately; never net deposits against withdrawals. Count opening
   cash deposits. Aggregate known conductor and beneficiary identities across
   accounts/tellers, counting a transaction once per person. Use America/New_York
   business date. Dates/thresholds should be reverified before real deployment.
2. CTR review due dates: 15 calendar days after the business date. Restricted Admin
   queue is labeled simulation. No exemption determination or BSA e-filing.
3. New customer identity workflow: birth date, physical address fields, fictional ID
   reference and verification status. It demonstrates the workflow; it DOES NOT
   collect a complete real CIP identification-number/document dataset or verify
   government documents. Use no real SSNs or identity documents in this project.
4. Preserve closed records: no ordinary delete function or automatic purge.
   Required CIP identifying records generally have five-year retention after closure;
   verification records generally have five years after creation. Indefinite classroom
   retention is not a complete production privacy/records-retention policy.
5. Transfers between different identities at $3,000+ produce restricted record-review
   notes. Same-person transfers do not generate that note. This is not a complete
   funds-transfer recordkeeping/Travel Rule implementation.
6. Admin-only manual suspicious-activity review notes. No automated inference of
   criminal intent, legal SAR threshold determination, customer notification or filing.
7. Actor IDs and before/after balances on new transactions; edit/closure audits and
   external committed-event export. There is no cryptographic tamper-proof ledger.

Sources:
- FinCEN aggregation: https://www.fincen.gov/resources/statutes-regulations/guidance/currency-transaction-report-aggregation-businesses-common
- FinCEN cash in/out: https://www.fincen.gov/resources/statutes-regulations/guidance/frequently-asked-questions-concerning-completion-part-ii
- FinCEN CTR FAQ: https://www.fincen.gov/resources/frequently-asked-questions-regarding-fincen-currency-transaction-report-ctr
- FFIEC CIP: https://bsaaml.ffiec.gov/manual/AssessingComplianceWithBSARegulatoryRequirements/01
- FFIEC retention: https://bsaaml.ffiec.gov/manual/Appendices/17
- FinCEN structuring: https://www.fincen.gov/resources/statutes-regulations/administrative-rulings/suspicious-activity-reporting-structuring
- FinCEN transfer recordkeeping: https://www.fincen.gov/resources/advisories/fincen-advisory-issue-3
- Federal Reserve Regulation CC (amended July 1, 2025): https://www.federalreserve.gov/frrs/regulations/regulation-cc-availability-of-funds-and-collection-of-checks.htm

## Outside implemented scope

Actual government filing, exemptions, full CIP/CDD including business beneficial
ownership, OFAC screening, full suspicious-activity monitoring/SAR confidentiality
program, check acceptance and Regulation CC holds/notices, electronic-payment
rails and Regulation E dispute/disclosure workflows, overdraft/fee disclosures,
interest and account disclosures, state-specific obligations, deposit insurance
calculations, enterprise key management, MFA, transport/storage encryption,
independent compliance review and regulatory certification.

Cash reporting is NOT a general $10,000 transaction cap. The storage limit is a
software limit, not a law. Zero-balance closure, 12-character passwords and timed
login lockouts are project policies, not claimed statutory thresholds.

Noncustomers conducting cash transactions are not supported; cash conductors
must already have a verified simulated customer identity. Joint/business accounts,
branches with differing business-day boundaries, and CTR exemptions are outside
scope. Original v2 data cannot retroactively identify cash transactions or known
shared persons. It must not be treated as fully reconstructable CTR history.
