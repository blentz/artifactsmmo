# Phase G-G — Max-Level Discovery & Cheapest-Path Projection Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Expose the documented character-level cap on `GameData` and add a `cheapest_path_to_level` projection that walks the `BlockerRegistry` DAG using observed per-monster XP to estimate cycles-to-reach. Foundation for G-H (char-XP-rate scoring) and G-I (path-aware meta-policy).

**Architecture:** No behavior change to goal selection in this phase. Just new read-only primitives. Two pieces: `GameData.max_character_level` (cached) and `cheapest_path_to_level(target, state, registry, store, game_data) -> PathPlan | None`. PathPlan is a pydantic model with `total_cycles` + `per_level` breakdown.

**Spec:** `docs/superpowers/specs/2026-05-18-max-level-objective-design.md` §1, §2.

**Tech Stack:** Python 3.13, uv, pydantic, pytest. No new dependencies.

---

## File Structure

### Modified files
```
src/artifactsmmo_cli/ai/game_data.py        # max_character_level computed property
src/artifactsmmo_cli/ai/learning/projections.py  # PathPlan + cheapest_path_to_level
tests/test_ai/test_game_data.py             # max_character_level test
tests/test_ai/test_learning_projections.py  # PathPlan + path projection tests
```

### New files
None.

---

## Task G-G.1: `GameData.max_character_level`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py`
- Modify: `tests/test_ai/test_game_data.py`

- [ ] **Step 1: Test**

```python
def test_max_character_level_from_monsters():
    gd = GameData()
    gd._monster_level = {"chicken": 1, "yellow_slime": 3, "sea_marauder": 45, "boss": 55}
    assert gd.max_character_level == 55

def test_max_character_level_empty_data():
    gd = GameData()
    assert gd.max_character_level == 1  # safe floor

def test_max_character_level_caches():
    gd = GameData()
    gd._monster_level = {"a": 10}
    assert gd.max_character_level == 10
```

- [ ] **Step 2: Add the property to GameData**

```python
@property
def max_character_level(self) -> int:
    """Highest character level required by any documented monster.

    Tentative ceiling derived from monster levels (no documented
    explicit cap in API). Used by G-G's path projection to bound the
    search. Returns 1 when no monsters are loaded (safe floor —
    treats char as already at max so the projection doesn't divide
    by zero or recurse forever)."""
    if not self._monster_level:
        return 1
    return max(self._monster_level.values())
```

- [ ] **Step 3: Tests pass.**

- [ ] **Step 4: Commit**

```bash
git add src/artifactsmmo_cli/ai/game_data.py tests/test_ai/test_game_data.py
git commit -m "feat(ai/game_data): expose max_character_level computed from monster ladder (G-G.1)"
```

---

## Task G-G.2: `PathPlan` + `cheapest_path_to_level`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/projections.py`
- Modify: `tests/test_ai/test_learning_projections.py`

### Approach

The path is a chain of monster-grind segments, one per character level. At each level, the bot grinds whichever beatable monster gives the highest observed char_xp/cycle (or a game-data default when unobserved).

Each segment cost = `xp_needed_for_next_level / char_xp_per_cycle * cycles_per_kill`.

We don't model gathering/crafting detours in this phase — those are blockers a future phase can route through. G-G handles the common case: combat-driven leveling.

### Pydantic models

```python
class PathSegment(BaseModel):
    from_level: int
    to_level: int
    monster_code: str
    estimated_cycles: float
    xp_per_cycle: float
    cycles_per_kill: float

class PathPlan(BaseModel):
    target_level: int
    total_cycles: float
    segments: list[PathSegment]
    blocked: bool = False
    """True when no beatable monster exists at some intermediate level."""

    @property
    def next_action_monster(self) -> str | None:
        return self.segments[0].monster_code if self.segments else None
```

### Function

```python
def cheapest_path_to_level(
    target_level: int,
    state: WorldState,
    registry: BlockerRegistry,
    store: LearningStore,
    game_data: GameData,
    default_xp_per_kill: float = 5.0,
    default_cycles_per_kill: float = 30.0,
) -> PathPlan:
    """Estimate cycles to reach target_level from state.level using
    the cheapest beatable monster at each intermediate level.

    Walks one level at a time. At each level, enumerates monsters where
    `monster_level <= sim_level + 1` (the FightAction.is_applicable
    margin). Picks the monster with the highest expected char_xp per
    cycle from history; falls back to `default_xp_per_kill *
    monster_level / default_cycles_per_kill` when unobserved.
    """
```

- [ ] **Step 1: Failing tests**

