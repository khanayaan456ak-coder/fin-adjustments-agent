# Manual adjustments review: 2024-Q4

Run `77615f210843` · 10 entries · 6 accepted · 2 quarantined · 2 rejected

| Entry | Description | Amount | Decision | Main reason |
|---|---|---:|---|---|
| JE-001 | Accrue Q4 bonus pool | 850,000.00 | ✅ ACCEPTED | MATERIAL_ENTRY |
| JE-002 | Reclassify marketing spend wrongly booked to T&E | 28,500.00 | ❌ REJECTED | DEBITS_NOT_EQUAL_CREDITS |
| JE-003 | FX revaluation of EUR cash balance to period-end rate | 11,200.00 | ⚠️ QUARANTINED | FX_REVAL_MISMATCH |
| JE-004 | Bad debt provision top-up | 45,000.00 | ✅ ACCEPTED | - |
| JE-005 | Reclass conference travel from old code | 18,500.00 | ⚠️ QUARANTINED | ACCOUNT_NOT_IN_COA |
| JE-006 | Depreciation catch-up — Q4 | 215,000.00 | ✅ ACCEPTED | - |
| JE-007 | Deferred tax true-up | 38,000.00 | ✅ ACCEPTED | - |
| JE-008 | Intercompany settlement — UK sub | 320,000.00 | ❌ REJECTED | CIRCULAR_NO_EFFECT |
| JE-009 | Accrue legal fees for ongoing litigation | 75,000.00 | ✅ ACCEPTED | - |
| JE-010 | Reclass long-term debt current portion | 200,000.00 | ✅ ACCEPTED | - |

## Notes for the finance team

### ✅ JE-001: Accrue Q4 bonus pool

**JE-001 passed all blocking checks and was posted.**

This entry (850,000.00) is above the materiality threshold of 340,325.00 (5% of pre-tax income 6,806,500.00). It can be posted but needs documented approval and supporting workings.

*What to do:* Attach approval evidence (e.g., Controller sign-off).

<sub>hash 4ff0cd44d7a3ad04 · explanation: template</sub>

### ❌ JE-002: Reclassify marketing spend wrongly booked to T&E

**JE-002 was rejected and not posted.**

Total debits are 28,500.00 but total credits are 25,000.00, a difference of 3,500.00. An entry must balance before it can be posted, and the system will not guess which side is wrong.

*What to do:* Confirm the correct amount with the preparer and resubmit with debits equal to credits (either both 28,500.00 or both 25,000.00).

<sub>hash 799f3985b1fd668a · explanation: template</sub>

### ⚠️ JE-003: FX revaluation of EUR cash balance to period-end rate

**JE-003 is on hold until someone reviews it.**

The entry books 11,200.00 of revaluation on 1110 (EUR), but recalculating from the trial balance and the given rates does not reproduce it (from period average rate 1.082: EUR 825,400.00 x (1.095 - 1.082) = 10,730.20; from opening rate 1.071: EUR 825,400.00 x (1.095 - 1.071) = 19,809.60). Also, if the trial balance is translated at the period-end rate anyway, this entry would count the revaluation twice.

*What to do:* Share the revaluation workings and confirm whether TB foreign rows are in local currency.

<sub>hash 4ac7468c29512e65 · explanation: template</sub>

### ✅ JE-004: Bad debt provision top-up

**JE-004 passed all blocking checks and was posted.**

No issues were found.

*What to do:* No action needed.

<sub>hash 73539254d54249f7 · explanation: template</sub>

### ⚠️ JE-005: Reclass conference travel from old code

**JE-005 is on hold until someone reviews it.**

Line JE-005#L1 posts 18,500.00 to account 6315, which does not exist in the chart of accounts. Closest matches: 6310 Travel and Entertainment (medium confidence); 6300 Marketing and Advertising (low confidence). Note: mapping to 6310 would put both sides of this entry on the same account, so it would have no effect. The preparer may intend a new account.

*What to do:* Either correct the account code, or have the COA owner create the account, or approve a mapping in overrides.json (the entry is then re-checked).

<sub>hash 680309371d536d48 · explanation: template</sub>

### ✅ JE-006: Depreciation catch-up — Q4

**JE-006 passed all blocking checks and was posted.**

