# Unify Grind Beatability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `cheapest_path_to_level` (the plan-screen projection) judge "can I grind this monster" with the same `combat.is_winnable` verdict the runtime uses, so the plan screen and the executor always pick the same monster.

**Architecture:** The projection shell filters candidates with `is_winnable` (deleting its bespoke win-rate filter); the proved `CheapestPath.lean` core gains a `winnable : Bool` per candidate that `isBeatable` ANDs in. The `predict_win`/`is_winnable`/greedy-pick proofs are reused; the runtime and the plan-screen display are unchanged (the fix flows through the cascade that already reads the projection gated by `is_winnable`).

**Tech Stack:** Python 3.13 (`~/.local/bin/uv run`), Lean 4 (formal/), Hypothesis differential + mutation gate.

## Global Constraints

- `~/.local/bin/uv run …`; focused tests `--no-cov`; 100% coverage required.
- No inline imports; never catch `Exception`; use only API data or fail.
- Beatability = level-applicability (`1 ≤ level ≤ sim_level+1`) AND `combat.is_winnable(state, game_data, code, store)`. The current-gear `state` is used for every projected `sim_level` — NO speculative gear/inventory projection (user directive 2026-06-26).
- Delete the projection's `MIN_PATH_SUCCESS_RATE` / `MIN_PATH_SAMPLES` win-rate filter (subsumed by `is_winnable`'s learned-loss veto).
- No import cycle: `combat.py` imports `equipment.projection` + `learning.store`, NOT `learning.projections` — the top-level `from artifactsmmo_cli.ai.combat import is_winnable` is safe.
- Formal: safety axioms ⊆ {propext, Classical.choice, Quot.sound}; no sorry/native_decide. The `accumulation-sell`/`dominance-pareto` commits are the template for the oracle/differential/mutation mechanics.

---

### Task 1: Projection uses `is_winnable` (delete the win-rate filter)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/projections.py` (`cheapest_path_to_level`, imports; remove `MIN_PATH_SUCCESS_RATE`/`MIN_PATH_SAMPLES` if now unused)
- Test: `tests/test_ai/test_projections.py` (or the existing projections test file — match it)

**Interfaces:**
- Consumes: `combat.is_winnable(state, game_data, monster_code, history) -> bool`.
- Produces: `cheapest_path_to_level` whose `beatable` filter is level-gate AND `is_winnable`; `next_action_monster` now equals the runtime's pick for the same state.

- [ ] **Step 1: Write the failing tests** (a tanky same-level monster excluded; a winnable lower monster picked though it has lower XP; blocked when nothing winnable). Monkeypatch `is_winnable` at the projections module so the scenario is deterministic.

```python
import artifactsmmo_cli.ai.learning.projections as proj
from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state


def _gd(levels):
    gd = GameData()
    gd._monster_level = dict(levels)
    return gd


def test_unwinnable_high_xp_monster_excluded(monkeypatch, tmp_path):
    # cow: level 8 (==char), high XP; green_slime: level 4, lower XP. is_winnable
    # says only green_slime is winnable → path picks green_slime despite cow's XP.
    gd = _gd({"cow": 8, "green_slime": 4})
    monkeypatch.setattr(proj, "is_winnable",
                        lambda s, g, code, h: code == "green_slime")
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="r")
    state = make_state(level=8, xp=0, max_xp=100)
    plan = cheapest_path_to_level(9, state, store, gd)
    assert plan.next_action_monster == "green_slime"
    assert plan.blocked is False


def test_blocked_when_nothing_winnable(monkeypatch, tmp_path):
    gd = _gd({"cow": 8})
    monkeypatch.setattr(proj, "is_winnable", lambda s, g, code, h: False)
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="r")
    state = make_state(level=8, xp=0, max_xp=100)
    plan = cheapest_path_to_level(9, state, store, gd)
    assert plan.blocked is True


def test_next_monster_is_always_winnable(monkeypatch, tmp_path):
    # Regression lock for the plan-screen<->execution mismatch: the projection's
    # emitted next monster MUST pass is_winnable, so the runtime cascade
    # (`_winnable_farm_target`: path_monster gated by is_winnable) returns the
    # SAME monster instead of falling through to pick_winnable.
    gd = _gd({"cow": 8, "green_slime": 4})
    monkeypatch.setattr(proj, "is_winnable",
                        lambda s, g, code, h: code == "green_slime")
    store = LearningStore(db_path=str(tmp_path / "p.db"), character="r")
    state = make_state(level=8, xp=0, max_xp=100)
    nxt = cheapest_path_to_level(9, state, store, gd).next_action_monster
    assert nxt is not None
    assert proj.is_winnable(state, gd, nxt, store) is True   # cascade will accept it
```

