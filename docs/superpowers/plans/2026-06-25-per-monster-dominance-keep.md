# Per-Monster-Aware Dominance Keep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep a weapon/armor piece that is the strictly-best choice against some winnable near-level monster (element/crit matchup), instead of selling it because a flat `equip_value` peer outranks it.

**Architecture:** A new pure `pareto_dominates(peer_scores, item_scores)` core replaces the per-peer `higher` verdict inside `_is_equippable_dominated`; the verdict is computed from per-monster `weapon_score`/`armor_score` vectors over the winnable near-level monster set (new `combat_targets.py`). The proved `_is_dominated_pure` fold and the `weapon_score`/`armor_score` cores are reused unchanged; flat-`equip_value` fallback when no winnable target or a non-weapon/armor type.

**Tech Stack:** Python 3.13 (`uv run`, `~/.local/bin/uv`), Lean 4 (formal/), Hypothesis differential + mutation gate.

## Global Constraints

- `~/.local/bin/uv run …`; focused tests use `--no-cov` (repo enforces 100% globally). 100% coverage required.
- No inline imports; one behavioral class per file; never catch `Exception`; use only API data or fail.
- `LEVEL_BAND_BELOW = 5`. Monster set upper end = beatability frontier via `is_winnable` (no fixed offset above).
- `pareto_dominates(peer, item)` = `all(p>=i) and any(p>i)` over the per-monster score vectors (exact int).
- Per-monster score: weapon (`type_=="weapon"`) → `equipment.scoring.weapon_score(stats, game_data.monster_resistance(m))`; armor (`type_ in {"helmet","body_armor","leg_armor","boots","shield"}`) → `equipment.scoring.armor_score(stats, game_data.monster_attack(m))`. Both already proven exact-int. `monster_resistance`/`monster_attack` are `dict[str,int]` accessors (game_data.py:567,573).
- Empty monster set OR non-weapon/armor equippable → flat `_equip_value` dominance (today's behavior, unchanged).
- Formal: safety axioms ⊆ {propext, Classical.choice, Quot.sound}; 100% kernel-checked, no sorry/native_decide.

---

### Task 1: `pareto_dominates` pure core

**Files:**
- Create: `src/artifactsmmo_cli/ai/dominance_pareto.py`
- Test: `tests/test_ai/test_dominance_pareto.py`

**Interfaces:**
- Produces: `pareto_dominates(peer_scores: list[int], item_scores: list[int]) -> bool`.

- [ ] **Step 1: Failing test**

```python
from artifactsmmo_cli.ai.dominance_pareto import pareto_dominates


def test_pareto_dominates_truth_table():
    assert pareto_dominates([5, 5], [3, 4]) is True     # >= all, > some
    assert pareto_dominates([5, 4], [3, 4]) is True      # tie on one, > other
    assert pareto_dominates([3, 4], [3, 4]) is False     # equal everywhere
    assert pareto_dominates([5, 2], [3, 4]) is False     # loses on monster 2
    assert pareto_dominates([], []) is False             # no monsters → not dominated
    assert pareto_dominates([3], [5]) is False
```

- [ ] **Step 2: Run → FAIL** (`~/.local/bin/uv run pytest tests/test_ai/test_dominance_pareto.py -q --no-cov`).

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/dominance_pareto.py
# dominance_pareto

"""Per-monster Pareto dominance: a peer dominates an item iff it scores at least
as high against EVERY monster and strictly higher against at least one. Pure,
integer-exact (mirrors Lean `Formal.DominancePareto.paretoDominates`)."""


def pareto_dominates(peer_scores: list[int], item_scores: list[int]) -> bool:
    """True iff `peer_scores >= item_scores` componentwise AND strictly greater
    on at least one component. Empty vectors → False (nothing to dominate)."""
    geq_all = all(p >= i for p, i in zip(peer_scores, item_scores))
    gt_some = any(p > i for p, i in zip(peer_scores, item_scores))
    return geq_all and gt_some
```

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `git commit -m "feat(dominance): pareto_dominates pure core"`

> Note: `zip` truncates to the shorter list; the two vectors are always the same length (same monster set), but the empty-vector case (`any([])==False`) gives the desired `False`.

---

### Task 2: `combat_target_monsters` — winnable near-level set (memoized)

**Files:**
- Create: `src/artifactsmmo_cli/ai/combat_targets.py`
- Test: `tests/test_ai/test_combat_targets.py`

**Interfaces:**
- Consumes: `combat.is_winnable(state, game_data, monster_code, history)`, `game_data.monster_levels` (Mapping[str,int]).
- Produces: `combat_target_monsters(state, game_data) -> list[str]`, `LEVEL_BAND_BELOW = 5`, `_clear_cache()` (test hook).

- [ ] **Step 1: Failing test**

```python
from artifactsmmo_cli.ai.combat_targets import (
    LEVEL_BAND_BELOW, combat_target_monsters, _clear_cache,
)
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
import artifactsmmo_cli.ai.combat_targets as ct


def _gd(levels):
    gd = GameData()
    gd._monster_level = dict(levels)
    return gd


def test_set_excludes_too_low_and_unwinnable(monkeypatch):
    _clear_cache()
    gd = _gd({"chick": 1, "wolf": 9, "dragon": 40})
    # winnable: everything <= level 10; dragon (40) unwinnable.
    monkeypatch.setattr(ct, "is_winnable",
                        lambda s, g, code, h=None: g._monster_level[code] <= 10)
    state = make_state(level=10)
    got = combat_target_monsters(state, gd)
    assert "wolf" in got              # level 9 >= 10-5 and winnable
    assert "chick" not in got         # level 1 < 10-5 (too low)
    assert "dragon" not in got        # unwinnable


def test_memoized_per_level_and_equipment(monkeypatch):
    _clear_cache()
    calls = {"n": 0}
    def fake(s, g, code, h=None):
        calls["n"] += 1
        return True
    monkeypatch.setattr(ct, "is_winnable", fake)
    gd = _gd({"wolf": 9})
    state = make_state(level=10)
    combat_target_monsters(state, gd)
    n_after_first = calls["n"]
    combat_target_monsters(state, gd)            # same key → cache hit
    assert calls["n"] == n_after_first
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/ai/combat_targets.py
# combat_targets

"""The winnable near-level monster set used to keep situationally-best gear.

Memoized single-entry on `(id(game_data), character level, equipment signature)`
because the dominance check that consumes it runs per inventory item. `is_winnable`
is called with `history=None` (cold/stat beatability) — the keep decision uses the
optimistic prediction, not the learned-loss veto, matching how planning calls it."""

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

LEVEL_BAND_BELOW = 5
"""A monster whose level is at least `character level - LEVEL_BAND_BELOW` counts as
one we might fight; the upper end is the beatability frontier (`is_winnable`)."""

_cache: dict[str, object] = {}


def _clear_cache() -> None:
    """Reset the single-entry memo (test hook; also harmless in production)."""
    _cache.clear()


def combat_target_monsters(state: WorldState, game_data: GameData) -> list[str]:
    """Codes of winnable monsters at or above `level - LEVEL_BAND_BELOW`."""
    equip_sig = tuple(sorted(c for c in state.equipment.values() if c is not None))
    key = (id(game_data), state.level, equip_sig)
    if _cache.get("key") == key:
        return _cache["val"]  # type: ignore[return-value]
    floor = state.level - LEVEL_BAND_BELOW
    out = [code for code, level in game_data.monster_levels.items()
           if level >= floor and is_winnable(state, game_data, code, None)]
    _cache["key"] = key
    _cache["val"] = out
    return out
```

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `git commit -m "feat(dominance): combat_target_monsters winnable near-level set"`

> Confirm `game_data._monster_level` is the backing field for `monster_levels` (game_data.py:845); if the property reads a different attr, set that in the fixture. Add `_clear_cache()` at the top of each test that exercises the memo to avoid cross-test pollution.

---

### Task 3: per-monster path in `_is_equippable_dominated`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/inventory_caps.py` (`_is_equippable_dominated`)
- Test: `tests/test_ai/test_per_monster_dominance.py`

**Interfaces:**
- Consumes: `pareto_dominates` (T1), `combat_target_monsters` (T2), `equipment.scoring.weapon_score`/`armor_score`, `_is_dominated_pure` (existing), `_equip_value` (existing).
- Produces: `_score_vector(stats, monsters, game_data) -> list[int]` (module-private helper in inventory_caps.py), updated `_is_equippable_dominated`.

- [ ] **Step 1: Failing test** (fire_staff kept vs iron_sword when a fire-weak monster is in the set; strictly-outclassed weapon still dominated; empty set → flat fallback)

```python
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_caps import _is_equippable_dominated
import artifactsmmo_cli.ai.combat_targets as ct
from artifactsmmo_cli.ai.combat_targets import _clear_cache
from tests.test_ai.fixtures import make_state


def _wstate(inv):
    return make_state(level=10, inventory=inv)


def test_both_weapons_kept_when_each_best_vs_a_different_monster(monkeypatch):
    _clear_cache()
    gd = GameData()
    gd._item_stats = {
        "fire_staff": ItemStats(code="fire_staff", level=5, type_="weapon",
                                attack={"fire": 16}, critical_strike=5),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                attack={"earth": 24}, critical_strike=5),
    }
    # TWO monsters: ember is fire-weak/earth-tanky (fire_staff wins), golem is
    # earth-weak/fire-tanky (iron_sword wins) → NEITHER pareto-dominates → both kept.
    gd._monster_level = {"ember": 8, "golem": 9}
    gd._monster_resistance = {"ember": {"fire": -50, "earth": 80},
                               "golem": {"fire": 80, "earth": -20}}
    monkeypatch.setattr(ct, "is_winnable", lambda s, g, c, h=None: True)
    state = _wstate({"fire_staff": 1, "iron_sword": 1})
    assert _is_equippable_dominated("fire_staff", state, gd) is False
    assert _is_equippable_dominated("iron_sword", state, gd) is False


def test_strictly_outclassed_weapon_is_dominated(monkeypatch):
    _clear_cache()
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"earth": 4}, critical_strike=5),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                attack={"earth": 24}, critical_strike=5),
    }
    gd._monster_level = {"slime": 8}
    gd._monster_resistance = {"slime": {"earth": 0}}
    monkeypatch.setattr(ct, "is_winnable", lambda s, g, c, h=None: True)
    state = make_state(level=10, inventory={"wooden_stick": 1, "iron_sword": 1})
    # same element, lower attack → iron_sword pareto-dominates everywhere → sold.
    assert _is_equippable_dominated("wooden_stick", state, gd) is True


def test_empty_monster_set_falls_back_to_flat_equip_value(monkeypatch):
    _clear_cache()
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"earth": 4}),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                attack={"earth": 24}),
    }
    gd._monster_level = {"slime": 1}
    monkeypatch.setattr(ct, "is_winnable", lambda s, g, c, h=None: False)  # nothing winnable
    state = make_state(level=30, inventory={"wooden_stick": 1, "iron_sword": 1})
    # empty set → flat equip_value path: iron_sword (higher attack) dominates wooden_stick.
    assert _is_equippable_dominated("wooden_stick", state, gd) is True
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** — add imports at top of `inventory_caps.py`:

```python
from artifactsmmo_cli.ai.combat_targets import combat_target_monsters
from artifactsmmo_cli.ai.dominance_pareto import pareto_dominates
from artifactsmmo_cli.ai.equipment.scoring import armor_score, weapon_score

_ARMOR_TYPES = frozenset({"helmet", "body_armor", "leg_armor", "boots", "shield"})


def _score_vector(stats: ItemStats, monsters: list[str], game_data: GameData) -> list[int]:
    """Per-monster combat score for a weapon (offense) or armor (defense) piece."""
    if stats.type_ == "weapon":
        return [weapon_score(stats, game_data.monster_resistance(m)) for m in monsters]
    return [armor_score(stats, game_data.monster_attack(m)) for m in monsters]
```

Then in `_is_equippable_dominated`, after computing `slots`, branch the `higher`
verdict. Replace the peer loop's `higher = _equip_value(peer) > my_value` with a
per-monster verdict when applicable:

```python
    slots = ITEM_TYPE_TO_SLOTS.get(stats.type_, [])
    if not slots:
        return False
    monsters = combat_target_monsters(state, game_data)
    per_monster = bool(monsters) and (stats.type_ == "weapon" or stats.type_ in _ARMOR_TYPES)
    item_vec = _score_vector(stats, monsters, game_data) if per_monster else []
    my_value = _equip_value(stats)
    # … (candidates / equipped_codes / bank_items unchanged) …
    for peer_code in candidates:
        peer = game_data.item_stats(peer_code)
        if peer is None:
            continue
        peer_slots = ITEM_TYPE_TO_SLOTS.get(peer.type_, [])
        fits = all(s in peer_slots for s in slots)
        if per_monster and fits:
            higher = pareto_dominates(_score_vector(peer, monsters, game_data), item_vec)
        else:
            higher = _equip_value(peer) > my_value
        # … covers / peer_count / peers.append unchanged …
    return _is_dominated_pure(peers, len(slots))
```

(`fits` already requires the peer to fit the item's slots, so `peer` is the same
weapon/armor family and `_score_vector(peer, …)` uses the same scoring function.)

- [ ] **Step 4: Run → PASS;** then full AI suite `~/.local/bin/uv run pytest tests/test_ai/ -q --no-cov` (the dominance change ripples into overstock/recycle/discard tests — investigate any regression before editing its asserts) and 100% coverage of `inventory_caps.py`.
- [ ] **Step 5: Commit** — `git commit -m "feat(dominance): per-monster keep in _is_equippable_dominated"`

---

### Task 4: Lean `DominancePareto.lean`

**Files:**
- Create: `formal/Formal/DominancePareto.lean`
- Modify: `formal/Formal.lean` (add `import Formal.DominancePareto` — orphan gate), `formal/Formal/Manifest.lean`, `formal/Formal/Contracts.lean`

**Interfaces:**
- Produces: `paretoDominates (peer item : List Int) : Bool` + theorems `pareto_implies_geq`, `pareto_needs_strict`, `pareto_irreflexive`.

- [ ] **Step 1: Write the def + theorems**

```lean
-- @concept: equipment, selling @property: safety
namespace Formal.DominancePareto

/-- Mirror of `dominance_pareto.pareto_dominates`: `peer ≥ item` componentwise
    (over the common prefix) AND strictly greater somewhere. -/
def geqAll : List Int → List Int → Bool
  | p :: ps, i :: is => (decide (i ≤ p)) && geqAll ps is
  | _, _ => true

def gtSome : List Int → List Int → Bool
  | p :: ps, i :: is => (decide (i < p)) || gtSome ps is
  | _, _ => false

def paretoDominates (peer item : List Int) : Bool := geqAll peer item && gtSome peer item

/-- A dominating peer is ≥ the item at every common index — the keep is sound. -/
theorem pareto_implies_geq (peer item : List Int) (k : Nat)
    (hk : k < peer.length) (hk2 : k < item.length)
    (h : paretoDominates peer item = true) :
    item.get ⟨k, hk2⟩ ≤ peer.get ⟨k, hk⟩ := by
  sorry

/-- Domination requires a STRICT win somewhere — equal-everywhere peers do not
    dominate (ties keep one via EQUIPPABLE_KEEP). -/
theorem pareto_needs_strict (peer item : List Int)
    (h : paretoDominates peer item = true) :
    gtSome peer item = true := by
  simp [paretoDominates, Bool.and_eq_true] at h; exact h.2

/-- A vector never dominates itself (no piece sells itself). -/
theorem pareto_irreflexive (v : List Int) : paretoDominates v v = false := by
  sorry

end Formal.DominancePareto
```

- [ ] **Step 2: Discharge the `sorry`s** (`lean4:prove`): `pareto_needs_strict` is already done; `pareto_implies_geq` by induction on the list / `k`; `pareto_irreflexive` by induction showing `gtSome v v = false` (no `i < i`). Build `cd formal && ~/.elan/bin/lake build` → green, no sorry.
- [ ] **Step 3: Pin** in Manifest (`#check @Formal.DominancePareto.<thm>` ×3) + Contracts (exact-statement `example := @…` ×3). Add `import Formal.DominancePareto` to `Formal.lean` (alphabetical). Add the `-- @concept:` tag (line 1, already shown) so the proof-concept index passes.
- [ ] **Step 4: Verify** — `lake build` + `bash gate/check_axioms.sh` (safety set) + `bash gate/check_no_orphan_modules.sh` + regen index `cd .. && uv run python scripts/gen_proof_concept_index.py`.
- [ ] **Step 5: Commit** — `git commit -m "feat(formal): DominancePareto core + role theorems"`

---

### Task 5: Differential + oracle

**Files:**
- Modify: `formal/Oracle.lean` (`pareto_dominates` command), `formal/Formal.lean`/imports as needed
- Create: `formal/diff/test_dominance_pareto_diff.py`

- [ ] **Step 1: Oracle command** — in `Oracle.lean` add `runParetoDominates` reading `[n, peer_0..peer_{n-1}, item_0..item_{n-1}]` → `{"dominated": paretoDominates peerList itemList}`; register `else if kind == "pareto_dominates"`. `cd formal && ~/.elan/bin/lake build oracle`.

- [ ] **Step 2: Differential**

```python
# formal/diff/test_dominance_pareto_diff.py
from hypothesis import given, settings
from hypothesis import strategies as st
from artifactsmmo_cli.ai.dominance_pareto import pareto_dominates
from formal.diff.oracle_client import run_oracle


@settings(max_examples=400)
@given(st.lists(st.tuples(st.integers(-100, 100), st.integers(-100, 100)),
                min_size=0, max_size=8))
def test_pareto_matches_lean(pairs):
    peer = [p for p, _ in pairs]
    item = [i for _, i in pairs]
    args = [len(peer), *peer, *item]
    lean = run_oracle("pareto_dominates", [args])[0]
    assert pareto_dominates(peer, item) == lean["dominated"]
```

- [ ] **Step 3: Run** `~/.local/bin/uv run pytest formal/diff/test_dominance_pareto_diff.py -q --no-cov` → PASS.
- [ ] **Step 4: Commit** — `git commit -m "feat(formal): pareto_dominates differential + oracle"`

---

### Task 6: Mutation anchors + full gate + finish

**Files:** Modify `formal/diff/mutate.py`; finish branch.

- [ ] **Step 1: Add `DOMINANCE_PARETO_MUTATIONS`** (SRC = `dominance_pareto.py`; killed by `test_dominance_pareto_diff.py`), verify each KILLED via the in-memory apply→test→restore loop (NOT `git checkout` — guardrail blocks it):
  - drop the `any`/strict requirement: `return geq_all and gt_some` → `return geq_all` (a tie now dominates — killed by `[3,4] vs [3,4]`).
  - flip `>=` to `>`: `all(p >= i …)` → `all(p > i …)` (a tie on one monster wrongly un-dominates — killed).
  - flip `>` to `>=` in `gt_some`: `any(p > i …)` → `any(p >= i …)` (equal vectors dominate — killed).
  Wire `run_group(DOMINANCE_PARETO_SRC, DOMINANCE_PARETO_MUTATIONS, "formal/diff/test_dominance_pareto_diff.py", survivors)`.
- [ ] **Step 2:** confirm NO bot running (`pgrep -af "artifactsmmo play"`), then `cd formal && bash gate.sh` → `ALL GATE PARTS PASSED`, `mutation gate OK`. (If a State/extraction drift appears, regen per the gate hint.)
- [ ] **Step 3:** `superpowers:finishing-a-development-branch` — merge to main.

---

## Notes for the implementer

- Tasks 1-3 are Python and independently testable; after Task 3 the feature is live.
- The proved `_is_dominated_pure` fold and `weapon_score`/`armor_score` cores are REUSED unchanged — do not modify them. The only new proven core is `paretoDominates`.
- The `e9b76f0b`-style State-field ripple does NOT apply here (no liveness State change). The relevant template for the oracle/differential/mutation mechanics is the just-merged `accumulation_sell` work (`git log --grep accumulation-sell`): `Oracle.lean` command + dispatch, `formal/diff/test_accumulation_sell_diff.py`, the `ACCUMULATION_SELL_MUTATIONS` group + its `run_group` call, and the `-- @concept:` tag + `import` into `Formal.lean`.
- CPU: `combat_target_monsters` is memoized single-entry; if the full gate or a live trace shows a hotspot, precompute score vectors per cycle (spec §5 follow-up).
