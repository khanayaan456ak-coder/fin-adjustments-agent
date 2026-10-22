"""Load raw inputs exactly as given, attaching a source reference to every row.

Nothing here cleans or fixes data. Every TB row gets a ref like
"trial_balance.csv:19" (file name + line number) and every journal line gets
"JE-001#L2", so any number downstream can be traced back to where it came from.
"""
from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

CENT = Decimal("0.01")


def money(value) -> Decimal:
    """Parse a money value into Decimal (never float) rounded to cents."""
    if value is None or str(value).strip() == "":
        return Decimal("0.00")
    try:
        return Decimal(str(value).strip()).quantize(CENT)
    except InvalidOperation as exc:
        raise ValueError(f"not a number: {value!r}") from exc


def fmt(amount: Decimal) -> str:
    return f"{amount:,.2f}"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class TBRow:
    ref: str
    account_code: str
    account_name: str
    currency: str
    debit: Decimal
    credit: Decimal

    @property
    def net(self) -> Decimal:  # debit-positive
        return self.debit - self.credit


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    type: str
    parent: str
    statement: str
    cf_category: str
    normal_balance: str
    ref: str

    @property
    def is_header(self) -> bool:
        return self.type == "Header"


@dataclass
class JELine:
    ref: str
    account: str
    debit: Decimal
    credit: Decimal
    memo: str
    errors: list[str] = field(default_factory=list)

    @property
    def net(self) -> Decimal:
        return self.debit - self.credit


@dataclass
class JournalEntry:
    id: str
    description: str
    date: str
    source: str
    lines: list[JELine]
    content_hash: str
    raw: dict
    errors: list[str] = field(default_factory=list)


@dataclass
class Inputs:
    tb: list[TBRow]
    prior_tb: list[TBRow]
    coa: dict[str, Account]
    coa_rows: list[Account]
    fx: dict[tuple[str, str], Decimal]
    batch: dict
    entries: list[JournalEntry]
    file_hashes: dict[str, str]
    period: str
    functional_currency: str


def load_tb(path: Path) -> list[TBRow]:
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for line_no, r in enumerate(csv.DictReader(f), start=2):
            ref = f"{path.name}:{line_no}"
            try:
                rows.append(TBRow(ref, r["account_code"].strip(), r["account_name"].strip(),
                                  r["currency"].strip().upper(), money(r["debit"]), money(r["credit"])))
            except ValueError as exc:  # fail loudly at ingestion with the exact row
                raise ValueError(f"{ref}: {exc}") from exc
    return rows


def load_coa(path: Path) -> list[Account]:
    out = []
    with path.open(newline="", encoding="utf-8") as f:
        for line_no, r in enumerate(csv.DictReader(f), start=2):
            out.append(Account(
                code=r["account_code"].strip(), name=r["account_name"].strip(),
                type=r["account_type"].strip(), parent=(r["parent_code"] or "").strip(),
                statement=r["statement"].strip(), cf_category=(r["cf_category"] or "").strip(),
                normal_balance=(r["normal_balance"] or "").strip(), ref=f"{path.name}:{line_no}"))
    return out


def load_fx(path: Path) -> dict[tuple[str, str], Decimal]:
    fx = {}
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fx[(r["currency"].strip().upper(), r["rate_type"].strip())] = Decimal(r["rate"].strip())
    return fx


def _parse_entry(raw: dict) -> JournalEntry:
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    entry = JournalEntry(
        id=str(raw.get("id", "")).strip(), description=str(raw.get("description", "")),
        date=str(raw.get("date", "")), source=str(raw.get("source", "")), lines=[],
        content_hash=hashlib.sha256(canonical.encode()).hexdigest()[:16], raw=raw)
    if not entry.id:
        entry.errors.append("Entry has no id.")
    for i, rl in enumerate(raw.get("lines") or [], start=1):
        line = JELine(ref=f"{entry.id}#L{i}", account=str(rl.get("account", "")).strip(),
                      debit=Decimal("0.00"), credit=Decimal("0.00"), memo=str(rl.get("memo", "")))
        for side in ("debit", "credit"):
            try:
                setattr(line, side, money(rl.get(side)))
            except ValueError as exc:
                line.errors.append(f"{side}: {exc}")
        entry.lines.append(line)
    return entry


def load_inputs(inputs_dir: Path) -> Inputs:
    inputs_dir = Path(inputs_dir)
    files = {
        "trial_balance": inputs_dir / "trial_balance.csv",
        "prior_period_tb": inputs_dir / "prior_period_tb.csv",
        "chart_of_accounts": inputs_dir / "chart_of_accounts.csv",
        "fx_rates": inputs_dir / "fx_rates.csv",
        "manual_adjustments": inputs_dir / "manual_adjustments.json",
    }
    coa_rows = load_coa(files["chart_of_accounts"])
    batch = json.loads(files["manual_adjustments"].read_text(encoding="utf-8"))
    return Inputs(
        tb=load_tb(files["trial_balance"]),
        prior_tb=load_tb(files["prior_period_tb"]),
        coa={a.code: a for a in coa_rows},
        coa_rows=coa_rows,
        fx=load_fx(files["fx_rates"]),
        batch={k: v for k, v in batch.items() if k != "entries"},
        entries=[_parse_entry(e) for e in batch.get("entries", [])],
        file_hashes={p.name: sha256_file(p) for p in files.values()},
        period=batch.get("period", ""),
        functional_currency=batch.get("functional_currency", "USD"),
    )
