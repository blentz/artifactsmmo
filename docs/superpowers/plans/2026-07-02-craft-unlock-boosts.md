# Craft Unlock-Boosts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When leveling is stalled (`_winnable_farm_target()` is `None`), craft the utility boost potion that makes the highest-XP in-band monster winnable — merely owning it flips `is_winnable` (via `pick_loadout`+`predict_win`), so crafting is enough.

**Architecture:** A pure selector `unlock_boost_target` scans in-band monsters × craftable-now non-heal boosts and returns the `(boost, monster)` unlocking the highest-XP monster, using the already-proven `predict_win` with the boost added to inventory. A high-priority `CRAFT_UNLOCK_BOOST` guard fires only when stalled and an unlock exists; its `CraftUnlockBoostGoal` crafts the boost via a craft ladder extracted from `CraftPotionsGoal` (DRY). No `predict_win`/Lean change — orchestration over the proven verdict.

**Tech Stack:** Python 3.13, pytest, `uv`. No Lean/differential/mutation work.

## Global Constraints

- ALWAYS prefix Python with `/home/blentz/.local/bin/uv run` (plain `uv` not on PATH).
- Imports at top (absolute, no inline); never catch `Exception`; never `if TYPE_CHECKING`; ONE behavioral class per file; use only API data or fail.
- Tests real, in `tests/`; 0 errors/warnings/skips, 100% coverage.
- Reuse, don't duplicate: the craft ladder is extracted once and shared by `CraftPotionsGoal` and `CraftUnlockBoostGoal`.
- `predict_win`/`combat.py`/`Formal/` are UNCHANGED — this feature only reads `predict_win`.

---

### Task 1: `unlock_boost_target` selector (pure core)

**Files:**
- Create: `src/artifactsmmo_cli/ai/unlock_boost.py`
- Test: `tests/test_ai/test_unlock_boost.py`

**Interfaces:**
- Consumes: `combat.predict_win(state, game_data, monster_code) -> bool`; `game_data.crafting_recipes` (Mapping code→{mat:qty}); `game_data.monster_levels` (Mapping code→level); `game_data.xp_per_kill(monster, char_level) -> int`; `game_data.item_stats(code) -> ItemStats | None`; `combat_targets.LEVEL_BAND_BELOW` (=5); `WorldState.skills`, `.inventory`, `.equipment`, `.level`.
- Produces: `unlock_boost_target(state: WorldState, game_data: GameData) -> tuple[str, str] | None` → `(boost_code, monster_code)`.

