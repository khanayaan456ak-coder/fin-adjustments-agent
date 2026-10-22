"""Turn deterministic findings into a plain-English note for a finance user.

The LLM's ONLY job is wording. It receives the decision and the findings, and
must not change the decision or introduce numbers. Its output is validated:
  1. valid JSON with the required keys
  2. every number it mentions must already exist in the facts (no hallucinated amounts)
  3. it must not contradict the decision
If validation fails, it gets ONE retry with the errors fed back; if that fails
too, a deterministic template is used. The source is recorded for audit.
"""
from __future__ import annotations

import json
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Callable

from .checks import ACCEPTED, QUARANTINED, REJECTED, Finding

LLMCall = Callable[[list[dict]], str]

SYSTEM_PROMPT = """You write short notes to finance users explaining why a journal entry was
accepted, rejected or quarantined by an automated control.
Rules:
- Use ONLY the facts given. Do not calculate anything new and do not invent amounts, accounts or dates.
- Never change or soften the decision.
- Plain English, no jargon beyond normal accounting terms, max 110 words for "explanation".
Return JSON only: {"headline": str, "explanation": str, "suggested_fix": str}"""

NUM_RE = re.compile(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?")
CONTRADICTIONS = {
    REJECTED: ["has been posted", "was posted", "was accepted", "has been accepted", "approved for posting"],
    QUARANTINED: ["has been posted", "was posted", "was rejected", "has been rejected"],
    ACCEPTED: ["was rejected", "has been rejected", "cannot be posted"],
}


def _norm(n: str) -> Decimal | None:
    try:
        return Decimal(n.replace(",", "").rstrip(".")).normalize()
    except InvalidOperation:
        return None


def allowed_numbers(*payloads) -> set[Decimal]:
    allowed = {Decimal(i) for i in range(0, 11)}
    for p in payloads:
        for n in NUM_RE.findall(json.dumps(p, default=str)):
            v = _norm(n)
            if v is not None:
                allowed.add(v)
    return allowed


def validate_explanation(text: str, decision: str, allowed: set[Decimal]) -> tuple[dict | None, list[str]]:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None, ["Output is not valid JSON."]
    errors = []
    for key in ("headline", "explanation", "suggested_fix"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            errors.append(f"Missing or empty key '{key}'.")
    if errors:
        return None, errors
    blob = " ".join(data[k] for k in ("headline", "explanation", "suggested_fix"))
    bad = sorted({n for n in NUM_RE.findall(blob) if _norm(n) not in allowed})
    if bad:
        errors.append(f"Mentions numbers not present in the facts: {bad}. Use only the given numbers.")
    for phrase in CONTRADICTIONS.get(decision, []):
        if phrase in blob.lower():
            errors.append(f"Contradicts the decision {decision} (phrase '{phrase}').")
    return (data if not errors else None), errors


def template_explanation(entry_id: str, decision: str, findings: list[Finding]) -> dict:
    head = {REJECTED: f"{entry_id} was rejected and not posted.",
            QUARANTINED: f"{entry_id} is on hold until someone reviews it.",
            ACCEPTED: f"{entry_id} passed all blocking checks and was posted."}[decision]
    order = {"ERROR": 0, "HOLD": 1, "WARN": 2, "INFO": 3}
    fs = sorted((f for f in findings if f.severity != "INFO"), key=lambda f: order[f.severity])
    expl = " ".join(f.message for f in fs) or "No issues were found."
    fixes = [f.fix for f in fs if f.fix and f.severity in ("ERROR", "HOLD")] or \
            [f.fix for f in fs if f.fix] or ["No action needed."]
    return {"headline": head, "explanation": expl, "suggested_fix": " ".join(dict.fromkeys(fixes))}


def llm_from_env() -> LLMCall | None:
    """OpenAI-compatible client. Works with OpenAI, or Gemini via LLM_BASE_URL."""
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    client = OpenAI(api_key=key, base_url=os.getenv("LLM_BASE_URL") or None)
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    def call(messages: list[dict]) -> str:
        resp = client.chat.completions.create(model=model, messages=messages, temperature=0,
                                              response_format={"type": "json_object"})
        return resp.choices[0].message.content or ""

    call.model_name = model  # type: ignore[attr-defined]
    return call


def explain(entry_raw: dict, decision: str, findings: list[Finding], llm: LLMCall | None,
            log: Callable[[dict], None] = lambda e: None) -> tuple[dict, str]:
    entry_id = entry_raw.get("id", "?")
    if llm is None:
        return template_explanation(entry_id, decision, findings), "template"
    facts = {"entry": entry_raw, "decision": decision, "findings": [f.to_dict() for f in findings]}
    allowed = allowed_numbers(facts)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(facts, default=str, indent=1)}]
    for attempt in (1, 2):
        try:
            text = llm(messages)
        except Exception as exc:  # network/provider failure must never block the control
            log({"event": "llm_error", "entry": entry_id, "attempt": attempt, "error": str(exc)})
            break
        data, errors = validate_explanation(text, decision, allowed)
        log({"event": "llm_attempt", "entry": entry_id, "attempt": attempt, "valid": not errors,
             "errors": errors})
        if data:
            return data, f"llm:{getattr(llm, 'model_name', 'custom')}"
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "Your answer failed validation: " + " ".join(errors)
                      + " Rewrite it following the rules."}]
    return template_explanation(entry_id, decision, findings), "template_fallback"
