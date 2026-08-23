# Goal/Decision Graph Implementation Plan (waves 1-2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Declare the meta-decisions that today live as control flow inside
`objective_step_goal`, and rewire the one that is wrong, so a skill-gated gear
target raises the skill instead of gathering materials it cannot use.

**Architecture:** Add `Decision` as a first-class node type beside the existing
`Goal` ABC, over an unchanged `GOAPPlanner`/A*/`Action` layer. Add a tier ladder
derived from game data (never hardcoded). Transcribe the eight implicit branches
of `objective_step_goal` into named `Decision` nodes with identical behaviour,
then change exactly one edge.

**Tech Stack:** Python 3.13, `uv`, pytest, mypy strict, ruff, Lean 4 (untouched
by waves 1-2).

**Spec:** `docs/superpowers/specs/2026-08-22-goal-decision-graph-design.md`

## Global Constraints

- Every Python command is prefixed `uv run` (CLAUDE.md).
- One behavioural class per file. Pure data/schema/enum groups may share a module.
- No inline imports; no `if TYPE_CHECKING`; no triple-dot imports.
- Never catch `Exception`.
- No defaulting around missing API data — use API data or fail with an error.
- Tests live under `tests/`; success criteria are 0 errors, 0 warnings, 0 skipped,
  100% coverage.
- Implementers end each task with `uv run ruff check src/ tests/` then
  `bash scripts/run_tests.sh`, run ONE AT A TIME. The controller runs the full
  `formal/gate.sh` between tasks. Check exit codes directly or via
  `${PIPESTATUS[0]}` — piping to `tail` masks the code.
- Do not create a second implementation of anything. Fix in place.

---

## Sequencing correction discovered while planning

The spec's wave 2 bundled the gate-closed action set and the `LevelSkill`
deletion with the edge rewire. Reading `ai/goals/reach_skill.py` shows those
cannot ship together:

`ReachSkillGoal.relevant_actions` selects **exactly** the `"skill_grind"`-tagged
`LevelSkill` actions. So the goal that the rewired edge routes to is *built on*
`LevelSkill`. Removing `LevelSkill` from the action set in the same wave would
break the very edge being fixed.

Correct order, reflected in the tasks below:

1. Waves 1-2 (this plan) — ladder, `Decision`, transcription, **one edge rewired
   using the existing `LevelSkill` machinery**, and `MaxGearForLevel`.
2. Wave 3 (separate plan) — teach `SkillToNextLevel` to plan the rung craft
   directly, then close the gate in `relevant_actions`, then delete `LevelSkill`.

This is strictly better: the one behaviour change ships alone and gets live
evidence before anything is deleted. The CPU win moves to wave 3.

## Known duplication to resolve, not silently

`src/artifactsmmo_cli/audit/content_tiers.py` already defines a `ContentTier`
with **fixed 10-level bands** (`level // 10`). It has **no production consumer** —
only `scripts/gen_content_tiers.py` and the behavioural-completeness matrix
document.

The ladder this plan adds is different: derived from item levels, eleven uneven
steps. Two things named "tier" is exactly the confusion this epic removes, so
Task 1 pins the distinction with a docstring cross-reference and a test. Do
**not** merge them in this plan; that decision belongs with the matrix owner.

---

## File structure

| File | Responsibility |
|---|---|
| `src/artifactsmmo_cli/ai/tiers/tier_ladder.py` (create) | Pure derived ladder: `ladder`, `tier_of_level`, `band`, `normal_band` |
| `src/artifactsmmo_cli/ai/tiers/tier_progress.py` (create) | State-aware: `next_uncleared_tier`, `gear_target_tier` |
| `src/artifactsmmo_cli/ai/decision.py` (create) | `Node` marker + `Decision` base class |
| `src/artifactsmmo_cli/ai/decisions/obtain_item.py` (create) | The six `ObtainItem` Decisions |
| `src/artifactsmmo_cli/ai/strategy_driver.py` (modify) | `objective_step_goal` delegates to the Decisions |
| `src/artifactsmmo_cli/ai/tiers/objective.py` (modify) | `near_term_gear` gains a blocker-emitting sibling |
| `tests/test_ai/test_tier_ladder.py` (create) | Ladder + partition census |
| `tests/test_ai/test_tier_progress.py` (create) | Clear rule and gear target tier |
| `tests/test_ai/test_decision.py` (create) | `Decision` protocol |
| `tests/test_ai/test_decisions_obtain_item.py` (create) | Transcription parity + the rewired edge |
| `tests/test_ai/test_max_gear_for_level.py` (create) | Blocker-instead-of-filter invariant |

---

## Task 1: Derived tier ladder

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/tier_ladder.py`
- Test: `tests/test_ai/test_tier_ladder.py`

**Interfaces:**
- Consumes: `GameData.all_item_stats` (`Mapping[str, ItemStats]`, each with
  `.level: int`, `.type_: str`), `GameData.monster_levels`
  (`Mapping[str, int]`), `GameData.monsters.types` (`dict[str, str]`),
  `ITEM_TYPE_TO_SLOTS` from `artifactsmmo_cli.ai.gear_taxonomy`.
- Produces:
  - `ladder(game_data: GameData) -> tuple[int, ...]`
  - `tier_of_level(game_data: GameData, level: int) -> int`
  - `band(game_data: GameData, tier: int) -> tuple[str, ...]`
  - `normal_band(game_data: GameData, tier: int) -> tuple[str, ...]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_tier_ladder.py`:

```python
"""The tier ladder is DERIVED from item levels, never hardcoded, and its
monster bands partition the whole monster table."""
from itertools import pairwise

import pytest

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.tier_ladder import (
    band,
    ladder,
    normal_band,
    tier_of_level,
)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "battlestaff": ItemStats(code="battlestaff", level=20, type_="weapon"),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
    }
    gd._monster_level = {"chicken": 1, "mushmush": 10, "skeleton": 18,
                         "spider": 20, "king_slime": 15}
    gd._monster_type = {"chicken": "normal", "mushmush": "normal",
                        "skeleton": "normal", "spider": "normal",
                        "king_slime": "boss"}
    return gd


