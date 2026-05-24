# Goal Tiers — P4: Tactical Cost Refinement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the bot fight with its best on-hand loadout (winnability + planner reliably sequencing the swap before the fight) and rest instead of wasting a consumable on a trivial heal — by sharpening existing projections and action costs, with no new decision tier.

**Architecture:** Extend `ItemStats` to capture all combat effects; a pure `project_loadout_stats` delta helper; `predict_win` evaluates the best-attainable loadout; `GrindCharacterXPGoal.is_satisfied` requires the optimal loadout AND `FightAction.cost` penalizes fighting under-geared (together they put `OptimizeLoadout` at `plan[0]` under the player's `plan[0]`-only execution); `UseConsumableAction.cost` becomes overheal-aware.

**Tech Stack:** Python 3.13, `uv run` (pytest, ruff line-length 120, mypy --strict), dataclasses. Spec: `docs/superpowers/specs/2026-05-24-goal-tiers-p4-tactical-cost-refinement-design.md`.

---

## File Structure

- `src/artifactsmmo_cli/ai/game_data.py` — MODIFY: `ItemStats` gains `dmg`/`dmg_elements`/`critical_strike`/`initiative`/`hp_bonus`; `_load_items` parses those effect codes.
- `src/artifactsmmo_cli/ai/equipment/projection.py` — CREATE: `ProjectedStats` + `project_loadout_stats`.
- `src/artifactsmmo_cli/ai/combat.py` — MODIFY: `predict_win` projects the optimal loadout for the player side.
- `src/artifactsmmo_cli/ai/goals/grind_character_xp.py` — MODIFY: `game_data` ctor arg + loadout-optimal term in `is_satisfied`.
- `src/artifactsmmo_cli/ai/actions/combat.py` — MODIFY: `FightAction.cost` loadout penalty.
- `src/artifactsmmo_cli/ai/strategy_driver.py` — MODIFY: `objective_step_goal` passes `game_data` to `GrindCharacterXPGoal`.
- Tests: `test_game_data.py`, new `test_equipment_projection.py`, `test_combat.py`, `test_grind_character_xp.py`, `test_strategy_driver.py`, `test_actions*` (combat cost, consumable cost).

Conventions: always `uv run`. `ELEMENTS = ("fire","earth","water","air")`. `ItemStats` dicts are sparse (drop zero entries), matching `WorldState`. `OptimizeLoadoutAction.apply` already updates simulated `state.equipment` (confirmed) — no change there.

---

### Task 1: Extend `ItemStats` + item loader

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py`
- Test: `tests/test_ai/test_game_data.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_game_data.py` (uses `MagicMock`/`patch`/`make_page`, already imported there):

```python
def test_loads_gear_combat_effects(self):
    gd = GameData()
    item = MagicMock()
    item.code = "power_ring"
    item.level = 5
    item.type_ = "ring"
    item.craft = UNSET  # no recipe
    eff = lambda code, value: type("E", (), {"code": code, "value": value})()
    item.effects = [eff("dmg", 8), eff("dmg_fire", 4), eff("critical_strike", 6),
                    eff("initiative", 20), eff("hp", 50)]
    with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=make_page([item])):
        gd._load_items(MagicMock())
    s = gd.item_stats("power_ring")
    assert s.dmg == 8
    assert s.dmg_elements == {"fire": 4}
    assert s.critical_strike == 6
    assert s.initiative == 20
    assert s.hp_bonus == 50
```

`UNSET` is imported in that file (`from artifactsmmo_api_client.types import UNSET`); if not, add it. Match the file's existing `_load_items` test style for the mock item (look at `test_loads_*` for items) — set `item.craft = UNSET` and `item.effects` as a list of objects with `.code`/`.value`.

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_game_data.py::TestGameDataLoadItems::test_loads_gear_combat_effects -v` (adjust class name to the actual items-load test class)
Expected: FAIL — `AttributeError: 'ItemStats' object has no attribute 'dmg'`.

- [ ] **Step 3: Add `ItemStats` fields**

