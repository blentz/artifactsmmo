# Goal Tiers P3a — Tier-3 Strategy Engine (Shadow Mode) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). The engine is pure; the only player change is additive (a trace field). No behavior change.

**Goal:** Build `StrategyEngine.decide` (rank Tier-1 roots by personality-weighted contribution ÷ structural cost, descend to the nearest actionable subgoal, emit a `StrategyDecision`) and run it in shadow — emit the decision to `traces.jsonl` each cycle without changing any decision.

**Architecture:** Pure `tiers/strategy.py` over P1 (`CharacterObjective`/`ObjectiveGap`/`Personality`) + P2 (`objective_roots`/`prerequisites`/meta-goal nodes). The player builds the engine once after game-data load and adds `record["strategy"]` in `_emit_trace`; nothing else changes.

**Tech Stack:** Python 3.13, uv, pytest.

---

## File Structure
- Create `src/artifactsmmo_cli/ai/tiers/strategy.py` — `RootScore`, `StrategyDecision`, `StrategyEngine`, module helpers (`actionable_step`, `unmet_closure_size`, `root_category`, `desired_state_of`), local `CRITICAL_HP_FRACTION`.
- Modify `src/artifactsmmo_cli/ai/tiers/__init__.py` — exports.
- Modify `src/artifactsmmo_cli/ai/player.py` — build objective+strategy once; emit `strategy` in `_emit_trace`.
- Tests: `tests/test_ai/test_tiers_strategy.py`, `tests/test_ai/test_player_strategy_shadow.py`.

---

## Task 1: `strategy.py` engine

**Files:** Create `src/artifactsmmo_cli/ai/tiers/strategy.py`; Test `tests/test_ai/test_tiers_strategy.py`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_tiers_strategy.py`:

```python
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import (
    StrategyEngine,
    actionable_step,
    desired_state_of,
    root_category,
    unmet_closure_size,
)
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"fire": 12}, crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}, "copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._monster_level = {"chicken": 1}
    return gd


def test_actionable_step_descends_to_ready_node():
    gd = _gd()
    # copper_dagger -> copper_bar -> copper_ore(gather, mining 1 met) is the
    # deepest node whose direct prereqs are all satisfied.
    step = actionable_step(ObtainItem("copper_dagger"), make_state(), gd)
    assert step == ObtainItem("copper_ore", 10)


def test_actionable_step_blocked_returns_none():
    gd = GameData()
    gd._crafting_recipes = {"a": {"a": 1}}  # self-referential, no gather/leaf path
    gd._item_stats = {"a": ItemStats(code="a", level=1, type_="resource")}
    assert actionable_step(ObtainItem("a"), make_state(), gd) is None


def test_unmet_closure_size_counts_unmet_nodes():
    gd = _gd()
    # dagger + bar + ore all unmet → 3 (min 1).
    assert unmet_closure_size(ObtainItem("copper_dagger"), make_state(), gd) == 3
    assert unmet_closure_size(ObtainItem("copper_ore"), make_state(), gd) == 1


def test_root_category():
    assert root_category(ReachCharLevel(50)) == "char_level"
    assert root_category(ReachSkillLevel("mining", 50)) == "skills"
    assert root_category(ObtainItem("x")) == "gear"


def test_desired_state_of():
    assert desired_state_of(ObtainItem("copper_ore", 6)) == {"have": {"copper_ore": 6}}
    assert desired_state_of(ReachSkillLevel("mining", 7)) == {"skill": {"mining": 7}}
    assert desired_state_of(ReachCharLevel(12)) == {"level": 12}
    assert desired_state_of(None) == {}


def test_decide_skips_satisfied_and_ranks_reachable():
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(objective=obj, personality=BalancedPersonality())
    d = eng.decide(make_state(level=5, skills={"mining": 3}), gd)
    assert d.chosen_root is not None
    assert d.chosen_step is not None
    assert d.desired_state  # non-empty descriptor
    # ranking only contains reachable, unmet roots
    assert all(rs.cost >= 1 for rs in d.ranking)


