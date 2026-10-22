"""CLI.

  python -m adjagent run   [--inputs data/inputs] [--out output] [--overrides FILE] [--no-llm]
  python -m adjagent trace ACCOUNT [--inputs data/inputs] [--overrides FILE]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import run, write_outputs
from .posting import PostingInvariantError, trace_lines


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="adjagent")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("run", "trace"):
        s = sub.add_parser(name)
        s.add_argument("--inputs", default="data/inputs", type=Path)
        s.add_argument("--overrides", type=Path)
        if name == "run":
            s.add_argument("--out", default="output", type=Path)
            s.add_argument("--no-llm", action="store_true", help="use deterministic templates only")
        else:
            s.add_argument("account")
    a = p.parse_args(argv)
    try:
        if a.cmd == "run":
            res = run(a.inputs, a.overrides, use_llm=not a.no_llm)
            write_outputs(res, a.out)
            for d in res.decisions:
                print(f"{d['entry_id']:<8} {d['decision']:<12} {d['explanation']['headline']}")
            print(f"\nrun_id={res.run_id}  outputs -> {a.out}/")
        else:
            res = run(a.inputs, a.overrides, use_llm=False)
            print("\n".join(trace_lines(res.inputs, res.ledger, a.account)))
    except PostingInvariantError as exc:
        print(f"ABORTED, no output written: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
