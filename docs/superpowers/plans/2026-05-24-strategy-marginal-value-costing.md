# Strategy Marginal-Value Goal Costing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the strategy's self-cancelling `contribution/cost` root score with a marginal-value model (`base_prior × marginal × balancing`, learned-blended) so goal selection reflects real leverage, rebalances with progress, and never decides by alphabetical tiebreak.

**Architecture:** All scoring changes live in `tiers/strategy.py`. `prerequisites()` already emits the gear-gated skill prereq and `decide()` already scores the gear root's actionable_step under the root, so §3 (value inheritance) needs no graph change — only the new value function plus a verification test. §4 (learned blend) threads optional `history`/`combat_monster` into `decide()`.

**Tech Stack:** Python 3.13, `uv run` (pytest, ruff line-length 120, mypy --strict), dataclasses. Spec: `docs/superpowers/specs/2026-05-24-strategy-marginal-value-costing-design.md`.

---

## File Structure

- `src/artifactsmmo_cli/ai/tiers/strategy.py` — MODIFY: category constants + `_base_prior`/`_marginal`/`_balancing`/`_value`/`_learned_blend` helpers; rewrite `decide()` ranking; drop the `instrumental` sort term; repurpose `RootScore` field population; add `history`/`combat_monster` params to `decide()`.
- `src/artifactsmmo_cli/ai/player.py` — MODIFY: pass `history` + the winnable combat monster into `decide()` (compute the monster before the `decide()` call).
- Tests: `tests/test_ai/test_tiers_strategy.py` — new value/prior/balancing/§3/§4/anti-degeneracy tests; curate the `instrumental`/`_contribution` tests.

Reconciliations (confirmed against current code):
- `prerequisites(ObtainItem)` (prerequisite_graph.py) ALREADY appends `ReachSkillLevel(stats.crafting_skill, stats.crafting_level)` when a craft is skill-gated → §3's prereq exists. `decide()` computes `contribution` for the **root** while `step = actionable_step(root)`, so a gear root whose step is a skill-level already gets the gear's value. §3 = verification.
- `Personality.category_weight(category)` exists and a reweighting test depends on it. `_base_prior` MUST multiply it: `tier_constant × personality.category_weight(category)` — so personality still shifts char_level/skills/gear, and the fine tiers add within-category distinction.
- `root_cost(root, state, game_data)` stays as the **effort** tiebreak function (unchanged); only its use as a divisor goes.
- `RootScore` fields: keep `score` (= final value), repurpose `contribution` = pre-blend `value`, `cost` = `effort`; `instrumental` stays in the dataclass (always `False`) for trace-shape compatibility.

---

### Task 1: Value helpers (prior, marginal, balancing, `_value`)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py`
- Test: `tests/test_ai/test_tiers_strategy.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_tiers_strategy.py` (it imports from `tiers.strategy` and uses `make_state`, a `GameData` fixture, `CharacterObjective`, `BalancedPersonality`). Import the new names:

