# Arbiter Focus-Aging Anti-Starvation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This repo also governs proof+impl work with the `formal-development` skill — invoke it for the Lean tasks (Task 5).

**Goal:** Stop the arbiter from starving an achievable low-value gear root (the 2nd `iron_ring` for `ring2_slot`) behind a stuck, higher-value drop-gated root (`wolf_ears`), by aging the focused root's selection weight down a deterministic falloff curve and deterministically interleaving other reachable roots.

**Architecture:** The gear-root choice is made by the pure argmax `gear_target_pick` in `progression_tree_core.py` (mirrored by `ProgressionTree.lean`). We add three pure functions — a `falloff` curve, a stateless deterministic `interleave_due` scheduler, and `focus_aging_pick` composing them — and swap `decide_tree` to call the aging pick. A per-root focus ledger (`dict[(slot, code), int]`) persists on `GamePlayer`, incremented for the chosen gear root each cycle and cleared on a real-progress event (level-up or a successful non-consumable-equippable craft). Everything in the decision path is exact-rational (`Fraction`), stateless-per-cycle, and deterministic, so the Lean proofs and mutation anchors extend cleanly.

**Tech Stack:** Python 3.13 (`uv run` for everything), `fractions.Fraction` (no float in the decision path), Lean 4 + Mathlib (`formal/`), pytest, mypy strict, ruff, `formal/diff/mutate.py` mutation gate.

## Global Constraints

- Run every Python command via `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- Success criteria for the gate: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- One behavioral class per file. Imports at top of file only. No `...` imports. No `if TYPE_CHECKING`. Never catch `Exception`. No inline imports.
- No float in the decision path — use `fractions.Fraction` (matches the existing `POTION_TYPE_WEIGHTS` pattern in `progression_tree_core.py`).
- Behavior changes ship Lean + mutation anchors in lockstep in the same change.
- Never run `formal/diff/mutate.py` or `formal/gate.sh` concurrently with anything importing `src` (including the bot).
- `gear_target_pick` in `progression_tree_core.py` is NOT wired to a differential oracle (unlike `select_pure`). Its gate is: Lean proof (`ProgressionTree.lean`) + unit test (`tests/test_ai/test_progression_tree_core.py`) + mutation anchors (`PROGRESSION_TREE_MUTATIONS` in `formal/diff/mutate.py`). Follow that precedent — do NOT add an Oracle.lean runner for the pick.
- We do NOT modify `select_pure`, so `formal/diff/test_arbiter_select_diff.py`, `test_decide_key_diff.py`, `test_strategy_traversal_diff.py` must stay untouched and green.

## File Structure

- `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py` — MODIFY. Add `FOCUS_FLAT`, `FOCUS_SPAN`, `FOCUS_FLOOR`, `falloff`, `interleave_due`, `focus_aging_pick`, `focus_aging_order`. Pure data only (no GameData/WorldState).
- `src/artifactsmmo_cli/ai/tiers/progression_tree.py` — MODIFY. `decide_tree` gains `focus`/`cycle` params; calls `focus_aging_pick`/`focus_aging_order` instead of `gear_target_pick`/`_ordered`.
- `src/artifactsmmo_cli/ai/tiers/strategy.py` — MODIFY. `StrategyEngine.decide` gains `focus`/`cycle` params, forwarded to `decide_tree`.
- `src/artifactsmmo_cli/ai/player.py` — MODIFY. Focus ledger field, increment, reset detection, pass into `decide`.
- `formal/Formal/ProgressionTree.lean` — MODIFY. Mirror the three pure functions + new theorems.
- `formal/diff/mutate.py` — MODIFY. Extend `PROGRESSION_TREE_MUTATIONS`.
- `tests/test_ai/test_progression_tree_core.py` — MODIFY. Unit tests for the pure functions (mutation-anchor target).
- `tests/test_ai/test_progression_tree.py` — MODIFY (or create if absent). `decide_tree` aging behavior.
- `tests/test_ai/test_player_focus_ledger.py` — CREATE. Ledger increment + reset detection.
- `tests/test_ai/test_ring2_starvation_repro.py` — CREATE. The headline bug: stuck drop root + craftable ring2 → ring2 realized within window.
- `tests/test_audit/test_craft_completeness.py` — MODIFY. Add a sequential-realization check for a duplicate ring (census gap fix).

---

## Task 1: Falloff curve + constants (pure)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py`
- Test: `tests/test_ai/test_progression_tree_core.py`

**Interfaces:**
- Produces: `FOCUS_FLAT: int`, `FOCUS_SPAN: int`, `FOCUS_FLOOR: Fraction`, `falloff(focus_level: int) -> Fraction`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_progression_tree_core.py` (import `Fraction` and the new names at top of file):

```python
def test_falloff_flat_full_weight_through_flat_window():
    for level in range(0, FOCUS_FLAT + 1):
        assert falloff(level) == Fraction(1)

def test_falloff_reaches_floor_at_and_after_span_end():
    end = FOCUS_FLAT + FOCUS_SPAN
    assert falloff(end) == FOCUS_FLOOR
    assert falloff(end + 50) == FOCUS_FLOOR

def test_falloff_monotone_non_increasing():
    prev = falloff(0)
    for level in range(1, FOCUS_FLAT + FOCUS_SPAN + 20):
        cur = falloff(level)
        assert cur <= prev
        prev = cur

def test_falloff_strictly_decreases_inside_decay_window():
    a = falloff(FOCUS_FLAT + 1)
    b = falloff(FOCUS_FLAT + FOCUS_SPAN - 1)
    assert b < a < Fraction(1)

