"""Apply ACCEPTED entries to the trial balance with full lineage, then verify.

Output is kept per (account, currency) in the amounts given by the TB; the
adjustments are in the functional currency (USD) as stated in the batch.
Translation to USD is deliberately NOT done here (blocked on the FX question).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from .loaders import Inputs, JournalEntry, fmt

Z = Decimal("0.00")


@dataclass
class LedgerLine:
    account_code: str
    account_name: str
    currency: str
    pre_debit: Decimal = Z
    pre_credit: Decimal = Z
    adj_debit: Decimal = Z
    adj_credit: Decimal = Z
    sources: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def post_net(self) -> Decimal:
        return self.pre_debit - self.pre_credit + self.adj_debit - self.adj_credit


class PostingInvariantError(RuntimeError):
    pass


def post(inp: Inputs, accepted: list[JournalEntry]) -> list[LedgerLine]:
    ledger: dict[tuple[str, str], LedgerLine] = {}
    tb_rows_per_key = defaultdict(int)

    def get(code, cur, name=""):
        key = (code, cur)
        if key not in ledger:
            acc = inp.coa.get(code)
            ledger[key] = LedgerLine(code, acc.name if acc else name, cur)
        return ledger[key]

    for r in inp.tb:
        ln = get(r.account_code, r.currency, r.account_name)
        ln.pre_debit += r.debit
        ln.pre_credit += r.credit
        ln.sources.append(r.ref)
        tb_rows_per_key[(r.account_code, r.currency)] += 1
    for (code, cur), n in tb_rows_per_key.items():
        if n > 1:
            ledger[(code, cur)].flags.append("DUPLICATE_SOURCE_ROWS")
        if code not in inp.coa:
            ledger[(code, cur)].flags.append("NOT_IN_COA")

    for e in accepted:
        for l in e.lines:
            ln = get(l.account, inp.functional_currency)
            ln.adj_debit += l.debit
            ln.adj_credit += l.credit
            ln.sources.append(l.ref)

    verify(inp, accepted, list(ledger.values()))
    return sorted(ledger.values(), key=lambda x: (x.account_code, x.currency != inp.functional_currency, x.currency))


def verify(inp: Inputs, accepted: list[JournalEntry], ledger: list[LedgerLine]) -> None:
    """Checks that must hold before ANY output is written. Violations abort the run."""
    adj_dr = sum((l.adj_debit for l in ledger), Z)
    adj_cr = sum((l.adj_credit for l in ledger), Z)
    if adj_dr != adj_cr:
        raise PostingInvariantError(f"Posted adjustments do not balance: Dr {fmt(adj_dr)} vs Cr {fmt(adj_cr)}")
    exp_dr = sum((l.debit for e in accepted for l in e.lines), Z)
    if adj_dr != exp_dr:
        raise PostingInvariantError("Posted adjustment total differs from accepted entries total")
    for e in accepted:
        for l in e.lines:
            if l.account not in inp.coa or inp.coa[l.account].is_header:
                raise PostingInvariantError(f"{l.ref} posts to invalid account {l.account}")
    tb_dr = sum((r.debit for r in inp.tb), Z)
    if sum((l.pre_debit for l in ledger), Z) != tb_dr:
        raise PostingInvariantError("Ledger lost or duplicated trial balance rows")


def trace_lines(inp: Inputs, ledger: list[LedgerLine], account: str) -> list[str]:
    lines = [l for l in ledger if l.account_code == account]
    if not lines:
        return [f"Account {account} has no balance in the post-adjustment TB."]
    tb_by_ref = {r.ref: r for r in inp.tb}
    je_lines = {l.ref: (e, l) for e in inp.entries for l in e.lines}
    out = []
    for ln in lines:
        out.append(f"{ln.account_code} {ln.account_name} [{ln.currency}]  post-adjustment net "
                   f"{fmt(ln.post_net)} (debit-positive)" + (f"  flags={ln.flags}" if ln.flags else ""))
        for ref in ln.sources:
            if ref in tb_by_ref:
                r = tb_by_ref[ref]
                out.append(f"  <- {ref:<26} TB row      Dr {fmt(r.debit):>16}  Cr {fmt(r.credit):>16}")
            else:
                e, l = je_lines[ref]
                out.append(f"  <- {ref:<26} {e.id} adj  Dr {fmt(l.debit):>16}  Cr {fmt(l.credit):>16}"
                           f"  '{e.description}' (source: {e.source})")
    return out
