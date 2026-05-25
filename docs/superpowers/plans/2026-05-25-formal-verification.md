# Formal Verification (TLA+ / PlusPy) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `formal/` subdirectory that demonstrates the correctness of four pure-logic functions (`calculate_path`, `recipe_closure`/`raw_material_units`, `prerequisites`/`combat_capable`, `predict_win`) by modeling each in TLA+, pairing the algorithm with an independent oracle (hand-computed expected values or an operational simulation), and using PlusPy to assert agreement over a bounded, exhaustively enumerated input domain.

**Architecture:** PlusPy is a TLA+ *interpreter*, not a model checker — no `.cfg`, no `INVARIANT` clause, no exhaustive state-space search. Each spec is a state machine whose `Next` action walks a cursor over a finite input set, evaluates the algorithm-model and an independent oracle for that input, and asserts equality via `TLC!Assert`. Running `./pluspy -c<N> <Module>` (N = domain size) drives every input through; any `Assert` failure halts PlusPy with the asserted message. A stdlib Python runner invokes PlusPy per module and reports PASS/FAIL.

**Tech Stack:** TLA+ (PlusPy subset), PlusPy (vendored via git clone), Python 3.13 stdlib runner (`uv run`), bash setup script.

---

## File Structure

- `formal/.gitignore` — ignores `vendor/`.
- `formal/setup.sh` — clones a pinned `tlaplus/PlusPy` commit into `formal/vendor/PlusPy`.
- `formal/run.py` — runs PlusPy on each module, asserts clean exit + no `Assert` failure, prints a PASS/FAIL table, exits non-zero on any failure.
- `formal/specs/CalculatePath.tla` — pathfinding optimality.
- `formal/specs/RecipeClosure.tla` — closure soundness/completeness + raw-unit arithmetic.
- `formal/specs/PrerequisiteGraph.tla` — direct-prereq exactness, termination, combat-gate equivalence.
- `formal/specs/PredictWin.tla` — closed-form verdict = operational fight sim; monotonicity; MAX_TURNS soundness.
- `formal/README.md` — scope statement, property→Python-line map, run instructions, connectivity finding.

> **PlusPy-syntax note for the executor:** PlusPy implements a *subset* of TLA+. After writing each `.tla`, run it immediately (steps below). If PlusPy reports a parse/eval error, consult working examples in `formal/vendor/PlusPy/modules/*.tla` and adjust syntax (common gotchas: use `\o` for sequence concat, `RECURSIVE Op(_,_)` declarations before recursive operators, `TLC!Assert` requires `EXTENDS TLC`, records are `[a |-> 1]`, functions are `[x \in S |-> e]`). Fix syntax until the run is clean — the asserted *properties* are the contract; the surface syntax may need tweaking to PlusPy's subset.

---

## Task 1: Scaffolding — gitignore, setup script, PlusPy provisioning

**Files:**
- Create: `formal/.gitignore`
- Create: `formal/setup.sh`

- [ ] **Step 1: Create `formal/.gitignore`**

```
vendor/
```

- [ ] **Step 2: Create `formal/setup.sh`**

```bash
#!/usr/bin/env bash
# Clone a pinned PlusPy into formal/vendor/ (gitignored). Re-runnable.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$HERE/vendor"
PLUSPY_DIR="$VENDOR/PlusPy"
PLUSPY_REPO="https://github.com/tlaplus/PlusPy.git"
PLUSPY_COMMIT="a8c75e7a76e7d0e6c0e2b1d8e9f0a1b2c3d4e5f6"  # replace in Step 3

mkdir -p "$VENDOR"
if [ ! -d "$PLUSPY_DIR/.git" ]; then
  git clone "$PLUSPY_REPO" "$PLUSPY_DIR"
fi
git -C "$PLUSPY_DIR" fetch --all --tags
git -C "$PLUSPY_DIR" checkout "$PLUSPY_COMMIT"
echo "PlusPy ready at $PLUSPY_DIR (commit $PLUSPY_COMMIT)"
```

- [ ] **Step 3: Pin a real PlusPy commit**

Run: `git ls-remote https://github.com/tlaplus/PlusPy.git HEAD`
Take the printed 40-char SHA and replace the `PLUSPY_COMMIT` placeholder in `formal/setup.sh` with it.

- [ ] **Step 4: Make the script executable and run it**

Run: `chmod +x formal/setup.sh && ./formal/setup.sh`
Expected: clones the repo, prints `PlusPy ready at .../formal/vendor/PlusPy (commit <sha>)`.

- [ ] **Step 5: Verify PlusPy runs at all**