In `game_data.py`, in the `ItemStats` dataclass (after `resistance`):

```python
    dmg: int = 0                                              # global damage % bonus
    dmg_elements: dict[str, int] = field(default_factory=dict)  # element -> dmg % bonus
    critical_strike: int = 0                                  # crit chance % bonus
    initiative: int = 0                                       # initiative bonus
    hp_bonus: int = 0                                         # flat max-HP bonus (gear)
```

- [ ] **Step 4: Parse the effects in `_load_items`**

In the effect loop, after the `res_` branch and before the `_GATHERING_SKILLS` branch, add:

```python
                        elif effect.code == "dmg":
                            stats.dmg = effect.value
                        elif effect.code.startswith("dmg_"):
                            stats.dmg_elements[effect.code[len("dmg_"):]] = effect.value
                        elif effect.code == "critical_strike":
                            stats.critical_strike = effect.value
                        elif effect.code == "initiative":
                            stats.initiative = effect.value
                        elif effect.code == "hp":
                            stats.hp_bonus = effect.value
```

(`== "dmg"` before `startswith("dmg_")` for clarity; `"dmg".startswith("dmg_")` is False so order is safe either way.)

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_game_data.py -q` (all pass)
`uv run ruff check src/artifactsmmo_cli/ai/game_data.py && uv run mypy src/artifactsmmo_cli/ai/game_data.py` (clean)

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit -m "feat(ai): parse gear dmg/crit/initiative/hp effects into ItemStats

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Loadout stat projection

**Files:**
- Create: `src/artifactsmmo_cli/ai/equipment/projection.py`
- Test: `tests/test_ai/test_equipment_projection.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_equipment_projection.py`:

```python
"""Tests for projecting a hypothetical loadout's combat stats."""

from artifactsmmo_cli.ai.equipment.projection import ProjectedStats, project_loadout_stats
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd(items):
    gd = GameData()
    gd._item_stats = items
    return gd


def test_identity_when_loadout_equals_current():
    state = make_state(attack={"fire": 10}, resistance={"earth": 5}, max_hp=120,
                       equipment={"weapon_slot": "wand", "ring1_slot": None})
    gd = _gd({"wand": ItemStats(code="wand", level=1, type_="weapon", attack={"fire": 7})})
    proj = project_loadout_stats(state, dict(state.equipment), gd)
    assert proj.attack == {"fire": 10}      # no delta
    assert proj.max_hp == 120


def test_swapping_in_stronger_weapon_raises_attack():
    state = make_state(attack={"fire": 10}, equipment={"weapon_slot": "wand"})
    gd = _gd({
        "wand": ItemStats(code="wand", level=1, type_="weapon", attack={"fire": 7}),
        "staff": ItemStats(code="staff", level=1, type_="weapon", attack={"fire": 12}),
    })
    proj = project_loadout_stats(state, {"weapon_slot": "staff"}, gd)
    assert proj.attack["fire"] == 10 + (12 - 7)   # current total + (new - old) contribution


def test_hp_bonus_ring_raises_max_hp():
    state = make_state(max_hp=100, equipment={"ring1_slot": None})
    gd = _gd({"hp_ring": ItemStats(code="hp_ring", level=1, type_="ring", hp_bonus=40)})
    proj = project_loadout_stats(state, {"ring1_slot": "hp_ring"}, gd)
    assert proj.max_hp == 140


def test_unknown_item_contributes_nothing():
    state = make_state(attack={"fire": 10}, equipment={"weapon_slot": "wand"})
    gd = _gd({})   # no stats for anything
    proj = project_loadout_stats(state, {"weapon_slot": "ghost"}, gd)
    assert proj.attack == {"fire": 10}   # ghost has no ItemStats -> no delta