def test_decide_hp_interrupt_flag_only():
    gd = _gd()
    eng = StrategyEngine(objective=CharacterObjective.from_game_data(gd),
                         personality=BalancedPersonality())
    low = make_state(level=5, hp=10, max_hp=100)   # 10% < 25%
    assert eng.decide(low, gd).interrupt == "restore_hp"
    ok = make_state(level=5, hp=90, max_hp=100)
    assert eng.decide(ok, gd).interrupt is None


def test_personality_reweighting_changes_choice():
    gd = _gd()
    obj = CharacterObjective.from_game_data(gd)
    state = make_state(level=49, skills={s: 1 for s in obj.target_skill_levels})  # tiny level gap, huge skill gaps

    class SkillFirst:
        def category_weight(self, category: str) -> float:
            return 10.0 if category == "skills" else 1.0

    skill_choice = StrategyEngine(obj, SkillFirst()).decide(state, gd).chosen_root
    assert root_category(skill_choice) == "skills"


def test_decide_empty_when_nothing_reachable():
    gd = GameData()  # no items, no monsters, no recipes
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(obj, BalancedPersonality())
    # maxed level+skills, no gear targets → no unmet reachable roots.
    maxed = make_state(level=50, skills={s: 50 for s in obj.target_skill_levels})
    d = eng.decide(maxed, gd)
    assert d.chosen_root is None
    assert d.desired_state == {}

    # trace form is JSON-friendly
    td = d.to_trace()
    assert td["chosen_root"] is None and td["ranking"] == []
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/ai/tiers/strategy.py`:

```python
"""Tier-3 strategy engine: rank Tier-1 roots and descend to the nearest
actionable subgoal. Pure; P3a runs it in shadow (traced, not enacted)."""

from dataclasses import asdict, dataclass, field

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, ObjectiveGap
from artifactsmmo_cli.ai.tiers.personality import Personality
from artifactsmmo_cli.ai.tiers.prerequisite_graph import objective_roots, prerequisites
from artifactsmmo_cli.ai.world_state import WorldState

# Mirrors RestoreHPGoal.CRITICAL_HP_FRACTION. Kept local so the tiers layer does
# not depend on goals/ (which P3c retires); P3c unifies the source.
CRITICAL_HP_FRACTION = 0.25


def root_category(node: MetaGoal) -> str:
    if isinstance(node, ReachCharLevel):
        return "char_level"
    if isinstance(node, ReachSkillLevel):
        return "skills"
    return "gear"  # ObtainItem


def desired_state_of(node: MetaGoal | None) -> dict[str, object]:
    if isinstance(node, ObtainItem):
        return {"have": {node.code: node.quantity}}
    if isinstance(node, ReachSkillLevel):
        return {"skill": {node.skill: node.level}}
    if isinstance(node, ReachCharLevel):
        return {"level": node.level}
    return {}


def actionable_step(root: MetaGoal, state: WorldState, game_data: GameData) -> MetaGoal | None:
    """Deepest unmet node reachable from root whose DIRECT prerequisites are all
    satisfied (the 'singular loop' step). None when cyclically blocked."""
    def _step(node: MetaGoal, visited: set[MetaGoal]) -> MetaGoal | None:
        if node in visited:
            return None
        visited.add(node)
        unmet = [p for p in prerequisites(node, state, game_data)
                 if not p.is_satisfied(state, game_data)]
        if not unmet:
            return node
        for prereq in sorted(unmet, key=repr):
            step = _step(prereq, visited)
            if step is not None:
                return step
        return None

    return _step(root, set())


def unmet_closure_size(root: MetaGoal, state: WorldState, game_data: GameData) -> int:
    """Structural cost proxy: count of unmet nodes in root's prereq closure (min 1)."""
    seen: set[MetaGoal] = set()
    stack: list[MetaGoal] = [root]
    count = 0
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        if not node.is_satisfied(state, game_data):
            count += 1
            stack.extend(prerequisites(node, state, game_data))
    return max(count, 1)


@dataclass(frozen=True)
class RootScore:
    root_repr: str
    category: str
    contribution: float
    cost: int
    score: float
    step_repr: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyDecision:
    interrupt: str | None
    chosen_root: MetaGoal | None
    chosen_step: MetaGoal | None
    desired_state: dict[str, object]
    ranking: list[RootScore] = field(default_factory=list)

    def to_trace(self) -> dict[str, object]:
        return {
            "interrupt": self.interrupt,
            "chosen_root": repr(self.chosen_root) if self.chosen_root is not None else None,
            "chosen_step": repr(self.chosen_step) if self.chosen_step is not None else None,
            "desired_state": self.desired_state,
            "ranking": [rs.to_dict() for rs in self.ranking],
        }


