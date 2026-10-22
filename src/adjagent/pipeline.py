"""Orchestrator. Plain code, fixed order, no LLM in control flow.

load -> preflight -> validate each entry -> decide -> apply human overrides ->
explain (LLM, validated) -> post accepted -> verify -> write outputs.

Idempotent: run_id is a hash of input files + config + overrides + code version,
so the same inputs always produce the same decisions and the same run_id.
"""
from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from . import __version__
from .checks import (ACCEPTED, HOLD, QUARANTINED, REJECTED, WARN, Config, Context, Finding,
                     decide, validate_batch, validate_entry)
from .explain import explain, llm_from_env
from .loaders import Inputs, JournalEntry, fmt, load_inputs
from .posting import LedgerLine, post
from .preflight import run_preflight


@dataclasses.dataclass
class RunResult:
    run_id: str
    inputs: Inputs
    preflight: list[dict]
    decisions: list[dict]
    ledger: list[LedgerLine]
    log: list[dict]


def load_overrides(path: Path | None) -> list[dict]:
    if not path:
        return []
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data.get("overrides", data) if isinstance(data, dict) else data


def _remap(e: JournalEntry, mapping: dict[str, str]) -> JournalEntry:
    new = dataclasses.replace(e, lines=[dataclasses.replace(l) for l in e.lines])
    for l in new.lines:
        if l.account in mapping:
            l.memo = f"{l.memo} [mapped {l.account}->{mapping[l.account]}]"
            l.account = mapping[l.account]
    return new


def apply_override(e: JournalEntry, decision: str, findings: list[Finding], ov: dict, ctx: Context,
                   batch_extra: list[Finding]):
    """Human-in-the-loop. Returns (entry, decision, findings, override_record)."""
    rec = {"approver": ov.get("approver"), "reason": ov.get("reason"), "applied": False}
    if ov.get("content_hash") != e.content_hash:
        rec["note"] = "Ignored: entry changed since the override was approved (content hash mismatch)."
        return e, decision, findings, rec
    if decision == REJECTED:
        rec["note"] = "Ignored: rejected entries (hard errors) cannot be overridden; fix at source."
        return e, decision, findings, rec
    if decision != QUARANTINED:
        rec["note"] = "Ignored: entry was not quarantined."
        return e, decision, findings, rec
    if not ov.get("approver") or not ov.get("reason"):
        rec["note"] = "Ignored: override must name an approver and a reason."
        return e, decision, findings, rec
    mapping = ov.get("account_mapping") or {}
    entry = _remap(e, mapping) if mapping else e
    new_findings = validate_entry(entry, ctx) + batch_extra  # always re-check after a human change
    ack = set(ov.get("acknowledge_rules") or [])
    for f in new_findings:
        if f.severity == HOLD and f.rule in ack:
            f.severity = WARN
            f.message += f" [Acknowledged by {ov['approver']}: {ov['reason']}]"
    rec.update(applied=True, account_mapping=mapping, acknowledged_rules=sorted(ack))
    return entry, decide(new_findings), new_findings, rec


def run(inputs_dir: Path, overrides_path: Path | None = None, use_llm: bool = True,
        llm=None, config: Config | None = None) -> RunResult:
    log: list[dict] = []

    def emit(ev: dict):
        log.append({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **ev})

    inp = load_inputs(Path(inputs_dir))
    config = config or Config()
    overrides = load_overrides(overrides_path)
    run_id = hashlib.sha256(json.dumps({
        "files": inp.file_hashes, "config": {k: str(v) for k, v in dataclasses.asdict(config).items()},
        "overrides": overrides, "version": __version__}, sort_keys=True).encode()).hexdigest()[:12]
    emit({"event": "run_start", "run_id": run_id, "files": inp.file_hashes})

    preflight = run_preflight(inp)
    emit({"event": "preflight", "issues": len(preflight)})

    ctx = Context(inp, config)
    if llm is None and use_llm:
        llm = llm_from_env()
    emit({"event": "llm", "enabled": llm is not None})

    batch_extra = validate_batch(inp.entries)
    ov_by_id = {o["entry_id"]: o for o in overrides}
    decisions, accepted = [], []
    for e in inp.entries:
        extra = batch_extra.get(e.content_hash, [])
        findings = validate_entry(e, ctx) + extra
        decision = initial = decide(findings)
        override_rec = None
        posted_entry = e
        if e.id in ov_by_id:
            posted_entry, decision, findings, override_rec = apply_override(e, decision, findings,
                                                                            ov_by_id[e.id], ctx, extra)
            emit({"event": "override", "entry": e.id, **override_rec, "decision": decision})
        explanation, source = explain(posted_entry.raw if posted_entry is e else {
            **e.raw, "lines": [{"account": l.account, "debit": float(l.debit), "credit": float(l.credit),
                                "memo": l.memo} for l in posted_entry.lines]},
            decision, findings, llm, emit)
        if decision == ACCEPTED:
            accepted.append(posted_entry)
        decisions.append({
            "entry_id": e.id, "content_hash": e.content_hash, "description": e.description,
            "date": e.date, "source": e.source,
            "total_debits": fmt(sum((l.debit for l in e.lines), Decimal("0"))),
            "initial_decision": initial, "decision": decision,
            "findings": [f.to_dict() for f in findings],
            "override": override_rec,
            "explanation": explanation, "explanation_source": source,
        })
        emit({"event": "decision", "entry": e.id, "decision": decision, "rules": [f.rule for f in findings]})

    ledger = post(inp, accepted)  # raises before any output if invariants fail
    emit({"event": "posted", "accepted": [e.id for e in accepted]})
    return RunResult(run_id, inp, preflight, decisions, ledger, log)