```python
from artifactsmmo_cli.ai.tiers.strategy import (
    PRIOR_CHAR_LEVEL, PRIOR_COMBAT_GEAR, PRIOR_UTILITY_GEAR,
    PRIOR_COMBAT_CRAFT_SKILL, PRIOR_GATHER_SKILL, PRIOR_CONSUMABLE_SKILL,
    SKILL_MARGINAL, CHAR_MARGINAL, GEAR_EQUIP_SCALE,
    BALANCE_K, BALANCE_THRESHOLD, BALANCE_MIN, BALANCE_MAX,
)
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality


def _eng(gd, target_gear=None):
    obj = CharacterObjective.from_game_data(gd)
    if target_gear is not None:
        obj = CharacterObjective(target_char_level=50,
                                 target_skill_levels=obj.target_skill_levels,
                                 target_gear=target_gear)
    return StrategyEngine(obj, BalancedPersonality())


class TestBalancing:
    def test_leader_suppressed(self):
        eng = _eng(GameData())
        state = make_state(skills={"alchemy": 5, "mining": 1, "woodcutting": 1, "fishing": 1,
                                   "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1})
        assert eng._balancing(ReachSkillLevel("alchemy", 50), state) == BALANCE_MIN   # leader -> 0.5

    def test_laggard_boosted(self):
        eng = _eng(GameData())
        state = make_state(skills={"alchemy": 7, "cooking": 1, "mining": 1, "woodcutting": 1,
                                   "fishing": 1, "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1})
        # cooking 6 behind leader(7): 1 + 0.25*(7-1-2)=1+1.0=2.0 -> capped at BALANCE_MAX
        assert eng._balancing(ReachSkillLevel("cooking", 50), state) == BALANCE_MAX

    def test_two_behind_neutral(self):
        eng = _eng(GameData())
        state = make_state(skills={"alchemy": 5, "cooking": 3, "mining": 1, "woodcutting": 1,
                                   "fishing": 1, "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1})
        assert eng._balancing(ReachSkillLevel("cooking", 50), state) == 1.0   # 5-3-2 = 0

    def test_balancing_one_for_gear_and_char(self):
        eng = _eng(GameData())
        st = make_state()
        assert eng._balancing(ReachCharLevel(50), st) == 1.0
        assert eng._balancing(ObtainItem("x"), st) == 1.0


class TestBasePrior:
    def test_char_and_skill_family_priors(self):
        eng = _eng(GameData())
        # BalancedPersonality.category_weight is 1.0 for all categories (verify in its tests);
        # so base_prior == tier constant.
        assert eng._base_prior(ReachCharLevel(50)) == PRIOR_CHAR_LEVEL
        assert eng._base_prior(ReachSkillLevel("weaponcrafting", 50)) == PRIOR_COMBAT_CRAFT_SKILL
        assert eng._base_prior(ReachSkillLevel("mining", 50)) == PRIOR_GATHER_SKILL
        assert eng._base_prior(ReachSkillLevel("alchemy", 50)) == PRIOR_CONSUMABLE_SKILL

    def test_gear_prior_combat_vs_utility(self):
        gd = GameData()
        gd._item_stats = {
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
            "small_potion": ItemStats(code="small_potion", level=1, type_="utility"),
        }
        eng = _eng(gd, target_gear={"weapon_slot": "copper_dagger", "utility1_slot": "small_potion"})
        assert eng._base_prior(ObtainItem("copper_dagger")) == PRIOR_COMBAT_GEAR
        assert eng._base_prior(ObtainItem("small_potion")) == PRIOR_UTILITY_GEAR


class TestMarginal:
    def test_gear_marginal_gain_over_empty_slot(self):
        gd = GameData()
        gd._item_stats = {"copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                                     attack={"fire": 6})}
        eng = _eng(gd, target_gear={"weapon_slot": "copper_dagger"})
        state = make_state(equipment={"weapon_slot": None})
        m = eng._marginal(ObtainItem("copper_dagger"), state, gd)
        assert m == min(1.0, equip_value(gd.item_stats("copper_dagger")) / GEAR_EQUIP_SCALE)
        assert m > 0

    def test_gear_marginal_zero_when_no_gain(self):
        gd = GameData()
        gd._item_stats = {"wand": ItemStats(code="wand", level=1, type_="weapon", attack={"fire": 3})}
        eng = _eng(gd, target_gear={"weapon_slot": "wand"})
        state = make_state(equipment={"weapon_slot": "wand"})   # already equipped -> gain 0
        assert eng._marginal(ObtainItem("wand"), state, gd) == 0.0

    def test_char_and_skill_marginal_constants(self):
        eng = _eng(GameData())
        st = make_state()
        assert eng._marginal(ReachCharLevel(50), st, GameData()) == CHAR_MARGINAL
        assert eng._marginal(ReachSkillLevel("mining", 50), st, GameData()) == SKILL_MARGINAL


class TestValueComposition:
    def test_value_is_prior_times_marginal_times_balancing(self):
        eng = _eng(GameData())
        state = make_state(skills={"alchemy": 5, "cooking": 1, "mining": 1, "woodcutting": 1,
                                   "fishing": 1, "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1})
        root = ReachSkillLevel("alchemy", 50)
        expected = eng._base_prior(root) * eng._marginal(root, state, GameData()) * eng._balancing(root, state)
        assert eng._value(root, state, GameData()) == expected
```