- [ ] **Step 1: Write the failing tests** (real `predict_win`; mirror the verified repro — a fire monster the char loses to bare but beats with a `fire_boost_potion` owned):
```python
def _gd_unlock():
    from tests.test_ai._monster_fixture import fill_monster_stat_defaults
    gd = GameData()
    gd._monster_level = {"mob": 30, "weak": 26}
    fill_monster_stat_defaults(gd)
    gd._monster_hp = {"mob": 800, "weak": 50}
    gd._monster_attack = {"mob": {"fire": 30}, "weak": {"fire": 5}}
    gd._monster_resistance = {"mob": {}, "weak": {}}
    gd._item_stats = {
        "wpn": ItemStats(code="wpn", level=30, type_="weapon", attack={"fire": 60}),
        "fire_boost_potion": ItemStats(code="fire_boost_potion", level=10, type_="utility",
                                       crafting_skill="alchemy", crafting_level=10,
                                       dmg_elements={"fire": 40}, combat_buff=40),
        "small_health_potion": ItemStats(code="small_health_potion", level=5, type_="utility",
                                         crafting_skill="alchemy", crafting_level=5, hp_restore=30),
    }
    gd._crafting_recipes = {"fire_boost_potion": {"sunflower": 3}, "small_health_potion": {"sunflower": 1}}
    return gd

def _state_stalled():
    return make_state(level=30, hp=300, max_hp=300, attack={"fire": 60},
                      equipment={"weapon_slot": "wpn"}, inventory={},
                      skills={"alchemy": 20, "mining": 1, "woodcutting": 1, "fishing": 1,
                              "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1})

def test_unlock_returns_boost_and_monster_when_boost_flips_win():
    gd, st = _gd_unlock(), _state_stalled()
    # bare: mob unwinnable; with fire_boost_potion owned -> winnable
    assert predict_win(st, gd, "mob") is False
    assert unlock_boost_target(st, gd) == ("fire_boost_potion", "mob")

def test_unlock_none_when_a_monster_already_winnable():
    gd, st = _gd_unlock(), _state_stalled()
    # 'weak' is already bare-winnable -> not stalled -> selector returns None (never over-crafts)
    assert predict_win(st, gd, "weak") is True
    assert unlock_boost_target(st, gd) is None

def test_unlock_skips_heal_potions_and_uncraftable_boosts():
    gd, st = _gd_unlock(), _state_stalled()
    del gd._monster_level["weak"]; gd._monster_attack.pop("weak", None); gd._monster_hp.pop("weak", None)
    st2 = dataclasses.replace(st, skills={**st.skills, "alchemy": 5})  # can't craft L10 boost
    assert unlock_boost_target(st2, gd) is None  # boost skill-gated, heal doesn't flip

def test_unlock_picks_highest_xp_monster(...):
    # two unlockable monsters -> the higher xp_per_kill wins (add a second flippable monster)
    ...
```

- [ ] **Step 2: Run — expect FAIL** (module missing). Run: `/home/blentz/.local/bin/uv run pytest tests/test_ai/test_unlock_boost.py -v --no-cov`

- [ ] **Step 3: Implement** `src/artifactsmmo_cli/ai/unlock_boost.py`:
```python
"""Select the craftable utility boost that unlocks a currently-unwinnable
leveling monster. When no in-band monster is beatable bare, owning a boost can
flip predict_win (pick_loadout equips it) — this picks the boost that unlocks the
highest-XP monster. Orchestration over the proven predict_win; no combat change."""

import dataclasses

from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.combat_targets import LEVEL_BAND_BELOW
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

# single-entry cache keyed like combat_target_monsters (level, equip, owned boosts)
_cache: dict[str, object] = {}


def _is_craftable_boost(code: str, state: WorldState, game_data: GameData) -> bool:
    stats = game_data.item_stats(code)
    if stats is None or stats.type_ != "utility" or stats.hp_restore > 0:
        return False  # not a utility, or it's a heal (Phase-1 economy owns heals)
    has_boost = bool(stats.dmg_elements) or bool(stats.resistance) or stats.hp_bonus > 0 \
        or stats.antipoison > 0 or stats.combat_buff > 0
    if not has_boost or stats.crafting_skill is None:
        return False
    return state.skills.get(stats.crafting_skill, 0) >= stats.crafting_level


def unlock_boost_target(state: WorldState, game_data: GameData) -> tuple[str, str] | None:
    """(boost_code, monster_code) of the craftable non-heal boost that flips the
    highest-XP in-band monster from unwinnable to winnable; None if some in-band
    monster is already bare-winnable, or no craftable boost unlocks anything.
    Deterministic tie-break: fewest recipe items, then smallest boost code, then
    smallest monster code."""
    equip_sig = tuple(sorted(c for c in state.equipment.values() if c is not None))
    owned = tuple(sorted(c for c in state.inventory if _is_craftable_boost(c, state, game_data)))
    key = (state.level, equip_sig, owned)
    if _cache.get("key") == key:
        return _cache["val"]  # type: ignore[return-value]

    floor = state.level - LEVEL_BAND_BELOW
    monsters = [(code, lvl) for code, lvl in game_data.monster_levels.items() if lvl >= floor]
    # If anything is already bare-winnable, we are not stalled -> no unlock crafting.
    result: tuple[str, str] | None = None
    if not any(predict_win(state, game_data, code) for code, _ in monsters):
        boosts = [c for c in sorted(game_data.crafting_recipes)
                  if _is_craftable_boost(c, state, game_data)]
        best_key: tuple[int, int, str, str] | None = None
        for monster, _lvl in monsters:
            xp = game_data.xp_per_kill(monster, state.level)
            for boost in boosts:
                owned_state = dataclasses.replace(
                    state, inventory={**state.inventory, boost: state.inventory.get(boost, 0) + 1})
                if predict_win(owned_state, game_data, monster):
                    recipe_items = len(game_data.crafting_recipes.get(boost, {}))
                    k = (-xp, recipe_items, boost, monster)   # highest xp first
                    if best_key is None or k < best_key:
                        best_key = k
                        result = (boost, monster)
    _cache["key"] = key
    _cache["val"] = result
    return result
```

