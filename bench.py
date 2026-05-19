"""
Benchmark runner.

Usage:
    python bench.py <tptp_file> <output_csv>
"""

from __future__ import annotations
import csv
import sys
from typing import List

from loader import load_problems
from engine import run_tableau, select_S, select_alphabeta, Metrics


COLUMNS = [
    "problem",
    # alpha/beta metrics
    "ab_closed", "ab_nodes", "ab_expansions", "ab_betas",
    "ab_depth_max", "ab_branches_closed", "ab_branches_open", "ab_time_ms",
    # S metrics
    "s_closed",  "s_nodes",  "s_expansions",  "s_betas",
    "s_depth_max",  "s_branches_closed",  "s_branches_open",  "s_time_ms",
    # ratios (S vs alpha/beta) -- only meaningful when both closed
    "node_ratio_ab_over_s",
    "exp_ratio_ab_over_s",
]


def row_for(name, m_ab: Metrics, m_s: Metrics):
    def ratio(a, b):
        if b == 0:
            return ""
        return f"{a / b:.3f}"
    return {
        "problem": name,
        "ab_closed":          int(m_ab.closed),
        "ab_nodes":           m_ab.nodes,
        "ab_expansions":      m_ab.expansions,
        "ab_betas":           m_ab.betas,
        "ab_depth_max":       m_ab.depth_max,
        "ab_branches_closed": m_ab.branches_closed,
        "ab_branches_open":   m_ab.branches_open,
        "ab_time_ms":         f"{m_ab.time_ms:.3f}",
        "s_closed":           int(m_s.closed),
        "s_nodes":            m_s.nodes,
        "s_expansions":       m_s.expansions,
        "s_betas":            m_s.betas,
        "s_depth_max":        m_s.depth_max,
        "s_branches_closed":  m_s.branches_closed,
        "s_branches_open":    m_s.branches_open,
        "s_time_ms":          f"{m_s.time_ms:.3f}",
        "node_ratio_ab_over_s": ratio(m_ab.nodes, m_s.nodes) if (m_ab.closed and m_s.closed) else "",
        "exp_ratio_ab_over_s":  ratio(m_ab.expansions, m_s.expansions) if (m_ab.closed and m_s.closed) else "",
    }


def _sort_key(name: str):
    """Sort problems so the CSV reads naturally: pel01, pel02, ..., pel17, pel01_b1, ..."""
    import re
    m = re.match(r"pel(\d+)(?:_b(\d+))?$", name)
    if not m:
        return (999, 999, name)
    batch = int(m.group(2)) if m.group(2) else 0
    num = int(m.group(1))
    return (batch, num, name)


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        print("usage: python bench.py <tptp_file> <output_csv>", file=sys.stderr)
        return 2

    tptp_path = argv[1]
    out_path = argv[2]

    problems = load_problems(tptp_path)
    print(f"loaded {len(problems)} problems from {tptp_path}", file=sys.stderr)

    names = sorted(problems.keys(), key=_sort_key)

    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()

        for name in names:
            prob = problems[name]
            m_ab = run_tableau(prob.signed_inputs, select_alphabeta)
            m_s  = run_tableau(prob.signed_inputs, select_S)
            writer.writerow(row_for(name, m_ab, m_s))
            status_ab = "OK" if m_ab.closed else "FAIL"
            status_s  = "OK" if m_s.closed  else "FAIL"
            print(
                f"  {name:14s}  "
                f"ab[{status_ab}] nodes={m_ab.nodes:5d} exp={m_ab.expansions:4d} "
                f"t={m_ab.time_ms:7.2f}ms  |  "
                f"S[{status_s}]  nodes={m_s.nodes:5d} exp={m_s.expansions:4d} "
                f"t={m_s.time_ms:7.2f}ms",
                file=sys.stderr,
            )

    print(f"wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
