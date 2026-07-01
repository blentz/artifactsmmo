# Bootstrap Potion-Supply Weighting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** At low level, raise the health-potion strategy root's score into the bootstrap band (tie an empty combat slot, 2.5) while equipped heal-potion qty is below the level-scaled baseline, so the bot stocks potions instead of drowning them under skill-up goals.

**Architecture:** One new `elif` branch in `StrategyEngine._marginal`'s `ObtainItem` handling, parallel to the existing `EMPTY_SLOT_URGENCY` branch, plus one derived constant. No guard change, no root-generation change, no quantity change. The boosted `quantity=1` root breaks the alchemy 1→5 deadlock; the existing `CraftPotionsGoal` guard maintains the baseline once alchemy unlocks crafting.

**Tech Stack:** Python 3.13, exact `fractions.Fraction` arithmetic, pytest. Run everything with `uv run`.

## Global Constraints

- All Python commands prefixed with `uv run` (`uv run pytest`, `uv run mypy`).
- Imports at top of file only — no inline imports, no `...` imports, no `if TYPE_CHECKING`.
- One behavioral class per file; `StrategyEngine` stays the sole class in `strategy.py`. New constant is a module-level `Fraction`.
- Never catch `Exception`.
- Ranking pipeline is exact-rational — all score constants/assertions use `Fraction`, never float.
- Score targets (verbatim): empty combat slot / boosted potion = `Fraction(5, 2)` (2.5); `PRIOR_UTILITY_GEAR = Fraction(2, 5)` (0.4); `EMPTY_SLOT_URGENCY = Fraction(5, 2)`; `PRIOR_COMBAT_GEAR = Fraction(1)`.
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.

---

### Task 1: Potion-supply urgency multiplier

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` — add constant near `EMPTY_SLOT_URGENCY` (~line 132-140); add imports (top of file); add `elif` branch in `_marginal` `ObtainItem` block (after line 540).
- Test: `tests/test_ai/test_tiers_strategy.py` — add a `TestPotionSupplyUrgency` test group.

**Interfaces:**
- Consumes: `potion_baseline_pure` (`ai/potion_baseline.py`), `POTION_LOW_LEVEL/POTION_LOW_QTY/POTION_HIGH_LEVEL/POTION_HIGH_QTY` (`ai/thresholds.py`), `equipped_potion_qty` (`ai/equipped_potion.py`), `ItemStats.type_`, `ItemStats.hp_restore`.
- Produces: `POTION_SUPPLY_URGENCY: Fraction` exported from `strategy.py`; `StrategyEngine._value` returns `Fraction(5, 2)` for an under-baseline heal-potion utility root.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_tiers_strategy.py`. Extend the existing `from artifactsmmo_cli.ai.tiers.strategy import (...)` block with `POTION_SUPPLY_URGENCY`. Add a potion to a local GameData and the test group:

```python
def _gd_potions() -> GameData:
    """GameData with a heal potion (alchemy L5) and a non-heal utility item."""
    gd = GameData()
    gd._item_stats = {
        "small_health_potion": ItemStats(
            code="small_health_potion", level=1, type_="utility",
            hp_restore=60, crafting_skill="alchemy", crafting_level=5),
        "sunflower": ItemStats(code="sunflower", level=1, type_="resource"),
        "fire_boost_potion": ItemStats(
            code="fire_boost_potion", level=1, type_="utility",
            hp_restore=0, resistance={"fire": 20},
            crafting_skill="alchemy", crafting_level=10),
    }
    gd._crafting_recipes = {"small_health_potion": {"sunflower": 3}}
    gd._resource_drops = {"sunflower_field": "sunflower"}
    gd._resource_skill = {"sunflower_field": ("alchemy", 1)}
    gd._monster_level = {"chicken": 1}  # mirror _gd() so from_game_data has a combat monster
    fill_monster_stat_defaults(gd)
    return gd


class TestPotionSupplyUrgency:
    def test_constant_ties_empty_combat_slot(self):
        # POTION_SUPPLY_URGENCY applied to the utility prior lands exactly on the
        # empty-combat-slot score (2.5).
        assert PRIOR_UTILITY_GEAR * POTION_SUPPLY_URGENCY == PRIOR_COMBAT_GEAR * EMPTY_SLOT_URGENCY
        assert PRIOR_UTILITY_GEAR * POTION_SUPPLY_URGENCY == Fraction(5, 2)

    def test_under_baseline_heal_potion_scores_bootstrap_band(self):
        gd = _gd_potions()
        eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
        state = make_state(level=5)  # alchemy 1, utility slots empty, qty 0 < baseline 5
        root = ObtainItem("small_health_potion", slot="utility1_slot")
        assert eng._value(root, state, gd) == Fraction(5, 2)

    def test_at_baseline_no_boost(self):
        gd = _gd_potions()
        eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
        state = make_state(
            level=5,
            equipment={**make_state().equipment, "utility1_slot": "small_health_potion"},
            utility1_slot_quantity=5,  # == baseline at L5
        )
        root = ObtainItem("small_health_potion", slot="utility1_slot")
        assert eng._value(root, state, gd) < Fraction(5, 2)

    def test_non_heal_utility_not_boosted(self):
        gd = _gd_potions()
        eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
        state = make_state(level=5)  # fire_boost_potion slot empty, but hp_restore == 0
        root = ObtainItem("fire_boost_potion", slot="utility1_slot")
        assert eng._value(root, state, gd) < Fraction(5, 2)

    def test_baseline_is_level_scaled(self):
        gd = _gd_potions()
        eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
        root = ObtainItem("small_health_potion", slot="utility1_slot")
        # 10 equipped: below the L45 baseline (100) → boosted; at/above the L5
        # baseline (5) → not boosted. Same equipped qty, opposite result ⇒ the
        # threshold follows potion_baseline_pure, not a constant.
        equip = {**make_state().equipment, "utility1_slot": "small_health_potion"}
        hi = make_state(level=45, equipment=equip, utility1_slot_quantity=10)
        lo = make_state(level=5, equipment=equip, utility1_slot_quantity=10)
        assert eng._value(root, hi, gd) == Fraction(5, 2)
        assert eng._value(root, lo, gd) < Fraction(5, 2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py::TestPotionSupplyUrgency -v`