- [ ] **Step 4: Run — expect PASS.** Run: `/home/blentz/.local/bin/uv run pytest tests/test_ai/test_unlock_boost.py -v --no-cov`

- [ ] **Step 5: Commit**
```bash
git add src/artifactsmmo_cli/ai/unlock_boost.py tests/test_ai/test_unlock_boost.py
git commit -m "feat(combat): unlock_boost_target — pick craftable boost that unlocks a monster"
```

---

### Task 2: Extract the shared craft-a-utility ladder from CraftPotionsGoal

**Files:**
- Create: `src/artifactsmmo_cli/ai/craft_ladder.py` (one function)
- Modify: `src/artifactsmmo_cli/ai/goals/craft_potions.py` `relevant_actions` (reroute to the helper)
- Test: `tests/test_ai/test_craft_ladder.py`, and the existing `tests/test_ai/test_craft_potions.py` must stay green.

**Interfaces:**
- Produces: `craft_utility_ladder(target_code: str, runs: int, equip_qty: int, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]` — the gather/buy/withdraw/craft(intermediates+target)/move/equip action filter for ONE utility target, batched to `runs` and equipping `equip_qty` into `utility1_slot`. Exactly the body currently inside `CraftPotionsGoal.relevant_actions` from the recipe-closure computation through the final `EquipAction`.

- [ ] **Step 1: Read `CraftPotionsGoal.relevant_actions`** and identify the ladder body (from `recipe = game_data.crafting_recipes[code]` / `craft_yield` down through `result.append(EquipAction(...))`). This block, parameterized by `(target_code, runs, equip_qty)`, is the helper. The `_target_potion` selection + `deficit`/`runs`/`equip_qty` computation STAY in `CraftPotionsGoal` (they are potion-baseline-specific).

- [ ] **Step 2: Write the failing test** for the helper (mirror `test_craft_from_held_emits_craft_and_equip`):
```python
def test_craft_utility_ladder_emits_craft_and_equip():
    gd = _gd_potion()  # reuse the craft_potions test fixture builder (copy or import)
    state = make_state(level=1, inventory={_INGREDIENT: 10})
    actions = [_craft_action(), GatherAction(resource_code=_RESOURCE, locations=frozenset({(2,0)})), MoveAction(x=0,y=0)]
    out = craft_utility_ladder(_POTION, runs=1, equip_qty=1, actions=actions, state=state, game_data=gd)
    assert any(isinstance(a, CraftAction) for a in out)
    assert any(isinstance(a, EquipAction) and a.slot == "utility1_slot" for a in out)
```

- [ ] **Step 3: Run — expect FAIL** (module missing). Run: `/home/blentz/.local/bin/uv run pytest tests/test_ai/test_craft_ladder.py -v --no-cov`