- [ ] **Step 2: Run → FAIL** (cow currently wins on XP).

- [ ] **Step 3: Implement** — add the import + the filter conjunct; delete the win-rate filter. Add at the top of `projections.py`:

```python
from artifactsmmo_cli.ai.combat import is_winnable
```

In `cheapest_path_to_level`, change the `beatable` comprehension to AND `is_winnable`:

```python
        beatable = [
            (code, lvl) for code, lvl in game_data.monster_levels.items()
            if 1 <= lvl <= sim_level + 1
            and is_winnable(state, game_data, code, store)
        ]
```

And DELETE the per-candidate win-rate filter inside the `for code, _lvl in beatable:` loop (the block):

```python
            samples = store.sample_count(fight_repr)
            if samples >= MIN_PATH_SAMPLES:
                rate = store.success_rate(fight_repr)
                if rate < MIN_PATH_SUCCESS_RATE:
                    continue
```

If `MIN_PATH_SUCCESS_RATE` / `MIN_PATH_SAMPLES` are now unused anywhere (grep), delete their definitions too; if still referenced elsewhere, leave them.

- [ ] **Step 4: Run → PASS;** then the full AI suite `~/.local/bin/uv run pytest tests/test_ai/ -q --no-cov` (the projection feeds `projected_cycles_to_max` and `_path_aligned_monster`; investigate any regression before touching its asserts) and 100% coverage of `projections.py`.
- [ ] **Step 5: Commit** — `git commit -m "fix(projection): grind path uses is_winnable (drop level-only beatability)"`

---

### Task 2: Lean core — `winnable` per candidate

**Files:**
- Modify: `formal/Formal/CheapestPath.lean` (`Monster` struct + `isBeatable`; update every `Monster` literal in the file/proofs to add the field), `formal/Formal/Manifest.lean` / `formal/Formal/Contracts.lean` only if a theorem statement names `Monster` fields.

**Interfaces:**
- Produces: `Monster` with `winnable : Bool`; `isBeatable simLevel m := decide (1 ≤ m.level) && decide (m.level ≤ simLevel+1) && m.winnable`.

- [ ] **Step 1: Add the field + conjunct**

```lean
structure Monster where
  code : Nat
  level : Nat
  xpPerCycle : Nat
  winnable : Bool          -- combat.is_winnable verdict (shell-computed); the
                           -- single beatability source shared with the runtime
  deriving Repr, DecidableEq

def isBeatable (simLevel : Nat) (m : Monster) : Bool :=
  decide (1 ≤ m.level) && decide (m.level ≤ simLevel + 1) && m.winnable
```

- [ ] **Step 2: Fix every `Monster` literal** — `cd formal && ~/.elan/bin/lake build` will error on each `{ code := …, level := …, xpPerCycle := … }` literal (in proofs / examples within CheapestPath.lean) that now lacks `winnable`. Add `, winnable := true` (or the case-appropriate bool) to each. Re-run until green. The `pickBest`/`stepLevel`/`buildPlan`/`cheapestPath` theorems are unchanged in statement — `isBeatable` gaining a conjunct only shrinks the filtered set, which the greedy/termination/blocked proofs already quantify over generically. If a proof breaks, it is a literal/`isBeatable`-unfold fix, not a statement change.