```python
class TestCheapestPathToLevel:
    def test_returns_empty_path_when_already_at_target(self):
        # state.level == target → zero-cycle path
        ...

    def test_uses_observed_xp_when_available(self, tmp_path):
        # Seed FarmMonster(chicken) with delta_xp=20/cycle.
        # Path from level 1 to 2 with xp_to_next_level=50 → 50/20 = 2.5 cycles.
        ...

    def test_falls_back_to_default_when_no_observations(self, tmp_path):
        # Empty store. Should still return a path using default XP heuristic.
        ...

    def test_blocked_when_no_beatable_monster_at_level(self, tmp_path):
        # GameData only has level-100 monsters; char at level 1.
        # Returns PathPlan(blocked=True, total_cycles=inf, segments=[]).
        ...

    def test_picks_highest_xp_monster_at_each_level(self, tmp_path):
        # Two beatable monsters: chicken yields 5xp/cycle, slime yields 15.
        # Path should pick slime.
        ...

    def test_path_extends_across_levels(self, tmp_path):
        # Char at level 1, target level 3. Path has 2 segments.
        ...

    def test_next_action_monster_returns_first_segment(self):
        # PathPlan with two segments → next_action_monster == segments[0].monster_code.
        ...
```

- [ ] **Step 2: Verify all fail.**

- [ ] **Step 3: Implement.** Algorithm:

```python
def cheapest_path_to_level(target_level, state, registry, store, game_data, ...):
    if state.level >= target_level:
        return PathPlan(target_level=target_level, total_cycles=0.0, segments=[])

    segments: list[PathSegment] = []
    sim_level = state.level
    sim_xp = state.xp
    sim_max_xp = state.max_xp

    while sim_level < target_level:
        # Find beatable monsters at this sim level.
        beatable = [
            (code, lvl) for code, lvl in game_data._monster_level.items()
            if 1 <= lvl <= sim_level + 1
        ]
        if not beatable:
            return PathPlan(target_level=target_level, total_cycles=float("inf"),
                            segments=segments, blocked=True)
        # Pick highest observed char_xp/cycle.
        best = None
        for code, lvl in beatable:
            yield_ = expected_yield_per_cycle(f"FarmMonster({code})", store)
            if yield_.sample_count > 0:
                xp_per_cycle = yield_.char_xp
            else:
                # Fallback: estimate XP from monster level.
                xp_per_cycle = default_xp_per_kill * lvl / default_cycles_per_kill
            if best is None or xp_per_cycle > best[1]:
                best = (code, xp_per_cycle, lvl)
        code, xp_per_cycle, lvl = best
        if xp_per_cycle <= 0:
            return PathPlan(target_level=target_level, total_cycles=float("inf"),
                            segments=segments, blocked=True)
        xp_needed = sim_max_xp - sim_xp
        cycles = xp_needed / xp_per_cycle
        # cycles_per_kill: how many cycles to kill one monster. Use observed cost
        # or a default.
        cost = store.action_cost(f"Fight({code})", default=default_cycles_per_kill)
        segments.append(PathSegment(
            from_level=sim_level, to_level=sim_level + 1,
            monster_code=code, estimated_cycles=cycles,
            xp_per_cycle=xp_per_cycle, cycles_per_kill=cost,
        ))
        sim_level += 1
        sim_xp = 0  # naive — assume new level starts at 0 XP
        # Re-fetch sim_max_xp from game data if available, else stay constant
        # (game data may not expose per-level XP curve; this is a known limitation).

    total = sum(s.estimated_cycles for s in segments)
    return PathPlan(target_level=target_level, total_cycles=total, segments=segments)
```

- [ ] **Step 4: Tests pass.**

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/projections.py tests/test_ai/test_learning_projections.py
git commit -m "feat(ai/learning): cheapest_path_to_level projection (G-G.2)"
```

---

## Final validation gate

- [ ] Full test suite: `uv run pytest -q`
- [ ] Sanity check on real data:

```bash
uv run python -c "
from pathlib import Path
from artifactsmmo_cli.config import Config
from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.blockers import BlockerRegistry, seed_documented_blockers
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
from artifactsmmo_cli.ai.world_state import WorldState
# ... build real state for Robby ...
plan = cheapest_path_to_level(gd.max_character_level, state, reg, store, gd)
print(f'max_level={gd.max_character_level}')
print(f'total_cycles={plan.total_cycles:.0f}')
print(f'next_monster={plan.next_action_monster}')
print(f'segments=')
for s in plan.segments[:10]:
    print(f'  L{s.from_level}→L{s.to_level}: {s.monster_code} ({s.estimated_cycles:.0f} cycles)')
"
```

Phase G-G is complete when those pass. G-H (char-XP-rate scoring) consumes
the projection.
