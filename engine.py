"""
Tableau engine: runs Smullyan-style tableaux with pluggable selection heuristics.

A *branch* is the path of signed formulas from the root to a leaf. We don't
build an explicit tree object; instead each Branch carries its own list of
signed formulas with per-formula "expanded" flags, and the search recurses on
copies when beta-branching occurs.

Metrics collected per run:
  - nodes:        total signed-formula occurrences appended across the tree
                  (initial inputs counted once; alpha adds 2; beta adds 1 per child)
  - expansions:   total expansion steps performed
  - betas:        number of beta-expansion steps
  - depth_max:    maximum branch length (in signed formulas) seen
  - closed:       whether the tableau closed
  - time_ms:      wall-clock milliseconds
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple
import time

from core import (
    Signed, Formula, Atom, Not,
    classify, expand, subformulas, is_atomic,
    ALPHA, BETA, ATOM,
)


# ---------------------------------------------------------------------------
# Branch representation
# ---------------------------------------------------------------------------

@dataclass
class BranchItem:
    sf: Signed
    expanded: bool = False
    age: int = 0       # insertion order (smaller = older)


@dataclass
class Branch:
    items: List[BranchItem] = field(default_factory=list)
    # set of signed-formula pairs (sign, formula) present on branch, for dedup
    present: set = field(default_factory=set)
    # set of conjugate atomic pairs check; closed if some signed atom and its
    # conjugate are both present.
    atoms_T: set = field(default_factory=set)   # formulas asserted T at atomic level
    atoms_F: set = field(default_factory=set)   # formulas asserted F at atomic level
    closed: bool = False

    def clone(self) -> "Branch":
        # shallow copy of items list, deep copy of sets
        new = Branch()
        # copy each BranchItem so toggling 'expanded' in one child doesn't leak
        new.items = [BranchItem(it.sf, it.expanded, it.age) for it in self.items]
        new.present = set(self.present)
        new.atoms_T = set(self.atoms_T)
        new.atoms_F = set(self.atoms_F)
        new.closed = self.closed
        return new

    def add(self, sf: Signed, age: int) -> bool:
        """Add a signed formula to the branch. Updates closure state.
        Returns True iff the formula was actually inserted (False if duplicate)."""
        key = (sf.sign, sf.formula)
        if key in self.present:
            return False  # avoid trivial duplicates on the same branch
        # Complementary closure at ANY formula level: if the conjugate
        # (opposite sign, same formula) is already present, the branch closes.
        # This is sound because T phi and F phi on the same branch is a
        # direct contradiction regardless of phi's structure.
        conjugate_key = (not sf.sign, sf.formula)
        if conjugate_key in self.present:
            self.closed = True
        self.present.add(key)
        self.items.append(BranchItem(sf, expanded=False, age=age))
        # Also keep atomic-level closure tracking (redundant with the above
        # for atoms, but cheap and used by no other code path).
        if is_atomic(sf.formula):
            # normalize: ~A asserted T is the same as A asserted F
            if isinstance(sf.formula, Not):
                # signed literal ~A
                base = sf.formula.sub
                if sf.sign:   # T ~A   == F A
                    self.atoms_F.add(base)
                else:         # F ~A   == T A
                    self.atoms_T.add(base)
            else:
                base = sf.formula
                if sf.sign:
                    self.atoms_T.add(base)
                else:
                    self.atoms_F.add(base)
            if base in self.atoms_T and base in self.atoms_F:
                self.closed = True
        return True


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

Selector = Callable[[Branch], Optional[BranchItem]]


def select_alphabeta(branch: Branch) -> Optional[BranchItem]:
    """S_{alpha/beta}: oldest unexpanded alpha; else oldest unexpanded beta.
    Atomic signed formulas and ~atom are skipped (not expanded).
    """
    oldest_alpha: Optional[BranchItem] = None
    oldest_beta:  Optional[BranchItem] = None
    for it in branch.items:
        if it.expanded:
            continue
        k = classify(it.sf)
        if k == ATOM:
            continue
        if k == ALPHA:
            if oldest_alpha is None or it.age < oldest_alpha.age:
                oldest_alpha = it
        elif k == BETA:
            if oldest_beta is None or it.age < oldest_beta.age:
                oldest_beta = it
    return oldest_alpha if oldest_alpha is not None else oldest_beta


def select_S(branch: Branch) -> Optional[BranchItem]:
    """S heuristic from the thesis (Definition 4.1):

      (1) If exists T phi, F chi  with sub(phi) <= sub(chi):  expand F chi.
      (2) If exists F chi, T phi  with sub(chi) <= sub(phi):  expand T phi.
      (3) Take (T phi, F chi) pair maximizing |sub(phi) cap sub(chi)|.
          If either is alpha, expand the alpha; else expand the older.
          If the chosen formula is atomic, expand the other member of the pair.
      (4) If T-set or F-set (of expandable formulas) is empty, fall back to alpha/beta.

    Atomic signed formulas are never selected for expansion themselves;
    they participate only in the sub() comparisons that drive selection of
    non-atomic partners.
    """
    # Partition unexpanded items into T- and F- buckets.
    # NOTE: atoms ARE included in comparisons (their sub-set is just {atom}),
    # but they are never returned as the chosen formula to expand. If rule (3)
    # would pick an atomic pair member, we expand the non-atomic partner instead.
    T_items: List[BranchItem] = []
    F_items: List[BranchItem] = []
    for it in branch.items:
        if it.expanded:
            continue
        if it.sf.sign:
            T_items.append(it)
        else:
            F_items.append(it)

    # Distinguish "any" T/F (incl. atoms, for comparison) from "expandable" (non-atomic).
    def expandable(it: BranchItem) -> bool:
        return classify(it.sf) != ATOM

    if not T_items or not F_items:
        return select_alphabeta(branch)

    # Precompute subformula sets.
    T_subs = [(it, subformulas(it.sf.formula)) for it in T_items]
    F_subs = [(it, subformulas(it.sf.formula)) for it in F_items]

    # Rule (1): exists T phi, F chi  with sub(phi) <= sub(chi) -> expand F chi.
    # F chi must be expandable (non-atomic) to be returned.
    rule1_candidates: List[BranchItem] = []
    for tit, ts in T_subs:
        for fit, fs in F_subs:
            if ts <= fs and expandable(fit):
                rule1_candidates.append(fit)
    if rule1_candidates:
        return min(rule1_candidates, key=lambda it: it.age)

    # Rule (2): exists F chi, T phi  with sub(chi) <= sub(phi) -> expand T phi.
    rule2_candidates: List[BranchItem] = []
    for fit, fs in F_subs:
        for tit, ts in T_subs:
            if fs <= ts and expandable(tit):
                rule2_candidates.append(tit)
    if rule2_candidates:
        return min(rule2_candidates, key=lambda it: it.age)

    # Rule (3): max-intersection pair; alpha wins; else older.
    # Consider only pairs with at least one expandable member (so we can return
    # something). When the best pair has an atomic member, expand the other.
    best_pair: Optional[Tuple[BranchItem, BranchItem]] = None
    best_score = -1
    for tit, ts in T_subs:
        for fit, fs in F_subs:
            if not (expandable(tit) or expandable(fit)):
                continue
            score = len(ts & fs)
            if score > best_score:
                best_score = score
                best_pair = (tit, fit)

    if best_pair is None:
        return select_alphabeta(branch)

    tit, fit = best_pair
    # If one member is atomic, expand the other.
    if not expandable(tit):
        return fit
    if not expandable(fit):
        return tit

    t_kind = classify(tit.sf)
    f_kind = classify(fit.sf)
    if t_kind == ALPHA and f_kind != ALPHA:
        return tit
    if f_kind == ALPHA and t_kind != ALPHA:
        return fit
    return tit if tit.age <= fit.age else fit


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class Metrics:
    nodes: int = 0          # total signed-formula occurrences appended
    expansions: int = 0     # total expansion steps
    betas: int = 0          # beta-expansion steps
    depth_max: int = 0      # max branch length encountered
    branches_closed: int = 0
    branches_open: int = 0
    closed: bool = False    # tableau closed (proof succeeded)
    time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Main tableau procedure
# ---------------------------------------------------------------------------

def run_tableau(
    initial: List[Signed],
    selector: Selector,
    node_limit: int = 200_000,
    time_limit_s: float = 30.0,
) -> Metrics:
    """Build a tableau starting from `initial` signed formulas using `selector`.

    Returns Metrics. If `closed` is True, every branch was closed (proof found).
    If False, either there's a saturated open branch (countermodel) or limits
    were hit.
    """
    m = Metrics()
    t0 = time.perf_counter()

    # ---- counter for ages, shared across the whole tableau
    age_counter = [0]

    def next_age() -> int:
        a = age_counter[0]
        age_counter[0] += 1
        return a

    def safe_add(branch: Branch, sf: Signed) -> None:
        """Add to branch; only burn an age + count a node if actually inserted."""
        # tentatively reserve an age, but only commit if add() returns True
        age = age_counter[0]
        if branch.add(sf, age):
            age_counter[0] += 1
            m.nodes += 1

    # initial branch
    root = Branch()
    for sf in initial:
        safe_add(root, sf)

    if root.closed:
        m.branches_closed = 1
        m.closed = True
        m.depth_max = len(root.items)
        m.time_ms = (time.perf_counter() - t0) * 1000.0
        return m

    # DFS over branches; each branch is processed to completion (closed or open-saturated)
    # before backtracking. Iterative stack of branches.
    stack: List[Branch] = [root]

    deadline = t0 + time_limit_s
    aborted = False

    while stack:
        if m.nodes >= node_limit:
            aborted = True
            break
        if time.perf_counter() > deadline:
            aborted = True
            break

        br = stack.pop()
        if br.closed:
            m.branches_closed += 1
            if len(br.items) > m.depth_max:
                m.depth_max = len(br.items)
            continue

        sel = selector(br)
        if sel is None:
            # nothing expandable left and branch isn't closed -> open branch
            m.branches_open += 1
            if len(br.items) > m.depth_max:
                m.depth_max = len(br.items)
            continue

        # expand
        sel.expanded = True
        m.expansions += 1
        children = expand(sel.sf)

        if len(children) == 1:
            # alpha: extend the same branch in place
            comps = children[0]
            for comp in comps:
                safe_add(br, comp)
            stack.append(br)
        else:
            # beta: one child branch per disjunct
            m.betas += 1
            for comps in children:
                child = br.clone()
                for comp in comps:
                    safe_add(child, comp)
                stack.append(child)

    # finalize
    m.closed = (m.branches_open == 0) and (not aborted)
    m.time_ms = (time.perf_counter() - t0) * 1000.0
    return m