(Need `from artifactsmmo_cli.ai.tiers.equip_value import equip_value` at the test top for the marginal test.)

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py::TestBalancing tests/test_ai/test_tiers_strategy.py::TestBasePrior tests/test_ai/test_tiers_strategy.py::TestMarginal tests/test_ai/test_tiers_strategy.py::TestValueComposition -v`
Expected: FAIL — `ImportError` on the new constants / `AttributeError` `_base_prior`/`_marginal`/`_balancing`/`_value`.

- [ ] **Step 3: Add constants + helpers to `strategy.py`**

After the `CRITICAL_HP_FRACTION` constant, add the category constants:

```python
PRIOR_CHAR_LEVEL = 1.0
PRIOR_COMBAT_GEAR = 1.0
PRIOR_UTILITY_GEAR = 0.4
PRIOR_COMBAT_CRAFT_SKILL = 0.6
PRIOR_GATHER_SKILL = 0.4
PRIOR_CONSUMABLE_SKILL = 0.3

SKILL_MARGINAL = 0.2
CHAR_MARGINAL = 1.0
GEAR_EQUIP_SCALE = 20.0
"""Normalizes gear equip-value gain to ~[0,1]; tune so a first-tier upgrade ≈ 0.7–0.9."""

BALANCE_K = 0.25
BALANCE_THRESHOLD = 2
BALANCE_MIN = 0.5
BALANCE_MAX = 2.0

_COMBAT_GEAR_SLOTS = frozenset({
    "weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot", "leg_armor_slot",
    "boots_slot", "ring1_slot", "ring2_slot", "amulet_slot",
})
_COMBAT_CRAFT_SKILLS = frozenset({"weaponcrafting", "gearcrafting", "jewelrycrafting"})
_GATHER_SKILLS = frozenset({"mining", "woodcutting", "fishing"})
_CONSUMABLE_CRAFT_SKILLS = frozenset({"alchemy", "cooking"})
```

Add methods to `StrategyEngine` (replacing `_contribution`):

```python
    def _base_prior(self, root: MetaGoal) -> float:
        category = root_category(root)
        weight = self.personality.category_weight(category)
        if isinstance(root, ReachCharLevel):
            tier = PRIOR_CHAR_LEVEL
        elif isinstance(root, ReachSkillLevel):
            if root.skill in _COMBAT_CRAFT_SKILLS:
                tier = PRIOR_COMBAT_CRAFT_SKILL
            elif root.skill in _GATHER_SKILLS:
                tier = PRIOR_GATHER_SKILL
            else:
                tier = PRIOR_CONSUMABLE_SKILL
        elif isinstance(root, ObtainItem):
            slot = next((s for s, c in self.objective.target_gear.items() if c == root.code), None)
            tier = PRIOR_COMBAT_GEAR if slot in _COMBAT_GEAR_SLOTS else PRIOR_UTILITY_GEAR
        else:
            tier = 0.0
        return tier * weight

    def _marginal(self, root: MetaGoal, state: WorldState, game_data: GameData) -> float:
        if isinstance(root, ReachCharLevel):
            return CHAR_MARGINAL
        if isinstance(root, ReachSkillLevel):
            return SKILL_MARGINAL
        if isinstance(root, ObtainItem):
            stats = game_data.item_stats(root.code)
            if stats is None:
                return 0.0
            slot = next((s for s, c in self.objective.target_gear.items() if c == root.code), None)
            current_code = state.equipment.get(slot) if slot is not None else None
            current_stats = game_data.item_stats(current_code) if current_code else None
            current_value = equip_value(current_stats) if current_stats is not None else 0.0
            gain = max(0.0, equip_value(stats) - current_value)
            return min(1.0, gain / GEAR_EQUIP_SCALE)
        return 0.0

    def _balancing(self, root: MetaGoal, state: WorldState) -> float:
        if not isinstance(root, ReachSkillLevel):
            return 1.0
        levels = state.skills.values()
        leader = max(levels) if levels else 0
        current = state.skills.get(root.skill, 0)
        raw = 1.0 + BALANCE_K * (leader - current - BALANCE_THRESHOLD)
        return max(BALANCE_MIN, min(BALANCE_MAX, raw))

    def _value(self, root: MetaGoal, state: WorldState, game_data: GameData) -> float:
        return self._base_prior(root) * self._marginal(root, state, game_data) * self._balancing(root, state)