def test_falloff_floor_is_positive():
    assert FOCUS_FLOOR > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -k falloff -q`
Expected: FAIL — `NameError: name 'falloff' is not defined`.

- [ ] **Step 3: Implement the curve**

Add to `progression_tree_core.py` (after the `POTION_TYPE_WEIGHTS` block; `Fraction` is already imported):

```python
FOCUS_FLAT = 10
"""Iterations a freshly-focused root farms at FULL weight before decay begins.
Below this the aging pick is bit-identical to the plain `gear_target_pick`
argmax (see `focus_aging_pick`)."""

FOCUS_SPAN = 100
"""Iterations over which a focused root's weight decays from 1 to FOCUS_FLOOR.
Decay runs on focus levels (FOCUS_FLAT, FOCUS_FLAT + FOCUS_SPAN]."""

FOCUS_FLOOR = Fraction(1, 8)
"""Minimum weight multiplier (> 0): a stuck drop root is NEVER fully abandoned,
so if its drop finally lands it resumes. Tuning surface — calibrated live
(Task 11)."""


def falloff(focus_level: int) -> Fraction:
    """Selection-weight multiplier for a root that has been the committed focus
    for `focus_level` iterations.

    Flat at 1 through FOCUS_FLAT (farm window), convex (quadratic ease-in)
    decay to FOCUS_FLOOR across the next FOCUS_SPAN iterations, then held at
    FOCUS_FLOOR. Convex so the hand-off is gentle early (keep farming) and
    steepens later. Exact `Fraction` — no float in the decision path. The
    constants are the ONLY tuning surface; the shape (flat -> convex -> floor)
    is pinned by the tests."""
    if focus_level <= FOCUS_FLAT:
        return Fraction(1)
    if focus_level >= FOCUS_FLAT + FOCUS_SPAN:
        return FOCUS_FLOOR
    t = Fraction(focus_level - FOCUS_FLAT, FOCUS_SPAN)
    return Fraction(1) - (Fraction(1) - FOCUS_FLOOR) * t * t
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -k falloff -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/progression_tree_core.py tests/test_ai/test_progression_tree_core.py
git commit -m "feat(arbiter): focus falloff curve (flat->convex->floor, exact Fraction)"
```

---

## Task 2: Deterministic weighted interleave scheduler (pure)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py`
- Test: `tests/test_ai/test_progression_tree_core.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `interleave_due(weighted: list[tuple[str, Fraction]], cycle: int) -> str | None`. `weighted` is `(key, weight)` with `weight > 0`; returns the key scheduled for `cycle`, or `None` if `weighted` is empty. Deterministic function of `(weighted, cycle)` only — no state, no RNG, no wall-clock.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_progression_tree_core.py`:

```python
def test_interleave_empty_is_none():
    assert interleave_due([], 0) is None

def test_interleave_single_key_always_that_key():
    for c in range(0, 20):
        assert interleave_due([("a", Fraction(3))], c) == "a"

def test_interleave_equal_weights_alternate():
    w = [("a", Fraction(1)), ("b", Fraction(1))]
    got = [interleave_due(w, c) for c in range(6)]
    # 1:1 split, deterministic
    assert got.count("a") == 3 and got.count("b") == 3
    assert got == [interleave_due(w, c) for c in range(6)]  # reproducible

def test_interleave_proportional_over_window():
    # weight 3:1 -> "a" gets ~3x the cycles of "b" over a full window
    w = [("a", Fraction(3)), ("b", Fraction(1))]
    got = [interleave_due(w, c) for c in range(4)]
    assert got.count("a") == 3 and got.count("b") == 1

def test_interleave_dominant_weight_gets_every_cycle_when_others_tiny():
    # 1000:1 -> "b" is due at most once per 1001 cycles; the first cycles are all "a"
    w = [("a", Fraction(1000)), ("b", Fraction(1))]
    assert all(interleave_due(w, c) == "a" for c in range(8))

def test_interleave_is_pure_function_of_cycle():
    w = [("a", Fraction(5)), ("b", Fraction(2)), ("c", Fraction(1))]
    assert [interleave_due(w, c) for c in range(20)] == [interleave_due(w, c) for c in range(20)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -k interleave -q`
Expected: FAIL — `NameError: name 'interleave_due' is not defined`.

- [ ] **Step 3: Implement the scheduler**

Add to `progression_tree_core.py`:

```python
def interleave_due(weighted: list[tuple[str, Fraction]], cycle: int) -> str | None:
    """Stateless deterministic weighted round-robin (largest-remainder /
    Bresenham). Over N cycles, key i receives approximately `weight_i / total`
    of the cycles, and the assignment for any single `cycle` is a pure function
    of `(weighted, cycle)` — no accumulator, no RNG, no wall-clock, so it is
    replayable and Lean-mirrorable.

    A key is "due" at `cycle` when its exact cumulative allocation increments
    from `cycle` to `cycle + 1`: floor(w_i*(cycle+1)/total) > floor(w_i*cycle/
    total). When several are due (or none are, at the very first cycles for
    tiny weights) the tie is broken by higher weight then key string — the same
    canonical, hash-independent order `gear_target_pick` uses. `None` only for
    an empty list."""
    if not weighted:
        return None
    total = sum(w for _, w in weighted)
    due: list[tuple[str, Fraction]] = []
    for key, w in weighted:
        prev = (w * cycle) // total
        now = (w * (cycle + 1)) // total
        if now > prev:
            due.append((key, w))
    pool = due if due else list(weighted)
    return max(pool, key=lambda kw: (kw[1], kw[0]))[0]
```

