"""
Core data structures for propositional Smullyan tableaux:
  - Formula AST (Atom, Not, And, Or, Imp, Iff)
  - Parser for the TPTP fof propositional fragment
  - Signed formulas and alpha/beta classification
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Union, List, Tuple, Optional
import re


# ---------------------------------------------------------------------------
# Formula AST
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Atom:
    name: str
    def __str__(self) -> str: return self.name

@dataclass(frozen=True)
class Not:
    sub: "Formula"
    def __str__(self) -> str: return f"~{self.sub}"

@dataclass(frozen=True)
class And:
    left: "Formula"
    right: "Formula"
    def __str__(self) -> str: return f"({self.left} & {self.right})"

@dataclass(frozen=True)
class Or:
    left: "Formula"
    right: "Formula"
    def __str__(self) -> str: return f"({self.left} | {self.right})"

@dataclass(frozen=True)
class Imp:
    left: "Formula"
    right: "Formula"
    def __str__(self) -> str: return f"({self.left} => {self.right})"

@dataclass(frozen=True)
class Iff:
    left: "Formula"
    right: "Formula"
    def __str__(self) -> str: return f"({self.left} <=> {self.right})"

Formula = Union[Atom, Not, And, Or, Imp, Iff]


def subformulas(f: Formula) -> frozenset:
    """All subformulas of f, including f itself (as Formula objects)."""
    if isinstance(f, Atom):
        return frozenset([f])
    if isinstance(f, Not):
        return frozenset([f]) | subformulas(f.sub)
    # binary
    return frozenset([f]) | subformulas(f.left) | subformulas(f.right)


def is_atomic(f: Formula) -> bool:
    return isinstance(f, Atom) or (isinstance(f, Not) and isinstance(f.sub, Atom))


# ---------------------------------------------------------------------------
# Parser for the TPTP fof propositional fragment
# ---------------------------------------------------------------------------
#
# Connective precedence (tightest first, like standard prop logic):
#   ~  (unary)
#   &
#   |
#   =>     (right-associative)
#   <=>    (right-associative)
#
# Tokens: ~ & | => <=> ( ) and identifiers [a-z_][A-Za-z0-9_]*
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"\s*(<=>|=>|~|&|\||\(|\)|[A-Za-z_][A-Za-z0-9_]*)")


class _Parser:
    def __init__(self, text: str):
        self.tokens: List[str] = []
        pos = 0
        while pos < len(text):
            m = _TOKEN_RE.match(text, pos)
            if not m:
                # skip unrecognized character (shouldn't happen for clean input)
                pos += 1
                continue
            self.tokens.append(m.group(1))
            pos = m.end()
        self.i = 0

    def peek(self) -> Optional[str]:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def eat(self, tok: str) -> None:
        if self.peek() != tok:
            raise ValueError(f"expected {tok!r}, got {self.peek()!r} at pos {self.i}")
        self.i += 1

    def parse(self) -> Formula:
        f = self.parse_iff()
        if self.i != len(self.tokens):
            raise ValueError(f"trailing tokens: {self.tokens[self.i:]}")
        return f

    def parse_iff(self) -> Formula:
        left = self.parse_imp()
        if self.peek() == "<=>":
            self.eat("<=>")
            right = self.parse_iff()  # right-assoc
            return Iff(left, right)
        return left

    def parse_imp(self) -> Formula:
        left = self.parse_or()
        if self.peek() == "=>":
            self.eat("=>")
            right = self.parse_imp()  # right-assoc
            return Imp(left, right)
        return left

    def parse_or(self) -> Formula:
        left = self.parse_and()
        while self.peek() == "|":
            self.eat("|")
            right = self.parse_and()
            left = Or(left, right)
        return left

    def parse_and(self) -> Formula:
        left = self.parse_unary()
        while self.peek() == "&":
            self.eat("&")
            right = self.parse_unary()
            left = And(left, right)
        return left

    def parse_unary(self) -> Formula:
        if self.peek() == "~":
            self.eat("~")
            return Not(self.parse_unary())
        return self.parse_atom()

    def parse_atom(self) -> Formula:
        tok = self.peek()
        if tok is None:
            raise ValueError("unexpected end of input")
        if tok == "(":
            self.eat("(")
            f = self.parse_iff()
            self.eat(")")
            return f
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tok):
            self.i += 1
            return Atom(tok)
        raise ValueError(f"unexpected token {tok!r}")


def parse_formula(text: str) -> Formula:
    return _Parser(text).parse()


# ---------------------------------------------------------------------------
# Signed formulas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Signed:
    sign: bool          # True = T (asserted true), False = F (asserted false)
    formula: Formula

    def __str__(self) -> str:
        return f"{'T' if self.sign else 'F'} {self.formula}"

    def conjugate(self) -> "Signed":
        return Signed(not self.sign, self.formula)


# Classification --------------------------------------------------------------
# alpha-rules: linear, two components added to same branch
# beta-rules:  branching, one component per child branch
# Atomic signed formulas are neither (used only for closure).

ALPHA = "alpha"
BETA  = "beta"
ATOM  = "atom"


def classify(sf: Signed) -> str:
    f = sf.formula
    if isinstance(f, Atom):
        return ATOM
    if isinstance(f, Not):
        # T ~A and F ~A are alpha (single component, which is the conjugate)
        if isinstance(f.sub, Atom):
            return ATOM   # signed literal
        return ALPHA
    if isinstance(f, And):
        return ALPHA if sf.sign else BETA
    if isinstance(f, Or):
        return BETA if sf.sign else ALPHA
    if isinstance(f, Imp):
        return BETA if sf.sign else ALPHA
    if isinstance(f, Iff):
        return BETA   # both T and F iff are now beta (direct Smullyan rules)
    raise TypeError(f"unknown formula type: {type(f)}")


def expand(sf: Signed) -> List[List[Signed]]:
    """Return list of branches; each branch is a list of signed formulas to add.

    For alpha: one branch with the two components.
    For beta:  two branches, each with one component (for iff: the two implication directions).
    For atom:  raises (atoms aren't expanded).
    """
    f = sf.formula
    s = sf.sign

    if isinstance(f, Atom):
        raise ValueError("cannot expand an atom")

    if isinstance(f, Not):
        # T ~A => F A;   F ~A => T A
        return [[Signed(not s, f.sub)]]

    if isinstance(f, And):
        if s:   # T (A & B) -> T A, T B   (alpha)
            return [[Signed(True, f.left), Signed(True, f.right)]]
        else:   # F (A & B) -> F A | F B  (beta)
            return [[Signed(False, f.left)], [Signed(False, f.right)]]

    if isinstance(f, Or):
        if s:   # T (A | B) -> T A | T B  (beta)
            return [[Signed(True, f.left)], [Signed(True, f.right)]]
        else:   # F (A | B) -> F A, F B   (alpha)
            return [[Signed(False, f.left), Signed(False, f.right)]]

    if isinstance(f, Imp):
        if s:   # T (A => B) -> F A | T B (beta)
            return [[Signed(False, f.left)], [Signed(True, f.right)]]
        else:   # F (A => B) -> T A, F B  (alpha)
            return [[Signed(True, f.left), Signed(False, f.right)]]

    if isinstance(f, Iff):
        # Standard direct Smullyan rules; both signs are beta-type.
        # No synthetic Imp construction, which keeps subformula sets faithful
        # to the original formula tree.
        if s:   # T (A <=> B) -> {T A, T B} | {F A, F B}
            return [[Signed(True,  f.left), Signed(True,  f.right)],
                    [Signed(False, f.left), Signed(False, f.right)]]
        else:   # F (A <=> B) -> {T A, F B} | {F A, T B}
            return [[Signed(True,  f.left), Signed(False, f.right)],
                    [Signed(False, f.left), Signed(True,  f.right)]]

    raise TypeError(f"unknown formula type: {type(f)}")