```

(Remove `_contribution`. `decide()` is rewired in Task 2 — leave the old `decide()`/`instrumental_skills` temporarily; tests for the old `decide` may still pass since `_value` is additive. If removing `_contribution` breaks `test_contribution_zero_for_unknown_node_type`, that test is curated in Task 2 — for now you may keep `_contribution` until Task 2 deletes it, OR delete it now and move that test fix into this task. Prefer deleting `_contribution` here and updating that one test to call `_value`.)

Update `test_contribution_zero_for_unknown_node_type` → assert `eng._value(_Dummy(), make_state(), gd) == 0.0` (unknown node type → prior 0 → value 0).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k "Balancing or BasePrior or Marginal or ValueComposition or contribution_zero" -v`
Expected: PASS. `uv run ruff check src/artifactsmmo_cli/ai/tiers/strategy.py && uv run mypy src/artifactsmmo_cli/ai/tiers/strategy.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(ai): marginal-value scoring helpers for strategy roots

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Rewire `decide()` ranking; drop the instrumental tiebreak

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py`
- Test: `tests/test_ai/test_tiers_strategy.py`

- [ ] **Step 1: Write the failing tests**

```python
class TestAntiDegeneracy:
    def test_gear_outranks_runaway_leading_skill(self):
        # Alchemy leads at 5, others ~1; a craftable combat-gear upgrade is available.
        gd = GameData()
        gd._item_stats = {
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                       attack={"fire": 6}, crafting_skill="weaponcrafting", crafting_level=1),
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}, "copper_bar": {"copper_ore": 10}}
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._resource_skill = {"copper_rocks": ("mining", 1)}
        eng = _eng(gd, target_gear={"weapon_slot": "copper_dagger"})
        state = make_state(level=2, equipment={"weapon_slot": None},
                           skills={"alchemy": 5, "mining": 3, "woodcutting": 1, "fishing": 1,
                                   "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1})
        d = eng.decide(state, gd)
        assert root_category(d.chosen_root) in ("gear", "char_level")   # NOT the leading alchemy skill
        assert d.chosen_root != ReachSkillLevel("alchemy", 50)

    def test_lagging_skill_outranks_leader(self):
        gd = GameData()
        eng = _eng(gd)
        state = make_state(level=1, skills={"alchemy": 7, "cooking": 1, "mining": 1, "woodcutting": 1,
                                            "fishing": 1, "weaponcrafting": 1, "gearcrafting": 1, "jewelrycrafting": 1})
        d = eng.decide(state, gd)
        ranks = {rs.root_repr: rs.score for rs in d.ranking}
        # the leading alchemy must not be the top skill; a laggard scores higher
        assert ranks.get("ReachSkillLevel(skill='alchemy', level=50)", 0.0) < BALANCE_MAX  # suppressed
        # at least one lagging skill scores above the leader
        skill_scores = {r: s for r, s in ranks.items() if "ReachSkillLevel" in r}
        alchemy = skill_scores.get("ReachSkillLevel(skill='alchemy', level=50)", 0.0)
        assert max(skill_scores.values()) > alchemy
```

(Also update the existing decide/instrumental tests — see Step 3.)

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py::TestAntiDegeneracy -v`
Expected: FAIL — old `decide()` still ranks by `contribution/cost` + instrumental, so alchemy (or alphabetical skill) wins.

- [ ] **Step 3: Rewrite `decide()` ranking + remove the instrumental term**

Replace the `decide()` body's scoring/sort. Keep `interrupt`, the reachable/satisfied filters, `actionable_step`, and `root_cost` (now as `effort`). New core:

```python
    def decide(self, state: WorldState, game_data: GameData,
               history: "LearningStore | None" = None,
               combat_monster: str | None = None) -> StrategyDecision:
        interrupt = "restore_hp" if state.hp_percent < CRITICAL_HP_FRACTION else None
        candidates: list[tuple[MetaGoal, MetaGoal, float, int]] = []   # root, step, final, effort
        for root in objective_roots(self.objective):
            if root.is_satisfied(state, game_data):
                continue
            if not is_reachable(root, state, game_data):
                continue
            step = actionable_step(root, state, game_data)
            assert step is not None
            value = self._value(root, state, game_data)
            final = self._learned_blend(root, value, history, combat_monster)
            effort = root_cost(root, state, game_data)
            candidates.append((root, step, final, effort))
        candidates.sort(key=lambda c: (-c[2], c[3], repr(c[0])))   # value desc, effort asc, repr last
        ranking = [
            RootScore(repr(r), root_category(r), value, effort, value, repr(s), False)
            for (r, s, value, effort) in candidates
        ]
        if candidates:
            chosen_root: MetaGoal | None = candidates[0][0]
            chosen_step: MetaGoal | None = candidates[0][1]
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

