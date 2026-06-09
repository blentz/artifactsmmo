# LevelSkill Gating Prioritization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `LevelSkill` a narrow skill-gate deadlock-breaker — dormant by default (no planner-budget burn), elevated to a plannable craft-one grind only when an under-leveled craft skill is the binding gate on a wanted gear/tool/task/combat item.

**Architecture:** Three new pure modules — `gating_skills` (which craft skills block a want), `skill_grind_target` (the shallow in-skill item to craft now), and `reorder_skill_candidates` (reposition/substitute LevelSkill candidates in the arbiter's ordered list). The arbiter calls them once per cycle before its cheap planning pass; non-gating LevelSkill sinks below the cheap winners (so it is never probed), gating LevelSkill becomes a plannable `GatherMaterials` craft-one goal. A LIV-SKILL-2 violation (gating craft skill with no craftable item) raises `SkillProgressionError` — fail loud on a genuine deadlock.

**Tech Stack:** Python 3.13, `uv`, pytest, mypy, ruff. Pure functions over `WorldState` / `GameData`; no I/O.

**Spec:** `docs/superpowers/specs/2026-06-08-levelskill-gating-prioritization-design.md`

**Project rules (from AGENTS.md):** Prefix all Python with `uv run`. Imports at top of file. One behavioral class per file. No `if TYPE_CHECKING`. Never catch `Exception`. Use only API/game data or fail with an error. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage. All tests in `tests/`.

---

## File Structure

New:
- `src/artifactsmmo_cli/ai/tiers/skill_gates.py` — `GateSource` (enum), `SkillGate` (frozen dataclass), `SkillProgressionError` (exception), `gating_skills()`. Cohesive value/enum/exception group + one behavioral entry point.
- `src/artifactsmmo_cli/ai/tiers/skill_grind_target.py` — `skill_grind_target()`.
- `src/artifactsmmo_cli/ai/strategy_reorder.py` — `reorder_skill_candidates()` + private insert helpers.

Modified:
- `src/artifactsmmo_cli/ai/strategy_driver.py` — `select()` gains `objective` param; compute gating + reorder before the cheap pass; raise on violation.
- `src/artifactsmmo_cli/ai/player.py` — pass `objective=self._objective` into `select()`.

Tests:
- `tests/test_ai/test_skill_gates.py`
- `tests/test_ai/test_skill_grind_target.py`
- `tests/test_ai/test_strategy_reorder.py`
- `tests/test_ai/test_levelskill_liveness.py`

---

## Task 1: `skill_gates.py` — gating predicate

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/skill_gates.py`
- Test: `tests/test_ai/test_skill_gates.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_skill_gates.py`:

```python
"""Tests for gating_skills: which craft skills block a strategic want."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.skill_gates import (
    GateSource,
    SkillGate,
    gating_skills,
)
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        # gear: needs gearcrafting 5
        "iron_helm": ItemStats(code="iron_helm", level=5, type_="helmet",
                               crafting_skill="gearcrafting", crafting_level=5),
        # weapon: needs weaponcrafting 10
        "iron_dagger": ItemStats(code="iron_dagger", level=10, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=10),
        # task item: needs cooking 8
        "cooked_trout": ItemStats(code="cooked_trout", level=8, type_="consumable",
                                  crafting_skill="cooking", crafting_level=8),
        # gear whose closure has an intermediate craft gated by jewelrycrafting
        "ruby_ring": ItemStats(code="ruby_ring", level=3, type_="ring",
                               crafting_skill="jewelrycrafting", crafting_level=1),
        "ruby_gem": ItemStats(code="ruby_gem", level=3, type_="resource",
                              crafting_skill="jewelrycrafting", crafting_level=12),
        # resource gathered at mining 20 (gather gate — must be EXCLUDED)
        "coal": ItemStats(code="coal", level=20, type_="resource"),
        "trout": ItemStats(code="trout", level=8, type_="resource"),
    }
    gd._crafting_recipes = {
        "iron_helm": {"iron_bar": 5},
        "iron_dagger": {"iron_bar": 6},
        "cooked_trout": {"trout": 1},
        "ruby_ring": {"ruby_gem": 2},
        "ruby_gem": {"coal": 3},
    }
    gd._resource_drops = {"trout_spot": "trout", "coal_rocks": "coal"}
    gd._resource_skill = {"trout_spot": ("fishing", 8), "coal_rocks": ("mining", 20)}
    return gd


def _obj(gd: GameData, gear=None, tools=None) -> CharacterObjective:
    return CharacterObjective(
        target_char_level=50,
        target_skill_levels={},
        target_gear=gear or {},
        _game_data=gd,
        target_tools=tools or {},
    )


def test_gear_gate_surfaces_with_gear_source():
    gd = _gd()
    obj = _obj(gd, gear={"helmet_slot": "iron_helm"})
    state = make_state(skills={"gearcrafting": 1})
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert gates["gearcrafting"] == SkillGate(required_level=5, source=GateSource.GEAR)


def test_owned_gear_is_not_gating():
    gd = _gd()
    obj = _obj(gd, gear={"helmet_slot": "iron_helm"})
    state = make_state(skills={"gearcrafting": 1}, inventory={"iron_helm": 1})
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert "gearcrafting" not in gates


def test_skill_already_high_enough_is_not_gating():
    gd = _gd()
    obj = _obj(gd, gear={"helmet_slot": "iron_helm"})
    state = make_state(skills={"gearcrafting": 5})
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert "gearcrafting" not in gates


def test_active_items_task_gate_has_task_item_source():
    gd = _gd()
    obj = _obj(gd)
    state = make_state(skills={"cooking": 1}, task_type="items",
                       task_code="cooked_trout", task_total=10, task_progress=0)
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert gates["cooking"] == SkillGate(required_level=8, source=GateSource.TASK_ITEM)


def test_combat_weapon_gate_has_combat_source():
    gd = _gd()
    obj = _obj(gd)
    state = make_state(skills={"weaponcrafting": 1})
    gates = gating_skills(state, gd, obj, combat_weapon="iron_dagger")
    assert gates["weaponcrafting"] == SkillGate(required_level=10, source=GateSource.COMBAT)


def test_closure_intermediate_craft_gate_surfaces():
    gd = _gd()
    obj = _obj(gd, gear={"ring1_slot": "ruby_ring"})
    state = make_state(skills={"jewelrycrafting": 1})
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    # ruby_ring itself craftable at 1, but its closure item ruby_gem needs 12.
    assert gates["jewelrycrafting"] == SkillGate(required_level=12, source=GateSource.GEAR)


def test_gather_gate_is_excluded():
    gd = _gd()
    # cooked_trout's material `trout` is gathered at fishing 8; coal at mining 20.
    obj = _obj(gd)
    state = make_state(skills={"cooking": 8, "fishing": 1, "mining": 1},
                       task_type="items", task_code="cooked_trout",
                       task_total=10, task_progress=0)
    gates = gating_skills(state, gd, obj, combat_weapon=None)
    assert "fishing" not in gates
    assert "mining" not in gates


def test_same_skill_two_wants_keeps_max_level_and_strongest_source():
    gd = _gd()
    # weaponcrafting gated by combat weapon (10) AND a task item needing 6.
    gd._item_stats["wc_task"] = ItemStats(
        code="wc_task", level=6, type_="consumable",
        crafting_skill="weaponcrafting", crafting_level=6)
    gd._crafting_recipes["wc_task"] = {"iron_bar": 1}
    obj = _obj(gd)
    state = make_state(skills={"weaponcrafting": 1}, task_type="items",
                       task_code="wc_task", task_total=5, task_progress=0)
    gates = gating_skills(state, gd, obj, combat_weapon="iron_dagger")
    # max level 10 (combat), strongest source TASK_ITEM.
    assert gates["weaponcrafting"] == SkillGate(required_level=10,
                                                source=GateSource.TASK_ITEM)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_skill_gates.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.tiers.skill_gates'`

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/ai/tiers/skill_gates.py`:

```python
"""Which craft skills currently gate a strategically interesting want.

A skill is "gating" iff it is the craft.skill of some wanted, not-yet-owned item
(gear / tool / active items-task item / combat weapon) — or an item in that item's
craftable recipe closure — at a craft.level above the character's current skill
level. Gather/resource skill gates are EXCLUDED: gather skills self-level through
the gathering the bot already does and cannot deadlock for lack of activity; only
craft skills can stall because nothing in the routine forces a craft.

See docs/superpowers/specs/2026-06-08-levelskill-gating-prioritization-design.md
(LIV-SKILL-1/2/3).
"""

from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import recipe_closure
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.owned_count import owned_count_pure
from artifactsmmo_cli.ai.world_state import WorldState


class SkillProgressionError(RuntimeError):
    """Raised when a craft skill gates a wanted item but no in-skill item is
    craftable at the current level — a genuine deadlock (LIV-SKILL-2 violation).
    Fail loud rather than silently drop the only candidate that could break it."""


class GateSource(Enum):
    """Why a skill is gating — drives the arbiter's preemption rule. Lower
    enum-rank (see _SOURCE_RANK) is the stronger source."""
    TASK_ITEM = "task_item"
    GEAR = "gear"
    TOOL = "tool"
    COMBAT = "combat"


_SOURCE_RANK = {
    GateSource.TASK_ITEM: 0,
    GateSource.GEAR: 1,
    GateSource.TOOL: 2,
    GateSource.COMBAT: 3,
}


@dataclass(frozen=True)
class SkillGate:
    """The level a wanted item needs in a skill, and why it is wanted."""
    required_level: int
    source: GateSource


def _stronger_source(a: GateSource, b: GateSource) -> GateSource:
    return a if _SOURCE_RANK[a] <= _SOURCE_RANK[b] else b


def gating_skills(
    state: WorldState,
    game_data: GameData,
    objective: CharacterObjective,
    combat_weapon: str | None,
) -> dict[str, SkillGate]:
    """Craft skills blocking a strategically interesting want. skill -> SkillGate.

    `combat_weapon` is the best attainable weapon to chase when the character is
    not combat-capable (else None) — passed in so this module avoids the
    combat/predict_win import cycle."""
    wants: list[tuple[str, GateSource]] = []
    for code in objective.target_gear.values():
        wants.append((code, GateSource.GEAR))
    for code in objective.target_tools.values():
        wants.append((code, GateSource.TOOL))
    if state.task_type == "items" and state.task_code:
        wants.append((state.task_code, GateSource.TASK_ITEM))
    if combat_weapon is not None:
        wants.append((combat_weapon, GateSource.COMBAT))

    equipped = [c for c in state.equipment.values() if c is not None]
    gates: dict[str, SkillGate] = {}
    for code, source in wants:
        if owned_count_pure(state.inventory, state.bank_items, equipped, code) >= 1:
            continue
        _resources, craftables = recipe_closure(game_data, [code])
        for node in set(craftables) | {code}:
            stats = game_data.item_stats(node)
            if stats is None or not stats.crafting_skill:
                continue
            current = state.skills.get(stats.crafting_skill, 0)
            if stats.crafting_level <= current:
                continue
            _record(gates, stats.crafting_skill,
                    SkillGate(stats.crafting_level, source))
    return gates


def _record(gates: dict[str, SkillGate], skill: str, gate: SkillGate) -> None:
    """Keep the highest required_level and the strongest source. Deterministic."""
    existing = gates.get(skill)
    if existing is None:
        gates[skill] = gate
        return
    gates[skill] = SkillGate(
        required_level=max(existing.required_level, gate.required_level),
        source=_stronger_source(existing.source, gate.source),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_skill_gates.py -q`
Expected: PASS (8 passed)

- [ ] **Step 5: Type-check + lint**

Run: `uv run mypy src/artifactsmmo_cli/ai/tiers/skill_gates.py && uv run ruff check src/artifactsmmo_cli/ai/tiers/skill_gates.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/skill_gates.py tests/test_ai/test_skill_gates.py
git commit -m "feat(planner): gating_skills predicate for skill-gate detection"
```

---

## Task 2: `skill_grind_target.py` — plannable craft-one selection

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/skill_grind_target.py`
- Test: `tests/test_ai/test_skill_grind_target.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_skill_grind_target.py`:

```python
"""Tests for skill_grind_target: the shallow in-skill item to craft now."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "iron_dagger": ItemStats(code="iron_dagger", level=10, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=10),
        "wooden_staff": ItemStats(code="wooden_staff", level=3, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=3),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "iron_dagger": {"iron_bar": 6},
        "wooden_staff": {"ash_plank": 4},
    }
    return gd


