"""Explicit tableau tracer that records every step so we can verify by hand.

For each input formula we produce a structured trace:
  - the initial signed inputs
  - for each step: which formula was selected, by what rule, and what was added
  - the final tree shape with closure markers

This is independent of the bench.py harness so we can spot bugs in either.
"""

from __future__ import annotations
import sys, copy
sys.path.insert(0, "/home/claude/tableau")

from core import (
    Signed, parse_formula, Formula, Atom, Not, And, Or, Imp, Iff,
    classify, expand, subformulas, is_atomic,
    ALPHA, BETA, ATOM,
)
from engine import Branch, BranchItem, select_S, select_alphabeta


def explicit_run(initial_signed, selector, name="?", max_steps=200):
    """Run a tableau with a fully-explicit trace. Returns a dict.

    Each branch is processed depth-first. We record selection + expansion + closure.
    """
    age = [0]
    def na():
        a = age[0]; age[0] += 1; return a

    log = []          # list of trace entries
    root = Branch()
    for sf in initial_signed:
        root.add(sf, na())
    log.append(("init", [str(s) for s in initial_signed], root.closed))

    nodes = len(initial_signed)
    expansions = 0
    betas = 0
    branches_closed = 0
    branches_open = 0
    max_depth = len(root.items)

    # DFS with explicit branch path tracking
    # Each stack entry: (branch, path_id) where path_id is a string like "L.R.L"
    stack = [(root, "root")]

    while stack:
        if len(log) > max_steps:
            log.append(("ABORT", "too many steps", None))
            break

        br, path = stack.pop()
        if br.closed:
            branches_closed += 1
            max_depth = max(max_depth, len(br.items))
            log.append(("branch_closed", path, len(br.items)))
            continue

        sel = selector(br)
        if sel is None:
            branches_open += 1
            max_depth = max(max_depth, len(br.items))
            log.append(("branch_open", path, [str(it.sf) for it in br.items]))
            continue

        sel.expanded = True
        expansions += 1
        kind = classify(sel.sf)
        children = expand(sel.sf)

        log.append(("expand", path, str(sel.sf), kind, sel.age,
                    [[str(c) for c in branch] for branch in children]))

        if len(children) == 1:
            for comp in children[0]:
                if br.add(comp, na()):
                    nodes += 1
            stack.append((br, path))
        else:
            betas += 1
            for i, comps in enumerate(children):
                child = br.clone()
                for comp in comps:
                    if child.add(comp, na()):
                        nodes += 1
                child_path = f"{path}.{'L' if i==0 else 'R'}"
                stack.append((child, child_path))

    return {
        "name": name,
        "log": log,
        "nodes": nodes,
        "expansions": expansions,
        "betas": betas,
        "branches_closed": branches_closed,
        "branches_open": branches_open,
        "max_depth": max_depth,
        "closed": branches_open == 0,
    }


def render(trace, max_lines=80):
    """Pretty-print a trace, truncating if huge."""
    lines = []
    for i, entry in enumerate(trace["log"]):
        kind = entry[0]
        if kind == "init":
            lines.append(f"INIT: {len(entry[1])} signed formulas")
            for s in entry[1]:
                lines.append(f"      {s}")
        elif kind == "expand":
            _, path, sf, k, age, children = entry
            arrow = " ".join("|".join(branch) for branch in children)
            lines.append(f"[{path}] expand [{k}] age={age}  {sf}")
            for j, branch in enumerate(children):
                marker = "  add:" if len(children)==1 else f"  branch {j+1}:"
                lines.append(f"   {marker} {', '.join(branch)}")
        elif kind == "branch_closed":
            lines.append(f"[{entry[1]}]  *** branch closed (depth {entry[2]}) ***")
        elif kind == "branch_open":
            lines.append(f"[{entry[1]}]  --- branch OPEN (countermodel found) ---")
            for sf in entry[2]:
                lines.append(f"      {sf}")
        if len(lines) > max_lines:
            lines.append(f"... (truncated; trace has {len(trace['log'])} entries)")
            break
    return "\n".join(lines)


def run_both(formula_str, name, expect_closed=True, premises=None,
             show_trace=("S_ab", "S")):
    """Run both heuristics on a formula and verify."""
    print("=" * 78)
    print(f"  {name}")
    print(f"  formula: {formula_str}")
    if premises:
        print(f"  premises (T-signed): {premises}")
    print(f"  expected: {'CLOSED (valid)' if expect_closed else 'OPEN (countermodel)'}")
    print("=" * 78)

    signed = []
    if premises:
        for p in premises:
            signed.append(Signed(True, parse_formula(p)))
    signed.append(Signed(False, parse_formula(formula_str)))

    results = {}
    for label, sel in [("S_ab", select_alphabeta), ("S", select_S)]:
        trace = explicit_run(signed, sel, name=f"{name}/{label}")
        results[label] = trace
        ok = trace["closed"] == expect_closed
        verdict = "OK" if ok else "**FAIL**"
        print(f"\n[{label}] {verdict}: closed={trace['closed']} expected={expect_closed}")
        print(f"  nodes={trace['nodes']} exp={trace['expansions']} "
              f"betas={trace['betas']} br_closed={trace['branches_closed']} "
              f"br_open={trace['branches_open']} depth_max={trace['max_depth']}")

    for label in show_trace:
        print(f"\n--- {label} trace ---")
        print(render(results[label]))
    print()
    return results


if __name__ == "__main__":
    # We'll be called with a single test name
    pass