def test_ladder_is_the_distinct_equippable_levels():
    assert ladder(_gd()) == (1, 10, 20)


def test_ladder_ignores_non_equippable_items():
    """ash_plank is level 1 but is a resource, not gear — it must not create
    or confirm a rung on its own."""
    gd = _gd()
    gd._item_stats = {"ash_plank": ItemStats(code="ash_plank", level=7,
                                             type_="resource")}
    assert ladder(gd) == ()


def test_tier_of_level_floors_to_the_rung():
    gd = _gd()
    assert tier_of_level(gd, 1) == 1
    assert tier_of_level(gd, 9) == 1
    assert tier_of_level(gd, 10) == 10
    assert tier_of_level(gd, 25) == 20


def test_tier_of_level_below_the_first_rung_is_the_first_rung():
    assert tier_of_level(_gd(), 0) == 1


def test_tier_of_level_with_no_equippables_raises():
    """The project gate is `--cov-fail-under=100`, so the totality guard needs
    a test rather than being left as an unexecuted line."""
    gd = GameData()
    gd._item_stats = {}
    with pytest.raises(ValueError, match="no equippable items"):
        tier_of_level(gd, 5)


def test_band_holds_monsters_from_the_rung_up_to_the_next():
    gd = _gd()
    assert band(gd, 1) == ("chicken",)
    assert band(gd, 10) == ("king_slime", "mushmush", "skeleton")
    assert band(gd, 20) == ("spider",)


def test_normal_band_drops_boss_elite_and_raid_boss():
    """king_slime is a level-15 boss with 1000 hp and 20 resist on every
    element; leaving it in band(10) would stall that rung forever."""
    assert normal_band(_gd(), 10) == ("mushmush", "skeleton")


def test_the_bands_partition_every_monster_exactly_once():
    gd = _gd()
    seen = [code for tier in ladder(gd) for code in band(gd, tier)]
    assert sorted(seen) == sorted(gd.monster_levels)
    assert len(seen) == len(set(seen))
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_ai/test_tier_ladder.py -q --no-cov
```

Expected: collection error, `ModuleNotFoundError: No module named
'artifactsmmo_cli.ai.tiers.tier_ladder'`.

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/ai/tiers/tier_ladder.py`:

```python
"""The progression ladder, DERIVED from game data.

Every equippable item in the game sits on one of a small set of levels, and the
craft-skill breakpoints use the same set. Against the live catalogue that set is
`(1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50)` — but it is read from the data on
every call, never written down, so a content patch moves the ladder without a
code change.

A tier's BAND is the monsters from that rung up to (not including) the next. The
bands partition the whole monster table.

NOT `audit/content_tiers.py`. That module buckets content into fixed ten-level
windows (`level // 10`) as the journey axis of the behavioural-completeness
matrix document, and has no production consumer. This ladder is uneven, derived,
and is what the planner descends. The two are different axes over the same world
and must not be merged without the matrix owner's agreement.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_taxonomy import ITEM_TYPE_TO_SLOTS

NON_FARMABLE_TYPES = frozenset({"boss", "elite", "raid_boss"})
"""Monster types excluded from a tier's clear condition.

The API publishes `monster.type` on every record (`MonsterCatalog.types`,
already read by `xp_per_kill`). Boss, elite and raid content is optional and
carries its own objectives; gating the ladder on it stalls progression. Live
case: `king_slime` is a level-15 boss with 1000 hp and 20 resistance on all four
elements, and it blocks a level-30 character out of the level-15 rung.
"""


def ladder(game_data: GameData) -> tuple[int, ...]:
    """The ascending distinct levels of every EQUIPPABLE item."""
    return tuple(sorted({
        stats.level for stats in game_data.all_item_stats.values()
        if stats.type_ in ITEM_TYPE_TO_SLOTS and stats.level > 0
    }))


def tier_of_level(game_data: GameData, level: int) -> int:
    """The highest rung at or below `level`; the first rung when below it all."""
    rungs = ladder(game_data)
    if not rungs:
        raise ValueError("no equippable items in game data — cannot derive a ladder")
    at_or_below = [rung for rung in rungs if rung <= level]
    return at_or_below[-1] if at_or_below else rungs[0]


def band(game_data: GameData, tier: int) -> tuple[str, ...]:
    """Monster codes from `tier` up to the next rung, sorted. Every monster
    falls in exactly one band."""
    rungs = ladder(game_data)
    higher = [rung for rung in rungs if rung > tier]
    ceiling = higher[0] if higher else None
    return tuple(sorted(
        code for code, level in game_data.monster_levels.items()
        if level >= tier and (ceiling is None or level < ceiling)
    ))


def normal_band(game_data: GameData, tier: int) -> tuple[str, ...]:
    """`band`, minus boss / elite / raid_boss — the monsters a rung is cleared on."""
    types = game_data.monsters.types
    return tuple(code for code in band(game_data, tier)
                 if types.get(code, "normal") not in NON_FARMABLE_TYPES)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_ai/test_tier_ladder.py -q --no-cov
```

Expected: 7 passed.

- [ ] **Step 5: Add the live partition census**

Append to `tests/test_ai/test_tier_ladder.py`:

```python
def test_the_live_catalogue_partitions_without_gaps(bundle_game_data):
    """Census: against the committed game-data bundle every monster is binned
    exactly once and no band is empty. This is the check that would have caught
    `cheapest_path_to_level`'s floor of 1 — a band with no lower edge."""
    gd = bundle_game_data
    rungs = ladder(gd)
    assert rungs, "ladder must be non-empty"
    assert rungs == tuple(sorted(set(rungs))), "ladder must be ascending and distinct"
    binned = [code for tier in rungs for code in band(gd, tier)]
    assert sorted(binned) == sorted(gd.monster_levels), "every monster binned once"
    assert len(binned) == len(set(binned)), "no monster in two bands"
    for tier in rungs:
        assert band(gd, tier), f"band T{tier} is empty"


