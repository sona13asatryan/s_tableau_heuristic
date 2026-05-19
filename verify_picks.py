"""Pick 10 problems from the actual benchmark file and verify each one.

For each problem:
  1. Show its identity and the signed inputs.
  2. Run both heuristics, recording the full tableau trace.
  3. Semantically cross-check: brute-force every truth assignment to confirm
     the problem is actually valid (no assignment makes premises T and
     conjecture F). The tableau must close iff brute-force says valid.
  4. Display traces and conclusions.

Picks span: trivial originals, harder originals, problems where S wins,
problems where S_ab wins, an entailment, and edge cases.
"""

import sys, itertools
sys.path.insert(0, "/home/claude/tableau")

from core import (
    parse_formula, Formula, Atom, Not, And, Or, Imp, Iff, Signed,
)
from loader import load_problems
from verify import explicit_run, render
from engine import select_S, select_alphabeta


# -----------------------------------------------------------------------------
# Semantic evaluator (brute-force truth-table check)
# -----------------------------------------------------------------------------

def collect_atoms(f: Formula, acc: set) -> None:
    if isinstance(f, Atom):
        acc.add(f.name)
    elif isinstance(f, Not):
        collect_atoms(f.sub, acc)
    else:
        collect_atoms(f.left, acc)
        collect_atoms(f.right, acc)


def evaluate(f: Formula, env: dict) -> bool:
    if isinstance(f, Atom): return env[f.name]
    if isinstance(f, Not):  return not evaluate(f.sub, env)
    if isinstance(f, And):  return evaluate(f.left, env) and evaluate(f.right, env)
    if isinstance(f, Or):   return evaluate(f.left, env) or  evaluate(f.right, env)
    if isinstance(f, Imp):  return (not evaluate(f.left, env)) or evaluate(f.right, env)
    if isinstance(f, Iff):  return evaluate(f.left, env) == evaluate(f.right, env)
    raise TypeError(f)


def is_valid_entailment(premises, conjecture):
    """Brute-force: for all assignments, premises -> conjecture must hold.
    Returns (valid: bool, countermodel: dict or None).
    """
    atoms = set()
    for p in premises:
        collect_atoms(p, atoms)
    collect_atoms(conjecture, atoms)
    atoms = sorted(atoms)
    for values in itertools.product([False, True], repeat=len(atoms)):
        env = dict(zip(atoms, values))
        if all(evaluate(p, env) for p in premises) and not evaluate(conjecture, env):
            return False, env
    return True, None


# -----------------------------------------------------------------------------
# Pick 10 problems and verify each
# -----------------------------------------------------------------------------

PICKS = [
    # (problem_name, why)
    ("pel01",     "trivial original: contraposition"),
    ("pel09",     "original with 3-way conjunction structure"),
    ("pel10",     "original entailment problem (axioms + conjecture)"),
    ("pel12",     "original where S beats S_ab (associativity of iff)"),
    ("pel17",     "the heaviest original (Pelletier 17)"),
    ("pel10_b1",  "B1 entailment (asymmetric-depth substitution)"),
    ("pel17_b2",  "B2 (mixed asymmetric, supposedly S-friendly)"),
    ("pel08_b3",  "B3 strict-chain Peirce variant"),
    ("pel17_b4",  "B4 huge-P variant of #17 (where S underperforms)"),
    ("pel09_b5",  "B5 recursive containment, multi-conjunct"),
]


def run_pick(name, why, problems):
    p = problems[name]
    print("\n" + "=" * 80)
    print(f"  {name}    -- {why}")
    print("=" * 80)
    print(f"  Conjecture: {p.conjecture}")
    if p.axioms:
        print(f"  Axioms ({len(p.axioms)}):")
        for axn, axf in p.axioms:
            print(f"    {axn}: {axf}")

    # Brute force semantic check
    premise_formulas = [ax for (_, ax) in p.axioms]
    valid, countermodel = is_valid_entailment(premise_formulas, p.conjecture)
    print(f"\n  Brute-force semantic check: "
          f"{'VALID (no countermodel)' if valid else 'INVALID -- counter-ex ' + str(countermodel)}")

    # Run both heuristics with full trace
    results = {}
    for label, sel in [("S_ab", select_alphabeta), ("S", select_S)]:
        # node_limit high enough for big traces but not infinite
        trace = explicit_run(p.signed_inputs, sel, name=f"{name}/{label}",
                              max_steps=10_000)
        closed = trace["closed"]
        results[label] = trace
        agreement = (closed == valid)
        print(f"\n  [{label}] closed={closed}  valid={valid}  "
              f"{'AGREES with semantics' if agreement else '*** DISAGREES! ***'}")
        print(f"        nodes={trace['nodes']:>5d}  exp={trace['expansions']:>4d}  "
              f"betas={trace['betas']:>4d}  br_closed={trace['branches_closed']}  "
              f"br_open={trace['branches_open']}  depth={trace['max_depth']}")

    # Show trace for the smaller proof (compactness)
    smaller = min(results, key=lambda k: results[k]["nodes"])
    print(f"\n  -- Trace ({smaller}; smaller of the two) --")
    print(render(results[smaller], max_lines=40))

    return name, valid, results


if __name__ == "__main__":
    problems = load_problems("/home/claude/tableau/pelletier_extended.p")
    print(f"Loaded {len(problems)} problems from benchmark.")

    summary = []
    for (name, why) in PICKS:
        n, valid, results = run_pick(name, why, problems)
        ab_closed = results["S_ab"]["closed"]
        s_closed  = results["S"]["closed"]
        ab_n = results["S_ab"]["nodes"]
        s_n  = results["S"]["nodes"]
        agrees = (ab_closed == valid) and (s_closed == valid)
        summary.append((n, valid, ab_closed, s_closed, ab_n, s_n, agrees))

    print("\n" + "=" * 80)
    print(" FINAL SUMMARY ")
    print("=" * 80)
    print(f"{'Problem':<14s}  {'valid':>6s}  {'S_ab':>6s}  {'S':>6s}  "
          f"{'ab_n':>6s}  {'s_n':>6s}  {'verdict':>10s}")
    for (n, valid, ab, s, abn, sn, ok) in summary:
        print(f"{n:<14s}  {str(valid):>6s}  {str(ab):>6s}  {str(s):>6s}  "
              f"{abn:>6d}  {sn:>6d}  {'OK' if ok else 'FAIL':>10s}")
    all_ok = all(row[6] for row in summary)
    print(f"\nAll picks consistent with brute-force semantics: {all_ok}")
