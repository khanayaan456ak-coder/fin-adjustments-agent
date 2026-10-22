"""Deterministic validation rules for manual journal entries.

Every rule returns Findings. The DECISION is made here, by code, never by the LLM:
  any ERROR -> REJECTED     (must be fixed at source, cannot be overridden)
  any HOLD  -> QUARANTINED  (needs a human decision, can be overridden)
  otherwise -> ACCEPTED     (WARN findings are attached as review flags)
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal

from .loaders import Inputs, JournalEntry, fmt
from .mapper import suggest_accounts
from .preflight import is_descendant

ERROR, HOLD, WARN, INFO = "ERROR", "HOLD", "WARN", "INFO"
REJECTED, QUARANTINED, ACCEPTED = "REJECTED", "QUARANTINED", "ACCEPTED"


@dataclass
class Finding:
    rule: str
    severity: str
    message: str  # plain English, written for a finance user
    fix: str = ""
    facts: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class Config:
    tolerance: Decimal = Decimal("0.01")
    fx_tolerance_pct: Decimal = Decimal("0.01")
    materiality_pct_of_pretax: Decimal = Decimal("0.05")  # assumption; audit team would set this


def quarter_bounds(period: str) -> tuple[date, date]:
    m = re.fullmatch(r"(\d{4})-Q([1-4])", period.strip())
    if not m:
        raise ValueError(f"Unsupported period format: {period!r}")
    y, q = int(m.group(1)), int(m.group(2))
    start = date(y, 3 * q - 2, 1)
    end = date(y + 1, 1, 1) if q == 4 else date(y, 3 * q + 1, 1)
    return start, date.fromordinal(end.toordinal() - 1)


class Context:
    """Facts about the inputs that rules need (computed once, deterministic)."""

    def __init__(self, inp: Inputs, config: Config | None = None):
        self.inp, self.coa, self.config = inp, inp.coa, config or Config()
        self.period_start, self.period_end = quarter_bounds(inp.period)
        self.usd_balance: dict[str, Decimal] = defaultdict(Decimal)
        self.has_foreign: set[str] = set()
        for r in inp.tb:
            if r.currency == inp.functional_currency:
                self.usd_balance[r.account_code] += r.net
            else:
                self.has_foreign.add(r.account_code)
        tax_root = next((a.code for a in inp.coa_rows if a.name.lower().startswith("income tax expense")), None)
        pl = [r for r in inp.tb if r.account_code in self.coa and self.coa[r.account_code].statement == "PL"
              and r.currency == inp.functional_currency
              and not (tax_root and is_descendant(r.account_code, tax_root, self.coa))]
        self.pretax_income = -sum((r.net for r in pl), Decimal("0"))
        self.materiality = (abs(self.pretax_income) * self.config.materiality_pct_of_pretax).quantize(Decimal("0.01"))


# ---------------------------------------------------------------- rules

def r_structure(e: JournalEntry, ctx: Context) -> list[Finding]:
    out = []
    for msg in e.errors:
        out.append(Finding("STRUCTURE", ERROR, msg, "Correct the entry data and resubmit."))
    if len(e.lines) < 2:
        out.append(Finding("STRUCTURE", ERROR, f"{e.id} has {len(e.lines)} line(s); an entry needs at least two.",
                           "Add the offsetting line."))
    for ln in e.lines:
        for msg in ln.errors:
            out.append(Finding("STRUCTURE", ERROR, f"Line {ln.ref} has an unreadable amount ({msg}).",
                               "Correct the amount."))
        if ln.debit < 0 or ln.credit < 0:
            out.append(Finding("STRUCTURE", ERROR, f"Line {ln.ref} has a negative amount.",
                               "Use the opposite column instead of a negative number."))
        if (ln.debit > 0) == (ln.credit > 0):
            out.append(Finding("STRUCTURE", ERROR,
                               f"Line {ln.ref} must have exactly one of debit or credit filled in.",
                               "Put the amount in one column only."))
    return out


def r_balance(e: JournalEntry, ctx: Context) -> list[Finding]:
    dr = sum((l.debit for l in e.lines), Decimal("0"))
    cr = sum((l.credit for l in e.lines), Decimal("0"))
    diff = dr - cr
    if abs(diff) <= ctx.config.tolerance:
        return []
    return [Finding(
        "DEBITS_NOT_EQUAL_CREDITS", ERROR,
        f"Total debits are {fmt(dr)} but total credits are {fmt(cr)}, a difference of {fmt(abs(diff))}. "
        f"An entry must balance before it can be posted, and the system will not guess which side is wrong.",
        f"Confirm the correct amount with the preparer and resubmit with debits equal to credits "
        f"(either both {fmt(dr)} or both {fmt(cr)}).",
        {"total_debits": fmt(dr), "total_credits": fmt(cr), "difference": fmt(abs(diff))})]


def r_accounts(e: JournalEntry, ctx: Context) -> list[Finding]:
    out = []
    for ln in e.lines:
        acc = ctx.coa.get(ln.account)
        if acc is None:
            cands = suggest_accounts(ln.account, f"{ln.memo} {e.description}", ctx.coa)
            other = {l.account for l in e.lines if l is not ln}
            clash = [c["code"] for c in cands if c["code"] in other]
            msg = (f"Line {ln.ref} posts {fmt(ln.debit or ln.credit)} to account {ln.account}, "
                   f"which does not exist in the chart of accounts.")
            if cands:
                msg += " Closest matches: " + "; ".join(
                    f"{c['code']} {c['name']} ({c['confidence']} confidence)" for c in cands) + "."
            if clash:
                msg += (f" Note: mapping to {', '.join(clash)} would put both sides of this entry on the same "
                        f"account, so it would have no effect. The preparer may intend a new account.")
            out.append(Finding("ACCOUNT_NOT_IN_COA", HOLD, msg,
                               "Either correct the account code, or have the COA owner create the account, "
                               "or approve a mapping in overrides.json (the entry is then re-checked).",
                               {"account": ln.account, "candidates": cands, "candidate_clashes": clash}))
        elif acc.is_header:
            out.append(Finding("POSTED_TO_HEADER", ERROR,
                               f"Line {ln.ref} posts to {acc.code} '{acc.name}', which is a header (total) account.",
                               "Post to one of its child accounts instead."))
    return out


def r_self_offset(e: JournalEntry, ctx: Context) -> list[Finding]:
    net = defaultdict(Decimal)
    sides = defaultdict(set)
    for ln in e.lines:
        net[ln.account] += ln.net
        sides[ln.account].add("Dr" if ln.debit else "Cr")
    total = sum((l.debit for l in e.lines), Decimal("0"))
    both = [a for a, s in sides.items() if len(s) == 2]
    if total > 0 and all(v == 0 for v in net.values()):
        return [Finding(
            "CIRCULAR_NO_EFFECT", ERROR,
            f"Every line nets to zero on the same account(s) ({', '.join(both)}): {fmt(total)} is debited and "
            f"credited to the same place, so the entry changes nothing. This usually means a counterparty "
            f"account was keyed wrongly.",
            "Identify the real counterparty account (e.g., cash or an intercompany receivable) and resubmit.",
            {"accounts": both, "amount": fmt(total)})]
    if both:
        return [Finding("SAME_ACCOUNT_BOTH_SIDES", WARN,
                        f"Account(s) {', '.join(both)} appear on both the debit and credit side.",
                        "Check this is intended.", {"accounts": both})]
    return []


def r_intercompany(e: JournalEntry, ctx: Context) -> list[Finding]:
    ic = [l.account for l in e.lines if l.account in ctx.coa and "intercompany" in ctx.coa[l.account].name.lower()]
    if not ic:
        return []
    others = [a for a in ctx.coa.values() if "intercompany" in a.name.lower() and a.code not in ic]
    if others:
        return []
    return [Finding("IC_NO_COUNTERPARTY", WARN,
                    f"The chart of accounts has no intercompany receivable or counterparty account to match "
                    f"{', '.join(sorted(set(ic)))} against, so this cannot be reconciled or eliminated with the "
                    f"other entity's books.",
                    "Confirm the counterparty entity and account.", {"accounts": sorted(set(ic))})]


def r_period(e: JournalEntry, ctx: Context) -> list[Finding]:
    try:
        d = date.fromisoformat(e.date)
    except ValueError:
        return [Finding("DATE_INVALID", ERROR, f"Entry date '{e.date}' is not a valid date.", "Use YYYY-MM-DD.")]
    if not (ctx.period_start <= d <= ctx.period_end):
        return [Finding("DATE_OUTSIDE_PERIOD", ERROR,
                        f"Entry date {e.date} is outside the period {ctx.inp.period} "
                        f"({ctx.period_start} to {ctx.period_end}).", "Post it in the correct period.")]
    return []


def r_fx_reval(e: JournalEntry, ctx: Context) -> list[Finding]:
    text = f"{e.description} {' '.join(l.memo for l in e.lines)}"
    touches_fx = any(l.account in ctx.coa and "fx" in ctx.coa[l.account].name.lower() for l in e.lines)
    if not (touches_fx or "reval" in text.lower()):
        return []
    fx, func = ctx.inp.fx, ctx.inp.functional_currency
    mentioned = {c for c in re.findall(r"\b[A-Z]{3}\b", text) if c != func}
    out = []
    for ln in e.lines:
        if ln.account not in ctx.has_foreign:
            continue
        for cur in sorted(mentioned or {r.currency for r in ctx.inp.tb
                                        if r.account_code == ln.account and r.currency != func}):
            bal = sum((r.net for r in ctx.inp.tb if r.account_code == ln.account and r.currency == cur), Decimal("0"))
            end = fx.get((cur, "period_end"))
            if end is None:
                out.append(Finding("FX_RATE_MISSING", HOLD,
                                   f"There is no period-end rate for {cur}, so the revaluation cannot be checked.",
                                   f"Provide the {cur} period-end rate."))
                continue
            expected = {}
            for basis in ("period_average", "opening"):
                if (cur, basis) in fx:
                    expected[basis] = (bal * (end - fx[(cur, basis)])).quantize(Decimal("0.01"))
            booked = ln.net
            ok = any(abs(booked - v) <= max(Decimal("1.00"), abs(v) * ctx.config.fx_tolerance_pct)
                     for v in expected.values())
            if not ok:
                calc = "; ".join(f"from {k.replace('_', ' ')} rate {fx[(cur, k)]}: "
                                 f"{cur} {fmt(bal)} x ({end} - {fx[(cur, k)]}) = {fmt(v)}"
                                 for k, v in expected.items())
                out.append(Finding(
                    "FX_REVAL_MISMATCH", HOLD,
                    f"The entry books {fmt(booked)} of revaluation on {ln.account} ({cur}), but recalculating from "
                    f"the trial balance and the given rates does not reproduce it ({calc}). Also, if the trial "
                    f"balance is translated at the period-end rate anyway, this entry would count the "
                    f"revaluation twice.",
                    "Share the revaluation workings and confirm whether TB foreign rows are in local currency.",
                    {"booked": fmt(booked), "foreign_balance": fmt(bal), "currency": cur,
                     "expected": {k: fmt(v) for k, v in expected.items()}}))
    return out


def r_materiality(e: JournalEntry, ctx: Context) -> list[Finding]:
    total = sum((l.debit for l in e.lines), Decimal("0"))
    if ctx.materiality and total > ctx.materiality:
        return [Finding("MATERIAL_ENTRY", WARN,
                        f"This entry ({fmt(total)}) is above the materiality threshold of {fmt(ctx.materiality)} "
                        f"(5% of pre-tax income {fmt(ctx.pretax_income)}). It can be posted but needs "
                        f"documented approval and supporting workings.",
                        "Attach approval evidence (e.g., Controller sign-off).",
                        {"amount": fmt(total), "threshold": fmt(ctx.materiality),
                         "pretax_income": fmt(ctx.pretax_income)})]
    return []


def r_sign_flip(e: JournalEntry, ctx: Context) -> list[Finding]:
    out = []
    change = defaultdict(Decimal)
    for ln in e.lines:
        change[ln.account] += ln.net
    for code, delta in change.items():
        acc = ctx.coa.get(code)
        if not acc or code in ctx.has_foreign or not acc.normal_balance:
            continue
        if "gain" in acc.name.lower():  # dual-nature gain/loss accounts legitimately swing either way
            continue
        pre = ctx.usd_balance.get(code, Decimal("0"))
        post = pre + delta
        def wrong(v):
            return v < 0 if acc.normal_balance == "Debit" else v > 0
        if wrong(post) and not wrong(pre):  # only flag flips CAUSED by this entry
            out.append(Finding("BALANCE_FLIPS_SIGN", WARN,
                               f"After this entry {code} '{acc.name}' would have a balance of {fmt(post)} "
                               f"(debit-positive), opposite to its normal {acc.normal_balance.lower()} balance.",
                               "Check the amount and direction.", {"account": code, "post_balance": fmt(post)}))
    return out


def r_reclass_scope(e: JournalEntry, ctx: Context) -> list[Finding]:
    if "reclass" not in e.description.lower():
        return []
    stmts = {ctx.coa[l.account].statement for l in e.lines if l.account in ctx.coa}
    if len(stmts) > 1:
        return [Finding("RECLASS_CROSSES_STATEMENTS", WARN,
                        "Described as a reclass but moves amounts between the balance sheet and P&L, "
                        "which changes profit.", "Confirm this is not an expense/capitalisation decision.")]
    return []


RULES = [r_structure, r_balance, r_accounts, r_self_offset, r_intercompany, r_period,
         r_fx_reval, r_materiality, r_sign_flip, r_reclass_scope]


def validate_entry(e: JournalEntry, ctx: Context, skip: set[str] = frozenset()) -> list[Finding]:
    findings = []
    for rule in RULES:
        findings.extend(f for f in rule(e, ctx) if f.rule not in skip)
    return findings


def validate_batch(entries: list[JournalEntry]) -> dict[str, list[Finding]]:
    """Cross-entry checks: duplicate ids, identical entries."""
    extra = defaultdict(list)
    ids = defaultdict(list)
    sigs = defaultdict(list)
    for e in entries:
        ids[e.id].append(e)
        sigs[tuple(sorted((l.account, str(l.debit), str(l.credit)) for l in e.lines))].append(e.id)
    for id_, es in ids.items():
        if len(es) > 1:
            for e in es:
                extra[e.content_hash].append(Finding("DUPLICATE_ENTRY_ID", ERROR,
                                                     f"Entry id {id_} is used {len(es)} times in this batch.",
                                                     "Give each entry a unique id."))
    for sig, id_list in sigs.items():
        if len(id_list) > 1:
            for e in entries:
                if e.id in id_list:
                    extra[e.content_hash].append(Finding("POSSIBLE_DUPLICATE_ENTRY", WARN,
                                                         f"Entries {', '.join(id_list)} have identical lines.",
                                                         "Confirm this is not posted twice."))
    return extra


def decide(findings: list[Finding]) -> str:
    sev = {f.severity for f in findings}
    if ERROR in sev:
        return REJECTED
    if HOLD in sev:
        return QUARANTINED
    return ACCEPTED
