# Generic Equipment Optimizer Per Action — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Robby picks the best equipment loadout (weapon + armor + accessories) for each fight, swapping in/out as needed. Currently he uses whatever's in his slots — fishing_net stays equipped even when fighting because nothing tells him to change.

**Architecture:** Element-aware scoring of every owned item against the target monster's attack profile and resistances. A new `OptimizeLoadoutAction(monster_code)` action becomes part of the planner's combat option list; it's only applicable when current loadout differs from optimal. Goals that drive combat (FarmMonster, GrindCharacterXP, ReachUnlockLevel) include it in `relevant_actions`. The planner naturally picks `Optimize → Fight` when the optimization is worth the equip-cost overhead.

**Spec:** None — design captured inline. Element model: fire, earth, water, air.

---

## File Structure

### New files
```
src/artifactsmmo_cli/ai/equipment/
├── __init__.py
├── elements.py              # ELEMENTS constant, helpers
├── scoring.py               # weapon_score(item, monster), armor_score(item, monster), pick_loadout
└── elements.py              # element list + per-element field lookups
src/artifactsmmo_cli/ai/actions/
└── optimize_loadout.py      # OptimizeLoadoutAction
```

### Modified files
```
src/artifactsmmo_cli/ai/game_data.py        # extend ItemStats + monster cache with element fields
src/artifactsmmo_cli/ai/world_state.py      # (no change — equipment dict already keyed by slot)
src/artifactsmmo_cli/ai/goals/combat.py     # FarmMonster.relevant_actions includes OptimizeLoadout
src/artifactsmmo_cli/ai/goals/grind_character_xp.py
src/artifactsmmo_cli/ai/goals/reach_unlock_level.py
src/artifactsmmo_cli/ai/player.py           # _build_actions creates OptimizeLoadoutAction per monster
```

---

## Task E-1: Extend ItemStats with element attack/resistance

**Files:** `src/artifactsmmo_cli/ai/game_data.py`

Add to ItemStats:
```python
attack: dict[str, int] = field(default_factory=dict)   # element_name -> attack value
resistance: dict[str, int] = field(default_factory=dict)  # element_name -> resistance %
```

Populate in `_load_items` by reading `item.effects`:
- An effect with code in `{"attack_fire", "attack_earth", "attack_water", "attack_air"}` → `attack[element] = value`
- An effect with code in `{"res_fire", "res_earth", "res_water", "res_air"}` → `resistance[element] = value`

Add tests asserting:
- weapon items expose `attack[element]`
- armor items expose `resistance[element]`

Commit.

---

## Task E-2: Extend monster cache with element profile

**Files:** `src/artifactsmmo_cli/ai/game_data.py`

Add to GameData:
```python
_monster_attack: dict[str, dict[str, int]] = field(default_factory=dict)
_monster_resistance: dict[str, dict[str, int]] = field(default_factory=dict)
```

Populate in `_load_monsters` from `mon.attack_{element}` and `mon.res_{element}` attributes.

Add accessor methods:
```python
def monster_attack(self, code: str) -> dict[str, int]:
def monster_resistance(self, code: str) -> dict[str, int]:
```

Tests for both.

Commit.

---

## Task E-3: Scoring + loadout picker

**Files:** `src/artifactsmmo_cli/ai/equipment/elements.py`, `scoring.py`

```python
# elements.py
ELEMENTS = ("fire", "earth", "water", "air")
```

```python
# scoring.py
def weapon_score(weapon_stats: ItemStats, monster_resistance: dict[str, int]) -> float:
    """Expected damage per hit. Higher = better against this monster."""
    score = 0.0
    for elem in ELEMENTS:
        atk = weapon_stats.attack.get(elem, 0)
        res_pct = monster_resistance.get(elem, 0)
        score += atk * max(0.0, 1.0 - res_pct / 100.0)
    return score

def armor_score(armor_stats: ItemStats, monster_attack: dict[str, int]) -> float:
    """Expected damage REDUCED per hit. Higher = better defense vs this monster."""
    score = 0.0
    for elem in ELEMENTS:
        mon_atk = monster_attack.get(elem, 0)
        armor_res_pct = armor_stats.resistance.get(elem, 0)
        score += mon_atk * armor_res_pct / 100.0
    return score

def pick_loadout(monster_code: str, state, game_data) -> dict[str, str]:
    """Return {slot: item_code} optimal loadout from items in inventory + equipment.

    Considers only items the char can equip (level >= item.level). Always
    includes whatever's already equipped as a candidate.

    Returns the current loadout unchanged when nothing better is available.
    """
```

Tests cover: water-vs-water-immune monster → 0 weapon score; weapon scores favor unresisted element; armor scores favor resisting monster's primary attack; pick_loadout returns dict keyed by slot.

Commit.

---

## Task E-4: OptimizeLoadoutAction

**Files:** `src/artifactsmmo_cli/ai/actions/optimize_loadout.py`

```python
class OptimizeLoadoutAction(Action):
    """Swap equipment to optimize for fighting `target_monster_code`."""

    tags = frozenset({"equip"})

    target_monster_code: str

    def is_applicable(self, state, game_data) -> bool:
        # Compute optimal loadout; applicable only when at least one slot
        # differs from the current loadout AND the target item is in inventory.
        ...

    def apply(self, state, game_data) -> WorldState:
        # Simulate: set state.equipment to the optimal dict.
        ...

    def cost(self, state, game_data, history=None) -> float:
        # ~5s per swap; cheap relative to a 30s fight cooldown.
        return 5.0 * num_swaps

    def execute(self, state, client) -> WorldState:
        # Dispatch unequip + equip API calls in sequence.
        # The MoveAction cooldown wait pattern doesn't apply (no movement).
        ...
```

Tests cover: applicable only when loadout differs; apply updates state.equipment; cost scales with swap count.

Commit.

---

## Task E-5: Wire into combat goals + action list

**Files:**
- `src/artifactsmmo_cli/ai/player.py` — `_build_actions` creates one `OptimizeLoadoutAction(code)` per monster the bot might fight.
- `src/artifactsmmo_cli/ai/goals/combat.py` (FarmMonsterGoal)
- `src/artifactsmmo_cli/ai/goals/grind_character_xp.py`
- `src/artifactsmmo_cli/ai/goals/reach_unlock_level.py`

For each combat goal's `relevant_actions`, include `OptimizeLoadoutAction(target_monster)` if present.

Tests:
- Building actions creates one OptimizeLoadout per monster
- FarmMonsterGoal.relevant_actions includes the OptimizeLoadout for its target monster
- End-to-end: planner picks `OptimizeLoadout(slime) → Fight(slime)` when current loadout is suboptimal

Commit.

---

## Final validation

- [ ] Full test suite: `uv run pytest -q`
- [ ] Smoke test on real Robby: confirm `pick_loadout("yellow_slime", state, gd)` recommends a weapon dealing water/air damage (yellow_slime res_earth=25, res_water=0, res_air=0, res_fire=0).
- [ ] Restart with `--tui`: observe `OptimizeLoadout(yellow_slime)` in goal_rank trace before the first Fight when loadout is wrong.