def test_the_live_ladder_is_not_the_audit_ten_level_banding(bundle_game_data):
    """Pins the distinction from `audit/content_tiers.py`, so a later reader
    cannot 'unify' them by accident. The derived ladder is uneven."""
    rungs = ladder(bundle_game_data)
    steps = {b - a for a, b in pairwise(rungs)}
    assert steps != {10}, "derived ladder must not be a uniform 10-level banding"
```

Add this fixture to `tests/test_ai/conftest.py`. That file currently holds
only `make_planner_gd`, so the fixture is new — append it, do not replace the
file:

```python
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.scenario import load_bundle_game_data

_BUNDLE = (Path(__file__).resolve().parents[1]
           / "test_ai" / "scenarios" / "fixtures" / "gamedata_bundle.json")


@pytest.fixture
def bundle_game_data():
    """The committed game-data bundle — the same fixture the scenario harness
    and the `plan --scenario` diagnostic load."""
    return load_bundle_game_data(_BUNDLE)
```

- [ ] **Step 6: Run the census**

```bash
uv run pytest tests/test_ai/test_tier_ladder.py -q --no-cov
```

Expected: 9 passed. If the bundle's monster records carry no `type`, the
`normal_band` default of `"normal"` keeps the census green — confirm by
inspecting one record rather than assuming.

- [ ] **Step 7: Lint and the coverage-enforcing suite**

Run these ONE AT A TIME, with nothing else running in the worktree:

```bash
uv run ruff check src/ tests/
bash scripts/run_tests.sh
```

Expected: `All checks passed!` from the first, and
`Required test coverage of 100% reached` from the second.

Do NOT use `--no-cov` — the project sets `--cov-fail-under=100` and an
unexecuted line in new code fails the gate. Do NOT run `formal/gate.sh` here;
the controller runs it between tasks. Two processes sharing this worktree
corrupt the shared `.coverage` file and produce a bogus ~45% total.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/tier_ladder.py \
        tests/test_ai/test_tier_ladder.py tests/test_ai/conftest.py
git commit -m "feat(tiers): derive the progression ladder from item levels

Every equippable sits on one of eleven levels and the craft breakpoints use the
same set, so the ladder is read from game data rather than written down. Bands
partition the whole monster table; boss/elite/raid_boss are excluded from a
rung's clear condition via the API's own monster.type.

Nothing consumes this yet."
```

---

## Task 2: Tier progress — the clear rule and the gear target

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/tier_progress.py`
- Test: `tests/test_ai/test_tier_progress.py`

**Interfaces:**
- Consumes: `ladder`, `normal_band`, `tier_of_level` from Task 1;
  `is_winnable(state, game_data, monster_code, history)` from
  `artifactsmmo_cli.ai.combat`.
- Produces:
  - `tier_cleared(state, game_data, tier, history) -> bool`
  - `next_uncleared_tier(state, game_data, history) -> int | None`
  - `gear_target_tier(state, game_data, history) -> int`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_tier_progress.py`:

```python
"""A rung is cleared when every NORMAL monster in its band is winnable; the gear
target is the rung being cleared, capped by character level."""
import artifactsmmo_cli.ai.tiers.tier_progress as mod
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.tier_progress import (
    gear_target_tier,
    next_uncleared_tier,
    tier_cleared,
)
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon"),
        "battlestaff": ItemStats(code="battlestaff", level=20, type_="weapon"),
    }
    gd._monster_level = {"chicken": 1, "mushmush": 10, "king_slime": 15,
                         "spider": 20}
    gd._monster_type = {"chicken": "normal", "mushmush": "normal",
                        "king_slime": "boss", "spider": "normal"}
    return gd


def test_a_rung_is_cleared_when_every_normal_monster_is_winnable(monkeypatch):
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: True)
    assert tier_cleared(make_state(level=30), _gd(), 10, None) is True


def test_an_unwinnable_normal_monster_leaves_the_rung_uncleared(monkeypatch):
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "mushmush")
    assert tier_cleared(make_state(level=30), _gd(), 10, None) is False


def test_an_unwinnable_boss_does_not_block_the_rung(monkeypatch):
    """king_slime sits in band(10) and is a boss. Live, it blocked a level-30
    character out of the level-15 rung forever."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "king_slime")
    assert tier_cleared(make_state(level=30), _gd(), 10, None) is True


def test_next_uncleared_is_the_lowest_rung_with_an_unwinnable_normal(monkeypatch):
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "spider")
    assert next_uncleared_tier(make_state(level=30), _gd(), None) == 20


def test_next_uncleared_is_none_when_everything_is_winnable(monkeypatch):
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: True)
    assert next_uncleared_tier(make_state(level=30), _gd(), None) is None


def test_gear_target_is_the_rung_being_cleared_not_the_character_level(monkeypatch):
    """Robby's live case: level 30 with the level-20 rung uncleared. Targeting
    T30 gear demands materials from monsters he cannot beat; T20 gear crafts
    from content he has already cleared."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "spider")
    assert gear_target_tier(make_state(level=30), _gd(), None) == 20


def test_gear_target_is_capped_by_character_level(monkeypatch):
    """A level-5 character clearing the level-20 rung still cannot wear T20."""
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: c != "spider")
    assert gear_target_tier(make_state(level=5), _gd(), None) == 1


def test_gear_target_with_nothing_left_to_clear_is_the_level_rung(monkeypatch):
    monkeypatch.setattr(mod, "is_winnable", lambda s, g, c, h: True)
    assert gear_target_tier(make_state(level=30), _gd(), None) == 20
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_ai/test_tier_progress.py -q --no-cov
```

