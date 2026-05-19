"""
Load problems from the extended Pelletier TPTP file.

Each problem is identified by its conjecture name (e.g. 'pel10_b3').
Axioms are grouped with their conjecture by name prefix:
  conjecture  'pel10_b3'   collects axioms named  'pel10_b3_ax1', 'pel10_b3_ax2', ...

For each problem we produce a list of signed formulas: T <axiom_i> for each
axiom, and F <conjecture> for the conjecture (standard sequent style).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple
import re

from core import Signed, parse_formula, Formula


_FOF_RE = re.compile(
    r"fof\(\s*([A-Za-z0-9_]+)\s*,\s*([a-z]+)\s*,\s*(.+?)\)\s*\.\s*$",
    re.DOTALL,
)


@dataclass
class Problem:
    name: str                   # conjecture name, e.g. 'pel10_b3'
    axioms: List[Tuple[str, Formula]]   # (axiom_name, formula)
    conjecture: Formula
    signed_inputs: List[Signed]         # ready to feed the tableau


def _strip_comments(text: str) -> str:
    # Remove % line comments
    return re.sub(r"%[^\n]*", "", text)


def _split_fof_blocks(text: str) -> List[str]:
    """Split the file into top-level fof(...) entries, respecting nested parens.

    The simple regex approach can choke on the heavily nested formulas, so we
    walk the text and split on the period that ends each fof(...) statement.
    """
    blocks = []
    i = 0
    n = len(text)
    while i < n:
        # find next 'fof'
        j = text.find("fof", i)
        if j == -1:
            break
        # find the opening paren after 'fof'
        k = text.find("(", j)
        if k == -1:
            break
        # walk parentheses to find matching close
        depth = 0
        p = k
        while p < n:
            c = text[p]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            p += 1
        if p >= n:
            break
        # advance past the closing paren and the terminating period
        end = p + 1
        # eat whitespace and a period
        while end < n and text[end].isspace():
            end += 1
        if end < n and text[end] == ".":
            end += 1
        blocks.append(text[j:end])
        i = end
    return blocks


def _parse_block(block: str):
    """Parse one fof(name, role, formula). entry. Returns (name, role, Formula)."""
    # Find name and role
    m = re.match(r"fof\(\s*([A-Za-z0-9_]+)\s*,\s*([a-z]+)\s*,", block)
    if not m:
        raise ValueError(f"could not parse header of: {block[:80]!r}")
    name = m.group(1)
    role = m.group(2)
    # The formula is everything between the second comma and the final ')' '.'
    # Strip leading "fof( name , role ," and trailing ")."
    inner = block[m.end():]
    # remove trailing whitespace + final ')' + final '.'
    inner = inner.rstrip()
    if inner.endswith("."):
        inner = inner[:-1].rstrip()
    if inner.endswith(")"):
        inner = inner[:-1]
    formula = parse_formula(inner.strip())
    return name, role, formula


def load_problems(path: str) -> Dict[str, Problem]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    text = _strip_comments(text)

    blocks = _split_fof_blocks(text)

    # First pass: classify each entry
    entries = []  # list of (name, role, formula)
    for blk in blocks:
        try:
            entries.append(_parse_block(blk))
        except Exception as e:
            raise ValueError(f"failed to parse block:\n{blk}\nerror: {e}")

    # Group axioms by conjecture-name-prefix
    # Convention used in the file: axioms for conjecture 'X' are named 'X_ax1', 'X_ax2', ...
    by_name = {n: (r, f) for (n, r, f) in entries}

    conjectures = [(n, f) for (n, r, f) in entries if r == "conjecture"]
    problems: Dict[str, Problem] = {}

    for cname, cformula in conjectures:
        axioms = []
        for (n, r, f) in entries:
            if r != "axiom":
                continue
            # axiom 'X_axK' belongs to conjecture 'X'
            if n.startswith(cname + "_ax"):
                axioms.append((n, f))
        signed = [Signed(True, ax_f) for (_, ax_f) in axioms] + \
                 [Signed(False, cformula)]
        problems[cname] = Problem(name=cname, axioms=axioms,
                                  conjecture=cformula, signed_inputs=signed)

    return problems
