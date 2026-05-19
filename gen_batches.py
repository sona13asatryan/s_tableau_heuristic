"""Generate batches B6 (Option F), B7 (G), B8 (H), B9 (I) using string substitution.

We define each of P, Q, R, S as fully-parenthesized strings, then plug them into
the 17 Pelletier templates. This guarantees paren balance.

Template numbering matches Pelletier's; we follow the exact same structure
already used in B1-B5.
"""
from textwrap import indent

# -----------------------------------------------------------------------------
# Substitutions (each is a fully-parenthesized TPTP string)
# -----------------------------------------------------------------------------

BATCHES = {
    "b6": {  # Option F -- moderate-depth, overlapping atoms
        "P": "( ( p1 & p2 ) | ( p3 & p4 ) )",
        "Q": "( ( p1 => p2 ) & p3 )",
        "R": "p4",
        "S": "( p1 | p3 )",
        "desc": "Option F (asymmetric, overlapping atoms)",
    },
    "b7": {  # Option G -- strict subformula chain  sub(S) c sub(R) c sub(Q) c sub(P)
        "P": "( ( ( p1 & p2 ) | p3 ) => p4 )",
        "Q": "( ( p1 & p2 ) | p3 )",
        "R": "( p1 & p2 )",
        "S": "p1",
        "desc": "Option G (strict subformula chain)",
    },
    "b8": {  # Option H -- one huge P, three shallow
        "P": "( ( ( ( p1 <=> p2 ) & ( p3 <=> p4 ) ) | ( p1 & ~p3 ) ) => ( p2 | ~p4 ) )",
        "Q": "p1",
        "R": "p2",
        "S": "~p3",
        "desc": "Option H (one huge formula, three shallow)",
    },
    "b9": {  # Option I -- recursive containment
        "P": "( ( ( p1 => p2 ) & ( q1 => q2 ) ) => r )",
        "Q": "( p1 => p2 )",
        "R": "( q1 => q2 )",
        "S": "r",
        "desc": "Option I (recursive containment, Phi-style structure)",
    },
}


# -----------------------------------------------------------------------------
# Pelletier templates: each is a function building the TPTP formula body
# from strings P, Q, R, S. The grouping/parens match the originals in the file.
# -----------------------------------------------------------------------------

def t1 (P,Q,R,S):  return f"( ( {P} => {Q} ) <=> ( ~{Q} => ~{P} ) )"
def t2 (P,Q,R,S):  return f"( ~~{P} <=> {P} )"
def t3 (P,Q,R,S):  return f"( ~( {P} => {Q} ) => ( {Q} => {P} ) )"
def t4 (P,Q,R,S):  return f"( ( ~{P} => {Q} ) <=> ( ~{Q} => {P} ) )"
def t5 (P,Q,R,S):  return f"( ( ( {P} | {Q} ) => ( {P} | {R} ) ) => ( {P} | ( {Q} => {R} ) ) )"
def t6 (P,Q,R,S):  return f"( {P} | ~{P} )"
def t7 (P,Q,R,S):  return f"( {P} | ~~~{P} )"
def t8 (P,Q,R,S):  return f"( ( ( {P} => {Q} ) => {P} ) => {P} )"
def t9 (P,Q,R,S):  return (
    f"( ( ( {P} | {Q} ) & ( ~{P} | {Q} ) & ( {P} | ~{Q} ) ) => ~( ~{P} | ~{Q} ) )"
)

# Problem 10: an entailment.  Returns (axioms, conjecture).
def t10(P,Q,R,S):
    axioms = [
        f"( {Q} => {R} )",
        f"( {R} => ( {P} & {Q} ) )",
        f"( {P} => ( {Q} | {R} ) )",
    ]
    conj = f"( {P} <=> {Q} )"
    return axioms, conj

def t11(P,Q,R,S):  return f"( {P} <=> {P} )"
def t12(P,Q,R,S):  return f"( ( ( {P} <=> {Q} ) <=> {R} ) <=> ( {P} <=> ( {Q} <=> {R} ) ) )"
def t13(P,Q,R,S):  return f"( ( {P} | ( {Q} & {R} ) ) <=> ( ( {P} | {Q} ) & ( {P} | {R} ) ) )"
def t14(P,Q,R,S):  return f"( ( {P} <=> {Q} ) <=> ( ( {Q} | ~{P} ) & ( ~{Q} | {P} ) ) )"
def t15(P,Q,R,S):  return f"( ( {P} => {Q} ) <=> ( ~{P} | {Q} ) )"
def t16(P,Q,R,S):  return f"( ( {P} => {Q} ) | ( {Q} => {P} ) )"
def t17(P,Q,R,S):  return (
    f"( ( ( {P} & ( {Q} => {R} ) ) => {S} )"
    f" <=> ( ( ~{P} | {Q} | {S} ) & ( ~{P} | ~{R} | {S} ) ) )"
)

# Map problem number to template builder.
SIMPLE_TEMPLATES = {
    1:t1, 2:t2, 3:t3, 4:t4, 5:t5, 6:t6, 7:t7, 8:t8, 9:t9,
    11:t11, 12:t12, 13:t13, 14:t14, 15:t15, 16:t16, 17:t17,
}


def emit_batch(batch_name: str, info: dict) -> str:
    """Build the full TPTP block for one batch."""
    P, Q, R, S = info["P"], info["Q"], info["R"], info["S"]

    header = (
        "%==============================================================================\n"
        f"% BATCH {batch_name.upper()[1:]} ({info['desc']})\n"
        f"%   P := {P}\n"
        f"%   Q := {Q}\n"
        f"%   R := {R}\n"
        f"%   S := {S}\n"
        "%==============================================================================\n\n"
    )

    lines = [header]

    for n in range(1, 18):
        if n == 10:
            axs, conj = t10(P, Q, R, S)
            for k, ax in enumerate(axs, start=1):
                lines.append(f"fof(pel10_{batch_name}_ax{k}, axiom, {ax} ).\n")
            lines.append(f"fof(pel10_{batch_name}, conjecture, {conj} ).\n\n")
        else:
            fbody = SIMPLE_TEMPLATES[n](P, Q, R, S)
            lines.append(f"fof(pel{n:02d}_{batch_name}, conjecture,\n    {fbody} ).\n\n")

    return "".join(lines)


def main():
    in_path = "/mnt/user-data/outputs/pelletier_extended.p"
    out_path = "/home/claude/tableau/pelletier_extended.p"

    with open(in_path, "r", encoding="utf-8") as f:
        original = f.read()

    # Strip any trailing 'End of file' banner, then re-append after new batches.
    eof_marker = ("%------------------------------------------------------------------------------\n"
                  "% End of file\n"
                  "%------------------------------------------------------------------------------\n")
    if eof_marker in original:
        original = original.replace(eof_marker, "")

    chunks = [original.rstrip() + "\n\n"]
    for name in ["b6", "b7", "b8", "b9"]:
        chunks.append(emit_batch(name, BATCHES[name]))
    chunks.append(eof_marker)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("".join(chunks))

    # Quick paren sanity check
    text = open(out_path).read()
    print(f"Wrote {out_path}")
    print(f"Total chars: {len(text)}")
    # Verify it loads
    import sys
    sys.path.insert(0, "/home/claude/tableau")
    from loader import load_problems
    probs = load_problems(out_path)
    print(f"Loaded {len(probs)} problems")


if __name__ == "__main__":
    main()
