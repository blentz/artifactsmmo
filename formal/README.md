# Formal verification (Lean 4)

Kernel-checked proofs that the AI's pure logic is correct **for all valid inputs**,
plus a gate that mechanically rejects the ways a proof can be faked or made vacuous.

## Soundness chain

> Python function correct ⇐ (Python ≡ Lean def, by the differential test)
> ∧ (Lean def proved correct ∀ inputs, by the kernel).

The only un-proved link — "is the Lean def a faithful model of the Python?" — is checked
**mechanically and randomly** by the Hypothesis differential test, not by assertion.

## The gate (`./formal/gate.sh`)

1. **kernel build** — `lake build` re-checks every proof; an unfinished proof fails.
2. **axiom lint** (`gate/check_axioms.sh`) — `#print axioms` on each role theorem must list
   only `propext, Classical.choice, Quot.sound`; `sorryAx`/custom axioms/`native_decide`
   (`ofReduceBool`) fail.
3. **role manifest** (`Formal/Manifest.lean`) — compiles only if each required theorem exists.
4. **statement contracts** (`Formal/Contracts.lean`) — each role theorem is ascribed its exact
   strong statement; a WEAKENED theorem (same name) fails to elaborate → build RED. This is the
   mechanized theorem-statement review.
5. **differential + mutation** — Hypothesis checks Python ≡ Lean over random inputs; the mutation
   runner perturbs the Python and fails if any mutant survives (spec too weak / coverage gap).

What the gate is demonstrated to reject (see the acceptance commit): a `sorry`, `native_decide`,
a custom axiom, a missing/renamed role theorem, a WEAKENED theorem statement, and a surviving mutant.

## Run locally

```bash
curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y
uv sync --dev
./formal/gate.sh
```

## Coverage

| Component | Lean | Roles proved |
|---|---|---|
| `calculate_path` (`utils/pathfinding.py:44`) | `Formal/CalculatePath.lean` | validity, optimality (lower-bound + achieved), cost (length≤Manhattan, Chebyshev≤Manhattan), estimated_time |

Backfill of the remaining components: see the design doc
(`docs/superpowers/specs/2026-05-26-lean-formal-verification-design.md`). The retired
TLA+/PlusPy predecessor: `docs/postmortems/2026-05-26-tlaplus-pluspy-formal-verification.md`.