- [ ] **Step 4: Extract** the ladder body into `craft_ladder.py::craft_utility_ladder(target_code, runs, equip_qty, actions, state, game_data)` (move the code verbatim, replacing `code`→`target_code`, `runs`/`equip_qty` now parameters). Then in `CraftPotionsGoal.relevant_actions`, after computing `code`/`runs`/`equip_qty`, `return craft_utility_ladder(code, runs, equip_qty, actions, state, game_data)`. Keep imports at top.

- [ ] **Step 5: Run — expect PASS + CraftPotions unchanged.** Run: `/home/blentz/.local/bin/uv run pytest tests/test_ai/test_craft_ladder.py tests/test_ai/test_craft_potions.py -q --no-cov` (all green — the reroute is behavior-preserving).

- [ ] **Step 6: Commit**
```bash
git add src/artifactsmmo_cli/ai/craft_ladder.py src/artifactsmmo_cli/ai/goals/craft_potions.py tests/test_ai/test_craft_ladder.py
git commit -m "refactor(craft): extract craft_utility_ladder shared by CraftPotions"
```

---

### Task 3: `CraftUnlockBoostGoal`

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/craft_unlock_boost.py`
- Test: `tests/test_ai/test_craft_unlock_boost.py`

**Interfaces:**
- Consumes: `unlock_boost_target` (Task 1); `craft_utility_ladder` (Task 2); `Goal` base (`base.py`); `game_data.craft_yield(code)` (used by CraftPotions for equip_qty — check its name/signature in craft_potions.py and reuse).
- Produces: `CraftUnlockBoostGoal(game_data: GameData | None = None)` with `value`, `is_satisfied`, `desired_state`, `relevant_actions`, `__repr__`; `preemptive = True`.

- [ ] **Step 1: Write the failing tests**
```python
def test_craft_unlock_boost_value_positive_when_unlock_available():
    gd, st = _gd_unlock(), _state_stalled()   # from Task 1's fixtures (copy/import)
    goal = CraftUnlockBoostGoal(game_data=gd)
    assert goal.value(st, gd) > 0

def test_craft_unlock_boost_value_zero_when_no_unlock():
    gd, st = _gd_unlock(), _state_stalled()   # 'weak' already winnable -> no unlock
    assert CraftUnlockBoostGoal(game_data=gd).value(st, gd) == 0.0

def test_craft_unlock_boost_relevant_actions_emit_target_craft():
    gd, st = _gd_unlock(), _state_stalled()
    st = dataclasses.replace(st, inventory={"sunflower": 10})   # ingredients for the boost
    goal = CraftUnlockBoostGoal(game_data=gd)
    acts = goal.relevant_actions([CraftAction(code="fire_boost_potion", quantity=1, workshop_location=(3,0)),
                                  MoveAction(x=0,y=0)], st, gd)
    assert any(isinstance(a, CraftAction) and a.code == "fire_boost_potion" for a in acts)

def test_craft_unlock_boost_satisfied_when_boost_owned():
    gd = _gd_unlock()
    st = dataclasses.replace(_state_stalled(), inventory={"fire_boost_potion": 1})
    assert CraftUnlockBoostGoal(game_data=gd).is_satisfied(st) is True
