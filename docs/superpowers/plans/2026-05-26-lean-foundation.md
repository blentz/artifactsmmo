# Lean 4 Formal Verification — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the Lean 4 verification foundation — a `lake` project in `formal/`, one fully kernel-proven reference component (`calculate_path`), and the four-part anti-gaming gate (kernel build · no-escape-hatch axiom lint · mutation-testing non-vacuity gate · Hypothesis differential bridge to Python) — wired so the gate is **green on the real proof and red on a `sorry`, a weakened theorem, or a surviving mutant**.

**Architecture:** Per the design doc (`docs/superpowers/specs/2026-05-26-lean-formal-verification-design.md`). The same Lean `def` is what the theorems prove about AND what the differential oracle executes against the Python. Lean core only (NO mathlib) to keep builds fast; `omega`/`decide` for arithmetic. Mutation targets the **Python** implementation.

**Tech Stack:** Lean 4 (via `elan`), `lake`, Lean core (no mathlib), Python 3.13 + Hypothesis (`uv` dev dep), bash gate scripts, GitHub Actions.

---

## Environment facts (verified at planning time)

- `lean`/`lake`/`elan` are NOT installed; `hypothesis` is NOT installed. Install sources reachable (elan script, GitHub releases, PyPI all HTTP 200). Platform: Linux x86_64.
- Work in the worktree at `/home/blentz/git/artifactsmmo/.claude/worktrees/formal-lean`. **Write/Edit files using the full worktree-prefixed absolute path** — a bare `/home/blentz/git/artifactsmmo/...` path resolves to the MAIN checkout, not the worktree (this bug already bit once). Verify with `git -C <worktree> status` that files land in the worktree before committing.
- `formal/` is currently empty (TLA+ POC removed). Commit messages end with the trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- Project uses `uv`. Lean proofs/build are NOT under `uv`; the differential test (Python) is run via `uv run pytest`.

## File structure

```
formal/
  lean-toolchain                      # pinned Lean version (resolved at bootstrap)
  lakefile.toml                       # lake package: lib `Formal`, exe `oracle`
  Formal.lean                         # root import
  Formal/
    CalculatePath.lean                # def + theorems + proofs (sorry-free)
    Manifest.lean                     # declares required theorem roles per component
    Audit.lean                        # `#print axioms` over manifest theorems (gate reads output)
  Oracle.lean                         # exe `main`: JSON stdin -> proved-def outputs -> JSON stdout
  diff/
    test_calculate_path_diff.py       # Hypothesis: Python calculate_path vs Lean oracle
    oracle_client.py                  # helper: invoke compiled oracle with JSON
    mutate.py                         # mutation runner against the Python impl
  gate.sh                             # runs all four gate parts; nonzero on any failure
  README.md                           # scope, soundness chain, how to run the gate
.github/workflows/formal-gate.yml     # CI: install elan + uv, run formal/gate.sh
```

---

## Task 1: Bootstrap — install Lean toolchain, scaffold lake project, add hypothesis

**Files:** Create `formal/lean-toolchain`, `formal/lakefile.toml`, `formal/Formal.lean`, `formal/Formal/CalculatePath.lean` (stub); modify `pyproject.toml` (dev dep).

- [ ] **Step 1: Install elan (non-interactive) and a stable Lean toolchain**

Run:
```bash
curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --default-toolchain stable
. "$HOME/.elan/env"
elan --version && lean --version && lake --version
```
Expected: versions print. Record the resolved Lean version (e.g. `lean --version` → `Lean (version 4.x.y...)`).

- [ ] **Step 2: Pin the toolchain**

Create `formal/lean-toolchain` containing exactly the resolved release tag, e.g.:
```
leanprover/lean4:v4.15.0
```
(Use the actual `v<major>.<minor>.<patch>` matching `lean --version` from Step 1. From `formal/`, `lake` will honor this file.)

- [ ] **Step 3: Create `formal/lakefile.toml`**

```toml
name = "Formal"
defaultTargets = ["Formal", "oracle"]

[[lean_lib]]
name = "Formal"