# ---------------------------------------------------------------- outputs

def write_outputs(res: RunResult, out_dir: Path) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {d: sum(1 for x in res.decisions if x["decision"] == d) for d in (ACCEPTED, QUARANTINED, REJECTED)}
    (out_dir / "input_diagnostics.json").write_text(json.dumps(res.preflight, indent=2, default=str))
    (out_dir / "adjustment_decisions.json").write_text(json.dumps(
        {"run_id": res.run_id, "period": res.inputs.period, "summary": counts,
         "entries": res.decisions}, indent=2, default=str))
    with (out_dir / "post_adjustment_tb.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["account_code", "account_name", "currency", "pre_debit", "pre_credit", "adj_debit",
                    "adj_credit", "post_net_debit_positive", "flags", "source_refs"])
        for l in res.ledger:
            w.writerow([l.account_code, l.account_name, l.currency, l.pre_debit, l.pre_credit, l.adj_debit,
                        l.adj_credit, l.post_net, ";".join(l.flags), "; ".join(l.sources)])
    (out_dir / "run_manifest.json").write_text(json.dumps(
        {"run_id": res.run_id, "code_version": __version__, "input_file_sha256": res.inputs.file_hashes,
         "summary": counts, "accepted_entries": [d["entry_id"] for d in res.decisions if d["decision"] == ACCEPTED],
         "explanation_sources": sorted({d["explanation_source"] for d in res.decisions})}, indent=2))
    with (out_dir / "run_log.jsonl").open("w") as f:
        for ev in res.log:
            f.write(json.dumps(ev, default=str) + "\n")
    (out_dir / "adjustment_report.md").write_text(render_report(res, counts))


ICON = {ACCEPTED: "✅", QUARANTINED: "⚠️", REJECTED: "❌"}


def render_report(res: RunResult, counts: dict) -> str:
    L = [f"# Manual adjustments review: {res.inputs.period}", "",
         f"Run `{res.run_id}` · {len(res.decisions)} entries · "
         f"{counts[ACCEPTED]} accepted · {counts[QUARANTINED]} quarantined · {counts[REJECTED]} rejected", "",
         "| Entry | Description | Amount | Decision | Main reason |", "|---|---|---:|---|---|"]
    for d in res.decisions:
        main = next((f["rule"] for f in d["findings"] if f["severity"] in ("ERROR", "HOLD")), None) \
            or next((f["rule"] for f in d["findings"] if f["severity"] == "WARN"), "-")
        L.append(f"| {d['entry_id']} | {d['description']} | {d['total_debits']} | "
                 f"{ICON[d['decision']]} {d['decision']} | {main} |")
    L += ["", "## Notes for the finance team", ""]
    for d in res.decisions:
        ex = d["explanation"]
        L += [f"### {ICON[d['decision']]} {d['entry_id']}: {d['description']}", "",
              f"**{ex['headline']}**", "", ex["explanation"], "", f"*What to do:* {ex['suggested_fix']}", ""]
        if d["override"]:
            L += [f"*Human override:* {json.dumps(d['override'])}", ""]
        L += [f"<sub>hash {d['content_hash']} · explanation: {d['explanation_source']}</sub>", ""]
    L += ["## Input diagnostics (found before reviewing entries)", "",
          "| Severity | Issue | Evidence |", "|---|---|---|"]
    for i in res.preflight:
        ev = ", ".join(i["evidence"][:4]) + (" …" if len(i["evidence"]) > 4 else "")
        L.append(f"| {i['severity']} | {i['title']} | {ev} |")
    return "\n".join(L) + "\n"