Note: `(w * cycle) // total` is exact-`Fraction` floor division yielding an
integer `Fraction`; comparison is exact.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -k interleave -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/progression_tree_core.py tests/test_ai/test_progression_tree_core.py
git commit -m "feat(arbiter): stateless deterministic weighted interleave scheduler"
```

---

## Task 3: `focus_aging_pick` + `focus_aging_order` (compose)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py`
- Test: `tests/test_ai/test_progression_tree_core.py`

**Interfaces:**
- Consumes: `GearCandidate(slot, code, gain: Fraction, level)`, `gear_target_pick`, `falloff`, `interleave_due`.
- Produces:
  - `focus_aging_pick(candidates: list[GearCandidate], focus: Mapping[tuple[str, str], int], cycle: int) -> GearCandidate | None`
  - `focus_aging_order(candidates: list[GearCandidate], focus: Mapping[tuple[str, str], int], cycle: int) -> list[GearCandidate]` — element 0 always equals `focus_aging_pick(...)`.
- Focus key is `(candidate.slot, candidate.code)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_progression_tree_core.py` (import `GearCandidate`, `gear_target_pick`, `focus_aging_pick`, `focus_aging_order`):

```python
def _gc(slot, code, gain, level=1):
    return GearCandidate(slot=slot, code=code, gain=Fraction(gain), level=level)

def test_aging_pick_empty_focus_equals_argmax():
    cands = [_gc("helmet_slot", "wolf_ears", 18100), _gc("ring2_slot", "iron_ring", 2000)]
    for c in range(50):
        assert focus_aging_pick(cands, {}, c) == gear_target_pick(cands)

def test_aging_pick_below_flat_window_equals_argmax():
    cands = [_gc("helmet_slot", "wolf_ears", 18100), _gc("ring2_slot", "iron_ring", 2000)]
    focus = {("helmet_slot", "wolf_ears"): FOCUS_FLAT}  # exactly at flat edge
    for c in range(50):
        assert focus_aging_pick(cands, focus, c) == gear_target_pick(cands)

def test_aging_pick_decayed_top_yields_some_cycles_to_alt():
    cands = [_gc("helmet_slot", "wolf_ears", 18100), _gc("ring2_slot", "iron_ring", 2000)]
    # push the stuck root deep into decay so its scaled gain approaches the alt
    focus = {("helmet_slot", "wolf_ears"): FOCUS_FLAT + FOCUS_SPAN}  # weight = FOCUS_FLOOR
    picks = {focus_aging_pick(cands, focus, c).code for c in range(40)}
    assert "iron_ring" in picks   # ring2 is no longer starved
    assert "wolf_ears" in picks   # floor keeps the drop root alive

def test_aging_order_head_equals_pick():
    cands = [_gc("helmet_slot", "wolf_ears", 18100), _gc("ring2_slot", "iron_ring", 2000)]
    focus = {("helmet_slot", "wolf_ears"): FOCUS_FLAT + FOCUS_SPAN}
    for c in range(20):
        assert focus_aging_order(cands, focus, c)[0] == focus_aging_pick(cands, focus, c)

def test_aging_order_is_permutation_of_input():
    cands = [_gc("helmet_slot", "wolf_ears", 18100), _gc("ring2_slot", "iron_ring", 2000)]
    focus = {("helmet_slot", "wolf_ears"): 50}
    out = focus_aging_order(cands, focus, 3)
    assert sorted(out, key=lambda c: c.code) == sorted(cands, key=lambda c: c.code)

def test_aging_pick_empty_candidates_is_none():
    assert focus_aging_pick([], {}, 0) is None
    assert focus_aging_order([], {}, 0) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -k aging -q`
Expected: FAIL — `NameError: name 'focus_aging_pick' is not defined`.

- [ ] **Step 3: Implement the composition**

Add to `progression_tree_core.py` (add `from collections.abc import Mapping` to the top-of-file imports next to `Callable`-style imports):

```python
def _scaled_weights(candidates: list[GearCandidate],
                    focus: Mapping[tuple[str, str], int]
                    ) -> list[tuple[str, Fraction]]:
    """(slot-keyed weight) = base gain * falloff(focus level) per candidate.
    Keyed by SLOT — unique per candidate (one gear candidate per slot), so two
    same-code candidates (e.g. iron_ring targeting ring1_slot AND ring2_slot)
    stay distinct; keying by code would collapse them. The caller maps the
    winning slot back to its GearCandidate."""
    return [(c.slot, c.gain * falloff(focus.get((c.slot, c.code), 0)))
            for c in candidates]


def focus_aging_pick(candidates: list[GearCandidate],
                     focus: Mapping[tuple[str, str], int],
                     cycle: int) -> GearCandidate | None:
    """The gear root to pursue THIS cycle, with anti-starvation aging.

    While every candidate is still inside its flat farm window (focus <=
    FOCUS_FLAT) the result is bit-identical to the proven `gear_target_pick`
    argmax — no jitter for fresh roots. Once any candidate has been focused
    past the flat window, its selection weight decays (see `falloff`) and the
    pick is drawn by the deterministic weighted interleave over scaled gains,
    so a decayed stuck root hands cycles to reachable alternatives without ever
    being fully abandoned (FOCUS_FLOOR > 0)."""
    if not candidates:
        return None
    if all(focus.get((c.slot, c.code), 0) <= FOCUS_FLAT for c in candidates):
        return gear_target_pick(candidates)
    winner_slot = interleave_due(_scaled_weights(candidates, focus), cycle)
    return next(c for c in candidates if c.slot == winner_slot)


def focus_aging_order(candidates: list[GearCandidate],
                      focus: Mapping[tuple[str, str], int],
                      cycle: int) -> list[GearCandidate]:
    """Display/fallback order whose head is exactly `focus_aging_pick` and
    whose tail is the remaining candidates in the canonical argmax order
    (`gear_target_pick`'s total order). Keeps `decide_tree`'s
    `ordered[0] == pick` invariant intact under aging."""
    if not candidates:
        return []
    pick = focus_aging_pick(candidates, focus, cycle)
    rest = sorted((c for c in candidates if c is not pick),
                  key=lambda c: (-c.gain, -c.level, c.code, c.slot))
    return [pick, *rest]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -k aging -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Run the whole core file + mypy**

Run: `uv run pytest tests/test_ai/test_progression_tree_core.py -q && uv run mypy src/artifactsmmo_cli/ai/tiers/progression_tree_core.py`
Expected: PASS, no type errors.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/progression_tree_core.py tests/test_ai/test_progression_tree_core.py
git commit -m "feat(arbiter): focus_aging_pick/order compose falloff+interleave (argmax when unaged)"
```