[[lean_exe]]
name = "oracle"
root = "Oracle"
```

- [ ] **Step 4: Create `formal/Formal.lean` (root import) and a stub component**

`formal/Formal.lean`:
```lean
import Formal.CalculatePath
```

`formal/Formal/CalculatePath.lean` (stub that compiles — real content in Task 2):
```lean
namespace Formal.CalculatePath

/-- Integer coordinate on the map. -/
abbrev Coord := Int × Int

end Formal.CalculatePath
```

- [ ] **Step 5: Build the scaffold**

Run: `cd formal && lake build Formal`
Expected: builds clean, exit 0 (downloads the toolchain on first run). If `lake` reports a manifest/toolchain mismatch, ensure `formal/lean-toolchain` matches the installed version.

- [ ] **Step 6: Add hypothesis as a dev dependency**

Run from repo root: `uv add --dev hypothesis`
Then: `uv run python -c "import hypothesis; print(hypothesis.__version__)"`
Expected: version prints.

- [ ] **Step 7: Commit**

```bash
git add formal/lean-toolchain formal/lakefile.toml formal/Formal.lean formal/Formal/CalculatePath.lean pyproject.toml uv.lock
git commit -m "build(formal): bootstrap Lean 4 lake project + hypothesis dev dep

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

> If `elan` cannot be installed in this environment (no network at run time), STOP and report BLOCKED — the entire foundation depends on the toolchain. Do not stub or fake the build.

---

## Task 2: `calculate_path` — Lean def + theorems + kernel-checked proofs

Mirrors `src/artifactsmmo_cli/utils/pathfinding.py:44` (`calculate_path`). READ it first. The Python produces a list of king-step `PathStep`s, `total_distance` = Manhattan, `estimated_time` = `len(steps)*5`. Prove validity + Chebyshev optimality + cost, **∀ coordinates**, sorry-free.

**Files:** Modify `formal/Formal/CalculatePath.lean`.

- [ ] **Step 1: Write the model + theorem statements in `formal/Formal/CalculatePath.lean`**

```lean
namespace Formal.CalculatePath

abbrev Coord := Int × Int

def absI (n : Int) : Int := if n < 0 then -n else n
def cheb (a b : Coord) : Int := max (absI (b.1 - a.1)) (absI (b.2 - a.2))
def manhattan (a b : Coord) : Int := absI (b.1 - a.1) + absI (b.2 - a.2)

/-- One king-step from `cur` toward `dst` (mirrors the Python loop body). -/
def stepToward (c d : Int) : Int := if c < d then c + 1 else if c > d then c - 1 else c
def kingStep (cur dst : Coord) : Coord := (stepToward cur.1 dst.1, stepToward cur.2 dst.2)

/-- The produced path: repeated king-steps, fuel-bounded by the Chebyshev distance
    (which is the exact number of steps). -/
def pathFromFuel (fuel : Nat) (cur dst : Coord) : List Coord :=
  if cur = dst then []
  else match fuel with
    | 0 => []
    | n + 1 => let nxt := kingStep cur dst; nxt :: pathFromFuel n nxt dst

def pathFrom (start dst : Coord) : List Coord :=
  pathFromFuel (cheb start dst).toNat start dst

/-- King-adjacency: differs by at most 1 on each axis, and not equal. -/
def adjacent (a b : Coord) : Prop :=
  absI (b.1 - a.1) ≤ 1 ∧ absI (b.2 - a.2) ≤ 1 ∧ a ≠ b

/-- A legal king-walk from `start` to `dst`. -/
def ValidKingWalk (start dst : Coord) (p : List Coord) : Prop :=
  (p = [] ∧ start = dst) ∨
  (p ≠ [] ∧ adjacent start p.head! ∧ p.getLast! = dst ∧
    ∀ i, (h : i + 1 < p.length) → adjacent (p[i]) (p[i+1]))

-- ===== THEOREMS (∀ inputs; proofs must be sorry-free) =====

/-- Role: validity. The produced path is a legal king-walk to the destination. -/
theorem pathFrom_valid (start dst : Coord) : ValidKingWalk start dst (pathFrom start dst) := by
  sorry  -- IMPLEMENTER: discharge. (the only `sorry` allowed is here during drafting; gate rejects it)

/-- Role: cost. Reported total distance equals Manhattan distance. -/
theorem pathFrom_cost (start dst : Coord) :
    manhattan start dst = absI (dst.1 - start.1) + absI (dst.2 - start.2) := by
  rfl

/-- Role: optimality lower bound. Every legal king-walk has length ≥ Chebyshev distance. -/
theorem kingWalk_len_ge_cheb (start dst : Coord) (p : List Coord)
    (h : ValidKingWalk start dst p) : (cheb start dst).toNat ≤ p.length := by
  sorry  -- IMPLEMENTER: discharge (each king-step cuts cheb-to-dst by ≤ 1).

/-- Role: optimality achieved. The produced path's length equals the Chebyshev optimum,
    so (with the lower bound above) it is a shortest king-walk. -/
theorem pathFrom_len_eq_cheb (start dst : Coord) :
    (pathFrom start dst).length = (cheb start dst).toNat := by
  sorry  -- IMPLEMENTER: discharge (induction on the fuel / cheb distance).

end Formal.CalculatePath
```

