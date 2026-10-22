# Defect inventory

**Seeded** = listed in the PDF. **Found** = not listed; discovered while profiling the data. Every item is detected by code (`output/input_diagnostics.json` or `output/adjustment_decisions.json`). None of them were fixed by hand.

| # | Type | File | Defect | Handling |
|---|---|---|---|---|
| 1 | Seeded | trial_balance | TB does not balance: raw −4,800; translated −338,687 at period-end (GBP excluded) / +171,730 at average. Far larger than rounding. | ERROR in diagnostics; asked client about basis |
| 2 | Seeded | trial_balance | 6310 T&E appears twice in USD (245,000 + 38,500) | Kept both rows, flagged `DUPLICATE_SOURCE_ROWS`, HOLD |
| 3 | Seeded | trial_balance | 9999 Suspense (12,400) not in COA | HOLD, no credible mapping |
| 4 | Seeded | COA | 1150 and 2170 cash-flow category = TBD | HOLD (CF blocked) |
| 5 | Seeded | COA | 1290 header has no children | WARN |
| 6 | Seeded | adjustments | JE-002 Dr 28,500 ≠ Cr 25,000 | **REJECTED** |
| 7 | Seeded | adjustments | JE-005 uses account 6315 (not in COA) | **QUARANTINED** with candidates |
| 8 | Seeded | adjustments | JE-008 debits and credits 2170 (circular IC) | **REJECTED** |
| 9 | Seeded | prior TB | 6905 'Sundry Operating Expenses' renamed to 6900 'Other Operating Expenses' | HOLD, 6900 suggested (high confidence), not auto-applied |
| 10 | Seeded | fx_rates | GBP has no period-end rate | HOLD, no fallback |
| 11 | Found | adjustments | JE-003 books 11,200 but EUR 825,400 × (1.095 − 1.082) = 10,730.20 (19,809.60 from opening). Plus double-count risk if TB is translated at period-end. | **QUARANTINED** with workings |
| 12 | Found | adjustments | Mapping 6315→6310 (the obvious fix for JE-005) makes the entry self-offsetting | Flagged in the candidate list; re-validation rejects it (HITL demo) |
| 13 | Found | adjustments | JE-001 (850,000) exceeds materiality (340,325 = 5% of pre-tax income 6,806,500) | ACCEPTED with approval flag |
| 14 | Found | adjustments | COA has no intercompany receivable or counterparty account; IC cannot be eliminated | WARN on JE-008 |
| 15 | Found | TB vs prior | Retained earnings 5,180,000 → 7,240,000 (+2,060,000) while P&L is still open | HOLD (SOCIE blocked); asked client |
| 16 | Found | prior TB | Prior TB does not balance (raw +2,832,800) and has no P&L accounts except 6905 | ERROR + WARN |
| 17 | Found | TB vs prior | PPE cost 11,800,000 → 17,007,700 (+5,207,700, +44%) with no capex entry | WARN |
| 18 | Found | fx_rates | Undocumented `opening` rate type; no USD opening row | INFO |
| 19 | Found | COA | 3300 Accumulated OCI typed Equity but is a parent of 3310 | WARN |
| 20 | Found | COA | 8000 Income Tax Expense typed Expense but is a top-level parent of 8100/8200 | WARN |
| 21 | Found | COA | 7000 Non-Operating Items has no normal balance | WARN |
| 22 | Found | COA | Contra accounts (1121, 1211, 1221, 3400, 4200) have a normal balance opposite to their type | INFO; sign logic uses `normal_balance` |
| 23 | Found | COA | 7310 Unrealized FX and 7400 Disposal gain are non-cash but tagged Operating / Investing | INFO for the CF builder (add-back) |
| 24 | Found | brief | PDF says "~80 accounts"; the TB has 62 rows covering 59 distinct accounts | noted |