Expected: `ModuleNotFoundError: ... tier_progress`.

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/ai/tiers/tier_progress.py`:

```python
"""Where a character stands on the derived ladder.

A rung is CLEARED when every normal monster in its band is winnable at
restorable HP. Boss, elite and raid content never gates it (see
`tier_ladder.NON_FARMABLE_TYPES`).

The GEAR TARGET is the rung being cleared, capped by character level — NOT the
character's level rung. Live 2026-08-22: Robby at level 30 had the level-20 rung
uncleared. Targeting level-30 gear demands `cyclops_eye`, `imp_tail` and
`demon_horn` from monsters he cannot beat, which is the same unreachable-target
failure the ladder exists to remove. Level-20 gear crafts from level-15 content,
which he has cleared by definition. Character level CAPS the target; it never
sets it.
"""

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.tier_ladder import ladder, normal_band, tier_of_level
from artifactsmmo_cli.ai.world_state import WorldState


def tier_cleared(state: WorldState, game_data: GameData, tier: int,
                 history: LearningStore | None) -> bool:
    """Is every normal monster in `tier`'s band winnable?"""
    return all(is_winnable(state, game_data, code, history)
               for code in normal_band(game_data, tier))


def next_uncleared_tier(state: WorldState, game_data: GameData,
                        history: LearningStore | None) -> int | None:
    """The lowest rung not yet cleared, or None when the ladder is finished."""
    for tier in ladder(game_data):
        if not tier_cleared(state, game_data, tier, history):
            return tier
    return None


def gear_target_tier(state: WorldState, game_data: GameData,
                     history: LearningStore | None) -> int:
    """The rung to gear for: the one being cleared, capped by character level."""
    level_rung = tier_of_level(game_data, state.level)
    clearing = next_uncleared_tier(state, game_data, history)
    if clearing is None:
        return level_rung
    return min(level_rung, clearing)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_ai/test_tier_progress.py -q --no-cov
```

Expected: 8 passed.

- [ ] **Step 5: Lint and the coverage-enforcing suite**

```bash
uv run ruff check src/ tests/
bash scripts/run_tests.sh
```

Run them ONE AT A TIME with nothing else active in the worktree — concurrent
processes corrupt the shared `.coverage` file and report a bogus ~45% total.
Never pass `--no-cov`: the project sets `--cov-fail-under=100`, so a single
unexecuted line in new code fails the gate. `formal/gate.sh` is the
controller's job, not yours.

Expected: `All checks passed!`, then `Required test coverage of 100% reached`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/tier_progress.py \
        tests/test_ai/test_tier_progress.py
git commit -m "feat(tiers): clear rule and gear target tier

A rung clears when every NORMAL monster in its band is winnable, so a boss
parked in a low band cannot stall progression. The gear target is the rung being
cleared capped by character level, not the character's level rung — targeting
above the cleared frontier demands materials from monsters the character cannot
beat.

Nothing consumes this yet."
```

---

## Task 3: The `Decision` node type

**Files:**
- Create: `src/artifactsmmo_cli/ai/decision.py`
- Test: `tests/test_ai/test_decision.py`

**Interfaces:**
- Consumes: `Goal` from `artifactsmmo_cli.ai.goals.base`.
- Produces: `Node` (type alias), `Decision` (ABC with `name: str` and
  `resolve(state, game_data, ctx, history) -> Node | None`), and
  `resolve_node(node, state, game_data, ctx, history) -> Goal | None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_decision.py`:

```python
"""Decision is a named branch point. It is never planned; it resolves to a Goal
or to another Decision."""
from artifactsmmo_cli.ai.decision import Decision, resolve_node
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from tests.test_ai.fixtures import make_state


class _Fixed(Decision):
    name = "Fixed"

    def __init__(self, child):
        self._child = child

    def resolve(self, state, game_data, ctx, history):
        return self._child


def test_resolve_node_returns_a_goal_unchanged():
    goal = WaitGoal()
    assert resolve_node(goal, make_state(), None, None, None) is goal


def test_resolve_node_walks_a_decision_to_its_goal():
    goal = WaitGoal()
    assert resolve_node(_Fixed(goal), make_state(), None, None, None) is goal


def test_resolve_node_walks_nested_decisions():
    goal = WaitGoal()
    nested = _Fixed(_Fixed(goal))
    assert resolve_node(nested, make_state(), None, None, None) is goal


def test_a_decision_resolving_to_none_yields_none():
    assert resolve_node(_Fixed(None), make_state(), None, None, None) is None


def test_a_cycle_raises_rather_than_hanging():
    """A Decision graph must be acyclic. A cycle is a programming error and
    must fail loudly, not spin."""
    class _Loop(Decision):
        name = "Loop"

        def resolve(self, state, game_data, ctx, history):
            return self

    try:
        resolve_node(_Loop(), make_state(), None, None, None)
    except RecursionError as exc:
        assert "Loop" in str(exc)
    else:
        raise AssertionError("expected RecursionError")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
uv run pytest tests/test_ai/test_decision.py -q --no-cov
```

Expected: `ModuleNotFoundError: ... ai.decision`.

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/ai/decision.py`:

```python
"""`Decision`: a named branch point in the goal graph.

The meta-decisions this bot makes — can I craft this tier, is there a combat
target, is an items task active — have always existed. They lived as control
flow inside `strategy_driver.objective_step_goal`, a 145-line `if`-pile, where
nothing could name them, test them one at a time, or notice that one of them
pointed at the wrong child. Live 2026-08-22: `Can_I_Craft_Current_Tier`'s "no"
branch routed to "gather the materials anyway" instead of "raise the skill", and
weaponcrafting sat frozen at 10 across the whole fleet for six days.

A `Decision` is never planned. It resolves to a `Goal` (which the unchanged
`GOAPPlanner` solves) or to another `Decision`. The GOAP layer, the `Goal` ABC
and every `Action` are untouched by this type.
"""

from abc import ABC, abstractmethod
from typing import Union

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