---

## Task 4: Thread `focus`/`cycle` into `decide_tree` and `StrategyEngine.decide`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree.py:200-293` (`decide_tree`), and its `_ordered` usage at 235-236, 280.
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`StrategyEngine.decide`).
- Test: `tests/test_ai/test_progression_tree.py`

**Interfaces:**
- Consumes: `focus_aging_pick`, `focus_aging_order` from Task 3.
- Produces: `decide_tree(..., focus: Mapping[tuple[str, str], int] = {}, cycle: int = 0)` and `StrategyEngine.decide(..., focus: Mapping[tuple[str, str], int] = {}, cycle: int = 0)`. Defaults reproduce today's argmax behavior for every existing caller (empty focus → all levels 0 ≤ FOCUS_FLAT → `focus_aging_pick == gear_target_pick`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_progression_tree.py` (reuse existing GameData/state builders in that file; build two gear candidates where a decayed top hands off to the alt). Minimal shape:

```python
def test_decide_tree_aging_hands_off_stuck_top(self):
    # Build a state + game_data yielding two gear candidates:
    #   high-gain "wolf_ears"->helmet_slot, low-gain "iron_ring"->ring2_slot.
    # (Follow the existing candidate-construction helpers in this test module.)
    state, gd, objective = _two_gear_candidate_fixture()  # helper added alongside
    stuck_key = ("helmet_slot", "wolf_ears")
    focus = {stuck_key: FOCUS_FLAT + FOCUS_SPAN}  # fully decayed
    seen = set()
    for cyc in range(40):
        d = decide_tree(state, gd, objective, band_adequate=False, focus=focus, cycle=cyc)
        seen.add(repr(d.chosen_root))
    assert any("ring2_slot" in r for r in seen)   # starved root now runs
    assert any("helmet_slot" in r for r in seen)  # floor keeps drop root alive

def test_decide_tree_empty_focus_matches_argmax(self):
    state, gd, objective = _two_gear_candidate_fixture()
    d0 = decide_tree(state, gd, objective, band_adequate=False)              # defaults
    d1 = decide_tree(state, gd, objective, band_adequate=False, focus={}, cycle=7)
    assert repr(d0.chosen_root) == repr(d1.chosen_root)  # helmet (argmax) both
```

If `_two_gear_candidate_fixture` has no analogue in the file, build it from the
existing `GameData()` + `make_state` helpers used by the other tests in the
module (two ring/helmet item stats + recipes so both slots yield a candidate).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_progression_tree.py -k aging_hands_off -q`
Expected: FAIL — `decide_tree() got an unexpected keyword argument 'focus'`.

- [ ] **Step 3: Modify `decide_tree`**

In `progression_tree.py`:
- Add imports: `from collections.abc import Mapping`, and add `focus_aging_pick, focus_aging_order` to the existing `from ...progression_tree_core import (...)` block (keep `gear_target_pick`, `_ordered` may stay for other uses).
- Change the signature (line 200-205) to add the two params before the return type:

```python
def decide_tree(state: WorldState, game_data: GameData,
                objective: CharacterObjective,
                band_adequate: bool = False,
                step_servable: Callable[[MetaGoal, MetaGoal], bool] | None = None,
                ctx: SelectionContext = NO_PROFILE_CONTEXT,
                focus: Mapping[tuple[str, str], int] = {},
                cycle: int = 0,
                ) -> "strategy.StrategyDecision":
```

- Replace the pick/order computation (lines 235-236) with:

```python
    ordered = focus_aging_order(candidates, focus, cycle)
    pick = focus_aging_pick(candidates, focus, cycle) if candidates else None
```

- The existing assert at 241 (`ordered[0] == pick`) still holds (Task 3
  guarantees it) — leave it unchanged.
- `_gear_ranking_rows(state, game_data, ordered, ctx)` at line 280 now receives
  the aged order; leave the call as-is (ranking display follows the aged head,
  matching what the arbiter pursues).

Note on the mutable default `focus={}`: it is read-only in `decide_tree` (only
`.get`), so the shared-default is safe; do NOT mutate it here. (The ledger is
owned and mutated by `GamePlayer`, Task 6.)

- [ ] **Step 4: Modify `StrategyEngine.decide`**

In `strategy.py`, add the two params to `decide` and forward them:

```python
    def decide(self, state: WorldState, game_data: GameData,
               step_servable: Callable[[MetaGoal, MetaGoal], bool] | None = None,
               band_adequate: bool = False,
               ctx: SelectionContext = NO_PROFILE_CONTEXT,
               focus: Mapping[tuple[str, str], int] = {},
               cycle: int = 0,
               ) -> StrategyDecision:
        ...
        return progression_tree.decide_tree(
            state, game_data, self.objective,
            band_adequate=band_adequate, step_servable=step_servable,
            ctx=ctx, focus=focus, cycle=cycle)