@dataclass(frozen=True)
class StrategyEngine:
    objective: CharacterObjective
    personality: Personality

    def _contribution(self, root: MetaGoal, gap: ObjectiveGap, game_data: GameData) -> float:
        category = root_category(root)
        weight = self.personality.category_weight(category)
        if isinstance(root, ReachCharLevel):
            share = gap.char_level_fraction
        elif isinstance(root, ReachSkillLevel):
            share = gap.skill_gaps.get(root.skill, 0) / game_data.max_skill_level
        else:  # ObtainItem (gear)
            slot = next((s for s, c in self.objective.target_gear.items() if c == root.code), None)
            total = sum(
                equip_value(stats)
                for c in self.objective.target_gear.values()
                if (stats := game_data.item_stats(c)) is not None
            )
            share = (gap.gear_gaps.get(slot, 0.0) / total) if (slot is not None and total > 0) else 0.0
        return weight * share

    def decide(self, state: WorldState, game_data: GameData) -> StrategyDecision:
        interrupt = "restore_hp" if state.hp_percent < CRITICAL_HP_FRACTION else None
        gap = self.objective.gap(state)
        candidates: list[tuple[MetaGoal, MetaGoal, float, int, float]] = []
        for root in objective_roots(self.objective):
            if root.is_satisfied(state, game_data):
                continue
            step = actionable_step(root, state, game_data)
            if step is None:
                continue
            contribution = self._contribution(root, gap, game_data)
            cost = unmet_closure_size(root, state, game_data)
            score = contribution / max(cost, 1)
            candidates.append((root, step, contribution, cost, score))
        candidates.sort(key=lambda c: (-c[4], repr(c[0])))
        ranking = [
            RootScore(repr(r), root_category(r), contribution, cost, score, repr(s))
            for (r, s, contribution, cost, score) in candidates
        ]
        if candidates:
            chosen_root, chosen_step = candidates[0][0], candidates[0][1]
        else:
            chosen_root = chosen_step = None
        return StrategyDecision(
            interrupt=interrupt,
            chosen_root=chosen_root,
            chosen_step=chosen_step,
            desired_state=desired_state_of(chosen_step),
            ranking=ranking,
        )
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(ai): Tier-3 StrategyEngine — frontier search + ranking (pure)"
```

---

## Task 2: Shadow wiring in the player + exports

**Files:** Modify `src/artifactsmmo_cli/ai/player.py`, `src/artifactsmmo_cli/ai/tiers/__init__.py`; Test `tests/test_ai/test_player_strategy_shadow.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_player_strategy_shadow.py`:

```python
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from artifactsmmo_cli.ai.tracing import Tracer
from tests.test_ai.fixtures import make_state


class _CaptureTracer(Tracer):
    def __init__(self) -> None:
        self.records: list[dict] = []

    def write_cycle(self, record: dict) -> None:
        self.records.append(record)

    def close(self) -> None:
        pass


def _gd() -> GameData:
    gd = GameData()
    gd._monster_level = {"chicken": 1}
    return gd


def test_emit_trace_includes_strategy_without_changing_selected_goal():
    player = GamePlayer(character="hero")
    player.game_data = _gd()
    player.state = make_state(level=3)
    player._objective = CharacterObjective.from_game_data(player.game_data)
    player._strategy = StrategyEngine(player._objective, BalancedPersonality())
    player.tracer = _CaptureTracer()

    player._emit_trace(action_name="Gather(x)", goal_name="FarmItems",
                       outcome="ok", planner_stats={})

    rec = player.tracer.records[0]
    assert rec["selected_goal"] == "FarmItems"   # unchanged — shadow only
    assert "strategy" in rec
    assert "chosen_root" in rec["strategy"]