MAX_RESOLVE_DEPTH = 32
"""Bound on one resolution walk.

Not a tuning knob: the graph is a DAG by construction, because every recursive
edge strictly decreases the lexicographic measure (tier, character level, skill
level, materials outstanding). Exceeding this means a cycle was introduced, which
is a programming error, so it raises rather than truncating.
"""


class Decision(ABC):
    """A named predicate over state that selects a child node."""

    name: str

    @abstractmethod
    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> Union["Decision", Goal, None]:
        """The child this decision selects for `state`. None = no child."""


Node = Union[Decision, Goal]


def resolve_node(node: Node | None, state: WorldState, game_data: GameData,
                 ctx: SelectionContext, history: LearningStore | None
                 ) -> Goal | None:
    """Walk `node` down to the Goal it selects, or None."""
    seen: list[str] = []
    current = node
    for _ in range(MAX_RESOLVE_DEPTH):
        if current is None or isinstance(current, Goal):
            return current
        seen.append(current.name)
        current = current.resolve(state, game_data, ctx, history)
    raise RecursionError(
        f"Decision graph did not terminate in {MAX_RESOLVE_DEPTH} steps; "
        f"walk was {' -> '.join(seen)}")
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_ai/test_decision.py -q --no-cov
```

Expected: 5 passed. (`WaitGoal()` takes no constructor arguments — verified
against `src/artifactsmmo_cli/ai/goals/wait.py:28`.)

- [ ] **Step 5: Lint and the coverage-enforcing suite**

```bash
uv run ruff check src/ tests/
bash scripts/run_tests.sh
```

Run them ONE AT A TIME with nothing else active in the worktree — concurrent
processes corrupt the shared `.coverage` file and report a bogus ~45% total.
Never pass `--no-cov`: the project sets `--cov-fail-under=100`, so a single
unexecuted line in new code fails the gate. `formal/gate.sh` is the
controller's job, not yours.

Expected: `All checks passed!`, then `Required test coverage of 100% reached`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/decision.py tests/test_ai/test_decision.py
git commit -m "feat(decision): Decision as a first-class node beside Goal

The meta-decisions already exist as control flow inside objective_step_goal.
Declaring them as nodes is what makes one of them reviewable as wrong. GOAP, the
Goal ABC and every Action are untouched.

Nothing consumes this yet."
```

---

## Task 4: Transcribe the six `ObtainItem` branches

**Files:**
- Create: `src/artifactsmmo_cli/ai/decisions/__init__.py` (empty)
- Create: `src/artifactsmmo_cli/ai/decisions/obtain_item.py`
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py:882-1006`
- Test: `tests/test_ai/test_decisions_obtain_item.py`

**Interfaces:**
- Consumes: `Decision`, `Node` from Task 3; every helper
  `objective_step_goal` already imports (`analyze_currency_leaves`,
  `_equippable_goal`, `_recipe_has_combat_drop_input`, `gather_step_target`,
  `_gather_step_target_is_root`, `ITEM_TYPE_TO_SLOTS`, `GatherMaterialsGoal`,
  `UpgradeEquipmentGoal`, `ReachCurrencyGoal`).
- Produces: `obtain_item_decision(step, root) -> Decision` — the entry node for
  an `ObtainItem` step.

**This task changes no behaviour.** It is a transcription. The parity test below
is the gate on that claim.

- [ ] **Step 1: Write the parity test FIRST**

Create `tests/test_ai/test_decisions_obtain_item.py`:

```python
"""Transcription parity: the Decision graph must return exactly what the
if-pile returned, for every ObtainItem shape the scenario set produces."""
import pytest

from artifactsmmo_cli.ai.decision import resolve_node
from artifactsmmo_cli.ai.decisions.obtain_item import obtain_item_decision
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem


@pytest.mark.parametrize("scenario_name", sorted(SCENARIOS))
def test_graph_matches_the_legacy_if_pile(scenario_name, bundle_game_data):
    """Compares against `_legacy_objective_step_goal`, the pre-transcription
    body kept verbatim for exactly this comparison and deleted in Task 5."""
    from artifactsmmo_cli.ai.strategy_driver import _legacy_objective_step_goal

    gd = bundle_game_data
    state = scenario_state(SCENARIOS[scenario_name], gd)
    for code in sorted(gd.crafting_recipes)[:25]:
        step = ObtainItem(code=code, quantity=1)
        legacy = _legacy_objective_step_goal(step, state, gd, NO_PROFILE_CONTEXT,
                                             root=step, committed_root=step,
                                             history=None)
        graph = resolve_node(obtain_item_decision(step, step), state, gd,
                             NO_PROFILE_CONTEXT, None)
        assert repr(graph) == repr(legacy), (
            f"{scenario_name}/{code}: graph={graph!r} legacy={legacy!r}")
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/test_ai/test_decisions_obtain_item.py -q --no-cov
```

Expected: `ModuleNotFoundError: ... ai.decisions.obtain_item`.

- [ ] **Step 3: Preserve the legacy body for comparison**

In `src/artifactsmmo_cli/ai/strategy_driver.py`, copy the current
`objective_step_goal` body verbatim into a module-level function named
`_legacy_objective_step_goal` with the identical signature. Do not edit the copy.
Add this docstring line to it:

```python
    """VERBATIM pre-transcription body, kept ONLY so
    `tests/test_ai/test_decisions_obtain_item.py` can assert the Decision graph
    returns the same goal. Deleted in Task 5 once parity is green."""