```

Add `from collections.abc import Mapping` if not already imported.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_progression_tree.py -q && uv run pytest tests/test_ai/test_strategy.py -q`
Expected: PASS (new aging tests + existing decide/engine tests unchanged).

- [ ] **Step 6: mypy + commit**

```bash
uv run mypy src/artifactsmmo_cli/ai/tiers/progression_tree.py src/artifactsmmo_cli/ai/tiers/strategy.py
git add src/artifactsmmo_cli/ai/tiers/progression_tree.py src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_progression_tree.py
git commit -m "feat(arbiter): thread focus/cycle through decide_tree + StrategyEngine.decide"
```

---

## Task 5: Lean lockstep — mirror the pure functions + theorems

**Files:**
- Modify: `formal/Formal/ProgressionTree.lean`
- Build: `cd formal && lake build`

**Interfaces:**
- Mirror (Python → Lean): `falloff` → `falloff (focusLevel : Nat) : Rat`; `interleave_due` → `interleaveDue (weighted : List (String × Rat)) (cycle : Nat) : Option String`; `focus_aging_pick` → `focusAgingPick (cs : List GearCand) (focus : List (String × Nat)) (cycle : Nat) : Option GearCand`. Use the existing `GearCand` struct (`slot, code : String; gain : Rat; level : Nat`) and `gearTargetPick`.

**Process:** Invoke the `formal-development` skill / `lean4:prove` + `lean4:proof-repair` agents to develop the proofs. This task is done when `lake build` is green with no `sorry` and no new axioms.

- [ ] **Step 1: Add the Lean definitions** mirroring the Python exactly (constants `focusFlat := 10`, `focusSpan := 100`, `focusFloor := (1 : Rat)/8`; convex decay `1 - (1 - focusFloor) * t^2` with `t := (focusLevel - focusFlat)/focusSpan`). `interleaveDue` uses `Rat` floor (`⌊w * cycle / total⌋`) for the "due" test and the `(weight, key)` max tiebreak. `focusAgingPick` returns `gearTargetPick cs` when all focus levels `≤ focusFlat`, else maps `interleaveDue` over scaled weights.

- [ ] **Step 2: State and prove the theorems** (statements to add; prove each):

```lean
theorem falloff_flat (l : Nat) (h : l ≤ focusFlat) : falloff l = 1
theorem falloff_floor_after (l : Nat) (h : focusFlat + focusSpan ≤ l) : falloff l = focusFloor
theorem falloff_floor_pos : (0 : Rat) < focusFloor
theorem falloff_antitone {a b : Nat} (h : a ≤ b) : falloff b ≤ falloff a
-- backward compatibility: unaged pick IS the proven argmax
theorem focusAgingPick_unaged_eq_argmax
    (cs : List GearCand) (focus : List (String × Nat)) (cycle : Nat)
    (h : ∀ c ∈ cs, (focusLevelOf focus c) ≤ focusFlat) :
    focusAgingPick cs focus cycle = gearTargetPick cs
-- no permanent starvation: any positive-weight key is due within a bounded window
theorem interleaveDue_reaches
    (weighted : List (String × Rat)) (key : String) (w : Rat)
    (hpos : 0 < w) (hmem : (key, w) ∈ weighted) :
    ∃ c, c < interleaveWindow weighted ∧ interleaveDue weighted c = some key
```

(`focusLevelOf` and `interleaveWindow` are small helpers you define alongside;
`interleaveWindow` is `⌈total / w_min⌉` or similar — pick the exact bound the
proof needs.)

- [ ] **Step 3: Build**

