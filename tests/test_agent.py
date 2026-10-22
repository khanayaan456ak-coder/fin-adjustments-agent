"""One test per seeded / discovered defect, plus the control properties
(LLM guardrails, human overrides, idempotency, traceability)."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from adjagent.checks import ACCEPTED, QUARANTINED, REJECTED
from adjagent.explain import allowed_numbers, validate_explanation
from adjagent.pipeline import run, write_outputs
from adjagent.posting import trace_lines

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "data" / "inputs"
OVERRIDES = ROOT / "examples" / "overrides.example.json"


@pytest.fixture(scope="module")
def res():
    return run(INPUTS, use_llm=False)


def by_id(res, id_):
    return next(d for d in res.decisions if d["entry_id"] == id_)


def rules(d):
    return {f["rule"] for f in d["findings"]}


def issue_ids(res):
    return [i["id"] for i in res.preflight]


# ---------------- adjustment decisions

def test_je002_rejected_debits_not_equal_credits(res):
    d = by_id(res, "JE-002")
    assert d["decision"] == REJECTED
    f = next(f for f in d["findings"] if f["rule"] == "DEBITS_NOT_EQUAL_CREDITS")
    assert f["facts"]["difference"] == "3,500.00"


def test_je003_quarantined_fx_recalc_mismatch(res):
    d = by_id(res, "JE-003")
    assert d["decision"] == QUARANTINED
    f = next(f for f in d["findings"] if f["rule"] == "FX_REVAL_MISMATCH")
    assert f["facts"]["expected"]["period_average"] == "10,730.20"
    assert f["facts"]["booked"] == "11,200.00"


def test_je005_quarantined_unknown_account_with_candidates(res):
    d = by_id(res, "JE-005")
    assert d["decision"] == QUARANTINED
    f = next(f for f in d["findings"] if f["rule"] == "ACCOUNT_NOT_IN_COA")
    assert f["facts"]["candidates"][0]["code"] == "6310"
    assert f["facts"]["candidate_clashes"] == ["6310"]  # mapping would self-offset


def test_je008_rejected_circular(res):
    d = by_id(res, "JE-008")
    assert d["decision"] == REJECTED
    assert {"CIRCULAR_NO_EFFECT", "IC_NO_COUNTERPARTY"} <= rules(d)


def test_je001_material_but_accepted(res):
    d = by_id(res, "JE-001")
    assert d["decision"] == ACCEPTED
    assert "MATERIAL_ENTRY" in rules(d)


@pytest.mark.parametrize("id_", ["JE-004", "JE-006", "JE-007", "JE-009", "JE-010"])
def test_clean_entries_accepted_without_flags(res, id_):
    d = by_id(res, id_)
    assert d["decision"] == ACCEPTED and d["findings"] == []


# ---------------- input diagnostics

def test_preflight_finds_seeded_and_hidden_defects(res):
    ids = issue_ids(res)
    titles = " | ".join(i["title"] for i in res.preflight)
    assert "TB_UNBALANCED_CURRENT" in ids and "TB_UNBALANCED_PRIOR" in ids
    assert "Account 6310 (USD) appears 2 times" in titles
    assert "9999" in titles and "6905" in titles
    assert "No period_end rate for GBP" in titles
    assert "Header 1290" in titles
    assert sum(1 for i in res.preflight if i["id"] == "COA_AMBIGUOUS_CF") == 2  # 1150, 2170
    assert "RE_UNEXPLAINED_MOVEMENT" in ids
    assert "1210" in titles  # unexplained PPE jump


def test_renamed_prior_account_suggested_not_applied(res):
    i = next(i for i in res.preflight if i["id"] == "TB_ACCOUNT_NOT_IN_COA" and i["facts"]["account"] == "6905")
    assert i["facts"]["candidates"][0]["code"] == "6900"
    assert i["severity"] == "HOLD"


def test_suspense_has_no_credible_mapping(res):
    i = next(i for i in res.preflight if i["id"] == "TB_ACCOUNT_NOT_IN_COA" and i["facts"]["account"] == "9999")
    assert i["facts"]["candidates"] == []


# ---------------- posting, verification, traceability

def test_only_accepted_entries_posted_and_balanced(res):
    adj_dr = sum(l.adj_debit for l in res.ledger)
    adj_cr = sum(l.adj_credit for l in res.ledger)
    assert adj_dr == adj_cr == Decimal("1423000.00")  # 850k+45k+215k+38k+75k+200k


def test_trace_accrued_expenses_back_to_source(res):
    out = "\n".join(trace_lines(res.inputs, res.ledger, "2120"))
    assert "-2,075,000.00" in out
    assert "trial_balance.csv:19" in out and "JE-001#L2" in out and "JE-009#L2" in out


def test_duplicate_rows_kept_and_flagged_not_deduped(res):
    line = next(l for l in res.ledger if l.account_code == "6310")
    assert "DUPLICATE_SOURCE_ROWS" in line.flags and len(line.sources) == 2


# ---------------- human in the loop

@pytest.fixture(scope="module")
def res_ov():
    return run(INPUTS, OVERRIDES, use_llm=False)


def test_override_acknowledges_fx_hold(res_ov):
    d = by_id(res_ov, "JE-003")
    assert d["initial_decision"] == QUARANTINED and d["decision"] == ACCEPTED
    assert d["override"]["applied"]


def test_override_mapping_is_rechecked_and_caught(res_ov):
    d = by_id(res_ov, "JE-005")  # 6315 -> 6310 makes the entry circular
    assert d["decision"] == REJECTED and "CIRCULAR_NO_EFFECT" in rules(d)


def test_override_cannot_unreject(res_ov):
    d = by_id(res_ov, "JE-002")
    assert d["decision"] == REJECTED and not d["override"]["applied"]


def test_stale_override_ignored(tmp_path):
    ov = json.loads(OVERRIDES.read_text())
    ov["overrides"][0]["content_hash"] = "deadbeefdeadbeef"
    p = tmp_path / "ov.json"
    p.write_text(json.dumps(ov))
    d = by_id(run(INPUTS, p, use_llm=False), "JE-003")
    assert d["decision"] == QUARANTINED and "hash mismatch" in d["override"]["note"]


# ---------------- LLM guardrails (no network: fake LLMs)

def test_llm_hallucinated_number_falls_back_to_template():
    calls = []

    def bad_llm(messages):
        calls.append(messages)
        return json.dumps({"headline": "JE-002 rejected", "explanation": "Off by 4,100.00.",
                           "suggested_fix": "Fix it."})

    r = run(INPUTS, use_llm=True, llm=bad_llm)
    d = by_id(r, "JE-002")
    assert d["explanation_source"] == "template_fallback"
    assert len(calls) == 2 * len(r.decisions)  # one retry per entry, then fallback


def test_llm_valid_output_is_used():
    def good_llm(messages):
        return json.dumps({"headline": "Entry not posted", "explanation": "Debits 28,500.00 vs credits 25,000.00.",
                           "suggested_fix": "Confirm the amount."})

    d = by_id(run(INPUTS, use_llm=True, llm=good_llm), "JE-002")
    assert d["explanation_source"].startswith("llm")
    assert d["decision"] == REJECTED  # LLM never changes the decision


def test_llm_contradicting_decision_is_rejected():
    allowed = allowed_numbers({"x": 1})
    data, errors = validate_explanation(json.dumps({"headline": "h", "explanation": "It was posted.",
                                                    "suggested_fix": "none"}), REJECTED, allowed)
    assert data is None and errors


def test_llm_exception_does_not_block():
    def broken(messages):
        raise TimeoutError("provider down")

    d = by_id(run(INPUTS, use_llm=True, llm=broken), "JE-001")
    assert d["decision"] == ACCEPTED and d["explanation_source"] == "template_fallback"


# ---------------- idempotency

def test_rerun_is_identical(tmp_path):
    a, b = run(INPUTS, use_llm=False), run(INPUTS, use_llm=False)
    write_outputs(a, tmp_path / "a")
    write_outputs(b, tmp_path / "b")
    assert a.run_id == b.run_id
    for f in ("adjustment_decisions.json", "post_adjustment_tb.csv", "input_diagnostics.json"):
        assert (tmp_path / "a" / f).read_text() == (tmp_path / "b" / f).read_text()