```

- [ ] **Step 4: Write the Decision transcription**

Create `src/artifactsmmo_cli/ai/decisions/__init__.py` (empty file).

Create `src/artifactsmmo_cli/ai/decisions/obtain_item.py` with one `Decision`
subclass per branch, named exactly:

| branch, current line | class |
|---|---|
| `strategy_driver.py:898` | `CanIAffordTheCurrencyLeaf` |
| `strategy_driver.py:903` | `IsTheStepTheEquippableItself` |
| `strategy_driver.py:910` | `IsThisAnIntermediateOnAChain` |
| `strategy_driver.py:924` | `DoesTheRecipeNeedAMonsterDrop` |
| `strategy_driver.py:972` | `CanICraftCurrentTier` |
| `strategy_driver.py:1003` | `DoesTheChainFitTheDepthBudget` |

Each `resolve` contains the **exact** condition and the **exact** returned goal
from its current line, with no change of any kind. Chain them in the order the
`if`-pile evaluates. Every comment block attached to a branch moves with it —
those comments are the recorded reasons the branch exists and must not be lost.

`obtain_item_decision(step, root)` returns `CanIAffordTheCurrencyLeaf(step, root)`,
the first node in the chain.

- [ ] **Step 5: Run the parity test**

```bash
uv run pytest tests/test_ai/test_decisions_obtain_item.py -q --no-cov
```

Expected: all parametrised cases pass. **Any failure is a transcription error,
not a design question — fix the transcription.**

- [ ] **Step 6: Lint and the coverage-enforcing suite**

```bash
uv run ruff check src/ tests/
bash scripts/run_tests.sh
```

Run them ONE AT A TIME with nothing else active in the worktree — concurrent
processes corrupt the shared `.coverage` file and report a bogus ~45% total.
Never pass `--no-cov`: the project sets `--cov-fail-under=100`, so a single
unexecuted line in new code fails the gate. `formal/gate.sh` is the
controller's job, not yours.

Expected: `All checks passed!`, then `Required test coverage of 100% reached`.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/decisions/ \
        src/artifactsmmo_cli/ai/strategy_driver.py \
        tests/test_ai/test_decisions_obtain_item.py
git commit -m "refactor(decision): declare the six ObtainItem meta-decisions

Transcription only — the graph returns the same goal as the if-pile for every
ObtainItem shape in the scenario set, asserted against a verbatim copy of the
old body. No behaviour change."
```

---

## Task 5: Rewire `CanICraftCurrentTier`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/decisions/obtain_item.py`
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (delete
  `_legacy_objective_step_goal`; point `objective_step_goal` at the graph)
- Test: `tests/test_ai/test_decisions_obtain_item.py`

**Interfaces:**
- Consumes: `ReachSkillGoal(skill_name: str, target_level: int)` from
  `artifactsmmo_cli.ai.goals.reach_skill` — reused unchanged. It admits the
  existing `LevelSkill` action, which is why the gate closure and the
  `LevelSkill` deletion are wave 3, not this task.
- Produces: no new names.

**This is the one behaviour change in the plan.**

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_decisions_obtain_item.py`:

```python
def test_a_skill_gated_root_raises_the_skill_by_one(bundle_game_data):
    """Robby's live case. gold_sword is weaponcrafting 30 and he has 10. The
    branch used to return GatherMaterials for the step — gather the materials
    for a craft that cannot run — so nothing ever demanded the skill and
    weaponcrafting sat at 10 fleet-wide from 2026-08-16.

    The increment is +1, not the target: the graph re-derives every cycle, so
    planning the whole 10->30 climb is both unnecessary and enormous."""
    gd = bundle_game_data
    root = ObtainItem(code="gold_sword", quantity=1, slot="weapon_slot")
    step = ObtainItem(code="gold_bar", quantity=8)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    goal = resolve_node(obtain_item_decision(step, root), state, gd,
                        NO_PROFILE_CONTEXT, None)

    assert repr(goal) == "ReachSkill(weaponcrafting->11)"
```

Add `from tests.test_ai.fixtures import make_state` to the imports.

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/test_ai/test_decisions_obtain_item.py::test_a_skill_gated_root_raises_the_skill_by_one -q --no-cov
```

Expected: FAIL, actual is `GatherMaterials(gold_bar, {gold_bar:8})`. Both
`gold_sword` and `gold_bar` are present in the committed bundle (verified: 522
items), so no substitution is needed.

- [ ] **Step 3: Rewire the edge**

In `CanICraftCurrentTier.resolve`, replace the returned goal:

```python
        # WAS: return GatherMaterialsGoal(target_item=step.code,
        #                                 needed={step.code: step.quantity})
        #
        # "I cannot craft this tier" -> gather the materials anyway. The only
        # link from a skill-gated target to the skill it needs pointed at the
        # sibling. Live 2026-08-16 to 2026-08-22: 11,434 LevelSkill actions,
        # target never once above 10, weaponcrafting frozen on four characters.
        #
        # +1, not the target level: the graph re-derives from live state every
        # cycle, so the increment advances on its own and nothing has to plan
        # the 10->30 climb.
        current = state.skills.get(root_stats.crafting_skill, 1)
        return ReachSkillGoal(skill_name=root_stats.crafting_skill,
                              target_level=current + 1)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
uv run pytest tests/test_ai/test_decisions_obtain_item.py -q --no-cov
```

Expected: the new test passes. **The parity test from Task 4 will now fail on
skill-gated cases — that is correct.** Narrow it: rename to
`test_graph_matches_the_legacy_if_pile_except_the_rewired_edge` and skip cases
where the legacy result is a `GatherMaterialsGoal` produced by the skill gate,
asserting instead that the graph returns a `ReachSkillGoal` for those.

- [ ] **Step 5: Point production at the graph and delete the legacy copy**

Replace `objective_step_goal`'s `ObtainItem` arm with
`return resolve_node(obtain_item_decision(step, root), state, game_data, ctx, history)`.
Delete `_legacy_objective_step_goal` and the parity test's import of it, keeping
the narrowed parity assertions against the graph alone.

- [ ] **Step 6: Add a mutation anchor**

Register an anchor for the rewired return so a mutant that restores
`GatherMaterialsGoal` is killed. The anchor must resolve to exactly one site.
Verify:

```bash
uv run python formal/diff/mutate.py --check-anchors
```

- [ ] **Step 7: Lint and the coverage-enforcing suite**

```bash
uv run ruff check src/ tests/
bash scripts/run_tests.sh
```

