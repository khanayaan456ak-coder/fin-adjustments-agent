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

**Journal Entry Accepted**

The journal entry for accruing the Q4 bonus pool has been accepted. However, it exceeds the materiality threshold of 340,325.00, which requires documented approval and supporting workings. This is a standard procedure to ensure proper oversight on significant entries.

*What to do:* Please attach approval evidence, such as Controller sign-off, to comply with the materiality requirement.

<sub>hash 4ff0cd44d7a3ad04 · explanation: llm:gpt-4o-mini</sub>

### ❌ JE-002: Reclassify marketing spend wrongly booked to T&E

**Journal Entry REJECTED due to imbalance**

The journal entry was rejected because the total debits of 28,500.00 do not equal the total credits of 25,000.00, resulting in a difference of 3,500.00. For a journal entry to be accepted, the debits must equal the credits. The system cannot determine which side is incorrect.

*What to do:* Confirm the correct amount with the preparer and resubmit with debits equal to credits (either both 28,500.00 or both 25,000.00).

<sub>hash 799f3985b1fd668a · explanation: llm:gpt-4o-mini</sub>

### ⚠️ JE-003: FX revaluation of EUR cash balance to period-end rate

**Journal Entry Quarantined Due to FX Revaluation Mismatch**

The journal entry has been quarantined because the FX revaluation amount of 11,200.00 does not match the expected calculations based on the trial balance and given rates. The recalculated amounts from both the period average and opening rates indicate discrepancies, suggesting that the revaluation may have been recorded incorrectly. Additionally, if the trial balance is already translated at the period-end rate, this entry could result in double counting the revaluation.

*What to do:* Please share the revaluation workings and confirm whether the trial balance foreign rows are in local currency.

<sub>hash 4ac7468c29512e65 · explanation: llm:gpt-4o-mini</sub>

### ✅ JE-004: Bad debt provision top-up

**Journal Entry Accepted**

The journal entry for the bad debt provision top-up has been accepted. It aligns with the AR aging review and appropriately reflects the necessary adjustments to the reserve and allowance accounts. The debit and credit amounts are balanced, ensuring compliance with accounting principles.

*What to do:* No changes needed.

<sub>hash 73539254d54249f7 · explanation: llm:gpt-4o-mini</sub>

### ⚠️ JE-005: Reclass conference travel from old code

**Journal Entry Quarantined**

Your journal entry JE-005 has been quarantined because it includes a line posting to account 6315, which does not exist in the chart of accounts. The closest match is account 6310, but mapping to it would result in both sides of the entry being on the same account, rendering it ineffective. This suggests you may need a new account.

*What to do:* Please correct the account code to one that exists, request the creation of account 6315 from the COA owner, or approve a mapping in overrides.json for re-checking.

<sub>hash 680309371d536d48 · explanation: llm:gpt-4o-mini</sub>

### ✅ JE-006: Depreciation catch-up — Q4

**Journal Entry Accepted**

The journal entry JE-006 for depreciation catch-up has been accepted. It includes a debit to account 6500 and a credit to account 1211, which are appropriate for recording depreciation. The amounts are balanced, and the entry aligns with standard accounting practices for fixed asset depreciation.

*What to do:* No changes are needed as the entry has been accepted.

<sub>hash 020f7159c0031d9c · explanation: llm:gpt-4o-mini</sub>

### ✅ JE-007: Deferred tax true-up

**Journal Entry Accepted**

The journal entry JE-007 for the deferred tax true-up has been accepted. It includes a debit to account 8200 for DTA reduction and a corresponding credit to account 1250 to reduce DTA. The amounts are balanced, and the entry aligns with the tax provision memo dated 2024-12-31.

*What to do:* No action needed as the entry has been accepted.

<sub>hash 7e2fada3a4111e13 · explanation: llm:gpt-4o-mini</sub>

### ❌ JE-008: Intercompany settlement — UK sub

**Journal Entry JE-008 Rejected**

The journal entry was rejected because it nets to zero on the same account (2170). Both a debit and credit of 320,000.00 were recorded, which means the entry has no effect. This typically indicates that a counterparty account was entered incorrectly.

*What to do:* Identify the correct counterparty account (e.g., cash or an intercompany receivable) and resubmit the entry.

<sub>hash 6f60da6bc732236b · explanation: llm:gpt-4o-mini</sub>

### ✅ JE-009: Accrue legal fees for ongoing litigation

**Journal Entry Accepted**

The journal entry for accruing legal fees related to ongoing litigation has been accepted. It includes a debit to account 6400 and a credit to account 2120, which are appropriate for this type of transaction. The entry is supported by a legal memo dated December 29, 2024, which provides the necessary documentation for the accrual.

*What to do:* No action needed; the entry is accepted.

<sub>hash 1995895fa654e725 · explanation: llm:gpt-4o-mini</sub>

### ✅ JE-010: Reclass long-term debt current portion

**Journal Entry Accepted**

The journal entry JE-010 for reclassifying the long-term debt's current portion has been accepted. It aligns with the Treasury schedule and correctly reflects the movement of funds between accounts 2210 and 2140. The debit and credit amounts are balanced, ensuring proper accounting practices.

*What to do:* No action needed, the entry is accepted.

<sub>hash f9d1755b29c2f75d · explanation: llm:gpt-4o-mini</sub>

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
