"""Filter and renumber the extended Pelletier benchmark.

Keep: originals, b3, b6, b7, b8, b9.
Renumber so they appear as:
  originals -> stay as pelNN
  b3        -> b1
  b6        -> b2
  b7        -> b3
  b8        -> b4
  b9        -> b5
"""

import re
import sys

IN  = "/home/claude/tableau/pelletier_extended.p"
OUT = "/home/claude/tableau/pelletier_extended_filtered.p"

# old batch number -> new batch number (None means keep as originals, no _bN suffix)
RENAME = {
    None: None,   # originals stay as originals
    "3":  "1",
    "6":  "2",
    "7":  "3",
    "8":  "4",
    "9":  "5",
}

# everything else gets dropped
KEEP_OLD = set([None]) | {k for k in RENAME if k is not None}


# -----------------------------------------------------------------------------
# Use the same robust paren-walker as the loader to extract fof(...) blocks.
# -----------------------------------------------------------------------------

def split_fof_blocks(text: str):
    """Yields (block_text, leading_whitespace_before_block) tuples in order."""
    blocks = []
    i = 0
    n = len(text)
    while i < n:
        j = text.find("fof", i)
        if j == -1:
            break
        k = text.find("(", j)
        if k == -1:
            break
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
        end = p + 1
        while end < n and text[end].isspace():
            end += 1
        if end < n and text[end] == ".":
            end += 1
        blocks.append((j, end, text[j:end]))
        i = end
    return blocks


def parse_name(block: str):
    """Return (problem_base, batch_or_None, suffix_or_None, role).
    e.g. 'pel10_b3_ax2' -> (10, '3', 'ax2', 'axiom').
         'pel17_b6'     -> (17, '6', None, 'conjecture').
         'pel05'        -> (5, None, None, 'conjecture').
    """
    m = re.match(r"fof\(\s*pel(\d+)(?:_b(\d+))?(?:_(ax\d+))?\s*,\s*([a-z]+)", block)
    if not m:
        raise ValueError(f"Cannot parse header: {block[:80]}")
    return int(m.group(1)), m.group(2), m.group(3), m.group(4)


def rename_in_block(block: str, new_batch):
    """Rewrite a fof(...) block, replacing its problem identifier.

    new_batch is either None (originals -> no suffix) or a string like '2'.
    """
    pno, old_batch, suffix, role = parse_name(block)
    # Build new name
    name = f"pel{pno:02d}"
    if new_batch is not None:
        name += f"_b{new_batch}"
    if suffix:
        name += f"_{suffix}"
    # Replace the identifier in the block. The first occurrence is in 'fof(NAME,'.
    # Use a precise replacement on the matched span.
    new_block = re.sub(
        r"(fof\(\s*)pel\d+(?:_b\d+)?(?:_ax\d+)?",
        lambda m: m.group(1) + name,
        block,
        count=1,
    )
    return new_block


def main():
    with open(IN, "r", encoding="utf-8") as f:
        text = f.read()

    # Strip % line comments so the block-walker doesn't trip on prose like "fof".
    text = re.sub(r"%[^\n]*", "", text)

    blocks = split_fof_blocks(text)
    print(f"Found {len(blocks)} fof blocks in input.", file=sys.stderr)

    kept = []
    for (start, end, block) in blocks:
        pno, old_batch, suffix, role = parse_name(block)
        if old_batch not in KEEP_OLD:
            continue
        new_batch = RENAME[old_batch]
        new_block = rename_in_block(block, new_batch)
        kept.append((old_batch, new_batch, pno, suffix or "", new_block))

    # Sort: originals first (batch=None), then new batches 1..5 in order; within each,
    # by problem number, then axioms before conjecture.
    def sort_key(item):
        old_batch, new_batch, pno, suffix, _ = item
        batch_order = 0 if new_batch is None else int(new_batch)
        # Axioms (ax1, ax2, ax3) should appear before the conjecture of the same problem.
        # suffix is "" for conjecture, "axN" for axioms.
        sub_order = (0, int(suffix[2:])) if suffix.startswith("ax") else (1, 0)
        return (batch_order, pno, sub_order)
    kept.sort(key=sort_key)

    # Emit with nice batch headers
    lines = []
    lines.append("%------------------------------------------------------------------------------\n")
    lines.append("% File     : pelletier_extended.p\n")
    lines.append("% Domain   : Propositional Logic\n")
    lines.append("% Problems : Pelletier originals + 5 selected asymmetric substitution batches.\n")
    lines.append("%\n")
    lines.append("% Batches (each has 17 problems, problem 10 has 3 axioms + 1 conjecture):\n")
    lines.append("%   originals : pel01 .. pel17\n")
    lines.append("%   B1        : pel01_b1 .. pel17_b1  -- asymmetric depth\n")
    lines.append("%                 P := ((p1 => p2) => p3) => p4\n")
    lines.append("%                 Q := p1,  R := ~p2,  S := p3 | p4\n")
    lines.append("%   B2        : pel01_b2 .. pel17_b2  -- mixed asymmetric, overlapping atoms\n")
    lines.append("%                 P := (p1 & p2) | (p3 & p4),  Q := (p1 => p2) & p3\n")
    lines.append("%                 R := p4,                     S := p1 | p3\n")
    lines.append("%   B3        : pel01_b3 .. pel17_b3  -- strict subformula chain\n")
    lines.append("%                 P := ((p1 & p2) | p3) => p4,  Q := (p1 & p2) | p3\n")
    lines.append("%                 R := p1 & p2,                 S := p1\n")
    lines.append("%   B4        : pel01_b4 .. pel17_b4  -- one huge P, three shallow\n")
    lines.append("%                 P := (((p1<=>p2) & (p3<=>p4)) | (p1 & ~p3)) => (p2 | ~p4)\n")
    lines.append("%                 Q := p1,  R := p2,  S := ~p3\n")
    lines.append("%   B5        : pel01_b5 .. pel17_b5  -- recursive containment (Phi-style)\n")
    lines.append("%                 P := ((p1 => p2) & (q1 => q2)) => r\n")
    lines.append("%                 Q := p1 => p2,  R := q1 => q2,  S := r\n")
    lines.append("%------------------------------------------------------------------------------\n\n")

    last_batch = "INIT"
    for (old_batch, new_batch, pno, suffix, block) in kept:
        if new_batch != last_batch:
            if new_batch is None:
                lines.append("\n%==============================================================================\n")
                lines.append("% Originals\n")
                lines.append("%==============================================================================\n\n")
            else:
                lines.append(f"\n%==============================================================================\n")
                lines.append(f"% Batch {new_batch}\n")
                lines.append(f"%==============================================================================\n\n")
            last_batch = new_batch
        lines.append(block + "\n")

    lines.append("\n%------------------------------------------------------------------------------\n")
    lines.append("% End of file\n")
    lines.append("%------------------------------------------------------------------------------\n")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("".join(lines))

    # Verify
    sys.path.insert(0, "/home/claude/tableau")
    from loader import load_problems
    probs = load_problems(OUT)
    print(f"Loaded {len(probs)} problems from filtered file.", file=sys.stderr)

    # Count by batch
    from collections import Counter
    bc = Counter()
    for name in probs:
        m = re.match(r"pel\d+(?:_b(\d+))?$", name)
        bc[m.group(1) or "0"] += 1
    for b in sorted(bc.keys()):
        label = "originals" if b == "0" else f"b{b}"
        print(f"  {label}: {bc[b]} problems", file=sys.stderr)


if __name__ == "__main__":
    main()