```

- [ ] **Step 2: Run — expect FAIL.** Run: `/home/blentz/.local/bin/uv run pytest tests/test_ai/test_craft_unlock_boost.py -v --no-cov`

- [ ] **Step 3: Implement** `craft_unlock_boost.py`:
```python
"""Craft the boost that unlocks a leveling monster when leveling is stalled.
Owning the boost flips is_winnable (pick_loadout equips it), so a single crafted
batch is enough. Reuses the shared craft ladder."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.craft_ladder import craft_utility_ladder
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.unlock_boost import unlock_boost_target
from artifactsmmo_cli.ai.world_state import WorldState

CRAFT_UNLOCK_BOOST = 3.0  # stall-breaker urgency (peer of the leveling bootstrap)


class CraftUnlockBoostGoal(Goal):
    """Craft the utility boost that unlocks the highest-XP stalled leveling target."""
    preemptive = True

    def __init__(self, game_data: GameData | None = None) -> None:
        self._game_data = game_data

    def _target(self, state: WorldState, game_data: GameData) -> str | None:
        pair = unlock_boost_target(state, game_data)
        return pair[0] if pair is not None else None

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return CRAFT_UNLOCK_BOOST if self._target(state, game_data) is not None else 0.0

    def is_satisfied(self, state: WorldState) -> bool:
        gd = self._game_data
        if gd is None:
            return True   # no data -> nothing to do
        target = self._target(state, gd)
        return target is None or state.inventory.get(target, 0) >= 1

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        target = self._target(state, game_data)
        return {"have": {target: 1}} if target is not None else {}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        target = self._target(state, game_data)
        if target is None:
            return []
        craft_yield = game_data.craft_yield(target)
        runs = 1
        equip_qty = min(craft_yield, game_data.crafting_recipes.get(target) and craft_yield or craft_yield)
        return craft_utility_ladder(target, runs, equip_qty, actions, state, game_data)

    def __repr__(self) -> str:
        return "CraftUnlockBoost"
```
(Confirm `game_data.craft_yield` exists — CraftPotions uses it. If the `equip_qty` line reads awkward, set `equip_qty = craft_yield`. Keep it simple: 1 run, equip the batch yield.)

- [ ] **Step 4: Run — expect PASS.** Run: `/home/blentz/.local/bin/uv run pytest tests/test_ai/test_craft_unlock_boost.py -q --no-cov`

- [ ] **Step 5: Commit**
```bash
git add src/artifactsmmo_cli/ai/goals/craft_unlock_boost.py tests/test_ai/test_craft_unlock_boost.py
git commit -m "feat(goals): CraftUnlockBoostGoal — craft the stall-unlocking boost"
```

---

### Task 4: Guard wiring (`CRAFT_UNLOCK_BOOST`)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/guards.py` (`GuardKind` enum, `GUARD_ORDER`, the `_fires` dispatch)
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` `map_guard` (~300)
- Test: `tests/test_ai/test_tiers_guards.py`, `tests/test_ai/test_strategy_driver.py`

**Interfaces:**
- Consumes: `unlock_boost_target` (Task 1), `CraftUnlockBoostGoal` (Task 3), `ctx.combat_monster` (the stall signal: `None` when no winnable target).
- Produces: `GuardKind.CRAFT_UNLOCK_BOOST`; `map_guard(GuardKind.CRAFT_UNLOCK_BOOST, ...) -> CraftUnlockBoostGoal(game_data=game_data)`.

- [ ] **Step 1: Write the failing tests**
```python
def test_craft_unlock_boost_guard_fires_when_stalled_and_unlockable():
    from artifactsmmo_cli.ai.tiers.guards import GuardKind, active_guards
    gd, st = _gd_unlock(), _state_stalled()
    ctx = _ctx(combat_monster=None)   # stall
    assert GuardKind.CRAFT_UNLOCK_BOOST in active_guards(st, gd, None, ctx)

def test_craft_unlock_boost_guard_quiet_when_not_stalled():
    gd, st = _gd_unlock(), _state_stalled()
    ctx = _ctx(combat_monster="weak")   # a winnable target exists -> not stalled
    assert GuardKind.CRAFT_UNLOCK_BOOST not in active_guards(st, gd, None, ctx)

def test_map_guard_returns_craft_unlock_boost_goal():
    from artifactsmmo_cli.ai.strategy_driver import map_guard
    from artifactsmmo_cli.ai.tiers.guards import GuardKind
    g = map_guard(GuardKind.CRAFT_UNLOCK_BOOST, _gd_unlock(), _ctx(combat_monster=None), state=_state_stalled())
    assert isinstance(g, CraftUnlockBoostGoal)
```

- [ ] **Step 2: Run — expect FAIL.** Run: `/home/blentz/.local/bin/uv run pytest tests/test_ai/test_tiers_guards.py tests/test_ai/test_strategy_driver.py -k "unlock_boost" -v --no-cov`

- [ ] **Step 3: Implement.**
  - `guards.py`: add `CRAFT_UNLOCK_BOOST = "craft_unlock_boost"` to `GuardKind`; insert it into `GUARD_ORDER` at a HIGH position (before the discretionary/relief guards, after the survival guards HP_CRITICAL/REST_FOR_COMBAT — it unblocks leveling, so it should preempt gear/discard but not survival). Add its `_fires` predicate: `return ctx.combat_monster is None and unlock_boost_target(state, game_data) is not None` (import `unlock_boost_target`). Place it in the `_fires` dispatch mirroring `CRAFT_POTIONS`.
  - `strategy_driver.py` `map_guard`: `if kind is GuardKind.CRAFT_UNLOCK_BOOST: return CraftUnlockBoostGoal(game_data=game_data)` (import the goal).

- [ ] **Step 4: Run — expect PASS + guard/strategy suites green.** Run: `/home/blentz/.local/bin/uv run pytest tests/test_ai/test_tiers_guards.py tests/test_ai/test_strategy_driver.py -q --no-cov`

- [ ] **Step 5: Commit**
```bash
git add src/artifactsmmo_cli/ai/tiers/guards.py src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/
git commit -m "feat(guards): CRAFT_UNLOCK_BOOST guard fires on leveling stall with an unlock"
```

---

### Task 5: Full gate + merge

**Files:** none.

- [ ] **Step 1: Unit suite @ 100% coverage.** Run: `/home/blentz/.local/bin/uv run pytest tests/ -q` — all pass, 100%, 0 warnings/skips.
- [ ] **Step 2: mypy.** Run: `/home/blentz/.local/bin/uv run mypy src/` — clean.
- [ ] **Step 3: Differential gate (unchanged combat — sanity).** Run: `cd formal && lake build oracle && cd .. && /home/blentz/.local/bin/uv run pytest formal/diff/ -q --no-cov -n auto` — all pass (no combat/Lean change; this confirms no accidental regression). Snapshot `*_match_live` may need `reference_snapshot_regen` if live drifted.
- [ ] **Step 4: Merge.**
```bash
git checkout main && git merge --no-ff feat/craft-unlock-boosts -m "Merge: craft unlock-boosts to break leveling stalls"
```

---

## Self-review notes

- **Spec coverage:** §1 selector → Task 1; §2 goal (reuse ladder) → Tasks 2+3; §3 arbiter wiring → Task 4; §4 cost control (cache + stall-gate) → Task 1's `_cache` + Task 4's `_fires` gate on `combat_monster is None`; §5 testing/no-formal → Tasks 1-5 (no Lean). All covered.
- **`predict_win` unchanged:** the selector only READS it; Task 5 Step 3 runs the differential purely to confirm no accidental combat regression.
- **Type consistency:** `unlock_boost_target(state, game_data) -> tuple[str,str] | None` (Task 1) consumed by Tasks 3-4; `craft_utility_ladder(target_code, runs, equip_qty, actions, state, game_data) -> list[Action]` (Task 2) consumed by Task 3; `CraftUnlockBoostGoal(game_data=...)` (Task 3) constructed in Task 4.
- **Open verifications for the implementer:** confirm `game_data.craft_yield(code)` exists (CraftPotions uses it) — Task 3; confirm the exact `GUARD_ORDER` insertion index (after survival guards, before relief/discretionary) — Task 4; confirm `_ctx(combat_monster=...)` test helper exists in the guard/strategy tests — Tasks 4.
- **Cost:** `unlock_boost_target` runs `predict_win` over monsters×boosts ONLY when `ctx.combat_monster is None` (stall) and caches on `(level, equip_sig, owned-boosts)` — off the hot path.