- [ ] **Step 3: Verify** — `lake build` green; `bash gate/check_axioms.sh`; `bash gate/check_no_orphan_modules.sh`; if a Contracts/Manifest statement references `Monster`, confirm it still elaborates (theorem statements should be unchanged).
- [ ] **Step 4: Commit** — `git commit -m "feat(formal): CheapestPath Monster.winnable — single beatability source"`

---

### Task 3: Oracle + differential + mutation + gate + finish

**Files:**
- Modify: `formal/Oracle.lean` (`runCheapestPath`: read a 4th per-monster field `winnable`), `formal/diff/test_cheapest_path_diff.py` (encode + feed `winnable`), `formal/diff/mutate.py` (CheapestPath anchor for the new conjunct)

- [ ] **Step 1: Oracle** — in `runCheapestPath` the per-monster stride becomes 4: `code = intArg args (5 + 4*k)`, `level = (…+1)`, `xpPerCycle = (…+2)`, `winnable = intArg args (5 + 4*k + 3) != 0`. Update `nMonsters` indexing accordingly. `cd formal && ~/.elan/bin/lake build oracle`.

- [ ] **Step 2: Differential** — in `test_cheapest_path_diff.py`:
  - `_encode_args`: per monster append `[code, lvl, xpc, 1 if winnable else 0]` (4 fields).
  - Each test must control `is_winnable` deterministically: `monkeypatch.setattr(projections_module, "is_winnable", <stub>)` so Python's internal filter is known, AND feed the SAME stub verdict per monster to `_run_lean` (compute `winnable = stub(state, gd, code, store)` when encoding). This binds the CORE composition (greedy + level-gate + winnable filter); `is_winnable` itself is bound by the predict_win differential, not here.
  - Add a case where a level-OK monster is `winnable=False` and a lower one is `winnable=True`, asserting the Lean plan picks the winnable one (kills the drop-winnable mutant).
  - `~/.local/bin/uv run pytest formal/diff/test_cheapest_path_diff.py -q --no-cov` → PASS.

- [ ] **Step 3: Mutation anchor** — add to the CheapestPath mutation group in `mutate.py` (find it; it targets `projections.py` killed by `test_cheapest_path_diff.py`): an anchor dropping the new beatability — Lean side isn't mutated, so anchor the PYTHON filter: `("cheapest_path: drop is_winnable filter", "            and is_winnable(state, game_data, code, store)", "")` — verify KILLED via the in-memory apply→differential→restore loop (NOT git checkout — guardrail). If the projections.py mutation group doesn't exist yet, create `CHEAPEST_PATH_MUTATIONS` + its `run_group` (template: the accumulation-sell group).

- [ ] **Step 4: Full gate** — confirm NO bot running (`pgrep -af "artifactsmmo play"`; ask the user to stop it if running — mutating `src` under the bot crashes it). Then `cd formal && bash gate.sh` → `ALL GATE PARTS PASSED`, `mutation gate OK`. Regenerate the proof-concept index / extraction if the gate flags drift (projections.py / CheapestPath.lean edits can shift line-refs).

- [ ] **Step 5: Finish** — `superpowers:finishing-a-development-branch` → merge to main.

---

## Notes for the implementer

- Task 1 is the behavioral fix (+ its regression lock); Tasks 2-3 formally gate it. After Task 1 the plan screen already shows the right monster.
- The runtime (`_winnable_farm_target`) and the snapshot (`path_next_action`) are NOT modified — the cascade already reads the projection gated by `is_winnable`, so a winnable projection pick flows straight through. Do not touch player.py.
- Use only API data: `is_winnable` raises on an unknown monster; the candidate loop only iterates `monster_levels` codes (all known).
- Template for the Lean/oracle/differential/mutation mechanics: `git log --grep "dominance-pareto\|accumulation-sell core differential"`.
