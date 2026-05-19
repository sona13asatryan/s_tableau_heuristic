"""Hand-crafted unit tests for the S heuristic rules.

Each test sets up a branch with specific signed formulas, predicts which
formula the heuristic should pick, and verifies the prediction.
"""
import sys
sys.path.insert(0, "/home/claude/tableau")

from core import parse_formula, Signed, classify, subformulas, ATOM
from engine import Branch, BranchItem, select_S


def make_branch(*signed_strs):
    """Build a branch from a list of 'T expr' or 'F expr' strings."""
    br = Branch()
    age = [0]
    for s in signed_strs:
        kind, _, expr = s.partition(" ")
        sign = (kind == "T")
        sf = Signed(sign, parse_formula(expr))
        br.add(sf, age[0]); age[0] += 1
    return br


def expect(test_name, br, expected_str):
    """Run S and assert it returns the formula matching expected_str."""
    sel = select_S(br)
    if sel is None:
        actual = "None"
    else:
        actual = str(sel.sf)
    ok = (actual == expected_str)
    status = "OK  " if ok else "FAIL"
    print(f"{status}  {test_name}")
    print(f"      expected: {expected_str}")
    print(f"      got:      {actual}")
    return ok


# -----------------------------------------------------------------------------
# Test 1: Rule (1) - sub(T) <= sub(F), expand F.
# T(p & q): sub = {p, q, p&q}
# F((p & q) | r): sub = {p, q, p&q, r, (p&q)|r}
# So sub(T) <= sub(F).
# -----------------------------------------------------------------------------
br = make_branch("T p & q", "F (p & q) | r")
expect("Rule 1: simple containment", br, "F ((p & q) | r)")


# -----------------------------------------------------------------------------
# Test 2: Rule (2) - sub(F) <= sub(T), expand T.
# -----------------------------------------------------------------------------
br = make_branch("F p & q", "T (p & q) | r")
expect("Rule 2: simple containment", br, "T ((p & q) | r)")


# -----------------------------------------------------------------------------
# Test 3: Rule (1) but where F-target candidate is atomic.
# T(p): sub = {p}
# F(p): sub = {p}    <- atomic, must NOT be selected!
# Both atoms, no other expandable. Should fall back to alphabeta -> None.
# But this case shouldn't normally happen because T(p) and F(p) would close
# the branch. Let me use:
# T(p): sub = {p}
# F(p|q): sub = {p, q, p|q}    <- {p} <= {p,q,p|q}, expand F(p|q).
# -----------------------------------------------------------------------------
br = make_branch("T p", "F p | q")
expect("Rule 1: T atom, F is non-atomic with containment", br, "F (p | q)")


# -----------------------------------------------------------------------------
# Test 4: Rule (2) with T being non-atomic and F atomic.
# F(q): sub = {q}
# T(p|q): sub = {p, q, p|q}    <- {q} <= {p,q,p|q}, expand T(p|q).
# This is the Phi^j_n pattern!
# -----------------------------------------------------------------------------
br = make_branch("F q", "T p | q")
expect("Rule 2: F atom, T non-atomic (Phi-pattern)", br, "T (p | q)")


# -----------------------------------------------------------------------------
# Test 5: Phi_5^5 from thesis.
# T(p1=>q1), ..., T(p5=>q5), T(p5), F(q5)
# Rule (2): sub(F q5) = {q5}; only T(p5=>q5) contains q5.
# So S should pick T(p5=>q5).
# -----------------------------------------------------------------------------
br = make_branch(
    "T p1 => q1", "T p2 => q2", "T p3 => q3", "T p4 => q4", "T p5 => q5",
    "T p5", "F q5"
)
expect("Rule 2: Phi_5^5 picks T(p5=>q5)", br, "T (p5 => q5)")


# -----------------------------------------------------------------------------
# Test 6: Rule (1) when multiple F candidates qualify - oldest should win.
# T p: sub = {p}
# F (p | q): age=1 - eligible by rule 1
# F (p | r): age=2 - also eligible by rule 1
# Should pick the older, F(p|q).
# -----------------------------------------------------------------------------
br = make_branch("T p", "F p | q", "F p | r")
expect("Rule 1: tie-break by age (older)", br, "F (p | q)")


# -----------------------------------------------------------------------------
# Test 7: Rule (3) when no containment, max intersection wins.
# T (p & q): sub = {p, q, p&q}
# F (q & r): sub = {q, r, q&r}  intersection with above = {q}, size 1
# F (s & t): sub = {s, t, s&t}  intersection with T(p&q) = {}, size 0
# Should pick the pair (T(p&q), F(q&r)). Both are alpha-type
# (T-And is alpha, F-And is beta). So T(p&q) is alpha, F(q&r) is beta.
# Rule 3 says "if one is alpha, expand the alpha" -> expand T(p&q).
# -----------------------------------------------------------------------------
br = make_branch("T p & q", "F q & r", "F s & t")
print(f"\n  [classifications:")
print(f"   T(p&q) is {classify(Signed(True,  parse_formula('p & q')))}]")
print(f"   F(q&r) is {classify(Signed(False, parse_formula('q & r')))}]")
expect("Rule 3: max intersection, alpha wins", br, "T (p & q)")


# -----------------------------------------------------------------------------
# Test 8: Rule (3) when both are beta, older wins.
# T(p | q): sub = {p, q, p|q}, age 0 - this is beta (T-Or is beta)
# F(p & q): sub = {p, q, p&q}, age 1 - this is beta (F-And is beta)
# intersection = {p, q}, size 2
# Both beta, older = T(p|q).
# -----------------------------------------------------------------------------
br = make_branch("T p | q", "F p & q")
expect("Rule 3: both beta, older wins", br, "T (p | q)")


# -----------------------------------------------------------------------------
# Test 9: Empty T or F - rule (4) fallback.
# Only T formulas, no F.
# -----------------------------------------------------------------------------
br = make_branch("T p & q", "T r | s")
# Should fall back to alphabeta: oldest alpha = T(p&q)
expect("Rule 4: empty F, fallback to alphabeta picks oldest alpha", br, "T (p & q)")


# -----------------------------------------------------------------------------
# Test 10: All atoms - should return None (after fallback to alphabeta).
# -----------------------------------------------------------------------------
br = make_branch("T p", "F q")
# No containment, no expandable formulas -> all rules fail -> None
sel = select_S(br)
print(f"OK    All atoms: returns {sel}" if sel is None else f"FAIL  All atoms: expected None, got {sel.sf}")


# -----------------------------------------------------------------------------
# Test 11: Critical case - rule (1) candidates include atoms.
# T (p): sub = {p}, age 0
# F (p): sub = {p}, age 1   <- ATOMIC and sub({p}) <= sub({p})
# F (p|q): sub = {p, q, p|q}, age 2  <- non-atomic and {p} <= sub
# Rule (1) should pick F(p|q), not F(p) which is atomic.
# Actually F(p) is atomic so 'expandable(fit)' filters it; good.
# Also note: T p AND F p on the same branch should mean closure -
# but our 'add' detects that. Let me verify.
# -----------------------------------------------------------------------------
print("\nTest 11: T(p) + F(p|q) -- but branch.add will close if T(p) and F(p) coexist")
br = Branch()
age = [0]
br.add(Signed(True, parse_formula("p")), age[0]); age[0] += 1
br.add(Signed(False, parse_formula("p | q")), age[0]); age[0] += 1
print(f"  branch.closed = {br.closed}")
sel = select_S(br)
print(f"  S picks: {sel.sf if sel else None}")
print(f"  Expected: F (p | q)")
