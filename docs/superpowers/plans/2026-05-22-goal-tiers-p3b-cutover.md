# Goal Tiers P3b — Strategy Cutover — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). FIRST behavior change: the strategy now drives progression. Keep the shadow trace.

**Goal:** Map the strategy's `chosen_step` to a parameterized existing goal and select it at a fixed band; remove the six progression goals from flat auto-selection; add a low-priority fallback grind; keep survival/economy/task goals.

**Architecture:** New `ai/strategy_driver.py` (above `goals/` and `tiers/` to avoid the `goals→tiers` import cycle) holds `MetaGoalAdapter(Goal)` (delegates planning to an inner goal, fixed `priority()`) and `strategy_goal(step, state, game_data, band, combat_monster)` (maps step→inner goal). The player builds the strategy goal + fallback each cycle from `strategy.decide()` and its existing `farm_target` picker.

**Tech Stack:** Python 3.13, uv, pytest.

---

## File Structure
- Create `src/artifactsmmo_cli/ai/strategy_driver.py` — `STRATEGY_BAND`, `FALLBACK_BAND`, `MetaGoalAdapter`, `strategy_goal`.
- Modify `src/artifactsmmo_cli/ai/player.py` — remove 6 progression goals from `_build_goals`; append strategy goal + fallback; drop now-unused imports.
- Tests: `tests/test_ai/test_strategy_driver.py` (new); update `tests/test_ai/test_player.py` `TestBuildGoals`.

---

## Task 1: `strategy_driver.py` — adapter + mapper

**Files:** Create `src/artifactsmmo_cli/ai/strategy_driver.py`; Test `tests/test_ai/test_strategy_driver.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_strategy_driver.py`:

```python
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.strategy_driver import (
    FALLBACK_BAND,
    STRATEGY_BAND,
    MetaGoalAdapter,
    strategy_goal,
)
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from tests.test_ai.fixtures import make_state


def _gd():
    gd = GameData()
    gd._item_stats = {
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                   resistance={"earth": 5}, crafting_skill="gearcrafting", crafting_level=1),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"wooden_shield": {"ash_plank": 6}, "ash_plank": {"ash_wood": 1}}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


def test_adapter_delegates_and_fixes_priority():
    inner = GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 6})
    adapter = MetaGoalAdapter(inner, STRATEGY_BAND)
    s = make_state(inventory={"ash_plank": 6})
    assert adapter.is_satisfied(s) == inner.is_satisfied(s)        # delegates
    assert adapter.desired_state(s, _gd()) == inner.desired_state(s, _gd())
    assert adapter.priority(make_state(), _gd()) == STRATEGY_BAND   # fixed band
    assert "GatherMaterials" in repr(adapter)


def test_material_obtain_maps_to_gather_materials():
    g = strategy_goal(ObtainItem("ash_plank", 6), make_state(), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g, MetaGoalAdapter)
    assert isinstance(g._inner, GatherMaterialsGoal)
    assert g._inner._needed == {"ash_plank": 6}


def test_gear_obtain_maps_to_upgrade_equipment_with_committed_target():
    g = strategy_goal(ObtainItem("wooden_shield", 1), make_state(), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g._inner, UpgradeEquipmentGoal)
    assert g._inner._committed_target == ("wooden_shield", "shield_slot")


def test_skill_maps_to_level_skill():
    g = strategy_goal(ReachSkillLevel("mining", 50), make_state(), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g._inner, LevelSkillGoal)
    assert g._inner._skill_name == "mining" and g._inner._target_level == 50


def test_char_level_maps_to_grind_with_initial_xp_and_monster():
    g = strategy_goal(ReachCharLevel(50), make_state(xp=120), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g._inner, GrindCharacterXPGoal)
    assert g._inner._target_monster == "chicken" and g._inner._initial_xp == 120


def test_char_level_none_when_no_monster():
    assert strategy_goal(ReachCharLevel(50), make_state(), _gd(), STRATEGY_BAND, None) is None


def test_strategy_goal_none_for_none_step():
    assert strategy_goal(None, make_state(), _gd(), STRATEGY_BAND, "chicken") is None
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/strategy_driver.py`:

```python
"""Tier-3 → planner bridge: map the strategy's chosen step to a parameterized
existing goal, selected at a fixed priority band.

Lives above goals/ and tiers/ (imports both) to avoid the goals→tiers cycle."""

from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.world_state import WorldState

STRATEGY_BAND = 50.0
"""Fixed selection priority for the strategy-driven goal — tactical-pursuit band,
below survival/economy interrupts (HP 110, complete-task/bank-unlock 90,
deposit-full→80) and above the fallback grind."""

FALLBACK_BAND = 25.0
"""Fixed priority for the safety-net grind: above idle accept-task (20), below
the strategy band so it only drives when the strategy step won't plan."""


class MetaGoalAdapter(Goal):
    """Selects at a fixed priority but delegates all planning to an inner goal."""

    def __init__(self, inner: Goal, priority_band: float) -> None:
        self._inner = inner
        self._priority_band = priority_band

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return self._inner.value(state, game_data, history)

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        return self._priority_band

    def is_satisfied(self, state: WorldState) -> bool:
        return self._inner.is_satisfied(state)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return self._inner.desired_state(state, game_data)

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        return self._inner.relevant_actions(actions, state, game_data)

    @property
    def max_depth(self) -> int:
        return self._inner.max_depth

    def __repr__(self) -> str:
        return f"Strategy({self._inner!r})"


def strategy_goal(step: MetaGoal | None, state: WorldState, game_data: GameData,
                  priority_band: float, combat_monster: str | None) -> MetaGoalAdapter | None:
    """Map the strategy's chosen step to a parameterized inner goal."""
    inner: Goal | None = None
    if isinstance(step, ObtainItem):
        stats = game_data.item_stats(step.code)
        slots = ITEM_TYPE_TO_SLOTS.get(stats.type_) if stats is not None else None
        if slots:  # equippable gear → craft + equip
            inner = UpgradeEquipmentGoal(committed_target=(step.code, slots[0]))
        else:       # material/raw → obtain qty via gather/craft
            inner = GatherMaterialsGoal(target_item=step.code, needed={step.code: step.quantity})
    elif isinstance(step, ReachSkillLevel):
        inner = LevelSkillGoal(skill_name=step.skill, target_level=step.level)
    elif isinstance(step, ReachCharLevel):
        if combat_monster is None:
            return None
        inner = GrindCharacterXPGoal(target_monster=combat_monster, initial_xp=state.xp)
    if inner is None:
        return None
    return MetaGoalAdapter(inner, priority_band)
```

NOTE: confirm `UpgradeEquipmentGoal(committed_target=...)` accepts that kwarg
alone (it also takes `initial_equipment`); pass `initial_equipment=state.equipment`
too if its `__init__` requires it. Mirror the player's existing construction
(`UpgradeEquipmentGoal(initial_equipment=..., committed_target=...)`).

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver.py
git commit -m "feat(ai): strategy_driver — map chosen step to a planner goal"
```

---

## Task 2: Player cutover

**Files:** Modify `src/artifactsmmo_cli/ai/player.py`; Test `tests/test_ai/test_player.py`.

- [ ] **Step 1: Update `TestBuildGoals` tests**

In `tests/test_ai/test_player.py`, the build-goals tests assert the now-removed
goals. Rewrite them to the new contract (set `player._strategy` so a strategy
goal can be built — mirror `test_player_strategy_shadow`'s setup):

```python
    def test_progression_goals_removed_strategy_goal_present(self):
        player = GamePlayer(character="hero")
        gd = make_game_data_mock()   # has chicken/cow monsters + items
        player.game_data = gd
        from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
        from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
        from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
        player._objective = CharacterObjective.from_game_data(gd)
        player._strategy = StrategyEngine(player._objective, BalancedPersonality())
        player.state = make_state(level=3)
        goals = player._build_goals()
        reprs = [repr(g) for g in goals]
        # progression goals gone from flat selection
        assert not any(r in ("UpgradeEquipment", "FarmItems") or r.startswith(("FarmMonster", "GrindCharacterXP", "GatherMaterials", "LevelSkill"))
                       for r in reprs if not r.startswith("Strategy"))
        # strategy goal + kept goals present
        assert any(r.startswith("Strategy(") for r in reprs)
        assert "RestoreHP" in reprs and "DepositInventory" in reprs