Expected: FAIL — `ImportError: cannot import name 'POTION_SUPPLY_URGENCY'` (and, once that import is stubbed, the value assertions fail because no boost branch exists).

- [ ] **Step 3: Add the imports**

At the top of `src/artifactsmmo_cli/ai/tiers/strategy.py`, in the existing import block (keep alphabetical/grouped with siblings):

```python
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure
from artifactsmmo_cli.ai.thresholds import (
    CRITICAL_HP_FRACTION,
    POTION_HIGH_LEVEL,
    POTION_HIGH_QTY,
    POTION_LOW_LEVEL,
    POTION_LOW_QTY,
)
```

(`CRITICAL_HP_FRACTION` is already imported from `ai.thresholds` at line 43 — merge the four potion constants into that existing import statement rather than adding a second `from ai.thresholds import`.)

- [ ] **Step 4: Add the constant**

Immediately after the `EMPTY_SLOT_URGENCY` definition/docstring (~line 140) in `strategy.py`:

```python
POTION_SUPPLY_URGENCY = EMPTY_SLOT_URGENCY * PRIOR_COMBAT_GEAR / PRIOR_UTILITY_GEAR
"""Urgency multiplier on an under-stocked health-potion utility root's marginal.
Derived so PRIOR_UTILITY_GEAR * POTION_SUPPLY_URGENCY == PRIOR_COMBAT_GEAR *
EMPTY_SLOT_URGENCY = 2.5 — an under-baseline heal potion ties an empty combat
slot at the top of the bootstrap band. Expressed as the ratio (not a literal
25/4) so it stays pinned to combat-gear-equivalent urgency if the priors are
retuned. Fires only while equipped heal-potion qty < potion_baseline (level-
scaled); breaks the alchemy-1→5 deadlock so the CraftPotions guard can then
maintain the stack. See docs/superpowers/specs/2026-07-01-bootstrap-potion-
supply-weighting-design.md."""
```

- [ ] **Step 5: Add the boost branch**

In `StrategyEngine._marginal`, `ObtainItem` block, after the `EMPTY_SLOT_URGENCY` `elif` (currently ending line 540 with `marginal = max(marginal, Fraction(1)) * EMPTY_SLOT_URGENCY`), add a sibling `elif`:

```python
            # Potion-supply urgency: an under-stocked health potion is as urgent
            # as an empty combat slot during bootstrap. Unlike the empty-slot
            # branch this is NOT gated on gain > 0 — a heal potion must stock
            # even when the strategic-value model scores its equip-gain at 0
            # (max(marginal, 1) forces the multiplier). `stats.type_ ==
            # "utility"` mirrors target_potion_pure's slot-family predicate;
            # equipped_potion_qty sums both utility slots. Breaks the alchemy
            # deadlock (see POTION_SUPPLY_URGENCY); the CraftPotions guard
            # maintains the baseline once alchemy unlocks crafting.
            elif (stats.type_ == "utility"
                    and getattr(stats, "hp_restore", 0) > 0
                    and equipped_potion_qty(state, root.code) < potion_baseline_pure(
                        state.level, POTION_LOW_LEVEL, POTION_LOW_QTY,
                        POTION_HIGH_LEVEL, POTION_HIGH_QTY)):
                marginal = max(marginal, Fraction(1)) * POTION_SUPPLY_URGENCY
            return marginal