(`RootScore` positional args: `root_repr, category, contribution, cost, score, step_repr, instrumental` — pass `contribution=value`, `cost=effort`, `score=value`, `instrumental=False`. Add a temporary `_learned_blend` that just returns `value` for now — Task 3 fills it in:)

```python
    def _learned_blend(self, root: MetaGoal, value: float,
                       history: "LearningStore | None", combat_monster: str | None) -> float:
        return value   # learned refinement added in the next task
```

Add the import at top: `from artifactsmmo_cli.ai.learning.store import LearningStore` (and drop the string-quote on the annotations) — confirm no import cycle (learning.store imports models/types, not tiers; safe).

**Remove** `instrumental_skills` and the `is_instrumental` closure (and the `from ... import` if unused elsewhere — grep first; `instrumental_skills` is imported in tests, so keep the function defined OR delete it and fix `test_instrumental_skills_are_target_gear_crafting_skills`). Decision: **delete `instrumental_skills`** and remove `test_instrumental_skills_are_target_gear_crafting_skills`, `test_instrumental_skill_wins_tie`, `test_rootscore_instrumental_false_for_non_skill` (the instrumental concept is gone). Curate `test_personality_reweighting_changes_choice` if it now picks differently — it should still pass (SkillFirst boosts the "skills" category_weight → a skill root's `_base_prior` rises → skills win; verify and adjust the asserted state if needed so the reweighting still flips the choice).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -v`
Expected: PASS (new anti-degeneracy + curated existing). `ruff` + `mypy` clean on strategy.py.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(ai): rank strategy roots by marginal value, not contribution/cost

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: §4 learned-refinement blend + wire `history`/`combat_monster` from the player

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py`, `src/artifactsmmo_cli/ai/player.py`
- Test: `tests/test_ai/test_tiers_strategy.py`

The grind yield key is `f"FarmMonster({monster})"` (the legacy repr the learning store uses, matching `goals/grind_character_xp.py`'s `expected_yield_per_cycle` call). `expected_yield_per_cycle(repr, history)` returns a `Yield` with `.char_xp` and `.sample_count`.

- [ ] **Step 1: Write the failing tests**

```python
from artifactsmmo_cli.ai.tiers.strategy import LEARN_W_MAX, LEARN_SAMPLE_FULL, XP_RATE_REFERENCE
from artifactsmmo_cli.ai.learning.store import LearningStore
from sqlmodel import Session
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel


class TestLearnedBlend:
    def test_no_history_is_pure_heuristic(self):
        eng = _eng(GameData())
        st = make_state(level=5)
        assert eng._learned_blend(ReachCharLevel(50), 1.0, None, None) == 1.0

    def test_char_level_blended_with_observed_xp(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "v.db"), character="hero")
        store.start_session()
        with Session(store._engine) as s:
            s.add(SessionModel(session_id=store._session_id, started_at="2026-05-24T00:00:00Z", character="hero"))
            for i in range(LEARN_SAMPLE_FULL):
                s.add(Cycle(session_id=store._session_id, ts=f"2026-05-24T00:{i:02d}:00Z", cycle_index=i,
                            character="hero", selected_goal="FarmMonster(chicken)", action_repr="Fight(chicken)",
                            action_class="FightAction", outcome="ok", delta_xp=int(XP_RATE_REFERENCE),
                            delta_gold=0, delta_hp=0, delta_inv_used=0, task_progress=0, task_total=0))
            s.commit()
        eng = _eng(GameData())
        try:
            blended = eng._learned_blend(ReachCharLevel(50), 1.0, store, "chicken")
            # full samples -> w = LEARN_W_MAX; observed normalized ~1.0; final = (1-w)*1 + w*1 == 1.0
            # use a heuristic value < normalized to see the blend move it:
            low = eng._learned_blend(ReachCharLevel(50), 0.4, store, "chicken")
            assert low > 0.4   # learned high-XP pulls the char-level value up
        finally:
            store.close()

    def test_blend_only_applies_to_char_level(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "v.db"), character="hero")
        eng = _eng(GameData())
        try:
            # gear/skill roots ignore history -> unchanged
            assert eng._learned_blend(ReachSkillLevel("alchemy", 50), 0.3, store, "chicken") == 0.3
            assert eng._learned_blend(ObtainItem("copper_dagger"), 0.8, store, "chicken") == 0.8
        finally:
            store.close()
