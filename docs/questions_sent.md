# Clarifying questions sent before starting

**To:** Mahak Sahu (cc: Kunal Tomar) · **Subject:** Re: AI Developer Assignment - AskGalore · **Sent:** 23 Oct 2026

> Hi Mahak,
>
> Thanks for sending the assignment. I went through the data and had 3 quick questions before I go further:
>
> 1. Are the EUR and GBP amounts in the trial balance in their own currency, or already converted to USD? This affects JE-003. When I recalculate the EUR revaluation using the given rates, I get around 10,730, not 11,200. Also, GBP doesn't have a period-end rate. Should I block it or use another rate?
>
> 2. Retained earnings goes from 5.18M in the prior TB to 7.24M now, but the P&L accounts are still open. Was there a dividend, restatement or partial close I should know about? The prior TB also doesn't balance on its own.
>
> 3. JE-008 debits and credits the same intercompany account (2170) for 320,000, so it has no effect. Should I treat it as an error and reject it? And who would normally approve entries that the system puts on hold, the Controller?
>
> So I don't hold things up, I'm continuing with safe assumptions for now (reject unbalanced entries, hold anything with missing data) and will note them in my submission.
>
> Thanks,
> Ayaan Khan

## Assumptions used while waiting

| Question | Assumption in the prototype |
|---|---|
| 1. FX basis | TB foreign rows are local currency; adjustments are USD. A missing rate **blocks** (no fallback). JE-003 is quarantined with the workings shown. |
| 2. Retained earnings | Not inferred. Flagged as HOLD; SOCIE would be blocked until answered. |
| 3. Intercompany / approver | JE-008 rejected. Overrides need a named approver (Controller assumed). ERRORs cannot be overridden. |