Run them ONE AT A TIME with nothing else active in the worktree — concurrent
processes corrupt the shared `.coverage` file and report a bogus ~45% total.
Never pass `--no-cov`: the project sets `--cov-fail-under=100`, so a single
unexecuted line in new code fails the gate. `formal/gate.sh` is the
controller's job, not yours.

Expected: `All checks passed!` and 100% coverage. Other suites will move — a skill-gated root now produces a
different goal. Update the tests that encode the old routing, and for each one
state in the commit message why the new expectation is right.

- [ ] **Step 8: Verify it fires at runtime, not just in tests**

Green tests are not runtime activation. Run the read-only diagnostic:

```bash
uv run artifactsmmo plan Robby --learn 2>&1 | sed -n '/^state:/,/^goals_tried/p'
```

Expected: a `ReachSkill(weaponcrafting->11)` goal appears, or the descent
explains why a different link is active. Record the actual output in the commit
message whichever way it goes.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "fix(decision): a skill-gated root raises the skill, not gathers

Can_I_Craft_Current_Tier's 'no' branch returned GatherMaterials for the step --
gather materials for a craft that cannot run. It was the only link between a
skill-gated gear target and the skill it needs, and it pointed at the sibling.

11,434 LevelSkill(weaponcrafting->10) actions, target never once above 10, dead
on four characters since 2026-08-16.

Increment is +1, not the target: the graph re-derives each cycle."
```

---

## Task 6: `MaxGearForLevel` — blockers instead of filtering

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/objective.py` (near `near_term_gear`)
- Test: `tests/test_ai/test_max_gear_for_level.py`

**Interfaces:**
- Consumes: `gear_target_tier` from Task 2; `is_attainable_now`,
  `_slot_assignments`, `pursuit_value` already in `tiers/objective.py`.
- Produces: `CharacterObjective.gear_targets_with_blockers(state, history)
  -> dict[str, GearTarget]` where
  `GearTarget = dataclass(code: str, attainable: bool, blocker: str | None)`.
  `blocker` is `None`, `"skill:<name>:<level>"`, or `"material:<code>"`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_max_gear_for_level.py`:

```python
"""A gear target that cannot be built today is a target WITH A BLOCKER, never a
target that was deleted."""
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from tests.test_ai.fixtures import make_state