```

Confirm `expected_yield_per_cycle`'s `Yield.char_xp` units match `delta_xp` aggregation (read `learning/projections.py`); adjust the seeded `delta_xp` / `XP_RATE_REFERENCE` so the normalized observed ≈ 1.0. If the projection averages per-cycle delta_xp, seeding `delta_xp = XP_RATE_REFERENCE` each cycle yields rate ≈ `XP_RATE_REFERENCE` → normalized 1.0.

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py::TestLearnedBlend -v`
Expected: FAIL — `ImportError` on `LEARN_W_MAX`/`LEARN_SAMPLE_FULL`/`XP_RATE_REFERENCE`; `_learned_blend` is the stub returning `value`.

- [ ] **Step 3: Implement `_learned_blend` + constants**

Add constants near the others:
```python
LEARN_W_MAX = 0.5
LEARN_SAMPLE_FULL = 20
XP_RATE_REFERENCE = 10.0
"""Observed char-XP/cycle that normalizes to 1.0; tune to a strong grind rate."""
```
Add the import: `from artifactsmmo_cli.ai.learning.projections import expected_yield_per_cycle`. Replace the stub:
```python
    def _learned_blend(self, root: MetaGoal, value: float,
                       history: LearningStore | None, combat_monster: str | None) -> float:
        if not (isinstance(root, ReachCharLevel) and history is not None and combat_monster):
            return value
        y = expected_yield_per_cycle(f"FarmMonster({combat_monster})", history)
        if y.sample_count <= 0:
            return value
        normalized = min(1.0, max(0.0, y.char_xp / XP_RATE_REFERENCE))
        w = LEARN_W_MAX * min(1.0, y.sample_count / LEARN_SAMPLE_FULL)
        return (1.0 - w) * value + w * normalized
```

- [ ] **Step 4: Wire the player to pass `history` + `combat_monster`**