def test_dmg_crit_initiative_project():
    state = make_state(equipment={"ring1_slot": None}, critical_strike=0, initiative=10)
    gd = _gd({"ring": ItemStats(code="ring", level=1, type_="ring",
                                dmg=8, dmg_elements={"fire": 3}, critical_strike=5, initiative=4)})
    proj = project_loadout_stats(state, {"ring1_slot": "ring"}, gd)
    assert proj.dmg == 8
    assert proj.dmg_elements == {"fire": 3}
    assert proj.critical_strike == 5
    assert proj.initiative == 14
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_equipment_projection.py -v`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.ai.equipment.projection`.

- [ ] **Step 3: Implement `projection.py`**

```python
"""Project a hypothetical loadout's combat stats as a delta from current totals.

The server reports only total stats (base + equipped gear), never base, so a
loadout's projected stats are computed as: current totals + Σ_slot (picked item
contribution − currently-equipped item contribution). Pure; used by predict_win
to judge winnability with the best-attainable loadout before equipping it."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import ELEMENTS, WorldState


@dataclass(frozen=True)
class ProjectedStats:
    attack: dict[str, int]
    dmg: int
    dmg_elements: dict[str, int]
    resistance: dict[str, int]
    critical_strike: int
    initiative: int
    max_hp: int


def _drop_zeros(d: dict[str, int]) -> dict[str, int]:
    return {k: v for k, v in d.items() if v != 0}


def project_loadout_stats(
    state: WorldState, loadout: dict[str, str | None], game_data: GameData,
) -> ProjectedStats:
    """Combat stats if `loadout` (slot -> item_code | None) were equipped."""
    attack = dict(state.attack)
    dmg = state.dmg
    dmg_elements = dict(state.dmg_elements)
    resistance = dict(state.resistance)
    critical_strike = state.critical_strike
    initiative = state.initiative
    max_hp = state.max_hp

    for slot, new_code in loadout.items():
        old_code = state.equipment.get(slot)
        if new_code == old_code:
            continue
        new_s: ItemStats | None = game_data.item_stats(new_code) if new_code else None
        old_s: ItemStats | None = game_data.item_stats(old_code) if old_code else None
        for elem in ELEMENTS:
            attack[elem] = (attack.get(elem, 0)
                            + (new_s.attack.get(elem, 0) if new_s else 0)
                            - (old_s.attack.get(elem, 0) if old_s else 0))
            dmg_elements[elem] = (dmg_elements.get(elem, 0)
                                  + (new_s.dmg_elements.get(elem, 0) if new_s else 0)
                                  - (old_s.dmg_elements.get(elem, 0) if old_s else 0))
            resistance[elem] = (resistance.get(elem, 0)
                                + (new_s.resistance.get(elem, 0) if new_s else 0)
                                - (old_s.resistance.get(elem, 0) if old_s else 0))
        dmg += (new_s.dmg if new_s else 0) - (old_s.dmg if old_s else 0)
        critical_strike += (new_s.critical_strike if new_s else 0) - (old_s.critical_strike if old_s else 0)
        initiative += (new_s.initiative if new_s else 0) - (old_s.initiative if old_s else 0)
        max_hp += (new_s.hp_bonus if new_s else 0) - (old_s.hp_bonus if old_s else 0)

    return ProjectedStats(
        attack=_drop_zeros(attack),
        dmg=dmg,
        dmg_elements=_drop_zeros(dmg_elements),
        resistance=_drop_zeros(resistance),
        critical_strike=critical_strike,
        initiative=initiative,
        max_hp=max_hp,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_equipment_projection.py -v` (pass)
`uv run ruff check src/artifactsmmo_cli/ai/equipment/projection.py tests/test_ai/test_equipment_projection.py && uv run mypy src/artifactsmmo_cli/ai/equipment/projection.py` (clean)
`uv run pytest tests/test_ai/test_equipment_projection.py --cov=artifactsmmo_cli.ai.equipment.projection --cov-report=term-missing -q` → 100%.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/equipment/projection.py tests/test_ai/test_equipment_projection.py
git commit -m "feat(ai): project hypothetical loadout combat stats (delta from current)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `predict_win` evaluates the best-attainable loadout