Run: `cd formal && lake build`
Expected: build succeeds, no `sorry`, no new axiom warnings (check with the repo's axiom-hygiene step if present).

- [ ] **Step 4: Commit**

```bash
git add formal/Formal/ProgressionTree.lean
git commit -m "feat(formal): mirror focus-aging pick in ProgressionTree.lean + no-starvation proof"
```

---

## Task 6: `GamePlayer` focus ledger — increment + reset

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (`__init__` around 143-182; the two `_strategy.decide(...)` calls at ~255 and ~487; the post-execution bookkeeping near `_record_cycle`/action execution).
- Test: `tests/test_ai/test_player_focus_ledger.py` (CREATE)

**Interfaces:**
- Consumes: `StrategyEngine.decide(..., focus=, cycle=)` (Task 4).
- Produces: `GamePlayer._gear_focus: dict[tuple[str, str], int]`, helper `_gear_root_key(root: MetaGoal) -> tuple[str, str] | None`, `_bump_focus(decision)`, `_maybe_reset_focus(prev_level, executed_action, outcome)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_player_focus_ledger.py`:

```python
from artifactsmmo_cli.ai.player import GamePlayer
# use the module's existing test construction pattern (see other test_player_*.py)

def test_gear_root_key_extracts_slot_code():
    # ObtainItem(code='iron_ring', slot='ring2_slot') -> ('ring2_slot', 'iron_ring')
    key = GamePlayer._gear_root_key(_obtain_item("iron_ring", "ring2_slot"))
    assert key == ("ring2_slot", "iron_ring")

def test_gear_root_key_none_for_non_gear_root():
    assert GamePlayer._gear_root_key(_reach_char_level(20)) is None

def test_bump_increments_chosen_gear_root():
    p = _bare_player()
    p._gear_focus = {}
    p._bump_focus(_decision_with_root(_obtain_item("wolf_ears", "helmet_slot")))
    p._bump_focus(_decision_with_root(_obtain_item("wolf_ears", "helmet_slot")))
    assert p._gear_focus[("helmet_slot", "wolf_ears")] == 2

def test_reset_on_level_up_clears_ledger():
    p = _bare_player()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    p._maybe_reset_focus(prev_level=14, cur_level=15, executed_action=None, outcome="ok")
    assert p._gear_focus == {}

def test_reset_on_equippable_craft_clears_ledger():
    p = _bare_player()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    craft = _craft_action("iron_ring")   # iron_ring is a ring (equippable)
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="ok")
    assert p._gear_focus == {}

def test_no_reset_on_consumable_craft():
    p = _bare_player()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    craft = _craft_action("small_health_potion")  # utility/consumable -> NOT a reset
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="ok")
    assert p._gear_focus == {("helmet_slot", "wolf_ears"): 40}

def test_no_reset_on_failed_craft():
    p = _bare_player()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    craft = _craft_action("iron_ring")
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="error")
    assert p._gear_focus == {("helmet_slot", "wolf_ears"): 40}
```

Write the small `_bare_player`, `_obtain_item`, `_reach_char_level`,
`_decision_with_root`, `_craft_action` helpers using the construction already
used by the other `tests/test_ai/test_player_*.py` files (real fixtures, no
mocking of the unit under test).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_player_focus_ledger.py -q`
Expected: FAIL — `AttributeError: ... '_gear_root_key'`.

- [ ] **Step 3: Implement the ledger on `GamePlayer`**

In `player.py __init__` add:

```python
        self._gear_focus: dict[tuple[str, str], int] = {}
```

Add the helpers (static/instance as signatured):

```python
    @staticmethod
    def _gear_root_key(root: "MetaGoal") -> tuple[str, str] | None:
        """(slot, code) for a slot-tagged gear obtain root, else None.
        Non-gear roots (ReachCharLevel, task roots without a slot) do not age."""
        code = getattr(root, "code", None)
        slot = getattr(root, "slot", None)
        if isinstance(code, str) and isinstance(slot, str):
            return (slot, code)
        return None

    def _bump_focus(self, decision: "StrategyDecision") -> None:
        key = self._gear_root_key(decision.chosen_root)
        if key is not None:
            self._gear_focus[key] = self._gear_focus.get(key, 0) + 1

    def _maybe_reset_focus(self, prev_level: int, cur_level: int,
                           executed_action: "Action | None", outcome: str) -> None:
        """Clear the aging ledger on real progress: a level-up, or a successful
        craft of a non-consumable EQUIPPABLE item. Consumables/potions and
        failed actions do NOT reset (the drop root must not get a free farm
        window for churning potions)."""
        if cur_level > prev_level:
            self._gear_focus.clear()
            return
        if outcome != "ok" or executed_action is None:
            return
        crafted = getattr(executed_action, "code", None)
        if not isinstance(crafted, str) or getattr(executed_action, "name", "") != "Craft":
            return
        stats = self._game_data.item_stats(crafted)
        if stats is None:
            return
        if stats.type_ in EQUIPMENT_SLOT_TYPES and stats.type_ != "utility":
            self._gear_focus.clear()
```

Use the existing equippable-type predicate the codebase already has (the
`ITEM_TYPE_TO_SLOTS` keys, minus `"utility"`) rather than a new hardcoded set —
import and reuse it as `EQUIPMENT_SLOT_TYPES` (define it as
`frozenset(ITEM_TYPE_TO_SLOTS) - {"utility"}` next to the other module-level
constants if no equivalent exists). This keeps the keep/junk categorization
generic over the API taxonomy.

- [ ] **Step 4: Wire the calls**

At each `self._strategy.decide(...)` call (~255 and ~487), pass the ledger and
cycle, capturing the prior level first:

```python
        prev_level = state.level
        decision = self._strategy.decide(
            state, game_data, ...,             # existing args unchanged
            focus=self._gear_focus, cycle=self._cycle_counter)
        self._bump_focus(decision)
```

After the selected action executes and its outcome is known (near
`_record_cycle`), call:

```python
        self._maybe_reset_focus(prev_level, state_after.level, executed_action, outcome)
```

Follow the existing variable names in `player.py` for `state_after` /
`executed_action` / `outcome` (the cycle-record path already has these).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_player_focus_ledger.py -q`
Expected: PASS (7 tests).

- [ ] **Step 6: mypy + commit**

```bash
uv run mypy src/artifactsmmo_cli/ai/player.py
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_focus_ledger.py
git commit -m "feat(arbiter): GamePlayer gear-focus ledger — bump chosen root, reset on level-up/equippable-craft"
```

---

## Task 7: Mutation anchors for the pure functions

**Files:**
- Modify: `formal/diff/mutate.py` (`PROGRESSION_TREE_MUTATIONS`, line ~2658)

**Interfaces:**
- Consumes: the exact source lines of `falloff`, `interleave_due`, `focus_aging_pick` from Tasks 1-3.

- [ ] **Step 1: Add mutation tuples**

Append to `PROGRESSION_TREE_MUTATIONS` (each `(description, old_string, new_string)` must match the source verbatim — copy from the committed file). Add at minimum:

```python
    ("falloff: floor instead of full weight in flat window",
     "    if focus_level <= FOCUS_FLAT:\n        return Fraction(1)",
     "    if focus_level <= FOCUS_FLAT:\n        return FOCUS_FLOOR"),
    ("falloff: drop the convex decay term",
     "    return Fraction(1) - (Fraction(1) - FOCUS_FLOOR) * t * t",
     "    return Fraction(1)"),
    ("interleave: invert due test",
     "        if now > prev:",
     "        if now < prev:"),
    ("interleave: tiebreak on lowest weight",
     "    return max(pool, key=lambda kw: (kw[1], kw[0]))[0]",
     "    return min(pool, key=lambda kw: (kw[1], kw[0]))[0]"),
    ("aging pick: never take the argmax fast-path",
     "    if all(focus.get((c.slot, c.code), 0) <= FOCUS_FLAT for c in candidates):\n        return gear_target_pick(candidates)",
     "    if False:\n        return gear_target_pick(candidates)"),
```

- [ ] **Step 2: Run the mutation group for the progression tree**

Run: `uv run python formal/diff/mutate.py --group progression_tree` (use the actual group selector the script exposes; if it runs all groups, run the whole file per the repo's normal invocation). Ensure you are NOT running the bot concurrently.
Expected: every new mutant is KILLED by `tests/test_ai/test_progression_tree_core.py` (0 survivors in the new tuples). If a mutant survives, add/strengthen a unit test in Task 1-3's file to kill it, then re-run.

- [ ] **Step 3: Commit**

```bash
git add formal/diff/mutate.py
git commit -m "test(formal): mutation anchors for focus falloff/interleave/aging-pick"
```

---

## Task 8: Repro test — ring2 no longer starves behind a stuck drop root

**Files:**
- Test: `tests/test_ai/test_ring2_starvation_repro.py` (CREATE)

This is the headline regression test for the bug in the spec. It drives the
FULL decision path (not the pure core in isolation) to prove the fix.

**Interfaces:**
- Consumes: `GamePlayer` / `StrategyEngine.decide` with the focus ledger.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_ring2_starvation_repro.py`. Build a `GameData` with:
`iron_ring` (type `ring`, craftable from a gatherable material) and `wolf_ears`
(type `helmet`, a monster drop with NO craft recipe and a monster the character
cannot beat — so the drop root is permanently unachievable). State: level with
`ring1_slot` already wearing `iron_ring`, `ring2_slot` empty, helmet worn is a
weaker helmet so `wolf_ears` scores far higher.

```python
def test_stuck_drop_root_does_not_starve_the_craftable_second_ring():
    state, gd, objective = _stuck_wolf_ears_plus_craftable_ring2()
    engine = StrategyEngine(objective, BalancedPersonality())
    focus: dict[tuple[str, str], int] = {}
    chosen_ring2 = False
    for cyc in range(FOCUS_FLAT + FOCUS_SPAN + 20):
        d = engine.decide(state, gd, band_adequate=False, focus=focus, cycle=cyc)
        key = ("ring2_slot", "iron_ring")
        wk = ("helmet_slot", "wolf_ears")
        chosen = repr(d.chosen_root)
        if "ring2_slot" in chosen:
            chosen_ring2 = True
        # simulate the ledger bump the player does
        if "helmet_slot" in chosen:
            focus[wk] = focus.get(wk, 0) + 1
        elif "ring2_slot" in chosen:
            focus[key] = focus.get(key, 0) + 1
    assert chosen_ring2, "ring2 iron_ring was never chosen — still starved"

def test_pre_fix_behavior_absent_aging_would_starve():
    # Sanity: with focus frozen empty (aging disabled), the argmax picks
    # wolf_ears every cycle — documents the exact bug the aging fixes.
    state, gd, objective = _stuck_wolf_ears_plus_craftable_ring2()
    engine = StrategyEngine(objective, BalancedPersonality())
    picks = {repr(engine.decide(state, gd, band_adequate=False, focus={}, cycle=c).chosen_root)
             for c in range(30)}
    assert all("helmet_slot" in p or "char_level" in p.lower() for p in picks) or \
        any("helmet_slot" in p for p in picks)
```

- [ ] **Step 2: Run test to verify it fails without the fix / passes with it**

Run: `uv run pytest tests/test_ai/test_ring2_starvation_repro.py -q`
Expected: `test_stuck_drop_root_does_not_starve...` PASSES with the aging in
place. (To confirm it is a real guard, temporarily set `FOCUS_FLOOR = Fraction(0)`
and a no-op `falloff` locally and observe it FAIL — then revert.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_ai/test_ring2_starvation_repro.py
git commit -m "test(arbiter): repro — stuck drop root no longer starves craftable ring2"
```

---

## Task 9: Census gap fix — sequential duplicate-ring realization

**Files:**
- Test: `tests/test_audit/test_craft_completeness.py` (MODIFY — add near the
  existing `census_state` tests around line 731).

The existing census pre-fills BOTH ring slots by fiat via `near_term_gear`,
so it can never observe "one ring crafted, second never". Add a check that the
census's near-term gear for a ring type actually assigns BOTH ring slots (the
target-setting half the runtime relies on), documenting the fiat and pinning
the assignment the aging path depends on.

**Interfaces:**
- Consumes: `CharacterObjective.near_term_gear`, `census_state`.

- [ ] **Step 1: Write the failing test**

```python
def test_near_term_gear_targets_both_ring_slots_for_a_ring() -> None:
    """Regression pin for the ring2 starvation class: near_term_gear must assign
    the best ring to BOTH ring1_slot and ring2_slot (the aspirational target the
    runtime aging path then realizes sequentially). If this ever drops ring2,
    the runtime can never even form the ring2 root."""
    gd = GameData()
    gd._item_stats = {
        "iron_ring": ItemStats(code="iron_ring", level=1, type_="ring",
                               subtype="", attack={"fire": 20}),
    }
    gd._resource_drops = {"iron_vein": "iron_ring"}
    bare = scenario_state(
        ScenarioCharacter(name="census_bare", level=5, skills={}), gd)
    gear = CharacterObjective.from_game_data(gd).near_term_gear(bare)
    assert gear.get("ring1_slot") == "iron_ring"
    assert gear.get("ring2_slot") == "iron_ring"
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_audit/test_craft_completeness.py -k both_ring_slots -q`
Expected: PASS if `_slot_assignments` already assigns both (it does today); this
locks that behavior so a future change can't silently drop ring2 and re-open the
starvation from the target-setting side.

- [ ] **Step 3: Commit**

```bash
git add tests/test_audit/test_craft_completeness.py
git commit -m "test(audit): pin near_term_gear assigns both ring slots (ring2 starvation guard)"
```

---

## Task 10: Full gate

**Files:** none (verification only).

- [ ] **Step 1: Run the Python suite (parallel runner)**

Run: `uv run bash scripts/run_tests.sh` (the repo's 2-lane runner; falls back to `uv run pytest -n auto` if the script differs). Ensure nothing else importing `src` runs concurrently.
Expected: 0 failures, 0 warnings, 0 skipped, 100% coverage.

- [ ] **Step 2: Types + lint**

Run: `uv run mypy src && uv run ruff check src tests`
Expected: clean.

- [ ] **Step 3: Formal build + differential + mutation**

Run:
```bash
cd formal && lake build && lake build oracle && cd ..
uv run pytest formal/diff/ -q --no-cov -n auto
uv run python formal/diff/mutate.py
```
Expected: Lean builds with no `sorry`/new axioms; all diff oracles green
(`test_arbiter_select_diff`, `test_decide_key_diff`, `test_strategy_traversal_diff`
UNCHANGED and passing — we did not touch `select_pure`); mutation survivors = 0
(including the new progression-tree anchors).

- [ ] **Step 4: Fix any fallout in-place**, then re-run the failed gate step. Do
  not simplify or skip. If an existing test asserted the old single-argmax gear
  pick under a real (non-empty) cycle with aging engaged, update it to the aged
  expectation (the default-args path is unchanged, so most should be unaffected).

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "test(arbiter): gate green — focus-aging lockstep (pytest/mypy/ruff/formal/mutation)"
```

---

## Task 11: Live calibration of the falloff constants

**Files:**
- Modify (tuning only): `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py`
  (`FOCUS_FLAT`, `FOCUS_SPAN`, `FOCUS_FLOOR`) and its Lean mirror if changed.

The unit tests pin the curve SHAPE and invariants, not exact percentages, so
tuning these constants stays green. Calibrate them against the real trace so a
stuck drop root hands ~half its cycles to the craftable alternative around the
intended window (the spec's "≈50% by iter 60" target for the wolf_ears≈9×ring2
gain ratio).

- [ ] **Step 1: Reproduce the scenario offline**

Run: `uv run artifactsmmo plan Robby` (or a short sim from a state matching the
trace: `ring1_slot` iron_ring, `ring2_slot` empty, stuck helmet root). Observe
how many cycles until `ObtainItem(...ring2_slot)` is first chosen with the
current constants.

- [ ] **Step 2: Tune** `FOCUS_FLOOR` / `FOCUS_SPAN` so the hand-off lands in the
  desired window. Keep `FOCUS_FLOOR > 0`. If a large gain ratio makes the exact
  "50% by 60" unreachable with a positive floor (it can be — floor 1/8 > the
  1/9 the wolf_ears ratio needs), record the achieved split and confirm with the
  user rather than forcing an inconsistent curve.

- [ ] **Step 3: Re-run the gate** (Task 10 steps) after any constant change —
  Lean mirror must move in lockstep if you touched the constants there.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "tune(arbiter): calibrate focus-aging constants against Robby trace"
```

---

## Self-review notes (for the executor)

- Spec coverage: §1 ledger → Task 6; §2 falloff → Task 1/5; §3 interleave +
  plan-leg atomicity → Task 2 (atomicity is inherited — the aging only changes
  WHICH gear root is chosen; sticky commitment in `select_pure` still holds a
  chosen root through its plan legs, so no mid-craft switching is introduced);
  §4 resets → Task 6; §5 rotation pool (gear/task/material) → Tasks 3-6 age the
  gear candidates; task/material roots already surface via `fallback_roots` when
  the gear head yields, and the aged head yielding is exactly what lets them run
  (verify in Task 8 that a non-gear fallback can win once the gear head is
  decayed — extend the repro if needed); §6 formal/tests → Tasks 5,7,8,9.
- Plan-leg atomicity claim depends on `select_pure` sticky commitment being
  unchanged (Global Constraints) — confirmed we do not touch it.
- Open constants (`FOCUS_FLAT/SPAN/FLOOR`, curve shape) are tuning surface,
  calibrated in Task 11; tests pin shape/invariants only.