In `player.py`, the cycle calls `decision = self._strategy.decide(state, game_data)`. The winnable monster is computed by `self._winnable_farm_target()` (used in `_selection_context`). Compute it once before `decide()` and pass both:
```python
        combat_monster = self._winnable_farm_target()
        decision = self._strategy.decide(state, game_data, history=self.history, combat_monster=combat_monster)
```
Reuse that `combat_monster` when building `SelectionContext` (avoid calling `_winnable_farm_target()` twice): set `ctx`'s `combat_monster` from the same local. (Check `_selection_context` — pass the precomputed value in, or have it accept an arg; keep it one computation per cycle.)

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py tests/test_ai/test_player.py -q` (green)
`uv run pytest -q` (FULL suite green — fix any caller of `decide()` now needing the new optional args; they default to None so existing callers/tests are unaffected)
`uv run ruff check src/artifactsmmo_cli/ai/tiers/strategy.py src/artifactsmmo_cli/ai/player.py && uv run mypy src/artifactsmmo_cli/ai/tiers/strategy.py src/artifactsmmo_cli/ai/player.py` (clean)

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py src/artifactsmmo_cli/ai/player.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(ai): blend learned char-XP rate into the char-level root value

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: §3 verification — gear-gated skill inherits the gear's value

**Files:**
- Test: `tests/test_ai/test_tiers_strategy.py` (no production change — `prerequisites` already emits the gate)

- [ ] **Step 1: Write the test**

```python
class TestGearGatedSkillInheritsValue:
    def test_skill_gated_gear_step_is_scored_under_gear_root(self):
        # copper_dagger needs weaponcrafting L3; char has weaponcrafting 1 -> the gear root's
        # actionable_step is ReachSkillLevel(weaponcrafting, 3), scored at the gear root's value.
        gd = GameData()
        gd._item_stats = {
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                       attack={"fire": 6}, crafting_skill="weaponcrafting", crafting_level=3),
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}}
        gd._resource_drops = {}
        gd._resource_skill = {}
        eng = _eng(gd, target_gear={"weapon_slot": "copper_dagger"})
        state = make_state(equipment={"weapon_slot": None},
                           inventory={"copper_bar": 6},          # materials ready -> skill is the binding gate
                           skills={"weaponcrafting": 1, "alchemy": 1, "mining": 1, "woodcutting": 1,
                                   "fishing": 1, "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1})
        d = eng.decide(state, gd)
        gear_rs = next((rs for rs in d.ranking if rs.root_repr == "ObtainItem(code='copper_dagger', quantity=1)"), None)
        assert gear_rs is not None
        assert gear_rs.step_repr == "ReachSkillLevel(skill='weaponcrafting', level=3)"   # gate is the step
        # value inherited from the gear root (combat prior * equip-gain), not the skill's 0.2 standalone
        assert gear_rs.score == eng._value(ObtainItem("copper_dagger"), state, gd)
```

(Confirm `ObtainItem.__repr__`/`ReachSkillLevel.__repr__` formats match — adjust the expected strings to the real reprs if they differ.)

- [ ] **Step 2: Run — expect PASS immediately (no prod change)**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py::TestGearGatedSkillInheritsValue -v`
Expected: PASS — `prerequisites` already emits the skill gate and `decide` scores the step under the gear root. If it FAILS, investigate whether `actionable_step` actually surfaces the skill gate (it should, since the unmet `ReachSkillLevel` prereq is recursed into); do NOT add new prod code without confirming the gap is real — report findings.

- [ ] **Step 3: Commit**

```bash
git add tests/test_ai/test_tiers_strategy.py
git commit -m "test(ai): gear-gated skill step inherits the gear root's value

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Full verification

**Files:** none

- [ ] **Step 1: Full suite** — `uv run pytest -q` → 0 failures, 0 errors, 0 skipped.
- [ ] **Step 2: Lint** — `uv run ruff check src tests` → clean.
- [ ] **Step 3: Type-check** — `uv run mypy src/artifactsmmo_cli/ai/tiers/strategy.py src/artifactsmmo_cli/ai/player.py` → no errors; confirm `uv run mypy src` error count ≤ the pre-existing baseline (zero new).
- [ ] **Step 4: Coverage on changed code** — `uv run pytest tests/test_ai/test_tiers_strategy.py --cov=artifactsmmo_cli.ai.tiers.strategy --cov-report=term-missing -q` → the new helpers/`decide`/`_learned_blend` lines covered; add targeted tests for any gap.
- [ ] **Step 5: Behavioral grep gate** — confirm `instrumental_skills` is gone: `grep -rn "instrumental_skills\|is_instrumental" src tests` → empty (or only an intentional remnant). Confirm no `contribution / ` ratio remains in `decide`.

---

## Self-Review

**Spec coverage:**
- Value model `base_prior × marginal × balancing`, rank by value desc → Tasks 1-2. ✓
- Prior tiers (char/combat-gear/utility-gear/combat-craft/gather/consumable) × personality → Task 1 `_base_prior`. ✓
- Marginal (gear equip-gain normalized, char 1.0, skill 0.2) → Task 1 `_marginal`. ✓
- Balancing (leader 0.5 / 2-behind 1.0 / 6-behind 2.0; gear/char 1.0) → Task 1 `_balancing`. ✓
- §3 gear-gated skill value inheritance → Task 4 (verify; prereq already emitted). ✓
- §4 learned blend (char-level only, cold-start pure heuristic) + player wiring → Task 3. ✓
- Ranking (value desc, effort tiebreak, repr last); remove contribution/cost ratio + instrumental → Task 2. ✓
- Anti-degeneracy (gear/laggard beat runaway leader) → Task 2 tests. ✓
- Testing 0/0/0, 100% changed, grep gate → Task 5. ✓

**Placeholder scan:** `GEAR_EQUIP_SCALE`/`XP_RATE_REFERENCE` are tunable constants with stated calibration intent (not placeholders). The §3/§4 tests instruct confirming exact reprs / projection units before asserting — flagged, not vague. All code steps show full code.

**Type consistency:** `_base_prior(root)`, `_marginal(root, state, game_data)`, `_balancing(root, state)`, `_value(root, state, game_data)`, `_learned_blend(root, value, history, combat_monster)`, `decide(state, game_data, history=None, combat_monster=None)` consistent across tasks. `RootScore` positional order matches its dataclass (`root_repr, category, contribution, cost, score, step_repr, instrumental`). Constants named identically in helpers and tests.
