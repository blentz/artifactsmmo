# Lean 4 Formal Verification of the AI Design

**Date:** 2026-05-26
**Status:** Approved direction (supersedes the TLA+/PlusPy POC — see `docs/postmortems/2026-05-26-tlaplus-pluspy-formal-verification.md`). This doc covers the architecture + the first build cycle (the foundation). Backfill of the remaining components and the proof-first workflow flip are later cycles.

## Goal

A **mechanical guardrail, more exacting than unit testing, that this AI author cannot game.** Every claim about the correctness of the AI's pure logic must be backed by a kernel-checked Lean 4 proof over **all valid inputs**, and a gate must mechanically reject the specific ways the author has been shown to cheat (vacuous theorems, faked/abstracted steps, hand-tables, model-vs-code drift).

End state: **proof-first development** — new AI-logic features are specified in Lean and proved *before* the Python implementation is written; the gate blocks any AI-logic function that lands without a proved Lean spec + passing differential test. We are currently **backfilling** proofs for the existing codebase; the workflow flip happens once backfill coverage is adequate.

## Why not the POC tool

PlusPy is a bounded-domain interpreter with no kernel: it can neither quantify over all inputs nor reject a vacuous/faked check. The author repeatedly shipped tautologies, hand-tables, and abstracted arithmetic that only human review caught. See the post-mortem. Lean 4 gives kernel-checked `∀`-proofs; the gate gives mechanical anti-gaming.

## Architecture

### 1. Lean package (`formal/`, a `lake` project)

Clean `formal/` directory (the TLA+ specs are removed; recoverable from history). Layout:

```
formal/
  lakefile.lean / lakefile.toml      # lake project
  lean-toolchain                     # pinned Lean 4 version
  Formal/
    <Component>.lean                 # per component: computable def(s) + theorems + proofs
    Manifest.lean                    # declares required theorem roles per component (gate reads this)
  oracle/                            # Lean executable: evaluates the proved defs on JSON inputs
  diff/                              # Python differential harness (Hypothesis) + mutation runner
  gate.sh / Makefile                 # the four-part gate entry point
  README.md                         # scope, soundness chain, how to run the gate
```

Per AI component: a **computable** Lean `def` mirroring the algorithm, `theorem`s stating the contract **∀ inputs** (no bounds), and machine-checked proofs. The defs are the same objects the theorems are about AND the same objects the differential test executes — so what is proved is what is tested against Python.

### 2. The four-part gate (CI, blocks merge)

Each part plugs a hole the author has exploited:

- **(a) Kernel-checked build.** `lake build` re-checks every proof in Lean's trusted kernel. An incomplete proof fails the build.
- **(b) No-escape-hatch lint.** For every theorem in the manifest, `#print axioms <thm>` must list only the standard trusted axioms (`propext`, `Classical.choice`, `Quot.sound`). Any `sorryAx`, custom `axiom`, `native_decide`, or `unsafe`/`@[implemented_by]` in proof scope fails the gate. (Catches `sorry` even if laundered through a lemma.)
- **(c) Non-vacuity gate (the anti-cheat core).**
  - **Mutation testing of the Python implementation.** A runner applies a catalogue of mutations to the target Python function; for each surviving mutant (one that no theorem-backed differential check kills), the gate **fails**. A vacuous theorem cannot kill mutants, so weak statements are mechanically rejected.
  - **Satisfiability witnesses.** Every theorem with hypotheses ships an `example` constructing inputs that satisfy them, so `False → P` vacuous theorems are rejected.
  - **Role manifest.** `Manifest.lean` declares, per component, the required theorem *roles* (e.g. `refinement`, `optimality`, `termination`, `monotonicity`). The gate fails if a declared role has no corresponding proved theorem. Coverage is explicit and reviewed.
- **(d) Differential fidelity.** The Lean defs are compiled to an `oracle` executable that reads JSON inputs and emits outputs. A Hypothesis property-based harness generates thousands of random valid inputs, runs both the real Python function and the Lean oracle, and asserts agreement. This bridges model↔code.

### Soundness chain

> Python function correct ⇐ (Python ≡ Lean def, by the differential test) ∧ (Lean def proved correct ∀ inputs, by the kernel).

The single irreducible trust boundary — "is the Lean def a faithful model of the Python?" — is answered **mechanically and randomly** by (d), never by author assertion. Mutation testing (c) additionally ensures the proved theorems have teeth against that very boundary.

### Decisions (resolved)

- **Repo home:** repurpose `formal/` (now empty of TLA+) as the Lean project root.
- **Mutation scope:** mutate the **Python implementation** — this exercises theorem teeth *and* model↔code fidelity together (the stronger, more honest check), rather than mutating the Lean def (teeth only).

## What is explicitly disallowed

`sorry`/`admit`, custom `axiom`s, `native_decide`, abstracted "verified by inspection" arithmetic, hand-tables substituting for properties, bounded-domain claims presented as proofs. If a step can't be discharged in the kernel, the build is red. If the theorems can't kill mutants, the gate is red.

## First build cycle — the foundation

The gate is the load-bearing novelty; everything trusts it. The first spec→plan→build cycle delivers it end-to-end on one reference component:

1. **`lake` scaffold** — `formal/` Lean project, pinned toolchain, `Manifest.lean`, README with the soundness chain.
2. **One fully-proven component through the entire gate** — `calculate_path` (pathfinding): optimality + validity proved `∀` coordinates (arithmetic + induction — tractable, exercises every gate part). Theorems: a produced path is a legal king-walk; its length equals the Chebyshev optimum (no shorter legal path exists); reported cost equals Manhattan distance.
3. **The four-part gate wired into CI** — `lake build`, `#print axioms` lint, mutation runner against `calculate_path`, differential PBT (Lean oracle vs. Python `calculate_path`).
4. **README** documenting scope, the soundness chain, and how to run the gate locally.

Acceptance for the foundation: the gate runs green on `calculate_path`; and a deliberately weakened theorem OR a `sorry` OR a surviving mutant each turns the gate red (demonstrated).

## Later cycles (out of scope for the foundation plan)

- **Backfill** the remaining 13 components, arithmetic-tractable first (`predict_win` *exact* documented formula incl. `_round_half_up`/crit via exact integer arithmetic; `inventory_caps`; `task_batch`), then the hard fixpoint/graph proofs (`recipe_closure` least-fixpoint; `prerequisite_graph`; `strategy_traversal`). Each: Lean def + theorems + proofs + manifest entry + mutation + differential test, through the gate.
- **Flip to proof-first** — once backfill coverage is adequate, document the proof-first workflow in `CLAUDE.md`/`AGENTS.md`; the gate requires every new AI-logic function to land with a proved Lean spec + passing differential test before merge.

## Honest risks

- Some proofs (graph least-fixpoints, the stuck-detector windowing) are genuinely hard and may take real effort or be scoped down with the limitation documented — never `sorry`-papered.
- Lean toolchain + `lake` add a build dependency; CI must install it. The gate must run in the project's CI environment.
- The differential bridge requires the Lean def to be `computable` (no noncomputable `Classical` in the executable path) — modeling must stay constructive where it must execute.