```

(The existing `return marginal` line stays as the block's tail — insert the `elif` before it. `stats` and `marginal` are already bound earlier in the block at lines 519 and 527.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py::TestPotionSupplyUrgency -v`
Expected: PASS (all 5 cases).

- [ ] **Step 7: Run the full scorer module + mypy on the changed file**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -q && uv run mypy src/artifactsmmo_cli/ai/tiers/strategy.py`
Expected: all pass; mypy clean. If any pre-existing scorer test now fails, a real ranking regression was introduced — investigate; do not edit the failing test to pass.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(strategy): boost under-stocked heal-potion root to bootstrap band"
```

---

### Task 2: Full-suite verification + live-plan sanity check

**Files:** none (verification only).

- [ ] **Step 1: Full suite with coverage**

Run: `uv run pytest`
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage. The new branch + constant are covered by Task 1's `TestPotionSupplyUrgency`.

- [ ] **Step 2: Repo-wide type check on the ai tier**

Run: `uv run mypy src/artifactsmmo_cli/ai/tiers`
Expected: no errors.

- [ ] **Step 3: Reproduce the trace scenario (offline, no API)**

Confirm the exact L5/alchemy-1 condition from the bug now scores the potion root in-band. Write a throwaway check (do not commit) at `/tmp/claude-1000/-home-blentz-git-artifactsmmo/af5e7528-26a6-4da7-86d6-519dbdf71ff7/scratchpad/repro_potion.py`:

```python
from fractions import Fraction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from tests.test_ai.fixtures import make_state
from tests.test_ai._monster_fixture import fill_monster_stat_defaults

gd = GameData()
gd._item_stats = {"small_health_potion": ItemStats(
    code="small_health_potion", level=1, type_="utility", hp_restore=60,
    crafting_skill="alchemy", crafting_level=5)}
gd._crafting_recipes = {"small_health_potion": {"sunflower": 3}}
fill_monster_stat_defaults(gd)
eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
v = eng._value(ObtainItem("small_health_potion", slot="utility1_slot"), make_state(level=5), gd)
print("potion root score at L5:", v)
assert v == Fraction(5, 2), v
print("OK — potion root now ties combat-gear band")
```

Run: `uv run python /tmp/claude-1000/-home-blentz-git-artifactsmmo/af5e7528-26a6-4da7-86d6-519dbdf71ff7/scratchpad/repro_potion.py`
Expected: prints `potion root score at L5: 5/2` then `OK`. Delete the file after.

- [ ] **Step 4: Live-plan check (best-effort, only if API creds present)**

If a TOKEN is configured, run `uv run artifactsmmo plan Robby` (the offline plan CLI, see docs/PLAN — prints the would-be plan without executing) and confirm a `small_health_potion` / potion-supply root now ranks in the 2.x band rather than 0.4. If no creds, skip and note it in the report — Step 3 already proves the scoring change against the exact scenario.

- [ ] **Step 5: If coverage < 100%, add the missing-line test**

Identify the uncovered line from the coverage report, add a targeted case in `TestPotionSupplyUrgency` (e.g. the `stats is None` / non-utility fall-through if newly uncovered), re-run `uv run pytest`. Do not lower the coverage bar.

---

## Self-Review

- **Spec coverage:** seam + new `elif` (Task 1 Step 5); derived constant tying 2.5 (Step 4); trigger predicate `type_=="utility"` + `hp_restore>0` + `equipped < potion_baseline` (Step 5); not-gated-on-gain (comment + `max(marginal,1)`, Step 5); imports (Step 3); tests for under-baseline=2.5, at-baseline off, non-heal off, level-scaled (Step 1); formal scope = unit-tests-only (no formal task, matching spec's "no perimeter expansion"); verification incl. exact repro of the bug scenario (Task 2). All spec sections mapped.
- **Placeholder scan:** none — every step shows full code/commands.
- **Type consistency:** `POTION_SUPPLY_URGENCY` name identical across Steps 1/2/4; `equipped_potion_qty`, `potion_baseline_pure`, and the four `POTION_*` constants match their source modules (verified against `equipped_potion.py`, `potion_baseline.py`, `thresholds.py`); `_value`/`_marginal` signatures match `strategy.py:476,578`; `ObtainItem(code, quantity=1, slot=None)` matches `meta_goal.py:52`.
- **Exactness note:** `marginal` before the branch is always `min(1, …) ≤ 1`, so `max(marginal, 1) == 1` and boosted `marginal == POTION_SUPPLY_URGENCY` exactly — `_value == PRIOR_UTILITY_GEAR * POTION_SUPPLY_URGENCY == 5/2` holds regardless of the potion's strategic gain, so `== Fraction(5,2)` is a sound exact assertion.