def test_picks_highest_craftable_at_current_level():
    gd = _gd()
    # current 3: copper_dagger(1) and wooden_staff(3) craftable; iron_dagger(10) not.
    # No materials in hand → tie on mats_missing, higher crafting_level wins.
    state = make_state(skills={"weaponcrafting": 3})
    assert skill_grind_target("weaponcrafting", state, gd) == "wooden_staff"


def test_prefers_materials_in_hand_over_higher_level():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3},
                       inventory={"copper_bar": 6})  # copper_dagger fully covered
    # copper_dagger has 0 missing mats; wooden_staff has 4 missing → copper wins.
    assert skill_grind_target("weaponcrafting", state, gd) == "copper_dagger"


def test_counts_bank_toward_materials_in_hand():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3},
                       bank_items={"copper_bar": 6})
    assert skill_grind_target("weaponcrafting", state, gd) == "copper_dagger"


def test_none_when_nothing_craftable_at_level():
    gd = _gd()
    # current 0: nothing at/below level 0 (copper_dagger needs 1).
    state = make_state(skills={"weaponcrafting": 0})
    assert skill_grind_target("weaponcrafting", state, gd) is None


def test_none_for_skill_with_no_recipes():
    gd = _gd()
    state = make_state(skills={"alchemy": 5})
    assert skill_grind_target("alchemy", state, gd) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_skill_grind_target.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.tiers.skill_grind_target'`

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/ai/tiers/skill_grind_target.py`:

```python
"""Pick the in-skill item to craft NOW to gain XP toward a skill gate.

The shallowest material chain (prefer materials already in inventory/bank), then
the highest skill level (more XP), tie-broken by code for determinism. Returns
None only when no in-skill recipe is craftable at the current level — which, for a
craft skill the bot can be gated on, signals a violation of the documented
monotone skill-progression property (LIV-SKILL-2). Inclusion does NOT depend on
inventory/bank availability (only ordering does), so None is a pure recipe-table
fact, free of bank-freshness false positives.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def skill_grind_target(skill: str, state: WorldState, game_data: GameData) -> str | None:
    current = state.skills.get(skill, 0)
    bank = state.bank_items or {}
    best: tuple[int, int, str] | None = None  # maximized key
    for code, stats in game_data._item_stats.items():
        if stats.crafting_skill != skill or stats.crafting_level > current:
            continue
        recipe = game_data._crafting_recipes.get(code)
        if not recipe:
            continue
        mats_missing = sum(
            max(0, qty - state.inventory.get(mat, 0) - bank.get(mat, 0))
            for mat, qty in recipe.items()
        )
        # Maximize: fewest missing mats first (-mats_missing), then higher level,
        # then code (lexicographically largest) for a deterministic tie-break.
        key = (-mats_missing, stats.crafting_level, code)
        if best is None or key > best:
            best = key
    return best[2] if best is not None else None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_skill_grind_target.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Type-check + lint**

Run: `uv run mypy src/artifactsmmo_cli/ai/tiers/skill_grind_target.py && uv run ruff check src/artifactsmmo_cli/ai/tiers/skill_grind_target.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/skill_grind_target.py tests/test_ai/test_skill_grind_target.py
git commit -m "feat(planner): skill_grind_target shallow craft-one selection"
```

---

## Task 3: `strategy_reorder.py` — candidate reordering policy

**Files:**
- Create: `src/artifactsmmo_cli/ai/strategy_reorder.py`
- Test: `tests/test_ai/test_strategy_reorder.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_strategy_reorder.py`:

```python
"""Tests for reorder_skill_candidates: the gating ordering policy."""

from artifactsmmo_cli.ai.arbiter_select import Candidate
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.strategy_reorder import reorder_skill_candidates
from artifactsmmo_cli.ai.tiers.skill_gates import GateSource, SkillGate
from tests.test_ai.fixtures import make_state


class _Stub:
    """A minimal non-LevelSkill goal whose repr drives the ordering anchors."""
    def __init__(self, name: str) -> None:
        self._name = name
    def __repr__(self) -> str:
        return self._name


def _cand(goal, is_means=True) -> Candidate:
    return Candidate(goal=goal, is_means=is_means, repr_=repr(goal))


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}}
    return gd


def _reprs(cands):
    return [c.repr_ for c in cands]


def test_non_gating_levelskill_demoted_before_wait():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1})
    cands = [
        _cand(_Stub("PursueTask(x)")),
        _cand(_Stub("AcceptTask")),
        _cand(LevelSkillGoal("weaponcrafting", 5)),
        _cand(_Stub("Wait")),
    ]
    out, violations = reorder_skill_candidates(cands, gates={}, state=state,
                                               game_data=gd, has_paying_task=True)
    assert violations == []
    # Non-gating LevelSkill is dropped (not substituted) and sinks before Wait.
    assert _reprs(out) == ["PursueTask(x)", "AcceptTask",
                           "LevelSkill(weaponcrafting->5)", "Wait"]


def test_task_item_gate_inserts_before_pursue_as_craft_one():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1})
    gates = {"weaponcrafting": SkillGate(required_level=5, source=GateSource.TASK_ITEM)}
    cands = [
        _cand(_Stub("PursueTask(x)")),
        _cand(_Stub("AcceptTask")),
        _cand(LevelSkillGoal("weaponcrafting", 5)),
        _cand(_Stub("Wait")),
    ]
    out, violations = reorder_skill_candidates(cands, gates, state, gd,
                                               has_paying_task=True)
    assert violations == []
    assert _reprs(out) == ["GatherMaterials(copper_dagger)", "PursueTask(x)",
                           "AcceptTask", "Wait"]
    grind = out[0].goal
    assert isinstance(grind, GatherMaterialsGoal)


def test_gear_gate_with_paying_task_inserts_after_pursue():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1})
    gates = {"weaponcrafting": SkillGate(required_level=5, source=GateSource.GEAR)}
    cands = [
        _cand(_Stub("PursueTask(x)")),
        _cand(_Stub("AcceptTask")),
        _cand(LevelSkillGoal("weaponcrafting", 5)),
        _cand(_Stub("Wait")),
    ]
    out, _ = reorder_skill_candidates(cands, gates, state, gd, has_paying_task=True)
    assert _reprs(out) == ["PursueTask(x)", "GatherMaterials(copper_dagger)",
                           "AcceptTask", "Wait"]


def test_gear_gate_no_paying_task_inserts_after_accept():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1})
    gates = {"weaponcrafting": SkillGate(required_level=5, source=GateSource.GEAR)}
    cands = [
        _cand(_Stub("AcceptTask")),
        _cand(LevelSkillGoal("weaponcrafting", 5)),
        _cand(_Stub("Wait")),
    ]
    out, _ = reorder_skill_candidates(cands, gates, state, gd, has_paying_task=False)
    assert _reprs(out) == ["AcceptTask", "GatherMaterials(copper_dagger)", "Wait"]


def test_gating_skill_without_craft_target_reports_violation():
    gd = GameData()
    gd._item_stats = {
        "iron_dagger": ItemStats(code="iron_dagger", level=10, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=10),
    }
    gd._crafting_recipes = {"iron_dagger": {"iron_bar": 6}}
    state = make_state(skills={"weaponcrafting": 1})  # nothing craftable at 1
    gates = {"weaponcrafting": SkillGate(required_level=10, source=GateSource.GEAR)}
    cands = [
        _cand(_Stub("AcceptTask")),
        _cand(LevelSkillGoal("weaponcrafting", 5)),
        _cand(_Stub("Wait")),
    ]
    out, violations = reorder_skill_candidates(cands, gates, state, gd,
                                               has_paying_task=False)
    assert violations == ["weaponcrafting"]


def test_no_levelskill_candidates_is_identity():
    gd = _gd()
    state = make_state()
    cands = [_cand(_Stub("PursueTask(x)")), _cand(_Stub("Wait"))]
    out, violations = reorder_skill_candidates(cands, gates={}, state=state,
                                               game_data=gd, has_paying_task=True)
    assert out is cands and violations == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_strategy_reorder.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.strategy_reorder'`

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/ai/strategy_reorder.py`:

```python
"""Reposition LevelSkill candidates in the arbiter's ordered candidate list per
the skill-gating policy, swapping a gating LevelSkill's unplannable goal for a
plannable craft-one GatherMaterials goal. Pure — unit-tested in isolation from
the planning loop.