```

(Adjust/remove the old `test_returns_base_goals`, `test_farm_target_*`,
`test_adds_gather_goal_*`, `test_no_gather_goal_*`,
`test_gather_goal_uses_full_recipe_qty` — they assert removed behavior. Replace
with the contract above + a kept-goals check. Show the actual edits when made.)

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_player.py -k BuildGoals -q`
Expected: FAIL — progression goals still present.

- [ ] **Step 3: Edit `_build_goals`**

In `src/artifactsmmo_cli/ai/player.py`, **keep** the committed-target /
`state.crafting_target` computation (it still feeds the scalarizer) and `farm_target`.
**Remove** the `upgrade_goal = UpgradeEquipmentGoal(...)` construction and these
list members/blocks: `upgrade_goal,` in the base list; the
`FarmMonsterGoal`/`GrindCharacterXPGoal` block; the `FarmItemsGoal` block; the
`active_gathering_skills` `LevelSkillGoal` loop; the task-gating `LevelSkillGoal`
block; the `GatherMaterialsGoal` block. Then append the strategy goal + fallback.

Concretely, the base `goals` list keeps everything except `upgrade_goal`, and
replace the combat/items/level-skill/gather tail (everything after the base list
up to the `return`) with:

```python
        # Tier-3 strategy drives progression: map the chosen step to a goal at a
        # fixed band; a low-priority grind is the safety net when it can't plan.
        decision = self._strategy.decide(self.state, self.game_data) if self._strategy else None
        step = decision.chosen_step if decision is not None else None
        sg = strategy_goal(step, self.state, self.game_data, STRATEGY_BAND, farm_target)
        if sg is not None:
            goals.append(sg)
        if farm_target is not None:
            goals.append(MetaGoalAdapter(
                GrindCharacterXPGoal(target_monster=farm_target, initial_xp=self.state.xp),
                FALLBACK_BAND))

        return [g for g in goals if repr(g) == "TaskCancel" or repr(g) not in self._suppressed_goals]
```

Add the import near the other `ai` imports:
`from artifactsmmo_cli.ai.strategy_driver import FALLBACK_BAND, STRATEGY_BAND, MetaGoalAdapter, strategy_goal`
and keep `GrindCharacterXPGoal` imported. Remove imports that become unused
(`FarmMonsterGoal`, `FarmItemsGoal`, `GatherMaterialsGoal`, `LevelSkillGoal`,
`PURSUE`, `task_decision`, `task_requirement` — verify with ruff F401 and delete
only the genuinely-unused). `UpgradeEquipmentGoal` stays (still used for the
committed-target probe).

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_player.py -k BuildGoals -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player.py
git commit -m "feat(ai): cut player progression over to the Tier-3 strategy"
```

---

## Task 3: Full verification

- [ ] **Step 1: Full suite + lint + coverage**

Run: `uv run pytest -q` → all pass, 0 skipped. Expect fallout in tests that
asserted the removed goals or items-task behavior — curate them to the new
contract (the strategy/fallback drive progression; items-tasks dormant). Show
edits when made.
Run: `uv run pytest tests/test_ai -q --cov=artifactsmmo_cli.ai.strategy_driver --cov-report=term-missing`
→ `strategy_driver.py` 100%.
Run: `uv run ruff check src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/player.py tests/test_ai/test_strategy_driver.py` → clean (mind the unused-import removals).
Run: `uv run mypy src/artifactsmmo_cli/ai/strategy_driver.py` → no errors.

- [ ] **Step 2: Commit fixups**

```bash
git add -A && git commit -m "test(ai): curate suite for P3b strategy cutover"
```

---

## Self-review notes
- **Spec coverage:** adapter delegate + fixed priority (T1); mapper material/gear/
  skill/char + none cases (T1); player removes 6 goals + adds strategy/fallback,
  keeps survival/economy/task (T2). All mapped.
- **Layering:** `strategy_driver.py` sits above `goals/` and `tiers/` (imports
  both) — no cycle (goals→tiers stays one-way).
- **Reuse:** mapper reuses tested goal classes; player's `farm_target` (path-
  aligned picker) feeds both the `ReachCharLevel` mapping and the fallback.
- **Behavior change:** first phase the bot obeys the engine; shadow `strategy`
  trace retained; `selected_goal` now reads `Strategy(...)`.
- **Risk:** the `_build_goals` edit is the delicate step — keep committed-target/
  `crafting_target` + `farm_target`; remove only the six progression members;
  re-run the full suite and curate fallout.