**Files:**
- Modify: `src/artifactsmmo_cli/ai/combat.py`
- Test: `tests/test_ai/test_combat.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_combat.py` (it has `make_state`, `_gd` helper, `GameData`, `ItemStats` may need importing):

```python
def test_predict_win_uses_best_inventory_loadout():
    # Current weapon too weak to kill in <=100 turns; a strong staff sits in
    # inventory. predict_win should pick it up (via pick_loadout) and judge winnable.
    gd = _gd(hp=200, attack={"fire": 1}, initiative=0)   # monster "mob"
    gd._item_stats = {
        "twig": ItemStats(code="twig", level=1, type_="weapon", attack={"fire": 1}),
        "staff": ItemStats(code="staff", level=1, type_="weapon", attack={"fire": 80}),
    }
    state = make_state(max_hp=100, attack={"fire": 1}, initiative=50,
                       equipment={"weapon_slot": "twig"}, inventory={"staff": 1}, level=1)
    assert predict_win(state, gd, "mob") is True       # with staff: 80/hit kills 200hp in 3


def test_predict_win_identity_without_better_gear():
    # No inventory upgrades + no item stats -> projection == current -> unchanged result.
    gd = _gd(hp=30, attack={"fire": 5}, initiative=0)
    state = make_state(max_hp=100, attack={"fire": 50}, initiative=50)
    assert predict_win(state, gd, "mob") is True
```