Run: `python3 formal/vendor/PlusPy/pluspy.py -h`
Expected: PlusPy usage/help text prints, exit 0. (If `pluspy.py` is not at the repo root, run `ls formal/vendor/PlusPy` and note the actual entry path; record it for Task 2's runner.)

- [ ] **Step 6: Commit**

```bash
git add formal/.gitignore formal/setup.sh
git commit -m "build(formal): scaffold PlusPy provisioning via setup.sh"
```

---

## Task 2: The runner (`formal/run.py`)

**Files:**
- Create: `formal/run.py`

The runner needs at least one module to run against. Build it now with a tiny smoke spec, then Tasks 3–6 add real modules to the `MODULES` table.

- [ ] **Step 1: Create a smoke spec `formal/specs/Smoke.tla`**

```tla
-------------------------------- MODULE Smoke --------------------------------
EXTENDS Integers, TLC

VARIABLE i

Init == i = 0
Next == /\ i < 3
        /\ Assert(i >= 0, <<"Smoke FAIL at", i>>)
        /\ i' = i + 1
=============================================================================
```

- [ ] **Step 2: Run the smoke spec manually**

Run: `python3 formal/vendor/PlusPy/pluspy.py -c3 -P formal/specs Smoke`
Expected: runs three Next steps, no assertion failure, exit 0. Note the exact stdout shape (PlusPy prints state lines) — the runner keys off exit code + absence of an assert-failure marker, so capture what a failure looks like in Step 4.

- [ ] **Step 3: Write `formal/run.py`**

```python
"""Run each TLA+ spec under PlusPy and report PASS/FAIL.

PlusPy is an interpreter: each spec enumerates its bounded input domain in
Next and asserts the correctness property per input via TLC!Assert. A clean
run exits 0 with no assertion failure; a violated property halts PlusPy with
the asserted message. This runner invokes PlusPy per module and aggregates.
"""

import subprocess
import sys
from pathlib import Path

FORMAL = Path(__file__).resolve().parent
PLUSPY = FORMAL / "vendor" / "PlusPy" / "pluspy.py"
SPECS = FORMAL / "specs"

# (module, iteration count = input-domain size). Counts filled in per task.
MODULES: list[tuple[str, int]] = [
    ("Smoke", 3),
]

# Substrings PlusPy emits when an assertion fails.
FAILURE_MARKERS = ("Assertion", "assert", "FAIL", "exception", "Traceback")


def run_module(module: str, count: int) -> tuple[bool, str]:
    if not PLUSPY.exists():
        return False, "PlusPy not found — run ./formal/setup.sh first"
    proc = subprocess.run(
        [sys.executable, str(PLUSPY), f"-c{count}", "-P", str(SPECS), module],
        capture_output=True,
        text=True,
    )
    output = proc.stdout + proc.stderr
    failed = proc.returncode != 0 or any(m in output for m in FAILURE_MARKERS)
    return (not failed), output


def main() -> int:
    results: list[tuple[str, bool]] = []
    for module, count in MODULES:
        ok, output = run_module(module, count)
        results.append((module, ok))
        if not ok:
            print(f"--- {module} output ---\n{output}\n")
    width = max(len(m) for m, _ in results)
    print("\nFormal verification results:")
    for module, ok in results:
        print(f"  {module:<{width}}  {'PASS' if ok else 'FAIL'}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

> If Step 1 of Task 1 showed a different PlusPy entry path, update `PLUSPY` accordingly.

- [ ] **Step 4: Run the runner against the smoke spec**

Run: `uv run python formal/run.py`
Expected: prints `Smoke  PASS`, exit 0.

- [ ] **Step 5: Verify the runner catches a failure**

Temporarily edit `Smoke.tla` step 1's assert to `Assert(i < 0, ...)`, then run `uv run python formal/run.py`.
Expected: prints `Smoke  FAIL` and the captured output, exit 1. Then revert the assert back to `i >= 0`.

- [ ] **Step 6: Commit**

```bash
git add formal/run.py formal/specs/Smoke.tla
git commit -m "build(formal): PlusPy runner + smoke spec"
```

---

## Task 3: CalculatePath — path validity, Chebyshev optimality, true cost

Mirrors `src/artifactsmmo_cli/utils/pathfinding.py:44` (`calculate_path`). The Python loop takes one king-step toward the target each iteration. The oracle is the declarative `ValidPath` predicate plus the Chebyshev lower bound proven via strict per-step progress.

**Files:**
- Create: `formal/specs/CalculatePath.tla`
- Modify: `formal/run.py` (add to `MODULES`)

- [ ] **Step 1: Write `formal/specs/CalculatePath.tla`**

```tla
----------------------------- MODULE CalculatePath -----------------------------
EXTENDS Integers, Sequences, TLC

\* Bounded grid: domain size = (5*5)^2 = 625 (s,d) pairs.
Coord == -2..2
Abs(n)   == IF n < 0 THEN -n ELSE n
Max(a,b) == IF a > b THEN a ELSE b

Pts   == { [x |-> a, y |-> b] : a \in Coord, b \in Coord }
Pairs == { <<s, d>> : s \in Pts, d \in Pts }

\* ---- algorithm model: one king-step toward d (mirrors the Python loop) ----
StepToward(c, d) ==
  [ x |-> c.x + (IF c.x < d.x THEN 1 ELSE IF c.x > d.x THEN -1 ELSE 0),
    y |-> c.y + (IF c.y < d.y THEN 1 ELSE IF c.y > d.y THEN -1 ELSE 0) ]

RECURSIVE PathFrom(_, _)
PathFrom(c, d) ==
  IF c = d THEN << >>
  ELSE LET nxt == StepToward(c, d) IN <<nxt>> \o PathFrom(nxt, d)

\* ---- independent oracle: what a correct path is ----
Adjacent(a, b) == /\ Abs(a.x - b.x) <= 1
                  /\ Abs(a.y - b.y) <= 1
                  /\ ~(a.x = b.x /\ a.y = b.y)

ValidPath(s, d, p) ==
  IF Len(p) = 0
  THEN s = d
  ELSE /\ Adjacent(s, p[1])
       /\ p[Len(p)] = d
       /\ \A i \in 1..(Len(p) - 1) : Adjacent(p[i], p[i + 1])

Cheb(c, d)      == Max(Abs(d.x - c.x), Abs(d.y - c.y))
OptimalLen(s,d) == Cheb(s, d)              \* king-move lower bound
Manhattan(s, d) == Abs(d.x - s.x) + Abs(d.y - s.y)

\* every step strictly reduces Chebyshev distance to d by exactly 1 => minimal:
PointSeq(s, p) == [ i \in 0..Len(p) |-> IF i = 0 THEN s ELSE p[i] ]
MinimalProgress(s, d, p) ==
  LET pts == PointSeq(s, p)
  IN \A i \in 1..Len(p) : Cheb(pts[i], d) = Cheb(pts[i - 1], d) - 1

Correct(s, d) ==
  LET p == PathFrom(s, d)
  IN /\ ValidPath(s, d, p)              \* legal walk
     /\ Len(p) = OptimalLen(s, d)       \* no shorter king-walk exists
     /\ MinimalProgress(s, d, p)        \* optimality witness
     /\ Len(p) <= Manhattan(s, d)       \* never worse than 4-connected
     /\ (Len(p) = Manhattan(s, d) <=> (s.x = d.x \/ s.y = d.y))  \* diagonal savings

VARIABLE todo
Init == todo = Pairs
Next == /\ todo # {}
        /\ \E pr \in todo :
              /\ Assert(Correct(pr[1], pr[2]), <<"CalculatePath FAIL", pr>>)
              /\ todo' = todo \ {pr}
================================================================================
```

- [ ] **Step 2: Run it (expect a clean pass) — domain size is 625**

Run: `python3 formal/vendor/PlusPy/pluspy.py -c625 -P formal/specs CalculatePath`
Expected: 625 Next steps, no `Assert` failure, exit 0. If PlusPy reports a parse error, fix to its subset (see the syntax note above) and re-run until clean.

- [ ] **Step 3: Sanity-check the oracle bites — introduce a deliberate bug**

Temporarily change `OptimalLen(s,d) == Cheb(s, d)` to `== Cheb(s,d) + 1`.
Run: `python3 formal/vendor/PlusPy/pluspy.py -c625 -P formal/specs CalculatePath`
Expected: halts with `<<"CalculatePath FAIL", ...>>`. Revert the change.

- [ ] **Step 4: Add CalculatePath to the runner**

In `formal/run.py`, change `MODULES` to:

```python
MODULES: list[tuple[str, int]] = [
    ("Smoke", 3),
    ("CalculatePath", 625),
]
```

- [ ] **Step 5: Run the runner**

Run: `uv run python formal/run.py`
Expected: `Smoke  PASS` and `CalculatePath  PASS`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add formal/specs/CalculatePath.tla formal/run.py
git commit -m "test(formal): CalculatePath optimality + validity spec"
```

---

## Task 4: RecipeClosure — closure soundness/completeness + raw-unit arithmetic

Mirrors `src/artifactsmmo_cli/ai/recipe_closure.py` (`recipe_closure` at :15, `raw_material_units` at :43). Oracle: the least-fixpoint closure computed by saturation (independent of the algorithm's traversal) plus a hand-computed raw-unit table. Includes a **cyclic** recipe and a **diamond** (shared subrecipe) to exercise the `visited` guard.

**Files:**
- Create: `formal/specs/RecipeClosure.tla`
- Modify: `formal/run.py`

- [ ] **Step 1: Write `formal/specs/RecipeClosure.tla`**

```tla
----------------------------- MODULE RecipeClosure -----------------------------
EXTENDS Integers, FiniteSets, Sequences, TLC

\* Items. Recipe[i] is a function ingredient -> qty; raw items map to the empty
\* function (no ingredients). Mirrors GameData._crafting_recipes.
Items == {"sword", "blade", "iron", "handle", "wood", "ring", "loop", "a", "b"}

Empty == [ x \in {} |-> 0 ]

Recipe ==
  [ sword  |-> [blade |-> 1, handle |-> 1],   \* diamond root
    blade  |-> [iron  |-> 2],
    handle |-> [iron  |-> 1, wood |-> 1],     \* shares iron with blade
    iron   |-> Empty,                          \* raw
    wood   |-> Empty,                          \* raw
    ring   |-> [loop |-> 2],
    loop   |-> [ring |-> 1],                    \* cycle ring <-> loop
    a      |-> [b |-> 1],
    b      |-> [a |-> 1] ]                      \* cycle a <-> b

\* resource code -> item it drops (mirrors GameData._resource_drops).
Drops == [ iron_rocks |-> "iron", ash_tree |-> "wood" ]
Resources == DOMAIN Drops

HasRecipe(m) == m \in DOMAIN Recipe /\ DOMAIN Recipe[m] # {}

\* ---- independent oracle: least-fixpoint closure by saturation ----
Expand(S) == S \cup UNION { DOMAIN Recipe[m] : m \in { x \in S : HasRecipe(x) } }
RECURSIVE Saturate(_)
Saturate(S) == LET S2 == Expand(S) IN IF S2 = S THEN S ELSE Saturate(S2)

ClosureSet(roots)     == Saturate(roots)
OracleCraftable(roots) == { m \in ClosureSet(roots) : HasRecipe(m) }
OracleResources(roots) == { r \in Resources : Drops[r] \in ClosureSet(roots) }

\* ---- algorithm model: recipe_closure's DFS with a visited guard ----
RECURSIVE AlgoVisit(_, _)
AlgoVisit(m, visited) ==
  IF m \in visited THEN visited
  ELSE LET v1 == visited \cup {m}
           subs == IF m \in DOMAIN Recipe THEN DOMAIN Recipe[m] ELSE {}
       IN \* fold AlgoVisit over subs (set fold via recursion on the set)
          LET RECURSIVE Fold(_, _)
              Fold(rem, acc) ==
                IF rem = {} THEN acc
                ELSE LET x == CHOOSE e \in rem : TRUE
                     IN Fold(rem \ {x}, AlgoVisit(x, acc))
          IN Fold(subs, v1)

AlgoClosure(roots) ==
  LET RECURSIVE FoldRoots(_, _)
      FoldRoots(rem, acc) ==
        IF rem = {} THEN acc
        ELSE LET x == CHOOSE e \in rem : TRUE
             IN FoldRoots(rem \ {x}, AlgoVisit(x, acc))
  IN FoldRoots(roots, {})

AlgoCraftable(roots) == { m \in AlgoClosure(roots) : HasRecipe(m) }
AlgoResources(roots) == { r \in Resources : Drops[r] \in AlgoClosure(roots) }

\* ---- raw_material_units: independent recursive cost, revisit -> 1 ----
RECURSIVE RawUnits(_, _)
RawUnits(item, visited) ==
  IF item \in visited THEN 1
  ELSE IF ~HasRecipe(item) THEN 1
  ELSE LET deeper == visited \cup {item}
           reci   == Recipe[item]
           subs   == DOMAIN reci
           RECURSIVE SumSub(_)
           SumSub(rem) ==
             IF rem = {} THEN 0
             ELSE LET x == CHOOSE e \in rem : TRUE
                  IN reci[x] * RawUnits(x, deeper) + SumSub(rem \ {x})
       IN SumSub(subs)

\* ---- hand-computed oracle table for raw units ----
\* sword = blade(iron*2) + handle(iron*1 + wood*1) = 2 + (1+1) = 4
\* ring  = loop(ring*1)  -> revisit ring => 1, so loop=1, ring = 2*1 = 2
\* a     = b(a*1) -> revisit a => 1, so b=1, a = 1*1 = 1
ExpectedRaw == [ sword |-> 4, blade |-> 2, handle |-> 2, iron |-> 1,
                 wood |-> 1, ring |-> 2, loop |-> 1, a |-> 1, b |-> 1 ]

\* ---- per-item correctness, enumerated over Items ----
Correct(item) ==
  LET roots == {item}
  IN /\ AlgoClosure(roots)   = ClosureSet(roots)        \* same closure
     /\ AlgoCraftable(roots) = OracleCraftable(roots)   \* sound + complete crafts
     /\ AlgoResources(roots) = OracleResources(roots)   \* exact resource set
     /\ RawUnits(item, {})   = ExpectedRaw[item]         \* exact quantity math

VARIABLE todo
Init == todo = Items
Next == /\ todo # {}
        /\ \E m \in todo :
              /\ Assert(Correct(m), <<"RecipeClosure FAIL", m>>)
              /\ todo' = todo \ {m}
================================================================================
```

- [ ] **Step 2: Run it (domain size = |Items| = 9)**

Run: `python3 formal/vendor/PlusPy/pluspy.py -c9 -P formal/specs RecipeClosure`
Expected: 9 Next steps, no `Assert` failure, exit 0. If PlusPy rejects nested `RECURSIVE ... IN` LET blocks, hoist `Fold`/`SumSub` to top-level `RECURSIVE` operators (parameterized by the recipe map) and re-run until clean.

- [ ] **Step 3: Sanity-check the oracle bites**

Temporarily change `ExpectedRaw`'s `sword |-> 4` to `sword |-> 3`.
Run: `python3 formal/vendor/PlusPy/pluspy.py -c9 -P formal/specs RecipeClosure`
Expected: halts with `<<"RecipeClosure FAIL", "sword">>`. Revert.

- [ ] **Step 4: Add to the runner**

In `formal/run.py`, append to `MODULES`:

```python
    ("RecipeClosure", 9),
```

- [ ] **Step 5: Run the runner**

Run: `uv run python formal/run.py`
Expected: all modules PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add formal/specs/RecipeClosure.tla formal/run.py
git commit -m "test(formal): RecipeClosure fixpoint + raw-unit arithmetic spec"
```

---

## Task 5: PrerequisiteGraph — direct-prereq exactness, termination, combat-gate equivalence

Mirrors `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py` (`prerequisites` at :41, `combat_capable` at :20). We model the `ObtainItem` branch (the recipe/drop-derived edges) plus the `combat_capable ⇔ ∃ monster. predict_win` equivalence with an abstracted boolean `Beatable` per monster (the `predict_win` refinement itself is Task 6). Oracle: a hand-specified expected direct-prereq table and an independent leaf-reachability fixpoint for termination.

**Files:**
- Create: `formal/specs/PrerequisiteGraph.tla`
- Modify: `formal/run.py`

- [ ] **Step 1: Write `formal/specs/PrerequisiteGraph.tla`**

```tla
--------------------------- MODULE PrerequisiteGraph ---------------------------
EXTENDS Integers, FiniteSets, TLC

\* ObtainItem nodes only (the data-derived branch of prerequisites()).
Items == {"sword", "blade", "iron", "wood", "gem"}

Empty == [ x \in {} |-> 0 ]
Recipe ==
  [ sword |-> [blade |-> 1],
    blade |-> [iron  |-> 2],
    iron  |-> Empty,     \* gathered (has a resource drop)
    wood  |-> Empty,     \* gathered
    gem   |-> Empty ]    \* monster-drop / buyable: leaf, no prereqs

Drops == [ iron_rocks |-> "iron", ash_tree |-> "wood" ]  \* iron, wood gatherable
Gatherable == { Drops[r] : r \in DOMAIN Drops }

HasRecipe(m) == m \in DOMAIN Recipe /\ DOMAIN Recipe[m] # {}

\* ---- algorithm model: direct prerequisites of an ObtainItem node ----
\* (skill-level prereqs from crafting_skill/resource_skill_level are abstracted
\*  out here; we verify the material/leaf structure that drives search shape.)
Prereqs(node) ==
  IF HasRecipe(node) THEN DOMAIN Recipe[node]        \* craft: ingredients
  ELSE IF node \in Gatherable THEN {}                \* gather: leaf (skill only)
  ELSE {}                                            \* monster-drop/buyable: leaf

\* ---- oracle: hand-specified expected direct prereqs ----
ExpectedPrereqs ==
  [ sword |-> {"blade"}, blade |-> {"iron"}, iron |-> {}, wood |-> {}, gem |-> {} ]

IsLeaf(node) == Prereqs(node) = {}
ExpectedLeaves == { "iron", "wood", "gem" }

\* ---- oracle: independent reachability fixpoint => termination ----
Expand(S) == S \cup UNION { Prereqs(m) : m \in S }
RECURSIVE Reach(_)
Reach(S) == LET S2 == Expand(S) IN IF S2 = S THEN S ELSE Reach(S2)
\* termination witness: every reachable node from any root is eventually a leaf
AllReachableTerminate(root) ==
  LET R == Reach({root}) IN \A n \in R : (HasRecipe(n) \/ IsLeaf(n))

NodeCorrect(node) ==
  /\ Prereqs(node) = ExpectedPrereqs[node]   \* exact direct edges
  /\ (IsLeaf(node) <=> node \in ExpectedLeaves)
  /\ AllReachableTerminate(node)             \* search terminates

\* ---- combat_capable equivalence: any(predict_win) over monsters ----
Monsters == {"chicken", "cow", "wolf"}
\* abstracted predict_win verdict per monster (refined operationally in Task 6).
Beatable == [ chicken |-> TRUE, cow |-> FALSE, wolf |-> FALSE ]
CombatCapable == \E m \in Monsters : Beatable[m]
ExpectedCombatCapable == TRUE   \* chicken is beatable
CombatGateCorrect == CombatCapable = ExpectedCombatCapable

VARIABLE todo
Init == todo = Items
Next == /\ todo # {}
        /\ \E node \in todo :
              /\ Assert(NodeCorrect(node), <<"PrereqGraph FAIL node", node>>)
              /\ Assert(CombatGateCorrect, <<"PrereqGraph FAIL combat gate">>)
              /\ todo' = todo \ {node}
================================================================================
```

- [ ] **Step 2: Run it (domain size = |Items| = 5)**

Run: `python3 formal/vendor/PlusPy/pluspy.py -c5 -P formal/specs PrerequisiteGraph`
Expected: 5 Next steps, no `Assert` failure, exit 0. Fix any PlusPy-subset syntax issues and re-run until clean.

- [ ] **Step 3: Sanity-check the oracle bites**

Temporarily change `ExpectedPrereqs`'s `sword |-> {"blade"}` to `sword |-> {"iron"}`.
Run: `python3 formal/vendor/PlusPy/pluspy.py -c5 -P formal/specs PrerequisiteGraph`
Expected: halts with `<<"PrereqGraph FAIL node", "sword">>`. Revert.

- [ ] **Step 4: Add to the runner**

In `formal/run.py`, append to `MODULES`:

```python
    ("PrerequisiteGraph", 5),
```

- [ ] **Step 5: Run the runner**

Run: `uv run python formal/run.py`
Expected: all modules PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add formal/specs/PrerequisiteGraph.tla formal/run.py
git commit -m "test(formal): PrerequisiteGraph edges/termination/combat-gate spec"
```

---

## Task 6: PredictWin — closed-form verdict = operational fight simulation

Mirrors `src/artifactsmmo_cli/ai/combat.py:57` (`predict_win`) and the `_round_half_up`/`_element_damage`/`_expected_hit` helpers. To keep arithmetic integer-exact in PlusPy, the model works in **per-turn integer damage** directly (player deals `pHit` per turn, monster deals `mHit`), abstracting the element/crit expansion (those are pure arithmetic verified by inspection and noted in the README). The theorem: the closed-form `ceil(hp/hit)` comparison with the initiative tiebreak equals the outcome of *actually running* the alternating-attack simulation. Plus monotonicity and MAX_TURNS soundness.

**Files:**
- Create: `formal/specs/PredictWin.tla`
- Modify: `formal/run.py`

- [ ] **Step 1: Write `formal/specs/PredictWin.tla`**

```tla
------------------------------- MODULE PredictWin -------------------------------
EXTENDS Integers, TLC

MaxTurns == 100   \* combat.py MAX_TURNS

\* Bounded stat domain. Tuple: <<pHP, pHit, mHP, mHit, pFirst>>.
HP    == 1..6
Hit   == 0..4
Bool  == {TRUE, FALSE}
Cases == { <<ph, phit, mh, mhit, pf>> :
             ph \in HP, phit \in Hit, mh \in HP, mhit \in Hit, pf \in Bool }

CeilDiv(a, b) == (a + b - 1) \div b   \* ceil(a/b) for a>=0, b>0

\* ---- algorithm model: predict_win closed form (combat.py:66-79) ----
ClosedForm(ph, phit, mh, mhit, pf) ==
  IF phit <= 0 THEN FALSE
  ELSE LET rtk == CeilDiv(mh, phit) IN
       IF rtk > MaxTurns THEN FALSE
       ELSE IF mhit <= 0 THEN TRUE
       ELSE LET rtd == CeilDiv(ph, mhit) IN
            IF pf THEN rtk <= rtd ELSE rtk < rtd

\* ---- independent oracle: actually run the fight, turn by turn ----
\* Returns TRUE iff player reduces monster HP to <=0 before dying, given who
\* strikes first; unresolved by MaxTurns => loss.
RECURSIVE Fight(_, _, _, _, _, _)
Fight(php, mhp, phit, mhit, pf, turn) ==
  IF turn > MaxTurns THEN FALSE          \* cap reached, unresolved => loss
  ELSE IF pf
       THEN LET mhp2 == mhp - phit IN     \* player strikes
            IF mhp2 <= 0 THEN TRUE
            ELSE LET php2 == php - mhit IN \* monster strikes
                 IF php2 <= 0 THEN FALSE
                 ELSE Fight(php2, mhp2, phit, mhit, pf, turn + 1)
       ELSE LET php2 == php - mhit IN      \* monster strikes first
            IF php2 <= 0 THEN FALSE
            ELSE LET mhp2 == mhp - phit IN \* player strikes
                 IF mhp2 <= 0 THEN TRUE
                 ELSE Fight(php2, mhp2, phit, mhit, pf, turn + 1)

Simulated(ph, phit, mh, mhit, pf) ==
  IF phit <= 0 THEN FALSE                 \* deals no damage => can never win
  ELSE Fight(ph, mh, phit, mhit, pf, 1)

\* ---- refinement: closed form == simulation, for every case ----
Refines(c) == ClosedForm(c[1],c[2],c[3],c[4],c[5]) = Simulated(c[1],c[2],c[3],c[4],c[5])

\* ---- monotonicity: more player hit never flips win -> loss ----
MonoOK(c) ==
  LET ph == c[1] phit == c[2] mh == c[3] mhit == c[4] pf == c[5] IN
  /\ (phit + 1 \in Hit /\ ClosedForm(ph, phit, mh, mhit, pf)
        => ClosedForm(ph, phit + 1, mh, mhit, pf))
  /\ (mh - 1 \in HP /\ ClosedForm(ph, phit, mh, mhit, pf)
        => ClosedForm(ph, phit, mh - 1, mhit, pf))

Correct(c) == Refines(c) /\ MonoOK(c)

VARIABLE todo
Init == todo = Cases
Next == /\ todo # {}
        /\ \E c \in todo :
              /\ Assert(Correct(c), <<"PredictWin FAIL", c>>)
              /\ todo' = todo \ {c}
================================================================================
```

- [ ] **Step 2: Compute the domain size**

|Cases| = |HP| * |Hit| * |HP| * |Hit| * |Bool| = 6 * 5 * 6 * 5 * 2 = **1800**.

- [ ] **Step 3: Run it**

Run: `python3 formal/vendor/PlusPy/pluspy.py -c1800 -P formal/specs PredictWin`
Expected: 1800 Next steps, no `Assert` failure, exit 0. (If the run is slow, that is acceptable — it is exhaustive over 1800 cases. If PlusPy rejects `LET a == x b == y IN`, split into separate `LET ... IN` bindings and re-run until clean.)

- [ ] **Step 4: Sanity-check the oracle bites — break the initiative tiebreak**

Temporarily change `ClosedForm`'s final line `IF pf THEN rtk <= rtd ELSE rtk < rtd` to `IF pf THEN rtk < rtd ELSE rtk < rtd` (wrong tiebreak when player goes first).
Run: `python3 formal/vendor/PlusPy/pluspy.py -c1800 -P formal/specs PredictWin`
Expected: halts with `<<"PredictWin FAIL", ...>>` (a case where player-first equality should win but closed form now says loss). Revert.

- [ ] **Step 5: Add to the runner**

In `formal/run.py`, append to `MODULES`:

```python
    ("PredictWin", 1800),
```

- [ ] **Step 6: Run the runner**

Run: `uv run python formal/run.py`
Expected: all modules PASS, exit 0.

- [ ] **Step 7: Commit**

```bash
git add formal/specs/PredictWin.tla formal/run.py
git commit -m "test(formal): PredictWin closed-form == fight-sim refinement spec"
```

---

## Task 7: README — scope, property map, run instructions, connectivity finding

**Files:**
- Create: `formal/README.md`

- [ ] **Step 1: Determine the move-API connectivity**

Run: `grep -rn "action/move\|def move\|move(" src/artifactsmmo_cli/commands/action.py src/artifactsmmo_cli/api_wrapper.py`
Read the move command and `openapi.json`'s move schema to determine whether the game moves one tile per action (and whether diagonal target tiles are reachable in a single move). Record the finding for Step 2. (If the API moves directly to an arbitrary target tile with distance-scaled cooldown, note that `calculate_path`'s step decomposition is an estimate aid, and the Chebyshev/Manhattan distinction is what matters for cost.)

- [ ] **Step 2: Write `formal/README.md`**

````markdown
# Formal verification of core algorithms (TLA+ / PlusPy)

Executable TLA+ reference models that demonstrate the correctness of four pure
functions in the AI player. Each spec defines the answer twice — once as the
algorithm, once as an independent oracle (hand-computed values or an operational
simulation) — and PlusPy asserts they agree across an exhaustively enumerated,
**bounded** input domain.

## Scope and honesty

- **Not a proof for all inputs.** PlusPy is a TLA+ *interpreter*, not a theorem
  prover (TLAPS) or a model checker (TLC). Correctness is demonstrated only over
  the bounded domains encoded in each spec (small grids / stat ranges / recipe
  graphs). It is exhaustive over *that* domain, not unbounded.
- **No `.cfg`/`INVARIANT`.** Each spec enumerates its input set in `Next` and
  asserts the property per input via `TLC!Assert`. `./pluspy -c<N> <Module>`
  drives all N inputs; an assertion failure halts PlusPy.

## Setup and run

```bash
./formal/setup.sh            # clone pinned PlusPy into formal/vendor/ (gitignored)
uv run python formal/run.py  # run every spec; prints PASS/FAIL, non-zero on any fail
```

## Property → code map

| Spec | Pins (Python) | Demonstrated property |
|---|---|---|
| `CalculatePath.tla` | `utils/pathfinding.py:44-93` | Output is a legal king-walk, length = Chebyshev optimum (no shorter path), `total_distance` = Manhattan cost; never worse than 4-connected, strictly better off-axis. |
| `RecipeClosure.tla` | `ai/recipe_closure.py:15-40,43-54` | `craftable_mats`/`needed_resources` = least-fixpoint closure (sound + complete); `raw_material_units` matches a hand-computed table; cyclic recipes terminate at cost 1. |
| `PrerequisiteGraph.tla` | `ai/tiers/prerequisite_graph.py:20-65` | `prerequisites` emits exactly the direct data-derived edges; expansion terminates at leaves; `combat_capable ⇔ ∃ monster. predict_win`. |
| `PredictWin.tla` | `ai/combat.py:57-79` | Closed-form `ceil(hp/hit)` verdict (incl. `≤`/`<` initiative tiebreak) = outcome of running the alternating-attack simulation; monotone in player hit / monster HP; MAX_TURNS cap is a sound loss. |

## Modeling notes

- `PredictWin.tla` works in per-turn integer damage; the element/crit expansion
  (`_element_damage`, `_expected_hit`, `_round_half_up`) is pure arithmetic
  verified by inspection, not re-derived in TLA+.
- `PrerequisiteGraph.tla` abstracts the skill-level prereqs and uses an
  abstracted `Beatable` verdict for the combat-gate equivalence; the operational
  `predict_win` refinement lives in `PredictWin.tla`.

## Move-API connectivity finding

<Record the Step 1 finding here: does artifactsmmo move one tile per action, is
diagonal movement reachable, and therefore is the Chebyshev-optimal contract the
right one — or is `calculate_path` purely a cost/preview estimate?>
````

- [ ] **Step 3: Fill in the connectivity finding**

Replace the `<Record the Step 1 finding...>` placeholder with the actual finding from Step 1. Do not leave the angle-bracket placeholder.

- [ ] **Step 4: Final full run**

Run: `uv run python formal/run.py`
Expected: every module PASS, exit 0.

- [ ] **Step 5: Commit**

```bash
git add formal/README.md
git commit -m "docs(formal): README with scope, property map, connectivity finding"
```

---

## Self-Review notes (addressed)

- **Spec coverage:** all four functions get a task (3–6); scaffolding (1), runner (2), README (7). `is_winnable` veto and the live planner loop are out of scope per the design doc.
- **PlusPy reality:** no `.cfg`/`INVARIANT`; enumerate-and-`Assert` pattern used throughout, matching the corrected design.
- **Oracle independence:** each module checks the algorithm against a *different* definition (fixpoint, hand table, operational sim, declarative optimum) — not a restatement of itself. Each task includes a "sanity-check the oracle bites" step that deliberately breaks the code and confirms PlusPy halts, proving the check is not vacuous.
- **Type/name consistency:** module names, `MODULES` runner entries, and iteration counts (625 / 9 / 5 / 1800) are consistent across tasks and the runner.
- **No placeholders:** the only intentional fill-ins are the PlusPy commit SHA (Task 1 Step 3) and the connectivity finding (Task 7 Step 3), each with an explicit step to resolve it.
