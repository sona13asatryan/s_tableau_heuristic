# s-tableau-heuristic

Python implementation of the **S subformula heuristic** for propositional analytic
tableaux, benchmarked against the classical α/β baseline on an extended
Pelletier suite.

This repository accompanies the master's thesis *Research of some proof
systems* (Yerevan State University, 2026). It implements two heuristics for
selecting the next formula to expand in Smullyan-style propositional analytic
tableaux:

- **S_αβ** — the classical strategy of expanding the oldest α-formula, falling
  back to the oldest β-formula.
- **S** — the proposed heuristic, which selects formulas based on
  subformula-set similarity between T-signed and F-signed formulas on the
  current branch, prioritizing pairs more likely to participate in branch
  closure.

Both heuristics are evaluated on a 102-problem benchmark built from Pelletier's
17 propositional problems together with five families of structural
substitutions designed to expose where each heuristic excels.

## Requirements

- Python ≥ 3.8 (uses dataclasses and modern type hints)
- [`openpyxl`](https://openpyxl.readthedocs.io/) — only needed for generating
  the colored Excel summary (`make_xlsx.py`)

Install with:

```bash
pip install openpyxl
```

The benchmark itself uses only the Python standard library.

## Quickstart

Run the full benchmark and write per-problem metrics to a CSV:

```bash
python bench.py pelletier_extended.p results.csv
```

The benchmark finishes in about a second. The CSV contains one row per
problem with nodes, expansions, β-counts, branch counts, and wall-clock
timing under each heuristic.

## Reproducing the thesis results

After running the benchmark, you should see the following aggregate numbers:

| Batch                       | N   | S_αβ | S    | S / S_αβ | (S / αβ / tie) |
|-----------------------------|-----|------|------|----------|----------------|
| Originals                   | 17  | 325  | 318  | 0.978    | 3 / 1 / 13     |
| B1 (asymmetric depth)       | 17  | 416  | 421  | 1.012    | 5 / 5 / 7      |
| B2 (mixed asymmetric)       | 17  | 449  | 487  | 1.085    | 4 / 5 / 8      |
| B3 (strict chain)           | 17  | 424  | 433  | 1.021    | 5 / 5 / 7      |
| B4 (one large *P*)          | 17  | 437  | 456  | 1.043    | 6 / 6 / 5      |
| B5 (recursive containment)  | 17  | 442  | 446  | 1.009    | 6 / 6 / 5      |
| **Total**                   | 102 | 2493 | 2561 | 1.027    | 29 / 28 / 45   |

Node counts are deterministic and should be byte-identical to the values
shipped in `results.csv`; only wall-clock timings vary between machines.

## Verifying correctness

Two scripts are included.

**Unit tests for the S heuristic** — eleven hand-crafted cases verifying that
each rule fires as specified in Definition 4.1 of the thesis:

```bash
python unit_test_S.py
```

**Brute-force semantic verification** — runs ten cherry-picked benchmark
problems with full tableau traces and cross-checks every conjecture against
an independent truth-table evaluator:

```bash
python verify_picks.py
```

Both scripts complete in a few seconds and end with confirmation that all
checked problems agree with brute-force semantics.

## Optional: colored Excel summary

`make_xlsx.py` converts `results.csv` to a color-coded `results.xlsx`:
green rows are S wins, red rows are S_αβ wins, gray rows are ties, and the
better cell in each metric pair is highlighted in yellow. A summary sheet
gives per-batch aggregates.

```bash
python make_xlsx.py
```

The script has the input and output paths hard-coded at the top; edit them
to point at your local files.

## Repository layout

| File                     | Purpose                                                                     |
|--------------------------|-----------------------------------------------------------------------------|
| `core.py`                | Formula AST, TPTP-fragment parser, signed formulas, α/β rules, expansions   |
| `engine.py`              | DFS tableau driver, branch state, closure detection, both heuristics        |
| `loader.py`              | TPTP file parser; groups axioms with their conjecture                       |
| `bench.py`               | Benchmark runner; writes the CSV                                            |
| `make_xlsx.py`           | Converts CSV to the colored Excel summary                                   |
| `gen_batches.py`         | Regenerates the substitution batches into a TPTP file                       |
| `filter_batches.py`      | Filters and renumbers batches to the final six used in the thesis           |
| `unit_test_S.py`         | Hand-crafted unit tests for the S heuristic                                 |
| `verify.py`              | Tableau tracer that records every step for inspection                       |
| `verify_picks.py`        | Cherry-picked verification with brute-force semantic cross-check            |
| `pelletier_extended.p`   | The 102-problem TPTP benchmark                                              |
| `results.csv`            | Canonical benchmark results                                                 |

## Benchmark structure

The benchmark file `pelletier_extended.p` follows the TPTP `fof` syntax. Each
problem is named `pel<NN>` (originals) or `pel<NN>_b<K>` (substitution
batch K). Problem 10 is an entailment, so it appears as three `axiom` clauses
plus a `conjecture`; all other problems are single tautologies.

The six batches are:

- **Originals** — Pelletier's propositional problems 1–17.
- **B1 (asymmetric depth)** —
  `P := ((p₁ → p₂) → p₃) → p₄`, `Q := p₁`, `R := ¬p₂`, `S := p₃ ∨ p₄`.
- **B2 (mixed asymmetric)** —
  `P := (p₁ ∧ p₂) ∨ (p₃ ∧ p₄)`, `Q := (p₁ → p₂) ∧ p₃`,
  `R := p₄`, `S := p₁ ∨ p₃`.
- **B3 (strict subformula chain)** —
  `P := ((p₁ ∧ p₂) ∨ p₃) → p₄`, `Q := (p₁ ∧ p₂) ∨ p₃`,
  `R := p₁ ∧ p₂`, `S := p₁`.
- **B4 (one huge P)** —
  `P := (((p₁ ↔ p₂) ∧ (p₃ ↔ p₄)) ∨ (p₁ ∧ ¬p₃)) → (p₂ ∨ ¬p₄)`,
  `Q := p₁`, `R := p₂`, `S := ¬p₃`.
- **B5 (recursive containment)** —
  `P := ((p₁ → p₂) ∧ (q₁ → q₂)) → r`, `Q := p₁ → p₂`,
  `R := q₁ → q₂`, `S := r`.

## Using the engine as a library

```python
from core import parse_formula, Signed
from engine import run_tableau, select_S, select_alphabeta

# T-signed for premises, F-signed for the conjecture (sequent style)
inputs = [
    Signed(True,  parse_formula("p => q")),
    Signed(True,  parse_formula("q => r")),
    Signed(False, parse_formula("p => r")),
]

m = run_tableau(inputs, select_S)
print(f"closed={m.closed} nodes={m.nodes} expansions={m.expansions}")
```

For a problem from the TPTP file:

```python
from loader import load_problems
problems = load_problems("pelletier_extended.p")
p = problems["pel17"]
m = run_tableau(p.signed_inputs, select_S)
```

## Citation

If you use this code or the benchmark in your work, please cite the thesis:

> Asatryan, S. T. *Research of some proof systems.* Master's thesis, Yerevan
> State University, Faculty of Informatics and Applied Mathematics, 2026.

## License

MIT — see [`LICENSE`](LICENSE).