No issues were found.

*What to do:* No action needed.

<sub>hash 020f7159c0031d9c · explanation: template</sub>

### ✅ JE-007: Deferred tax true-up

**JE-007 passed all blocking checks and was posted.**

No issues were found.

*What to do:* No action needed.

<sub>hash 7e2fada3a4111e13 · explanation: template</sub>

### ❌ JE-008: Intercompany settlement — UK sub

**JE-008 was rejected and not posted.**

Every line nets to zero on the same account(s) (2170): 320,000.00 is debited and credited to the same place, so the entry changes nothing. This usually means a counterparty account was keyed wrongly. The chart of accounts has no intercompany receivable or counterparty account to match 2170 against, so this cannot be reconciled or eliminated with the other entity's books.

*What to do:* Identify the real counterparty account (e.g., cash or an intercompany receivable) and resubmit.

<sub>hash 6f60da6bc732236b · explanation: template</sub>

### ✅ JE-009: Accrue legal fees for ongoing litigation

**JE-009 passed all blocking checks and was posted.**

No issues were found.

*What to do:* No action needed.

<sub>hash 1995895fa654e725 · explanation: template</sub>

### ✅ JE-010: Reclass long-term debt current portion

**JE-010 passed all blocking checks and was posted.**

No issues were found.

*What to do:* No action needed.

<sub>hash f9d1755b29c2f75d · explanation: template</sub>

## Input diagnostics (found before reviewing entries)

| Severity | Issue | Evidence |
|---|---|---|
| ERROR | Current trial balance does not balance |  |
| ERROR | Prior trial balance does not balance |  |
| HOLD | Account 6310 (USD) appears 2 times in current TB | trial_balance.csv:48, trial_balance.csv:49 |
| HOLD | Current TB account 9999 'Suspense - Unmapped' is not in the COA | trial_balance.csv:63 |
| HOLD | Prior TB account 6905 'Sundry Operating Expenses' is not in the COA | prior_period_tb.csv:34 |
| HOLD | No period_end rate for GBP |  |
| INFO | Undocumented 'opening' rate type, USD row missing |  |
| INFO | 1121 'Allowance for Doubtful Accounts' is Asset with Credit normal balance (contra) | chart_of_accounts.csv:6 |
| HOLD | 1150 'Other Current Assets' has cash-flow category TBD | chart_of_accounts.csv:10 |
| INFO | 1211 'Accumulated Depreciation - PPE' is Asset with Credit normal balance (contra) | chart_of_accounts.csv:13 |
| INFO | 1221 'Accumulated Amortization' is Asset with Credit normal balance (contra) | chart_of_accounts.csv:15 |
| WARN | Header 1290 'Other Assets' has no children | chart_of_accounts.csv:19 |
| HOLD | 2170 'Intercompany Payable' has cash-flow category TBD | chart_of_accounts.csv:28 |
| WARN | 3300 'Accumulated OCI' is typed Equity but is a parent of 3310 | chart_of_accounts.csv:38 |
| INFO | 3400 'Treasury Stock' is Equity with Debit normal balance (contra) | chart_of_accounts.csv:40 |
| INFO | 4200 'Sales Returns and Allowances' is Revenue with Debit normal balance (contra) | chart_of_accounts.csv:44 |
| WARN | 7000 'Non-Operating Items' has no normal balance | chart_of_accounts.csv:65 |
| INFO | 7310 'FX Gain/Loss - Unrealized' is non-cash but tagged cf_category 'Operating' | chart_of_accounts.csv:69 |
| INFO | 7400 'Gain/Loss on Disposal of Assets' is non-cash but tagged cf_category 'Investing' | chart_of_accounts.csv:70 |
| WARN | 8000 'Income Tax Expense' is typed Expense but is a parent of 8100, 8200 | chart_of_accounts.csv:71 |
| HOLD | Retained earnings moved while P&L is still open | trial_balance.csv:31, prior_period_tb.csv:31 |
| WARN | Prior TB has (almost) no P&L accounts | prior_period_tb.csv:34 |
| WARN | 1210 'Property, Plant & Equipment - Cost' moved 5,207,700.00 vs prior | trial_balance.csv:11, prior_period_tb.csv:11 |