def test_emit_trace_omits_strategy_when_engine_absent():
    player = GamePlayer(character="hero")
    player.state = make_state(level=3)
    player.tracer = _CaptureTracer()
    player._emit_trace(action_name="a", goal_name="g", outcome="ok", planner_stats={})
    assert "strategy" not in player.tracer.records[0]
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_player_strategy_shadow.py -q`
Expected: FAIL — `GamePlayer` has no `_strategy`/`_objective`; `_emit_trace` adds no `strategy`.

- [ ] **Step 3: Add exports**

In `src/artifactsmmo_cli/ai/tiers/__init__.py`, add to imports and `__all__`:

```python
from artifactsmmo_cli.ai.tiers.strategy import (
    RootScore,
    StrategyDecision,
    StrategyEngine,
    actionable_step,
    desired_state_of,
    root_category,
    unmet_closure_size,
)
```
Append those seven names to `__all__`.

- [ ] **Step 4: Wire the player**

In `src/artifactsmmo_cli/ai/player.py`:

Add the import near the other `artifactsmmo_cli.ai` imports:
```python
from artifactsmmo_cli.ai.tiers import BalancedPersonality, CharacterObjective, StrategyEngine
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine as _StrategyEngineType  # noqa: F401
```
(If a single import line suffices, use just the first; the alias line is only if a type annotation needs it — omit otherwise.)

In `__init__`, alongside the other `self._...` initialisations, add:
```python
        self._objective: CharacterObjective | None = None
        self._strategy: StrategyEngine | None = None
```

Immediately after `self.game_data = GameData.load(client)` (the
`print("...Loading game data...")` block, ~line 224):
```python
        self._objective = CharacterObjective.from_game_data(self.game_data)
        self._strategy = StrategyEngine(self._objective, BalancedPersonality())
```

In `_emit_trace`, just before `self.tracer.write_cycle(record)`:
```python
        if self._strategy is not None:
            record["strategy"] = self._strategy.decide(self.state, self.game_data).to_trace()
```
(`self.state` is already guaranteed non-None by the early return at the top of
`_emit_trace`.)

- [ ] **Step 5: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_player_strategy_shadow.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/ai/tiers/__init__.py tests/test_ai/test_player_strategy_shadow.py
git commit -m "feat(ai): shadow-emit Tier-3 strategy decision to the trace"
```

---

## Task 3: Full verification

- [ ] **Step 1: Full suite + lint + coverage**

Run: `uv run pytest -q` → all pass, 0 skipped.
Run: `uv run pytest tests/test_ai -q --cov=artifactsmmo_cli.ai.tiers --cov-report=term-missing`
→ `tiers/*` 100% (add a test for any missed branch — e.g. an unreachable-step root excluded from ranking).
Run: `uv run ruff check src/artifactsmmo_cli/ai/tiers src/artifactsmmo_cli/ai/player.py tests/test_ai/test_tiers_strategy.py tests/test_ai/test_player_strategy_shadow.py` → clean.
Run: `uv run mypy src/artifactsmmo_cli/ai/tiers` → no errors.

- [ ] **Step 2: Commit any coverage/lint fixups**

```bash
git add -A && git commit -m "test(ai): close coverage/lint gaps for P3a strategy shadow"
```

---

## Self-review notes
- **Spec coverage:** `actionable_step` deepest/blocked (T1), `unmet_closure_size` (T1), `root_category`/`desired_state_of` (T1), `decide` ranking + skip-satisfied + empty (T1), HP-interrupt flag (T1), personality reweight (T1), shadow trace field + selected_goal unchanged + absent-engine guard (T2), exports (T2). All mapped.
- **No behavior change:** the only player edits are the additive `record["strategy"]` and the one-time engine build; `selected_goal`/action/planner untouched (asserted in T2).
- **Layering:** `tiers/strategy.py` imports only `tiers/*` + `game_data` + `world_state`; no dependency on `goals/` (local `CRITICAL_HP_FRACTION`).
- **Type consistency:** `decide(WorldState, GameData) -> StrategyDecision`; helpers `(MetaGoal, WorldState, GameData)`; `StrategyEngine(objective, personality)` used identically in tests and player.
- Frozen dataclasses; `StrategyDecision`/`RootScore` carry node refs but `to_trace`/`to_dict` emit only JSON-friendly reprs/scalars.