Ordering table (see spec 2026-06-08-levelskill-gating-prioritization-design.md):
  TASK_ITEM gate            -> craft-one, immediately BEFORE the PursueTask candidate
  gear/tool/combat, task    -> craft-one, immediately AFTER  the PursueTask candidate
  gear/tool/combat, no task -> craft-one, immediately AFTER  the AcceptTask candidate
  not gating                -> demote unchanged to just before Wait
  gating but no craft target-> LIV-SKILL-2 violation (caller raises)
"""

from collections.abc import Callable

from artifactsmmo_cli.ai.arbiter_select import Candidate
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.tiers.skill_gates import GateSource, SkillGate
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState


def _is_pursue(c: Candidate) -> bool:
    return c.repr_.startswith("PursueTask")


def _is_accept(c: Candidate) -> bool:
    return c.repr_ == "AcceptTask"


def _is_wait(c: Candidate) -> bool:
    return c.repr_ == "Wait"


def _insert_before(lst: list[Candidate], bucket: list[Candidate],
                   anchor: Callable[[Candidate], bool],
                   fallback: Callable[[Candidate], bool] | None) -> list[Candidate]:
    if not bucket:
        return lst
    for i, c in enumerate(lst):
        if anchor(c):
            return lst[:i] + bucket + lst[i:]
    if fallback is not None:
        for i, c in enumerate(lst):
            if fallback(c):
                return lst[:i] + bucket + lst[i:]
    return lst + bucket


def _insert_after(lst: list[Candidate], bucket: list[Candidate],
                  anchor: Callable[[Candidate], bool],
                  fallback: Callable[[Candidate], bool] | None) -> list[Candidate]:
    if not bucket:
        return lst
    for i, c in enumerate(lst):
        if anchor(c):
            return lst[:i + 1] + bucket + lst[i + 1:]
    if fallback is not None:
        for i, c in enumerate(lst):
            if fallback(c):
                return lst[:i] + bucket + lst[i:]
    return lst + bucket


def reorder_skill_candidates(
    candidates: list[Candidate],
    gates: dict[str, SkillGate],
    state: WorldState,
    game_data: GameData,
    has_paying_task: bool,
) -> tuple[list[Candidate], list[str]]:
    """Return (reordered_candidates, liveness_violations).

    liveness_violations: gating craft skills with no craftable item at the
    current level (LIV-SKILL-2). The caller raises SkillProgressionError on a
    non-empty list. When there are no LevelSkill candidates, the input list is
    returned unchanged (identity)."""
    skill_idx = [i for i, c in enumerate(candidates)
                 if isinstance(c.goal, LevelSkillGoal)]
    if not skill_idx:
        return candidates, []

    skill_set = set(skill_idx)
    base = [c for i, c in enumerate(candidates) if i not in skill_set]

    before_pursue: list[Candidate] = []
    after_pursue: list[Candidate] = []
    after_accept: list[Candidate] = []
    demoted: list[Candidate] = []
    violations: list[str] = []

    for i in skill_idx:
        cand = candidates[i]
        skill = cand.goal._skill_name
        gate = gates.get(skill)
        if gate is None:
            demoted.append(cand)
            continue
        target = skill_grind_target(skill, state, game_data)
        if target is None:
            violations.append(skill)
            continue
        grind = GatherMaterialsGoal(target_item=target, needed={target: 1})
        grind_cand = Candidate(goal=grind, is_means=True, repr_=repr(grind))
        if gate.source is GateSource.TASK_ITEM:
            before_pursue.append(grind_cand)
        elif has_paying_task:
            after_pursue.append(grind_cand)
        else:
            after_accept.append(grind_cand)

    result = base
    result = _insert_before(result, before_pursue, _is_pursue, _is_wait)
    result = _insert_after(result, after_pursue, _is_pursue, _is_wait)
    result = _insert_after(result, after_accept, _is_accept, _is_wait)
    result = _insert_before(result, demoted, _is_wait, None)
    return result, violations
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_strategy_reorder.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Type-check + lint**

Run: `uv run mypy src/artifactsmmo_cli/ai/strategy_reorder.py && uv run ruff check src/artifactsmmo_cli/ai/strategy_reorder.py`
Expected: no errors

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_reorder.py tests/test_ai/test_strategy_reorder.py
git commit -m "feat(planner): reorder_skill_candidates gating ordering policy"
```

---

## Task 4: Wire into the arbiter + player

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (`select` signature + candidate-assembly block ~line 611)
- Modify: `src/artifactsmmo_cli/ai/player.py` (`select` call ~line 320)
- Test: `tests/test_ai/test_strategy_driver.py` (add an integration test)

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_ai/test_strategy_driver.py` (reuse the file's existing imports for `StrategyArbiter`, `GOAPPlanner`, `SelectionContext`, `make_state`; add any missing imports shown):

```python
import pytest

from artifactsmmo_cli.ai.arbiter_select import Candidate
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.tiers.skill_gates import SkillProgressionError


def test_select_raises_on_gating_skill_without_craft_target(monkeypatch):
    """A gating craft skill with no craftable item at current level => fail loud.

    Drive the path directly: stub the arbiter's candidate walk so a single
    gating LevelSkill candidate with no grind target reaches the reorder step."""
    from artifactsmmo_cli.ai import strategy_driver as sd

    arbiter = StrategyArbiter(GOAPPlanner(), history=None)

    # Game data where weaponcrafting only has a level-10 recipe (nothing at 1).
    gd = GameData()
    gd._item_stats = {
        "iron_dagger": ItemStats(code="iron_dagger", level=10, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=10),
    }
    gd._crafting_recipes = {"iron_dagger": {"iron_bar": 6}}
    obj = CharacterObjective(
        target_char_level=50, target_skill_levels={},
        target_gear={"weapon_slot": "iron_dagger"}, _game_data=gd, target_tools={})
    state = make_state(skills={"weaponcrafting": 1})

    # Force the assembled candidates to contain the gating LevelSkill so the
    # reorder block is exercised regardless of upstream tier ranking.
    monkeypatch.setattr(
        sd, "_assemble_candidates_for_test", None, raising=False)

    decision = type("D", (), {"chosen_step": None, "chosen_root": None,
                              "fallback_steps": [], "fallback_roots": []})()
    ctx = _make_ctx(combat_monster="slime")  # combat-capable => no combat want

    # Inject a LevelSkill candidate via the suppression-free path: patch
    # objective_step_goal to surface LevelSkillGoal(weaponcrafting) as the step.
    monkeypatch.setattr(
        sd, "objective_step_goal",
        lambda step, st, g, c, root=None: LevelSkillGoal("weaponcrafting", 5))
    monkeypatch.setattr(sd, "active_guards", lambda *a, **k: [])
    monkeypatch.setattr(sd, "active_means", lambda *a, **k: ([], []))

    with pytest.raises(SkillProgressionError):
        arbiter.select(decision, state, gd, [], ctx, objective=obj)
```

> Implementer note: `_make_ctx` is the existing context-builder helper in `test_strategy_driver.py`; if it is named differently, use that file's established `SelectionContext` constructor. The two `monkeypatch.setattr` calls for `active_guards` / `active_means` neutralize the tier layer so the single stubbed step reaches the reorder block. Remove the unused `_assemble_candidates_for_test` line if the file has no such hook — it is a no-op guard.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py::test_select_raises_on_gating_skill_without_craft_target -q`
Expected: FAIL — `TypeError: select() got an unexpected keyword argument 'objective'`

- [ ] **Step 3: Add imports + objective param + reorder block to `strategy_driver.py`**

Add to the import block near the other `tiers` imports (top of file):

```python
from artifactsmmo_cli.ai.strategy_reorder import reorder_skill_candidates
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.prerequisite_graph import best_attainable_weapon
from artifactsmmo_cli.ai.tiers.skill_gates import SkillProgressionError, gating_skills
```

Change the `select` signature (currently ends with `suppressed=...`):

```python
    def select(
        self,
        decision: object,
        state: WorldState,
        game_data: GameData,
        actions: list[Action],
        ctx: SelectionContext,
        suppressed: frozenset[str] | set[str] = frozenset(),
        objective: CharacterObjective | None = None,
    ) -> tuple[Goal | None, list[Action], list[dict[str, object]]]:
```

Insert the reorder block immediately AFTER the candidate list is fully built
(after the `for mk in discretionary_kinds:` loop that appends discretionary
candidates, currently ending ~line 611) and BEFORE the
`guard_reprs = {c.repr_ for c in candidates if not c.is_means}` line (~line 616):

```python
        # ── Skill-gate prioritization ──────────────────────────────────────
        # Demote non-gating LevelSkill candidates below the cheap winners (this
        # is what kills the planner-budget burn — they are never probed) and
        # elevate a LevelSkill only when its skill is the binding craft gate on a
        # wanted gear/tool/task/combat item, swapping the unplannable
        # ReachSkillLevel target for a plannable craft-one GatherMaterials goal.
        # A gating craft skill with no craftable item at the current level is a
        # genuine deadlock (LIV-SKILL-2) — fail loud. See
        # docs/superpowers/specs/2026-06-08-levelskill-gating-prioritization-design.md.
        if objective is not None:
            combat_weapon = (best_attainable_weapon(game_data)
                             if ctx.combat_monster is None else None)
            gates = gating_skills(state, game_data, objective, combat_weapon)
            has_paying_task = (
                state.task_type == "items" and bool(state.task_code)
                and state.task_total > 0 and state.task_progress < state.task_total)
            candidates, skill_violations = reorder_skill_candidates(
                candidates, gates, state, game_data, has_paying_task)
            if skill_violations:
                raise SkillProgressionError(
                    "gating craft skill(s) with no craftable item at current "
                    "level (LIV-SKILL-2 deadlock): "
                    + ", ".join(sorted(skill_violations)))
```

- [ ] **Step 4: Run the integration test to verify it passes**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py::test_select_raises_on_gating_skill_without_craft_target -q`
Expected: PASS

- [ ] **Step 5: Pass `objective` from the player**

In `src/artifactsmmo_cli/ai/player.py`, the `select` call (~line 320) currently reads:

```python
                selected_goal, plan, goals_tried = self._arbiter.select(
                    decision, state, game_data, actions, ctx,
                    suppressed=set(self._suppressed_goals),
                )
```

Change it to:

```python
                selected_goal, plan, goals_tried = self._arbiter.select(
                    decision, state, game_data, actions, ctx,
                    suppressed=set(self._suppressed_goals),
                    objective=self._objective,
                )
```

- [ ] **Step 6: Run the full arbiter + player test files**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py tests/test_ai/test_player.py -q`
Expected: PASS (no regressions — existing tests pass `objective=None` by default and behave exactly as before)

- [ ] **Step 7: Type-check + lint the modified files**

Run: `uv run mypy src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/player.py && uv run ruff check src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/player.py`
Expected: no errors

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/player.py tests/test_ai/test_strategy_driver.py
git commit -m "feat(planner): wire skill-gate reordering into the arbiter"
```

---

## Task 5: Liveness invariant tests (LIV-SKILL-1/2/3)

**Files:**
- Create: `tests/test_ai/test_levelskill_liveness.py`

- [ ] **Step 1: Write the liveness tests**

Create `tests/test_ai/test_levelskill_liveness.py`:

```python
"""Liveness obligations for the skill-gate mechanism (LIV-SKILL-1/2/3).

