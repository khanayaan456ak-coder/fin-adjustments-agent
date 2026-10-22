"""Input diagnostics: find what is wrong with the inputs BEFORE touching adjustments.

All checks are deterministic. Each issue carries evidence (source refs) so a
reviewer can open the exact row. Nothing is auto-fixed.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .loaders import Inputs, TBRow, fmt
from .mapper import suggest_accounts

DEFAULT_NORMAL = {"Asset": "Debit", "Expense": "Debit",
                  "Liability": "Credit", "Equity": "Credit", "Revenue": "Credit"}


def issue(id_, severity, title, detail, evidence=None, **facts):
    return {"id": id_, "severity": severity, "title": title, "detail": detail,
            "evidence": evidence or [], "facts": facts}


def translate(rows: list[TBRow], fx, rate_type: str, functional: str):
    """Translate TB to functional currency with one rate type. Never guesses a missing rate."""
    dr = cr = Decimal("0")
    missing = set()
    for r in rows:
        if r.currency == functional:
            rate = Decimal("1")
        else:
            rate = fx.get((r.currency, rate_type))
            if rate is None:
                missing.add(r.currency)
                continue  # excluded, reported as missing
        dr += r.debit * rate
        cr += r.credit * rate
    return dr.quantize(Decimal("0.01")), cr.quantize(Decimal("0.01")), sorted(missing)


def is_descendant(code: str, ancestor: str, coa) -> bool:
    seen = set()
    while code and code not in seen:
        if code == ancestor:
            return True
        seen.add(code)
        code = coa[code].parent if code in coa else ""
    return False


def run_preflight(inp: Inputs) -> list[dict]:
    out: list[dict] = []
    coa, fx, func = inp.coa, inp.fx, inp.functional_currency

    # 1. TB balance: raw and translated
    for label, rows in (("current", inp.tb), ("prior", inp.prior_tb)):
        raw_dr = sum((r.debit for r in rows), Decimal("0"))
        raw_cr = sum((r.credit for r in rows), Decimal("0"))
        res = {}
        for rt in ("period_end", "period_average"):
            dr, cr, missing = translate(rows, fx, rt, func)
            res[rt] = {"debits": fmt(dr), "credits": fmt(cr), "difference": fmt(dr - cr),
                       "currencies_excluded_missing_rate": missing}
        if raw_dr != raw_cr or any(v["difference"] != "0.00" for v in res.values()):
            out.append(issue(
                f"TB_UNBALANCED_{label.upper()}", "ERROR", f"{label.title()} trial balance does not balance",
                f"Raw (mixed-currency) debits {fmt(raw_dr)} vs credits {fmt(raw_cr)}, difference "
                f"{fmt(raw_dr - raw_cr)}. Translated differences are far larger than rounding, so this "
                f"is not an 'FX rounding' issue: it depends on whether foreign rows are in local "
                f"currency and which rate applies (asked the client).",
                raw_difference=fmt(raw_dr - raw_cr), translated=res))

    # 2. Duplicate (account, currency) rows
    for label, rows in (("current", inp.tb), ("prior", inp.prior_tb)):
        groups = defaultdict(list)
        for r in rows:
            groups[(r.account_code, r.currency)].append(r)
        for (code, cur), rs in groups.items():
            if len(rs) > 1:
                out.append(issue(
                    "TB_DUPLICATE_ROW", "HOLD", f"Account {code} ({cur}) appears {len(rs)} times in {label} TB",
                    "Kept both rows (not deduplicated) because it could be a genuine split or a double "
                    "export. Needs confirmation from the ERP owner. Amounts: "
                    + ", ".join(fmt(r.net) for r in rs),
                    [r.ref for r in rs], account=code))

    # 3. Accounts not in COA (orphans)
    for label, rows in (("current", inp.tb), ("prior", inp.prior_tb)):
        for r in rows:
            if r.account_code not in coa:
                cands = suggest_accounts(r.account_code, r.account_name, coa)
                prior_rename = label == "prior"
                out.append(issue(
                    "TB_ACCOUNT_NOT_IN_COA", "HOLD",
                    f"{label.title()} TB account {r.account_code} '{r.account_name}' is not in the COA",
                    ("Likely renamed/re-coded since prior period. " if prior_rename else "")
                    + "Not mapped automatically. Candidate mappings for human review: "
                    + ("; ".join(f"{c['code']} {c['name']} ({c['confidence']}, {c['score']})" for c in cands)
                       or "none credible"),
                    [r.ref], account=r.account_code, amount=fmt(r.net), candidates=cands))
        for r in rows:
            if r.account_code in coa and coa[r.account_code].is_header:
                out.append(issue("TB_POSTED_TO_HEADER", "ERROR", f"Balance posted to header {r.account_code}",
                                 "Header accounts are totals and cannot carry balances.", [r.ref]))

    # 4. FX rate gaps
    foreign = sorted({r.currency for r in inp.tb + inp.prior_tb if r.currency != func})
    for cur in foreign:
        for rt in ("period_end", "period_average", "opening"):
            if (cur, rt) not in fx:
                out.append(issue("FX_RATE_MISSING", "HOLD" if rt == "period_end" else "WARN",
                                 f"No {rt} rate for {cur}",
                                 f"{cur} balance sheet rows cannot be translated at {rt}. "
                                 "System blocks rather than falling back to another rate.",
                                 [], currency=cur, rate_type=rt))
    if (func, "opening") not in fx and any(k[1] == "opening" for k in fx):
        out.append(issue("FX_RATE_TABLE_INCONSISTENT", "INFO", "Undocumented 'opening' rate type, USD row missing",
                         "fx_rates.csv has 'opening' rates for EUR/GBP but not USD, and the README does not "
                         "document this rate type.", []))

    # 5. COA structure problems
    children = defaultdict(list)
    for a in inp.coa_rows:
        if a.parent:
            children[a.parent].append(a.code)
    for a in inp.coa_rows:
        if a.is_header and not children[a.code]:
            out.append(issue("COA_EMPTY_HEADER", "WARN", f"Header {a.code} '{a.name}' has no children",
                             "Statement line would always be zero; mapping may be missing.", [a.ref]))
        if not a.is_header and children[a.code]:
            out.append(issue("COA_NON_HEADER_PARENT", "WARN",
                             f"{a.code} '{a.name}' is typed {a.type} but is a parent of {', '.join(children[a.code])}",
                             "Ambiguous: is it a posting account or a subtotal? Risk of double counting.", [a.ref]))
        if a.cf_category == "TBD":
            out.append(issue("COA_AMBIGUOUS_CF", "HOLD", f"{a.code} '{a.name}' has cash-flow category TBD",
                             "Cash flow statement cannot classify this account until finance decides.", [a.ref]))
        if not a.normal_balance:
            out.append(issue("COA_MISSING_NORMAL_BALANCE", "WARN", f"{a.code} '{a.name}' has no normal balance",
                             "", [a.ref]))
        if a.parent and a.parent not in coa:
            out.append(issue("COA_BAD_PARENT", "ERROR", f"{a.code} parent {a.parent} does not exist", "", [a.ref]))
        default = DEFAULT_NORMAL.get(a.type)
        if default and a.normal_balance and a.normal_balance != default:
            out.append(issue("COA_CONTRA_ACCOUNT", "INFO",
                             f"{a.code} '{a.name}' is {a.type} with {a.normal_balance} normal balance (contra)",
                             "Sign logic must use normal_balance, not account type.", [a.ref]))
        if a.statement == "PL" and any(k in a.name.lower() for k in ("unrealized", "disposal")):
            out.append(issue("COA_NONCASH_CF_TAG", "INFO",
                             f"{a.code} '{a.name}' is non-cash but tagged cf_category '{a.cf_category}'",
                             "Indirect cash flow must add this back, not treat it as a cash movement.", [a.ref]))
    seen = set()
    for a in inp.coa_rows:
        if a.code in seen:
            out.append(issue("COA_DUPLICATE_CODE", "ERROR", f"COA code {a.code} defined twice", "", [a.ref]))
        seen.add(a.code)

    # 6. Retained earnings roll-forward and large unexplained movements
    def bal(rows, code):
        return sum((r.net for r in rows if r.account_code == code), Decimal("0"))

    re_codes = [a.code for a in inp.coa_rows if "retained earnings" in a.name.lower()]
    pl_open = any(r.account_code in coa and coa[r.account_code].statement == "PL" and r.net
                  for r in inp.tb)
    for code in re_codes:
        prior_re, cur_re = -bal(inp.prior_tb, code), -bal(inp.tb, code)
        if prior_re != cur_re and pl_open:
            out.append(issue("RE_UNEXPLAINED_MOVEMENT", "HOLD", "Retained earnings moved while P&L is still open",
                             f"Prior {fmt(prior_re)} -> current {fmt(cur_re)} (change {fmt(cur_re - prior_re)}). "
                             "In a pre-closing TB retained earnings should equal opening less dividends. "
                             "Possible restatement, dividend or partial close: asked the client.",
                             [r.ref for r in inp.tb + inp.prior_tb if r.account_code == code],
                             change=fmt(cur_re - prior_re)))
    prior_pl = [r for r in inp.prior_tb if r.account_code not in coa or coa[r.account_code].statement == "PL"]
    if inp.prior_tb and len(prior_pl) <= 1:
        out.append(issue("PRIOR_TB_INCOMPLETE", "WARN", "Prior TB has (almost) no P&L accounts",
                         "Looks like a post-closing TB, yet it does not balance; P&L comparatives unavailable.",
                         [r.ref for r in prior_pl]))
    for a in inp.coa_rows:
        if a.statement != "BS" or a.is_header or "retained" in a.name.lower():
            continue
        p, c = bal(inp.prior_tb, a.code), bal(inp.tb, a.code)
        if p and abs(c - p) > Decimal("1000000") and abs(c - p) / abs(p) > Decimal("0.25"):
            out.append(issue("BS_LARGE_MOVEMENT", "WARN", f"{a.code} '{a.name}' moved {fmt(c - p)} vs prior",
                             f"Prior {fmt(p)} -> current {fmt(c)}. No supporting entry in the adjustment batch.",
                             [r.ref for r in inp.tb + inp.prior_tb if r.account_code == a.code]))
    return out