def test_an_unattainable_target_is_kept_and_carries_its_blocker(bundle_game_data):
    """near_term_gear drops these. Live 2026-08-22 that left Robby with the
    battlestaff he was already wearing as his best weapon target, so no weapon
    root existed and weaponcrafting had no demand path at all."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    targets = objective.gear_targets_with_blockers(state, None)

    assert "weapon_slot" in targets, "the weapon slot must produce a target"
    weapon = targets["weapon_slot"]
    if not weapon.attainable:
        assert weapon.blocker is not None, "unattainable target must name a blocker"


def test_every_unattainable_target_names_a_blocker(bundle_game_data):
    """The invariant whose absence caused the freeze: nothing is dropped for
    unattainability without saying what would unblock it."""
    gd = bundle_game_data
    objective = CharacterObjective.from_game_data(gd)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    for slot, target in objective.gear_targets_with_blockers(state, None).items():
        if not target.attainable:
            assert target.blocker is not None, f"{slot}/{target.code} has no blocker"
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/test_ai/test_max_gear_for_level.py -q --no-cov
```

Expected: `AttributeError: 'CharacterObjective' object has no attribute
'gear_targets_with_blockers'`.

- [ ] **Step 3: Implement**

Add to `tiers/objective.py`, beside `near_term_gear` (do not delete
`near_term_gear` in this task — it still has callers):

```python
@dataclass(frozen=True)
class GearTarget:
    """A per-slot target and, when it cannot be built today, WHY.

    `near_term_gear` filters unattainable candidates out. That answers "what can
    I build today" correctly and hides "what do I need". Live 2026-08-22: eight
    weapons each unlocked a fight Robby could not win, every one failed
    `is_attainable_now`, so the best surviving candidate was the battlestaff he
    already wore and no weapon root existed at all.
    """

    code: str
    attainable: bool
    blocker: str | None
```

and the method, selecting candidates up to `gear_target_tier` with **no**
attainability filter, then classifying each:

```python
    def gear_targets_with_blockers(
        self, state: WorldState, history: LearningStore | None
    ) -> dict[str, GearTarget]:
        """Best target per slot up to the gear target tier, each carrying its
        blocker when it cannot be built now."""
        tier = gear_target_tier(state, self._game_data, history)
        by_type: dict[str, list[tuple[int, str]]] = {}
        for code, stats in self._game_data.all_item_stats.items():
            if (stats.type_ not in ITEM_TYPE_TO_SLOTS
                    or stats.type_ == "utility"
                    or stats.level > tier):
                continue
            value = pursuit_value(stats)
            if value > 0:
                by_type.setdefault(stats.type_, []).append((value, code))
        targets: dict[str, GearTarget] = {}
        for type_, items in by_type.items():
            slots = [s for s in ITEM_TYPE_TO_SLOTS[type_] if s in EQUIPMENT_SLOTS]
            ranked = sorted(items, key=lambda vc: (-vc[0], vc[1]))
            for slot, value, code in _slot_assignments(type_, slots, ranked):
                if value <= self._item_value(state.equipment.get(slot)):
                    continue
                targets[slot] = self._classify_target(code, state)
        return targets

    def _classify_target(self, code: str, state: WorldState) -> GearTarget:
        """Attainable now, or the first blocker standing in front of it."""
        if is_attainable_now(code, state, self._game_data):
            return GearTarget(code=code, attainable=True, blocker=None)
        stats = self._game_data.item_stats(code)
        if (stats is not None and stats.crafting_skill
                and state.skills.get(stats.crafting_skill, 1) < stats.crafting_level):
            return GearTarget(
                code=code, attainable=False,
                blocker=f"skill:{stats.crafting_skill}:{stats.crafting_level}")
        recipe = self._game_data.crafting_recipe(code) or {}
        for material in sorted(recipe):
            if not is_attainable_now(material, state, self._game_data):
                return GearTarget(code=code, attainable=False,
                                  blocker=f"material:{material}")
        return GearTarget(code=code, attainable=False, blocker=f"material:{code}")
```

Add the imports `gear_target_tier` and `GearTarget`'s `dataclass` at the top of
the module — never inline.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_ai/test_max_gear_for_level.py -q --no-cov
```

Expected: 2 passed.

- [ ] **Step 5: Lint and the coverage-enforcing suite**

```bash
uv run ruff check src/ tests/
bash scripts/run_tests.sh
```

Run them ONE AT A TIME with nothing else active in the worktree — concurrent
processes corrupt the shared `.coverage` file and report a bogus ~45% total.
Never pass `--no-cov`: the project sets `--cov-fail-under=100`, so a single
unexecuted line in new code fails the gate. `formal/gate.sh` is the
controller's job, not yours.

Expected: `All checks passed!`, then `Required test coverage of 100% reached`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/objective.py \
        tests/test_ai/test_max_gear_for_level.py
git commit -m "feat(tiers): gear targets carry their blocker instead of vanishing

near_term_gear filters unattainable candidates out, which answers 'what can I
build today' correctly and hides 'what do I need'. Eight weapons each unlocking
a fight Robby cannot win all failed is_attainable_now, so his best weapon target
was the battlestaff he already wore.

Targets now survive with a blocker: skill:<name>:<level> or material:<code>.
No consumer yet — wiring is a follow-up."
```

---

## Task 7: Live acceptance and baseline capture

**Files:**
- Create: `docs/PLAN_goal_decision_graph_baseline.md`

**Interfaces:** none — this task produces evidence, not code.

- [ ] **Step 1: Capture the baseline BEFORE the fleet restarts on the new code**

Read from `~/.cache/artifactsmmo/learning.db` only. Trace files are deleted
periodically and are not a durable basis for any claim.

```bash
uv run python - <<'PY'
import sqlite3, os, shutil, tempfile
src = os.path.expanduser("~/.cache/artifactsmmo/learning.db")
dst = os.path.join(tempfile.mkdtemp(), "snap.db")
for suffix in ("", "-wal", "-shm"):
    if os.path.exists(src + suffix):
        shutil.copy(src + suffix, dst + suffix)
conn = sqlite3.connect(dst)
conn.execute("pragma wal_checkpoint(TRUNCATE)")
q = lambda sql, *a: list(conn.execute(sql, a))
print("planner nodes per cycle, last 24h:")
for row in q("""select character, count(*), round(avg(planner_nodes),0),
                max(planner_nodes) from cycles
                where ts > '2026-08-22' group by 1"""):
    print("  ", row)
print("weaponcrafting LevelSkill above 10, all time:")
print("  ", q("""select count(*) from cycles where action_class='LevelSkill'
                 and action_repr like 'LevelSkill(weaponcrafting->%'
                 and cast(replace(replace(action_repr,
                     'LevelSkill(weaponcrafting->',''),')','') as integer) > 10"""))
PY
```

Paste the output into `docs/PLAN_goal_decision_graph_baseline.md` with the
capture timestamp.

- [ ] **Step 2: Restart the fleet on the new code and let it run at least 2 hours**

At the measured ~52 cycles/hour/character that is ~100 cycles each, enough for
the goal mix to be meaningful.

- [ ] **Step 3: Re-run the same query and compare**

Acceptance, all three required:

1. `LevelSkill(weaponcrafting->N)` with `N > 10` appears at least once. Baseline
   is zero — it has never happened.
2. Gear-tier lag falls: for each character, the count of equipped slots below
   `gear_target_tier` is strictly lower than at baseline.
3. Planner nodes per cycle do not regress. A drop is expected only in wave 3
   when the gate closes; waves 1-2 must simply not make it worse.

- [ ] **Step 4: Record the result honestly**

Append the post-run numbers to the same document, including any acceptance
criterion that did **not** hold. A criterion that fails is a finding, not a
reason to re-run until it passes.

- [ ] **Step 5: Commit**

```bash
git add docs/PLAN_goal_decision_graph_baseline.md
git commit -m "docs: waves 1-2 live baseline and acceptance measurement"
```

---

## Self-review

**Spec coverage.** Wave 1 → Tasks 1-2. Wave 2's `Decision` type → Task 3;
transcription of the six `ObtainItem` branches → Task 4; the rewired edge →
Task 5; `MaxGearForLevel` → Task 6; live acceptance → Task 7.

**Two spec items are deliberately NOT in this plan**, with reasons recorded
above rather than dropped silently:

- The two `ReachCharLevel` Decisions (`Is_There_A_Combat_Target`,
  `Is_An_Items_Task_Active`) — nothing in waves 1-2 changes their behaviour, and
  transcribing them buys no reviewability until wave 5 touches combat targeting.
  They stay in `objective_step_goal` for now.
- The gate-closed action set and the `LevelSkill` deletion — moved to wave 3 for
  the dependency reason recorded under "Sequencing correction": the rewired edge
  routes to `ReachSkillGoal`, which is built on `LevelSkill`.

**Type consistency.** `gear_target_tier(state, game_data, history)` has the same
signature in Tasks 2 and 6. `resolve_node(node, state, game_data, ctx, history)`
is identical in Tasks 3, 4 and 5. `ReachSkillGoal(skill_name=, target_level=)`
matches the existing constructor in `ai/goals/reach_skill.py`.

**Known soft spots** an implementer will hit, flagged rather than hidden:

- Task 3's tests use `WaitGoal`; read its `__init__` before writing them.
- Task 5 step 4 requires narrowing the Task 4 parity test. That is expected — the
  whole point is that exactly one edge changes.
- Task 6's `_classify_target` reports only the FIRST blocker. That is sufficient
  for the invariant being tested and for wave 3's consumer; a full blocker chain
  is not needed and should not be built speculatively.