- [ ] **Step 2: Discharge every `sorry` — proofs must be real**

Replace each `sorry` with a complete proof (induction on `(cheb start dst).toNat` / on `pathFromFuel`'s fuel; `omega` for the integer arithmetic of `absI`/`stepToward`/`cheb`). `pathFrom_cost` is `rfl`/`omega`. The optimality pair (`kingWalk_len_ge_cheb` + `pathFrom_len_eq_cheb`) together establish that `pathFrom` is a shortest king-walk.

This is genuine proof work. If a theorem turns out to need mathlib lemmas not in core, FIRST try `omega`/`decide`/manual induction; only if truly necessary, report back to add a minimal dependency (do not silently weaken a statement to make it provable).

- [ ] **Step 3: Build — no `sorry`, no axioms beyond the standard three**

Run: `cd formal && lake build Formal`
Expected: builds clean, exit 0.
Then run an axiom check on each theorem (interim, formalized in Task 4):
```bash
cd formal && lake env lean --run <(printf 'import Formal\nopen Formal.CalculatePath\n#print axioms pathFrom_valid\n#print axioms kingWalk_len_ge_cheb\n#print axioms pathFrom_len_eq_cheb\n#print axioms pathFrom_cost\n')
```
Expected: each prints `'thm' depends on axioms: [propext, Classical.choice, Quot.sound]` (or a subset). If any shows `sorryAx` or a custom axiom, the proof is not done — fix it.

- [ ] **Step 4: Commit**

```bash
git add formal/Formal/CalculatePath.lean
git commit -m "feat(formal): prove calculate_path validity + Chebyshev optimality in Lean

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

> Do NOT commit while any `sorry` remains or `#print axioms` shows `sorryAx`. A red kernel is a failed task, not a checkpoint.

---

## Task 3: Differential bridge — Lean oracle executable + Hypothesis test vs Python

The proved Lean `def`s must be the ones executed against the real Python, closing the model↔code gap.

**Files:** Create `formal/Oracle.lean`, `formal/diff/oracle_client.py`, `formal/diff/test_calculate_path_diff.py`.

- [ ] **Step 1: Write `formal/Oracle.lean` (executable evaluating the proved defs)**

```lean
import Formal
import Lean.Data.Json
open Lean Formal.CalculatePath

/-- Read JSON `[[sx,sy,ex,ey], ...]` from stdin; emit
    `[{"steps": [[x,y],...], "total_distance": n}, ...]`. Uses the SAME `pathFrom`
    and `manhattan` the theorems are about. -/
def runOne (sx sy ex ey : Int) : Json :=
  let start : Coord := (sx, sy)
  let dst : Coord := (ex, ey)
  let steps := pathFrom start dst
  let stepsJson := Json.arr (steps.map (fun c => Json.arr #[Json.num c.1, Json.num c.2])).toArray
  Json.mkObj [("steps", stepsJson), ("total_distance", Json.num (manhattan start dst))]

def main : IO Unit := do
  let stdin ← IO.getStdin
  let input ← stdin.readToEnd
  match Json.parse input with
  | .error e => IO.eprintln s!"parse error: {e}"; IO.Process.exit 1
  | .ok j =>
    let arr := j.getArr?.toOption.getD #[]
    let results := arr.map (fun item =>
      let xs := (item.getArr?.toOption.getD #[]).map (fun n => (n.getInt?.toOption.getD 0))
      runOne xs[0]! xs[1]! xs[2]! xs[3]!)
    IO.println (Json.arr results).compress
```
(If `Lean.Data.Json` field accessors differ in the pinned version, adapt — the contract is: stdin JSON list of `[sx,sy,ex,ey]` → stdout JSON list of `{steps,total_distance}` computed by `pathFrom`/`manhattan`. Build with `cd formal && lake build oracle`; the binary lands at `formal/.lake/build/bin/oracle`.)

- [ ] **Step 2: Build the oracle**

Run: `cd formal && lake build oracle`
Expected: `formal/.lake/build/bin/oracle` exists. Smoke:
```bash
echo '[[0,0,3,2]]' | ./.lake/build/bin/oracle
```
Expected: JSON like `[{"steps":[[1,1],[2,2],[3,2]],"total_distance":5}]`.

- [ ] **Step 3: Write `formal/diff/oracle_client.py`**

```python
"""Invoke the compiled Lean oracle with a batch of inputs, parse its JSON output."""
import json
import subprocess
from pathlib import Path

ORACLE = Path(__file__).resolve().parent.parent / ".lake" / "build" / "bin" / "oracle"


def run_oracle(inputs: list[tuple[int, int, int, int]]) -> list[dict]:
    if not ORACLE.exists():
        raise RuntimeError(f"oracle not built: {ORACLE} (run `cd formal && lake build oracle`)")
    payload = json.dumps([list(t) for t in inputs])
    proc = subprocess.run([str(ORACLE)], input=payload, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"oracle failed: {proc.stderr}")
    return json.loads(proc.stdout)
```

- [ ] **Step 4: Write `formal/diff/test_calculate_path_diff.py`**

```python
"""Differential test: the real Python calculate_path must agree with the proved Lean def."""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.utils.pathfinding import calculate_path
from formal.diff.oracle_client import run_oracle

coord = st.integers(min_value=-40, max_value=40)


@settings(max_examples=400)
@given(sx=coord, sy=coord, ex=coord, ey=coord)
def test_python_matches_lean(sx, sy, ex, ey):
    py = calculate_path(sx, sy, ex, ey)
    lean = run_oracle([(sx, sy, ex, ey)])[0]
    assert [[s.x, s.y] for s in py.steps] == lean["steps"]
    assert py.total_distance == lean["total_distance"]
```
(If importing `formal.diff...` needs a path entry, add a `conftest.py` under `formal/` inserting the repo root on `sys.path`, or run pytest from repo root with `formal` importable. Keep imports top-of-file per CLAUDE.md.)

- [ ] **Step 5: Run the differential test**

Run: `cd formal && lake build oracle && cd .. && uv run pytest formal/diff/test_calculate_path_diff.py -q`
Expected: PASS (Python ≡ Lean over 400 random inputs). If it FAILS, the divergence is real — investigate which (the Python, the Lean model, or the oracle JSON) is wrong; do not loosen the assertion to pass.

- [ ] **Step 6: Commit**

```bash
git add formal/Oracle.lean formal/diff/oracle_client.py formal/diff/test_calculate_path_diff.py formal/diff/__init__.py
git commit -m "feat(formal): Lean oracle + Hypothesis differential bridge for calculate_path

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: The anti-gaming gate — axiom lint, role manifest, mutation runner, gate.sh

**Files:** Create `formal/Formal/Manifest.lean`, `formal/Formal/Audit.lean`, `formal/gate/check_axioms.sh`, `formal/diff/mutate.py`, `formal/gate.sh`.

- [ ] **Step 1: Declare the role manifest `formal/Formal/Manifest.lean`**

```lean
import Formal
/-! Required theorem roles per component. The gate checks each named theorem exists
    and is proved (the file compiles only if they do). Add a line per (component, role). -/
open Formal.CalculatePath
-- CalculatePath: validity, optimality lower-bound, optimality-achieved, cost
example : True := by trivial
#check @pathFrom_valid        -- role: validity
#check @kingWalk_len_ge_cheb  -- role: optimality-lower-bound
#check @pathFrom_len_eq_cheb  -- role: optimality-achieved
#check @pathFrom_cost         -- role: cost
```
(The `#check`s fail to compile if a theorem is missing/renamed — a mechanical coverage gate. As components are added, append their `#check`s here.)

- [ ] **Step 2: Write `formal/Formal/Audit.lean`**

```lean
import Formal
open Formal.CalculatePath
#print axioms pathFrom_valid
#print axioms kingWalk_len_ge_cheb
#print axioms pathFrom_len_eq_cheb
#print axioms pathFrom_cost
```

- [ ] **Step 2b: Write `formal/gate/check_axioms.sh`**

```bash
#!/usr/bin/env bash
# Fail if any audited theorem depends on a non-standard axiom or sorryAx.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."   # formal/
OUT="$(lake env lean Formal/Audit.lean 2>&1)"
echo "$OUT"
# Allowed axioms: propext, Classical.choice, Quot.sound. Anything else (esp. sorryAx) fails.
if echo "$OUT" | grep -Eiq 'sorryAx|sorry'; then
  echo "GATE FAIL: a proof uses sorry"; exit 1
fi
BAD="$(echo "$OUT" | tr ',' '\n' | grep -Eo '[A-Za-z_][A-Za-z0-9_.]*' \
       | grep -Ev '^(propext|Classical\.choice|Quot\.sound|depends|on|axioms|.* )$' \
       | grep -E '\.' | grep -Ev '^(Classical\.choice|Quot\.sound)$' || true)
# Conservative: explicitly require each theorem line lists ONLY the allowed set.
if echo "$OUT" | grep -Eq 'depends on axioms' ; then
  if echo "$OUT" | grep -E 'depends on axioms' | grep -Eqv '\[(propext|Classical.choice|Quot.sound|, )+\]'; then
    echo "GATE FAIL: non-standard axiom present"; exit 1
  fi
fi
echo "axiom check OK"
```
(IMPLEMENTER: `#print axioms` output format is `'thm' depends on axioms: [propext, Classical.choice, Quot.sound]`. Make the parser robust to that exact format — assert the bracketed set is a subset of the three allowed names, and fail hard on `sorryAx`. Verify by temporarily adding a `sorry` and confirming the script exits nonzero.)

- [ ] **Step 3: Write the mutation runner `formal/diff/mutate.py`**

```python
"""Mutation gate: perturb the Python calculate_path; every mutant the differential
test fails to kill is a survivor => the spec is too weak => gate fails.

Mutations are textual edits applied to a copy of pathfinding.py; for each, we run
the differential test against the mutated module and require it to FAIL (mutant killed).
"""
import importlib
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "artifactsmmo_cli" / "utils" / "pathfinding.py"

# (description, old, new) textual mutations of calculate_path's loop/cost.
MUTATIONS = [
    ("x-step inverted", "next_x += 1", "next_x -= 1"),
    ("y-step inverted", "next_y += 1", "next_y -= 1"),
    ("x-cond flipped", "if current_x < end_x:", "if current_x > end_x:"),
    ("manhattan->0", "total_distance = abs(end_x - start_x) + abs(end_y - start_y)",
                     "total_distance = 0"),
    ("drop y move", "next_y += 1", "next_y += 0"),
]


def run_diff_against(path: Path) -> int:
    """Return pytest exit code (0 = passed = mutant SURVIVED)."""
    return subprocess.run(
        ["uv", "run", "pytest", "formal/diff/test_calculate_path_diff.py", "-q", "-x"],
        cwd=Path(__file__).resolve().parents[2],
    ).returncode


def main() -> int:
    original = SRC.read_text()
    survivors: list[str] = []
    try:
        for desc, old, new in MUTATIONS:
            if old not in original:
                print(f"MUTATION NOT APPLICABLE (text not found): {desc}")
                survivors.append(f"{desc} (stale mutation)")
                continue
            SRC.write_text(original.replace(old, new, 1))
            code = run_diff_against(SRC)
            if code == 0:
                print(f"SURVIVED (diff test passed on mutant): {desc}")
                survivors.append(desc)
            else:
                print(f"killed: {desc}")
    finally:
        SRC.write_text(original)  # always restore
    if survivors:
        print(f"GATE FAIL: {len(survivors)} surviving mutant(s): {survivors}")
        return 1
    print("mutation gate OK (all mutants killed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
(IMPLEMENTER: confirm the `old` strings exactly match `pathfinding.py`'s current text; adjust to match. The runner edits the real file in-place and **always restores it in `finally`** — verify the file is byte-identical after a run with `git diff --quiet src/.../pathfinding.py`.)

- [ ] **Step 4: Write `formal/gate.sh` (the four-part gate)**

```bash
#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
. "$HOME/.elan/env" 2>/dev/null || true

echo "== (a) kernel build =="
( cd "$HERE" && lake build )

echo "== (b) no-escape-hatch axiom lint =="
bash "$HERE/gate/check_axioms.sh"

echo "== (b') role manifest compiles (coverage) =="
( cd "$HERE" && lake env lean Formal/Manifest.lean >/dev/null && echo "manifest OK" )

echo "== (d) differential fidelity (Python == Lean) =="
( cd "$HERE" && lake build oracle )
( cd "$ROOT" && uv run pytest formal/diff/test_calculate_path_diff.py -q )

echo "== (c) mutation non-vacuity gate =="
( cd "$ROOT" && uv run python formal/diff/mutate.py )

echo "ALL GATE PARTS PASSED"
```

- [ ] **Step 5: Make scripts executable and run the full gate**

Run: `chmod +x formal/gate.sh formal/gate/check_axioms.sh && ./formal/gate.sh`
Expected: every section prints OK / passes, ends `ALL GATE PARTS PASSED`, exit 0.

- [ ] **Step 6: Commit**

```bash
git add formal/Formal/Manifest.lean formal/Formal/Audit.lean formal/gate/check_axioms.sh formal/diff/mutate.py formal/gate.sh
git commit -m "feat(formal): four-part anti-gaming gate (axioms/manifest/mutation/differential)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: CI wiring + README + acceptance demonstration (gate must go RED on cheats)

**Files:** Create `.github/workflows/formal-gate.yml`, `formal/README.md`.

- [ ] **Step 1: Write `.github/workflows/formal-gate.yml`**

```yaml
name: formal-gate
on:
  pull_request:
    paths: ["formal/**", "src/artifactsmmo_cli/utils/pathfinding.py", ".github/workflows/formal-gate.yml"]
  push:
    branches: [main]
    paths: ["formal/**", "src/artifactsmmo_cli/utils/pathfinding.py"]
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install elan (Lean)
        run: |
          curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y --default-toolchain none
          echo "$HOME/.elan/bin" >> "$GITHUB_PATH"
      - name: Install uv
        uses: astral-sh/setup-uv@v5
      - name: Sync deps
        run: uv sync --dev
      - name: Run the formal gate
        run: ./formal/gate.sh
```

- [ ] **Step 2: Write `formal/README.md`**

````markdown
# Formal verification (Lean 4)

Kernel-checked proofs that the AI's pure logic is correct **for all valid inputs**,
plus a gate that mechanically rejects the ways a proof can be faked or made vacuous.

## Soundness chain

> Python function correct ⇐ (Python ≡ Lean def, by the differential test)
> ∧ (Lean def proved correct ∀ inputs, by the kernel).

The only un-proved link — "is the Lean def a faithful model of the Python?" — is
checked **mechanically and randomly** by the Hypothesis differential test, not by
assertion. Mutation testing ensures the proved theorems have teeth against that link.

## The gate (`./formal/gate.sh`)

1. **kernel build** — `lake build` re-checks every proof; an unfinished proof fails.
2. **axiom lint** — `#print axioms` on each theorem must list only
   `propext, Classical.choice, Quot.sound`; `sorryAx`/custom axioms/`native_decide` fail.
3. **role manifest** — `Manifest.lean` compiles only if each required theorem exists.
4. **differential + mutation** — Hypothesis checks Python ≡ Lean over random inputs;
   the mutation runner perturbs the Python and fails if any mutant survives (spec too weak).

## Run locally

```bash
curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | sh -s -- -y
uv sync --dev
./formal/gate.sh        # green only if proofs are real, complete, and have teeth
```

## Coverage

| Component | Lean | Roles proved |
|---|---|---|
| `calculate_path` (`utils/pathfinding.py:44`) | `Formal/CalculatePath.lean` | validity, optimality (lower-bound + achieved), cost |

Backfill of the remaining components is tracked in the design doc
(`docs/superpowers/specs/2026-05-26-lean-formal-verification-design.md`). The TLA+/PlusPy
predecessor and why it was retired: `docs/postmortems/2026-05-26-tlaplus-pluspy-formal-verification.md`.
````

- [ ] **Step 3: Acceptance demonstration — prove the gate goes RED on each cheat**

Run each, confirm the gate FAILS (nonzero), then revert:
1. **`sorry`:** temporarily replace one proof body with `sorry`; run `./formal/gate.sh`; expect the axiom lint (or build) to fail. Revert.
2. **weakened theorem + surviving mutant:** temporarily weaken `pathFrom_len_eq_cheb` to `(pathFrom start dst).length ≥ 0` (trivially true) and re-prove; run `./formal/gate.sh`; expect the **mutation gate** to fail (a length-related mutant now survives because no theorem/diff pins the length). Revert.
3. **surviving mutant (diff coverage hole):** temporarily comment out the `total_distance` assertion in the differential test; run `./formal/gate.sh`; expect the `manhattan->0` mutant to survive → mutation gate fails. Revert.

Record the three RED outcomes in the commit message. (These demonstrate the gate constrains the author, which is the whole point.)

- [ ] **Step 4: Final green run + commit**

Run: `./formal/gate.sh` → `ALL GATE PARTS PASSED`, exit 0.
```bash
git add .github/workflows/formal-gate.yml formal/README.md
git commit -m "ci(formal): wire Lean gate into CI + README; demonstrate gate red on sorry/weak-theorem/surviving-mutant

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review notes (addressed)

- **Spec coverage:** scaffold+toolchain (T1); proved reference component (T2); differential bridge (T3); four-part gate (T4); CI + README + red-on-cheat acceptance (T5). Matches the design doc's foundation cycle and acceptance criteria.
- **Anti-gaming enforced mechanically:** kernel build (a), `#print axioms` sorryAx/custom-axiom rejection (b), role manifest coverage (b'), differential fidelity (d), mutation non-vacuity (c). T5 Step 3 demonstrates each goes RED.
- **No `sorry` shipped:** T2 forbids committing with `sorry`; the gate rejects `sorryAx`; T5 demonstrates it.
- **Honest BLOCKED paths:** T1 says BLOCK if elan can't install; T2 says report (not weaken) if a proof needs mathlib; T3/T4 say investigate (not loosen) on differential/mutation failure.
- **Worktree path hazard called out** in the environment facts (Write to the worktree-prefixed path).
- **Placeholders:** Lean proof bodies are intentionally left for the implementer to discharge (kernel-enforced, sorry-free) — the theorem STATEMENTS (the contract) are concrete; gate scripts are concrete with implementer notes only for format-robustness (`#print axioms` parsing, exact mutation text matching).
- **Type/name consistency:** theorem names (`pathFrom_valid`, `kingWalk_len_ge_cheb`, `pathFrom_len_eq_cheb`, `pathFrom_cost`), `pathFrom`/`manhattan`/`cheb` used consistently across CalculatePath.lean, Oracle.lean, Manifest.lean, Audit.lean, and the gate.