Confirm `_gd` (the combat-test monster builder) and `ItemStats` import. The `_gd` in test_combat.py sets `_monster_hp/_monster_attack/_monster_resistance/_monster_critical_strike/_monster_initiative`; pick_loadout also reads those plus `_item_stats` + `_monster_level` (set `gd._monster_level = {"mob": 1}` if pick_loadout/candidate level-gating needs it — `_candidates_for_slot` checks `state.level < stats.level`, not monster level, so monster_level isn't required by pick_loadout; but include it if any assertion path needs it).

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_combat.py::test_predict_win_uses_best_inventory_loadout -v`
Expected: FAIL — currently `predict_win` reads `state.attack` (fire 1) → can't kill 200hp in 100 turns → returns False, but test expects True.

- [ ] **Step 3: Update `predict_win`**

In `combat.py`, add imports at top:

```python
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.equipment.scoring import pick_loadout
```

Replace the player-side stat reads in `predict_win` so the player's stats come from the projected optimal loadout:

```python
def predict_win(state: WorldState, game_data: GameData, monster_code: str) -> bool:
    """True if the documented formula says the player beats the monster using the
    best on-hand loadout (inventory + equipped) for it."""
    loadout = pick_loadout(monster_code, state, game_data)
    p = project_loadout_stats(state, loadout, game_data)
    player_hit = _expected_hit(
        p.attack, p.dmg, p.dmg_elements,
        game_data.monster_resistance(monster_code), p.critical_strike,
    )
    if player_hit <= 0:
        return False
    rounds_to_kill = math.ceil(game_data.monster_hp(monster_code) / player_hit)
    if rounds_to_kill > MAX_TURNS:
        return False
    monster_hit = _expected_hit(
        game_data.monster_attack(monster_code), 0, {},
        p.resistance, game_data.monster_critical_strike(monster_code),
    )
    if monster_hit <= 0:
        return True
    rounds_to_die = math.ceil(p.max_hp / monster_hit)
    player_first = p.initiative >= game_data.monster_initiative(monster_code)
    return rounds_to_kill <= rounds_to_die if player_first else rounds_to_kill < rounds_to_die
```

(Everything else — `_round_half_up`/`_element_damage`/`_expected_hit`/`MAX_TURNS` — unchanged. The only change is the player's stats now come from `p` (projected optimal loadout) instead of `state`.) `combat.py` importing `equipment/` is acyclic: `equipment/scoring.py`/`projection.py` import `actions/equipment`, `game_data`, `world_state` — none import `combat`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_combat.py -v` (all pass — the existing tests use states with no inventory/item_stats, so `pick_loadout` returns current equipment → projection is identity → unchanged results)
`uv run ruff check src/artifactsmmo_cli/ai/combat.py && uv run mypy src/artifactsmmo_cli/ai/combat.py` (clean)
`uv run pytest tests/test_ai/test_combat.py --cov=artifactsmmo_cli.ai.combat --cov-report=term-missing -q` → 100%.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/combat.py tests/test_ai/test_combat.py
git commit -m "feat(ai): predict_win judges winnability with the best on-hand loadout

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `GrindCharacterXPGoal` requires the optimal loadout

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/grind_character_xp.py`
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (pass `game_data`)
- Test: `tests/test_ai/test_grind_character_xp.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_grind_character_xp.py`:

```python
from artifactsmmo_cli.ai.game_data import ItemStats   # add at top if absent


def test_not_satisfied_until_loadout_optimal():
    gd = _gd_with_monster()           # has _monster_level={"chicken":1}; add stats below
    gd._monster_attack = {"chicken": {"fire": 2}}
    gd._monster_resistance = {"chicken": {}}
    gd._item_stats = {
        "twig": ItemStats(code="twig", level=1, type_="weapon", attack={"fire": 1}),
        "sword": ItemStats(code="sword", level=1, type_="weapon", attack={"fire": 9}),
    }
    # xp progressed, but a better weapon (sword) is in inventory -> loadout not optimal
    state = make_state(xp=200, task_code=None, level=1,
                       equipment={"weapon_slot": "twig"}, inventory={"sword": 1})
    goal = GrindCharacterXPGoal("chicken", initial_xp=100, game_data=gd)
    assert goal.is_satisfied(state) is False        # loadout still suboptimal


def test_satisfied_when_xp_up_and_loadout_optimal():
    gd = _gd_with_monster()
    gd._monster_attack = {"chicken": {"fire": 2}}
    gd._monster_resistance = {"chicken": {}}
    gd._item_stats = {"sword": ItemStats(code="sword", level=1, type_="weapon", attack={"fire": 9})}
    state = make_state(xp=200, task_code=None, level=1,
                       equipment={"weapon_slot": "sword"}, inventory={})
    goal = GrindCharacterXPGoal("chicken", initial_xp=100, game_data=gd)
    assert goal.is_satisfied(state) is True


def test_game_data_none_falls_back_to_xp_only():
    goal = GrindCharacterXPGoal("chicken", initial_xp=100)   # no game_data
    assert goal.is_satisfied(make_state(xp=200)) is True
    assert goal.is_satisfied(make_state(xp=50)) is False
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_grind_character_xp.py -k "loadout or falls_back" -v`
Expected: FAIL — `__init__` takes no `game_data`; `is_satisfied` ignores loadout.

- [ ] **Step 3: Update the goal**

In `goals/grind_character_xp.py`, add the import and `game_data` field, and the loadout-optimal check:

```python
from artifactsmmo_cli.ai.equipment.scoring import pick_loadout
```

```python
    def __init__(self, target_monster: str, initial_xp: int = 0,
                 game_data: GameData | None = None) -> None:
        self._target_monster = target_monster
        self._initial_xp = initial_xp
        self._game_data = game_data

    def _loadout_optimal(self, state: WorldState) -> bool:
        if self._game_data is None:
            return True
        optimal = pick_loadout(self._target_monster, state, self._game_data)
        return all(state.equipment.get(slot) == code for slot, code in optimal.items())

    def is_satisfied(self, state: WorldState) -> bool:
        return state.xp > self._initial_xp and self._loadout_optimal(state)
```

Leave `value`, `desired_state`, `relevant_actions`, `__repr__` unchanged (`relevant_actions` already includes the per-target `OptimizeLoadoutAction` via the `"equip"` tag branch).

- [ ] **Step 4: Pass `game_data` from the driver**

In `src/artifactsmmo_cli/ai/strategy_driver.py`, `objective_step_goal`'s `ReachCharLevel` branch — change the construction to pass `game_data`:

```python
        return GrindCharacterXPGoal(target_monster=ctx.combat_monster,
                                    initial_xp=state.xp, game_data=game_data)
```

Grep for other `GrindCharacterXPGoal(` construction sites in `src/` (`grep -rn "GrindCharacterXPGoal(" src/`) and pass `game_data` where a real one is available; the P3c cutover should leave only the driver site.

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_grind_character_xp.py -v` (all pass; fix any existing test that constructed the goal and now asserts old is_satisfied — those without `game_data` keep xp-only behavior, so they should be unaffected)
`uv run ruff check src/artifactsmmo_cli/ai/goals/grind_character_xp.py src/artifactsmmo_cli/ai/strategy_driver.py && uv run mypy src/artifactsmmo_cli/ai/goals/grind_character_xp.py src/artifactsmmo_cli/ai/strategy_driver.py` (clean)

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/grind_character_xp.py src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_grind_character_xp.py
git commit -m "feat(ai): grind goal requires optimal loadout for the target

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `FightAction.cost` loadout penalty + planner sequencing

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/combat.py`
- Test: `tests/test_ai/test_grind_character_xp.py` (planner integration) + a cost unit test

- [ ] **Step 1: Write the failing test**

Add a cost unit test and the decisive planner-integration test. Put the integration test where `GOAPPlanner` is already used with grind goals (`test_grind_character_xp.py`); confirm the planner import there.

```python
from artifactsmmo_cli.ai.actions.combat import FightAction, LOADOUT_PENALTY
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.planner import GOAPPlanner


def _combat_gd():
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    gd._monster_locations = {"chicken": [(0, 0)]}
    gd._monster_attack = {"chicken": {"fire": 2}}
    gd._monster_resistance = {"chicken": {}}
    gd._monster_hp = {"chicken": 30}
    gd._item_stats = {
        "twig": ItemStats(code="twig", level=1, type_="weapon", attack={"fire": 1}),
        "sword": ItemStats(code="sword", level=1, type_="weapon", attack={"fire": 9}),
    }
    return gd


def test_fight_cost_penalized_when_loadout_suboptimal():
    gd = _combat_gd()
    fight = FightAction(monster_code="chicken", locations=frozenset({(0, 0)}))
    under = make_state(level=1, equipment={"weapon_slot": "twig"}, inventory={"sword": 1}, x=0, y=0)
    optimal = make_state(level=1, equipment={"weapon_slot": "sword"}, inventory={}, x=0, y=0)
    assert fight.cost(under, gd) == fight.cost(optimal, gd) + LOADOUT_PENALTY


def test_planner_swaps_loadout_before_fighting():
    gd = _combat_gd()
    actions = [
        FightAction(monster_code="chicken", locations=frozenset({(0, 0)})),
        OptimizeLoadoutAction(target_monster_code="chicken", game_data=gd),
    ]
    state = make_state(level=1, xp=0, task_code=None, hp=100, max_hp=100,
                       equipment={"weapon_slot": "twig"}, inventory={"sword": 1}, x=0, y=0)
    goal = GrindCharacterXPGoal("chicken", initial_xp=0, game_data=gd)
    plan = GOAPPlanner().plan(state, goal, actions, gd, None)
    assert plan and repr(plan[0]) == "OptimizeLoadout(chicken)"   # swap FIRST

    # After swapping, the optimal loadout is equipped -> plan[0] is the Fight.
    equipped = make_state(level=1, xp=0, task_code=None, hp=100, max_hp=100,
                          equipment={"weapon_slot": "sword"}, inventory={}, x=0, y=0)
    plan2 = GOAPPlanner().plan(equipped, goal, actions, gd, None)
    assert plan2 and repr(plan2[0]) == "Fight(chicken)"
```

Verify `FightAction.is_applicable` lets the fight plan in this world (it checks `hp_percent > 0.3`, `min_level <= monster_level <= level+2`, and `best_equipped_level >= monster_level - 1`). With level 1, chicken level 1, twig/sword level 1 → applicable. Adjust the fixture if `is_applicable` blocks it (e.g. ensure `inventory_free >= 1`).

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_grind_character_xp.py -k "loadout_before or cost_penalized" -v`
Expected: FAIL — `ImportError: cannot import name 'LOADOUT_PENALTY'`; and the planner picks `Fight` first (no penalty yet).

- [ ] **Step 3: Add the penalty to `FightAction.cost`**

In `actions/combat.py`, add the import and constant, and the penalty term:

```python
from artifactsmmo_cli.ai.equipment.scoring import pick_loadout

LOADOUT_PENALTY = 5.0
"""Added to Fight cost when the loadout is suboptimal for the monster, so the
planner sequences OptimizeLoadout before the fight (player executes plan[0] only)."""
```

In `cost`, compute the base as today, then add the penalty:

```python
    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = _nearest(self.locations, state)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        static = 10.0 + dist
        if history is None:
            base = static
        else:
            learned = history.action_cost(repr(self), default=static, window=50)
            rate = history.success_rate(repr(self), window=50)
            base = learned / max(rate, 0.1) if rate < 0.95 else learned
        if pick_loadout(self.monster_code, state, game_data) != state.equipment:
            base += LOADOUT_PENALTY
        return base
```

(Refactor the existing branches into `base`, then add the penalty once.) `actions/combat.py` importing `equipment/scoring` is acyclic (scoring imports `actions/equipment`, not `actions/combat`).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_grind_character_xp.py -v` (all pass, incl. the sequencing test)
`uv run pytest -q` (full suite green — existing Fight-cost tests may need a `pick_loadout`-returns-current setup; if any existing test asserts an exact Fight cost, ensure its state's loadout is optimal/empty so no penalty applies, or update the expected value by `LOADOUT_PENALTY`)
`uv run ruff check src/artifactsmmo_cli/ai/actions/combat.py && uv run mypy src/artifactsmmo_cli/ai/actions/combat.py` (clean)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/combat.py tests/test_ai/test_grind_character_xp.py
git commit -m "feat(ai): penalize under-geared fights so the planner swaps loadout first

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Consumable-vs-rest overheal avoidance

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/consumable.py`
- Test: `tests/test_ai/test_actions_tier3.py` (or wherever `UseConsumableAction` is tested — grep `UseConsumableAction`)

- [ ] **Step 1: Write the failing test**

Find the consumable test file (`grep -rln "UseConsumableAction" tests/`). Add:

```python
def test_consumable_cheap_when_deficit_justifies_it():
    # deficit 60 >= potion restore 50 -> cheap (beats Rest 10.0)
    item_stats = {"potion": ItemStats(code="potion", level=1, type_="consumable", hp_restore=50)}
    action = UseConsumableAction(item_stats=item_stats)   # match real ctor
    state = make_state(hp=40, max_hp=100, inventory={"potion": 3})
    assert action.cost(state, GameData()) == 2.0


def test_consumable_expensive_when_overheal():
    # deficit 10 < potion restore 50 -> overheal -> cost above Rest (10.0)
    item_stats = {"potion": ItemStats(code="potion", level=1, type_="consumable", hp_restore=50)}
    action = UseConsumableAction(item_stats=item_stats)
    state = make_state(hp=90, max_hp=100, inventory={"potion": 3})
    assert action.cost(state, GameData()) > 10.0
```

Match `UseConsumableAction`'s real constructor (read `consumable.py` — it likely takes `item_stats` and uses `_best_consumable(state.inventory, self._item_stats)`).

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest <consumable test file> -k "overheal or deficit_justifies" -v`
Expected: FAIL — cost is the static `2.0` in both cases.

- [ ] **Step 3: Make `cost` overheal-aware**

In `actions/consumable.py`, replace the static `cost`:

```python
    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        best = _best_consumable(state.inventory, self._item_stats)
        if best is None:
            return 2.0                      # not applicable anyway; keep cheap default
        _, restore = best
        deficit = state.max_hp - state.hp
        if deficit >= restore:
            return 2.0                      # heal not wasted -> beats Rest (10.0)
        return 100.0                        # overheal -> let the planner Rest instead
```

(`_best_consumable` returns `(item_code, hp_restore)`; confirm its import/signature in the file. `RestAction.cost` stays `10.0`.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest <consumable test file> -v` (pass)
`uv run pytest -q` (full suite — fix any existing test asserting `UseConsumable` cost 2.0 in an overheal state)
`uv run ruff check src/artifactsmmo_cli/ai/actions/consumable.py && uv run mypy src/artifactsmmo_cli/ai/actions/consumable.py` (clean)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/consumable.py tests/test_ai/<consumable test file>
git commit -m "feat(ai): rest instead of overhealing with a consumable

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Full verification

**Files:** none

- [ ] **Step 1: Full suite** — `uv run pytest -q` → 0 failures, 0 errors, 0 skipped.
- [ ] **Step 2: Lint** — `uv run ruff check src tests` → clean.
- [ ] **Step 3: Type-check** — `uv run mypy src/artifactsmmo_cli/ai/game_data.py src/artifactsmmo_cli/ai/equipment/projection.py src/artifactsmmo_cli/ai/combat.py src/artifactsmmo_cli/ai/goals/grind_character_xp.py src/artifactsmmo_cli/ai/actions/combat.py src/artifactsmmo_cli/ai/actions/consumable.py src/artifactsmmo_cli/ai/strategy_driver.py` → no errors. Confirm `uv run mypy src` error count ≤ the pre-existing baseline (was 129 after P3c) — zero new errors in changed files.
- [ ] **Step 4: Coverage on changed code** — `uv run pytest tests/test_ai/test_equipment_projection.py tests/test_ai/test_combat.py tests/test_ai/test_game_data.py tests/test_ai/test_grind_character_xp.py --cov=artifactsmmo_cli.ai.equipment.projection --cov=artifactsmmo_cli.ai.combat --cov-report=term-missing -q` → `projection.py` and `combat.py` 100%; the added `ItemStats`/`grind`/`FightAction.cost`/`consumable.cost` lines covered. Add targeted tests for any uncovered new line.
- [ ] **Step 5: Commit (if Step 4 added tests)**

```bash
git add -A
git commit -m "test(ai): cover P4 tactical-refinement edge cases

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- ItemStats combat-effect parsing → Task 1. ✓
- `project_loadout_stats`/`ProjectedStats` → Task 2. ✓
- `predict_win` on best loadout → Task 3. ✓
- Grind goal loadout prerequisite (`is_satisfied` + `game_data` ctor) → Task 4. ✓
- Driver passes `game_data` → Task 4. ✓
- `FightAction.cost` loadout penalty + plan[0] sequencing (the decisive integration test) → Task 5. ✓
- Consumable overheal-avoidance → Task 6. ✓
- `OptimizeLoadout.apply` already updates equipment (no task needed — noted). ✓
- Testing (0/0/0, 100% on changed pure modules, grep/baseline) → Task 7. ✓

**Placeholder scan:** No TBD/TODO. Every code step shows full code. Test fixtures point at real helpers (`make_state`, `_gd` in test_combat, `_gd_with_monster` in test_grind, `make_page`) and name the exact import/constructor confirmations to do before writing (UseConsumable ctor, consumable test-file location, FightAction.is_applicable preconditions).

**Type consistency:** `ProjectedStats` fields ↔ `predict_win`'s `p.*` usage match (Task 2 ↔ 3). `project_loadout_stats(state, loadout, game_data)` signature consistent. `pick_loadout(monster_code, state, game_data)` used identically in combat.py, grind goal, and FightAction.cost. `GrindCharacterXPGoal(target_monster, initial_xp, game_data)` consistent Task 4 ↔ 5 ↔ driver. `LOADOUT_PENALTY` defined in actions/combat.py, imported by its test. `ItemStats` new fields (`dmg`/`dmg_elements`/`critical_strike`/`initiative`/`hp_bonus`) consistent Task 1 ↔ 2.
