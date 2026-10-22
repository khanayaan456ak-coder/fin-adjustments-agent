# Manual Adjustments Agent (AI Agentic Engineer take-home)

Prototype slice: **"Manual adjustments agent that validates entries, detects balance violations, and explains rejections in plain English to a finance user."** It runs on the provided messy data **unmodified** (`data/inputs/`).

| Deliverable | Where |
|---|---|
| Architecture document (main) | [`docs/architecture.md`](docs/architecture.md) |
| One-page reflection | [`docs/reflection.md`](docs/reflection.md) |
| Defect inventory (10 seeded + 14 found) | [`docs/defects.md`](docs/defects.md) |
| Clarifying questions sent + assumptions | [`docs/questions_sent.md`](docs/questions_sent.md) |
| Generated outputs, traces, logs | [`output/`](output/) |

## Result on the provided batch

| Entry | Decision | Why |
|---|---|---|
| JE-001 Bonus accrual 850,000 | ✅ Accepted, flagged | Above materiality (340,325); needs approval evidence |
| JE-002 Marketing reclass | ❌ Rejected | Debits 28,500 ≠ credits 25,000 |
| JE-003 EUR FX reval 11,200 | ⚠️ Quarantined | Recomputes to 10,730.20 from the given rates; double-count risk |
| JE-004 / 006 / 007 / 009 / 010 | ✅ Accepted | All checks passed |
| JE-005 Conference travel | ⚠️ Quarantined | Account 6315 not in COA; best match 6310 would make it self-offsetting |
| JE-008 IC settlement | ❌ Rejected | Debits and credits 2170 for the same amount; no IC counterparty in COA |

The input diagnostics found 23 issues before any entry was reviewed (unbalanced TBs, duplicate 6310, orphan 9999, renamed 6905, missing GBP rate, retained earnings break, COA structure issues…).

## Setup and run

Requires Python 3.10+. There are no runtime dependencies (the LLM is optional).

```bash
git clone <repo> && cd fin-adjustments-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # add ,llm for the OpenAI client

adjagent run --no-llm              # deterministic run -> output/
adjagent trace 2120                # trace an account back to source rows / JE lines
adjagent run --no-llm --overrides examples/overrides.example.json --out output/hitl_demo
pytest -q                          # 25 tests
```

Without installing: `PYTHONPATH=src python -m adjagent run --no-llm` (PowerShell: `$env:PYTHONPATH="src"; python -m adjagent run --no-llm`). If editable install fails, upgrade pip first.

**With an LLM for explanations** (optional; the decisions are identical either way):
```bash
pip install -e ".[llm]"
export OPENAI_API_KEY=...                     # or LLM_API_KEY
export LLM_MODEL=gpt-4o-mini                  # default
# Gemini via its OpenAI-compatible endpoint:
# export LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/  LLM_MODEL=gemini-2.0-flash
adjagent run
```

## How it works

```
load (row refs, file hashes) -> preflight diagnostics -> per-entry rules -> decision
   -> human overrides (hash-pinned, re-validated) -> LLM explanation (validated, 1 retry, template fallback)
   -> post accepted entries with lineage -> verify invariants -> write outputs
```

- **Code decides, the LLM explains.** ERROR → rejected (cannot be overridden). HOLD → quarantined (a human can resolve it). WARN → accepted with a flag.
- **LLM guardrails:** the output must be valid JSON, may only contain numbers present in the facts, and must not contradict the decision. Otherwise it gets one retry with the errors fed back, and then falls back to a template. A provider outage never blocks posting.
- **Traceability:** every TB row has a ref (`trial_balance.csv:19`) and every JE line has one (`JE-001#L2`). `post_adjustment_tb.csv` lists the source refs for each balance.
- **Idempotent:** `run_id = hash(inputs + config + overrides + version)`; re-runs are byte-identical (tested). Money uses `Decimal`.

## Outputs (`output/`)

| File | Contents |
|---|---|
| `adjustment_report.md` | Human-readable review for the finance team |
| `adjustment_decisions.json` | Per entry: decision, findings, facts, explanation, override, content hash |
| `input_diagnostics.json` | Issues in TB / COA / FX / prior TB with evidence refs |
| `post_adjustment_tb.csv` | TB + accepted adjustments, with flags and source refs |
| `run_manifest.json`, `run_log.jsonl` | Run id, input hashes, event log |
| `trace_*.txt` | Example traces (2120, 6310, 1110) |
| `hitl_demo/` | Same run with example human overrides: JE-003 acknowledged → accepted; JE-005 mapped 6315→6310 → **re-check rejects it**; override on JE-002 refused |

`output/` was generated with OpenAI `gpt-4o-mini` explanations (see `explanation_sources` in `run_manifest.json`). Decisions and `run_id` are identical to a `--no-llm` run. `output/hitl_demo/` uses template explanations.

## Repo layout

```
src/adjagent/
  loaders.py    raw inputs -> typed rows with source refs (no cleaning)
  preflight.py  input diagnostics (TB, COA, FX, prior TB)
  checks.py     deterministic rules + decision
  mapper.py     candidate COA accounts for unknown codes (suggest only)
  explain.py    LLM explanation + validator + retry + template fallback
  posting.py    post accepted entries, invariants, trace
  pipeline.py   orchestration, overrides, outputs
tests/          one test per defect + guardrail/HITL/idempotency tests
```

## Assumptions (pending client answers, see `docs/questions_sent.md`)
Adjustments are in USD and TB foreign rows are in local currency; a missing FX rate blocks; materiality = 5% of pre-tax income; duplicate TB rows are kept and flagged; the retained earnings break is held, not explained away.