These tests are the point of the feature: a craft-skill gate must never leave the
planner without a forward action, the grind target must exist for any gating
craft skill (monotone progression), and the gating set must strictly shrink as a
skill is driven across its gate (no livelock)."""

from artifactsmmo_cli.ai.arbiter_select import Candidate
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.strategy_reorder import reorder_skill_candidates
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.skill_gates import GateSource, SkillGate, gating_skills
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from tests.test_ai.fixtures import make_state


def _progression_gd() -> GameData:
    """A craft skill with a recipe at every level 1..5 (monotone progression)."""
    gd = GameData()
    gd._item_stats = {
        f"wc_t{lvl}": ItemStats(code=f"wc_t{lvl}", level=lvl, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=lvl)
        for lvl in range(1, 6)
    }
    gd._crafting_recipes = {f"wc_t{lvl}": {"bar": 1} for lvl in range(1, 6)}
    return gd


def test_liv_skill_1_gate_yields_a_forward_action():
    """A wanted item blocked solely by an under-leveled craft skill produces a
    plannable craft-one candidate (never a no-op)."""
    gd = _progression_gd()
    gates = {"weaponcrafting": SkillGate(required_level=5, source=GateSource.GEAR)}
    state = make_state(skills={"weaponcrafting": 2})

    class _Stub:
        def __init__(self, n): self._n = n
        def __repr__(self): return self._n

    cands = [
        Candidate(goal=_Stub("AcceptTask"), is_means=True, repr_="AcceptTask"),
        Candidate(goal=LevelSkillGoal("weaponcrafting", 5), is_means=True,
                  repr_="LevelSkill(weaponcrafting->5)"),
        Candidate(goal=_Stub("Wait"), is_means=True, repr_="Wait"),
    ]
    out, violations = reorder_skill_candidates(cands, gates, state, gd,
                                               has_paying_task=False)
    assert violations == []
    grind = [c for c in out if isinstance(c.goal, GatherMaterialsGoal)]
    assert len(grind) == 1  # a real forward action exists


def test_liv_skill_2_grind_target_total_over_progression():
    """For every level 1..max-1 of a monotone craft skill, a grind target exists."""
    gd = _progression_gd()
    for lvl in range(1, 5):
        state = make_state(skills={"weaponcrafting": lvl})
        assert skill_grind_target("weaponcrafting", state, gd) is not None


def test_liv_skill_3_gating_set_strictly_shrinks_as_skill_rises():
    """Driving the skill across the gate removes it from gating_skills and it is
    not re-added (no livelock)."""
    gd = _progression_gd()
    # Want an item that needs weaponcrafting 5.
    gd._item_stats["target_weapon"] = ItemStats(
        code="target_weapon", level=5, type_="weapon",
        crafting_skill="weaponcrafting", crafting_level=5)
    gd._crafting_recipes["target_weapon"] = {"wc_t5": 1}
    obj = CharacterObjective(
        target_char_level=50, target_skill_levels={},
        target_gear={"weapon_slot": "target_weapon"}, _game_data=gd, target_tools={})

    gated_levels = []
    for lvl in range(1, 6):
        state = make_state(skills={"weaponcrafting": lvl})
        gates = gating_skills(state, gd, obj, combat_weapon=None)
        gated_levels.append("weaponcrafting" in gates)
    # Gating for levels 1..4, cleared at 5, never re-added.
    assert gated_levels == [True, True, True, True, False]
```

- [ ] **Step 2: Run the liveness tests**

Run: `uv run pytest tests/test_ai/test_levelskill_liveness.py -q`
Expected: PASS (3 passed)

- [ ] **Step 3: Commit**

```bash
git add tests/test_ai/test_levelskill_liveness.py
git commit -m "test(planner): LIV-SKILL-1/2/3 liveness obligations"
```

---

## Task 6: Full suite, coverage, trace sanity

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite with coverage**

Run: `uv run pytest -q`
Expected: 0 failures, 0 errors, 0 warnings, 0 skipped. If coverage gating is configured in `pyproject.toml`, it must report 100% for the new modules.

- [ ] **Step 2: If any new line is uncovered, add a targeted test**

Check coverage for the three new modules:

Run: `uv run pytest --cov=src/artifactsmmo_cli/ai/tiers/skill_gates --cov=src/artifactsmmo_cli/ai/tiers/skill_grind_target --cov=src/artifactsmmo_cli/ai/strategy_reorder --cov-report=term-missing -q`
Expected: 100% for each. Add a test for any `term-missing` line (e.g. the `_insert_*` `return lst + bucket` append-fallback paths, the `_stronger_source` `b` branch).

- [ ] **Step 3: Whole-repo type-check + lint**

Run: `uv run mypy src && uv run ruff check src tests`
Expected: no errors

- [ ] **Step 4: Final commit (if Step 2 added tests)**

```bash
git add tests/test_ai/
git commit -m "test(planner): close coverage gaps on skill-gate modules"
```

---

## Self-Review (completed during plan authoring)

**Spec coverage:**
- Component 1 `gating_skills` → Task 1. ✓ (demand set: gear/tool/task/combat; gather-gate exclusion; closure; owned filter; multi-want aggregation).
- Component 2 `skill_grind_target` → Task 2. ✓ (shallowest chain, in-hand preference, None on no-recipe).
- Component 3 reorder + 4-row ordering table → Task 3. ✓ (one test per row + identity + violation).
- Arbiter wiring + `objective` param + raise → Task 4. ✓
- Player passes objective → Task 4 Step 5. ✓
- LIV-SKILL-1/2/3 → Task 5. ✓
- Coverage / 0-warning gate → Task 6. ✓

**Placeholder scan:** No TBDs. Every code step shows complete code. The Task 4 integration test carries an implementer note about monkeypatch target names (injection mechanics only, not behavior).

**Type consistency:** `SkillGate(required_level, source)`, `GateSource.{TASK_ITEM,GEAR,TOOL,COMBAT}`, `gating_skills(state, game_data, objective, combat_weapon)`, `skill_grind_target(skill, state, game_data) -> str | None`, `reorder_skill_candidates(candidates, gates, state, game_data, has_paying_task) -> tuple[list[Candidate], list[str]]`, `GatherMaterialsGoal(target_item=, needed=)` with `repr` `GatherMaterials(<code>)`, `select(..., objective=None)` — names match across all tasks and the production signatures verified in source.

**Known risk:** Task 4's integration test monkeypatches `active_guards` / `active_means` / `objective_step_goal` on the `strategy_driver` module to force a single gating LevelSkill candidate into the assembled list. If those symbols are imported into `strategy_driver` under different local names, patch the names actually referenced inside `select`. The behavior under test (raise on violation) is unambiguous; only the injection mechanics may need adjustment to the file's real structure.
