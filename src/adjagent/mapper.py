"""Suggest COA accounts for an unknown account code.

Deterministic scoring (name overlap + code proximity). Suggestions are ONLY
suggestions: the system never auto-posts to a suggested account. A human must
approve a mapping via overrides.json, and the entry is then re-validated.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

STOP = {"and", "of", "the", "to", "from", "out", "in", "into", "a", "for", "old", "new", "code"}
SYNONYMS = {"conf": "conference", "dep": "depreciation", "accum": "accumulated", "ic": "intercompany",
            "sundry": "other", "misc": "other", "miscellaneous": "other", "t&e": "travel"}


def tokens(text: str) -> set[str]:
    out = set()
    for t in re.findall(r"[a-z&]+", text.lower()):
        t = SYNONYMS.get(t, t)
        if t in STOP or len(t) < 3:
            continue
        out.add(t[:-1] if t.endswith("s") and len(t) > 4 else t)
    return out


def _code_similarity(a: str, b: str) -> float:
    if not (a.isdigit() and b.isdigit()) or a[:2] != b[:2]:
        return 0.0
    return max(0.0, 1 - abs(int(a) - int(b)) / 100)


def suggest_accounts(code: str, text: str, coa: dict, top_n: int = 3) -> list[dict]:
    q = tokens(text)
    scored = []
    for acc in coa.values():
        if acc.is_header:
            continue
        name_t = tokens(acc.name)
        overlap = len(q & name_t) / len(name_t) if name_t else 0.0
        fuzzy = SequenceMatcher(None, text.lower(), acc.name.lower()).ratio()
        name_score = max(overlap, fuzzy * 0.6)
        code_score = _code_similarity(code, acc.code)
        score = round(0.6 * name_score + 0.4 * code_score, 2)
        if score < 0.35:
            continue
        reasons = []
        if q & name_t:
            reasons.append(f"shares words {sorted(q & name_t)}")
        if code_score:
            reasons.append(f"code {acc.code} is near {code}")
        scored.append({"code": acc.code, "name": acc.name, "score": score,
                       "confidence": "high" if score >= 0.75 else "medium" if score >= 0.5 else "low",
                       "reason": "; ".join(reasons) or "weak fuzzy match"})
    scored.sort(key=lambda c: (-c["score"], c["code"]))
    return scored[:top_n]
