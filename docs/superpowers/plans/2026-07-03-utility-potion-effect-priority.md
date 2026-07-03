# Utility-Potion Effect-Based Priority — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the strategy arbiter forcing a ~30-level alchemy grind for a high-tier utility potion when a basic heal potion is adequate — judge utility/consumable slots by effect (craftable-now), not by level-based best-in-slot.

**Architecture:** Route the utility-slot "want" through a single effect-based, level-exempt target (`bootstrap_potion_target`): the effect-best potion craftable NOW, or the cheapest-to-unlock heal if none is craftable yet. Emit that as the only utility `ObtainItem` root; remove `utility` from the armor best-in-slot enumerators (`target_gear`, `near_term_gear`); gate `POTION_SUPPLY_URGENCY` to fire only on that target. Aspirational tiers (`enhanced_health_potion`) then score as ordinary low-value gear and lose to char-leveling and smaller skill grinds.

**Tech Stack:** Python 3.13, `uv`, pytest. Pure decision cores extracted per repo convention; differential + mutation gate (`gate.sh`) over the strategy layer.

## Global Constraints

- Run every Python command with `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- One behavioral class per file. Imports at top of file only. No inline imports. No `if TYPE_CHECKING`. Never catch `Exception`. No triple-dot imports.
- Use only API data or fail with an error; no defaulting over missing game data.
- Potion crafting SKILL is item metadata (`stats.crafting_skill`) — never hardcode `"alchemy"`.
- Tests live in `tests/`; use the existing `GameData()` + `ItemStats` + `make_state` fixture pattern. Do not create ad-hoc "simple" tests outside the suite.
- Serialize gate runs — never run `gate.sh` concurrently with anything importing `src` (including the bot).

---

### Task 1: `bootstrap_potion_target` + `_cheapest_heal_potion` cores

Effect-based, level-exempt selection of the utility heal to pursue.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/potion_supply.py`
- Test: `tests/test_ai/test_potion_supply.py` (create)

**Interfaces:**
- Consumes: `target_potion_pure(state, game_data, effect="hp_restore") -> str | None` (existing, same file); `game_data.crafting_recipes` (dict), `game_data.item_stats(code) -> ItemStats | None` with `.type_`, `.crafting_skill`, `.crafting_level`, and `getattr(stats, effect, 0)`.
- Produces:
  - `_cheapest_heal_potion(game_data: GameData, effect: str = "hp_restore") -> str | None` — the craftable utility heal with the smallest `crafting_level` (deterministic smallest-code tie-break); `None` when none exists.
  - `bootstrap_potion_target(state: WorldState, game_data: GameData, effect: str = "hp_restore") -> str | None` — `target_potion_pure(state, game_data, effect)` if non-None, else `_cheapest_heal_potion(game_data, effect)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ai/test_potion_supply.py`:

```python
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.potion_supply import (
    bootstrap_potion_target,
    _cheapest_heal_potion,
)
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    """small (alchemy 5) and enhanced (alchemy 45) heal potions, both craftable."""
    gd = GameData()
    gd._item_stats = {
        "small_health_potion": ItemStats(code="small_health_potion", level=5,
            type_="utility", hp_restore=50, crafting_skill="alchemy", crafting_level=5),
        "enhanced_health_potion": ItemStats(code="enhanced_health_potion", level=45,
            type_="utility", hp_restore=300, crafting_skill="alchemy", crafting_level=45),
    }
    gd._crafting_recipes = {
        "small_health_potion": {"sunflower": 3},
        "enhanced_health_potion": {"sunflower": 3},
    }
    return gd


def test_cheapest_heal_potion_is_lowest_crafting_level():
    assert _cheapest_heal_potion(_gd()) == "small_health_potion"


def test_cheapest_heal_potion_none_when_no_heal():
    gd = GameData()
    gd._item_stats = {"copper_ore": ItemStats(code="copper_ore", level=1, type_="resource")}
    gd._crafting_recipes = {"copper_ore": {}}
    assert _cheapest_heal_potion(gd) is None


def test_bootstrap_target_prefers_craftable_now():
    # alchemy 16: small craftable now, enhanced not -> small.
    gd = _gd()
    state = make_state(level=10, skills={"alchemy": 16})
    assert bootstrap_potion_target(state, gd) == "small_health_potion"


def test_bootstrap_target_falls_back_to_cheapest_when_none_craftable():
    # alchemy 1: nothing craftable now -> cheapest-to-unlock (small).
    gd = _gd()
    state = make_state(level=3, skills={"alchemy": 1})
    assert bootstrap_potion_target(state, gd) == "small_health_potion"


def test_bootstrap_target_climbs_with_skill():
    # alchemy 45: enhanced now craftable and higher-restore -> enhanced.
    gd = _gd()
    state = make_state(level=45, skills={"alchemy": 45})
    assert bootstrap_potion_target(state, gd) == "enhanced_health_potion"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_potion_supply.py -v`
Expected: FAIL with `ImportError: cannot import name 'bootstrap_potion_target'`.

- [ ] **Step 3: Implement the cores**

Add to `src/artifactsmmo_cli/ai/potion_supply.py` (after `target_potion_pure`, imports already present — `GameData`, `WorldState` are imported at top):

```python
def _cheapest_heal_potion(game_data: GameData, effect: str = "hp_restore") -> str | None:
    """The craftable utility heal with the smallest crafting_level (the next tier
    to ever unlock); deterministic smallest-code tie-break. None when none exists.

    Level-exempt bootstrap target: unlike target_potion_pure it does NOT require
    the skill to already meet the recipe gate, so the arbiter can drive the FIRST
    unlock. The crafting skill is item metadata, never assumed to be alchemy."""
    best_code: str | None = None
    best_level = 0
    for code in sorted(game_data.crafting_recipes):
        stats = game_data.item_stats(code)
        if stats is None or stats.type_ != "utility":
            continue
        if getattr(stats, effect, 0) <= 0 or stats.crafting_skill is None:
            continue
        if best_code is None or stats.crafting_level < best_level:
            best_code, best_level = code, stats.crafting_level
    return best_code


def bootstrap_potion_target(
    state: WorldState, game_data: GameData, effect: str = "hp_restore"
) -> str | None:
    """The utility heal to pursue: the effect-best potion craftable NOW, or — when
    none is craftable yet — the cheapest-to-unlock heal so the arbiter can drive
    the first skill unlock. Level-exempt (a potion's item level never gates it;
    utility is judged by effect, not level). Single source of truth for the
    utility-slot root and the POTION_SUPPLY_URGENCY gate."""
    craftable = target_potion_pure(state, game_data, effect)
    if craftable is not None:
        return craftable
    return _cheapest_heal_potion(game_data, effect)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_potion_supply.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/potion_supply.py tests/test_ai/test_potion_supply.py
git commit -m "feat(potion): level-exempt bootstrap_potion_target core"
```

---

### Task 2: Route utility through the potion target; remove it from armor BiS

`target_gear` and `near_term_gear` stop enumerating `utility`; a new `utility_potion_targets` emits the effect-based root.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/objective.py` (`from_game_data` ~228, `near_term_gear` ~274, add method)
- Test: `tests/test_ai/test_tiers_objective.py`

**Interfaces:**
- Consumes: `bootstrap_potion_target(state, game_data)` from Task 1.
- Produces: `CharacterObjective.utility_potion_targets(state: WorldState) -> dict[str, str]` — `{"utility1_slot": code}` when `bootstrap_potion_target` is non-None, else `{}`. `target_gear` / `near_term_gear` no longer contain any `type_ == "utility"` code.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ai/test_tiers_objective.py` (module already imports `GameData`, `ItemStats`, `CharacterObjective`, `make_state`):

```python
def _gd_with_potions() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon", attack={"fire": 4}),
        "small_health_potion": ItemStats(code="small_health_potion", level=5,
            type_="utility", hp_restore=50, crafting_skill="alchemy", crafting_level=5),
        "enhanced_health_potion": ItemStats(code="enhanced_health_potion", level=45,
            type_="utility", hp_restore=300, crafting_skill="alchemy", crafting_level=45),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"bar": 1},
        "small_health_potion": {"sunflower": 3},
        "enhanced_health_potion": {"sunflower": 3},
    }
    gd._resource_drops = {"rocks": "bar", "sunflower_field": "sunflower"}
    gd._resource_skill = {"rocks": ("mining", 1), "sunflower_field": ("alchemy", 1)}
    return gd


def test_target_gear_excludes_utility():
    obj = CharacterObjective.from_game_data(_gd_with_potions())
    assert all("utility" not in slot for slot in obj.target_gear)
    assert "enhanced_health_potion" not in obj.target_gear.values()


def test_near_term_gear_excludes_utility():
    obj = CharacterObjective.from_game_data(_gd_with_potions())
    targets = obj.near_term_gear(make_state(level=10, skills={"alchemy": 16}))
    assert all("utility" not in slot for slot in targets)


def test_utility_potion_targets_picks_craftable_now():
    obj = CharacterObjective.from_game_data(_gd_with_potions())
    targets = obj.utility_potion_targets(make_state(level=10, skills={"alchemy": 16}))
    assert targets == {"utility1_slot": "small_health_potion"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_tiers_objective.py -k "utility" -v`
Expected: FAIL — `utility_potion_targets` missing (AttributeError) and/or `enhanced_health_potion` present in `target_gear`.

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/tiers/objective.py`:

Add import at top with the other `ai` imports:

```python
from artifactsmmo_cli.ai.potion_supply import bootstrap_potion_target
```

In `from_game_data`, change the type filter (currently `if stats.type_ not in ITEM_TYPE_TO_SLOTS:`) to also skip utility:

```python
            if stats.type_ not in ITEM_TYPE_TO_SLOTS or stats.type_ == "utility":
                continue
```

In `near_term_gear`, change the filter (currently `if stats.type_ not in ITEM_TYPE_TO_SLOTS or stats.level > state.level:`) to:

```python
            if (stats.type_ not in ITEM_TYPE_TO_SLOTS
                    or stats.type_ == "utility"
                    or stats.level > state.level):
                continue
```

Add the method (next to `near_term_gear`):

```python
    def utility_potion_targets(self, state: WorldState) -> dict[str, str]:
        """The utility-slot heal to pursue, judged by EFFECT not level (potions
        are level-exempt). Delegates to bootstrap_potion_target — the effect-best
        potion craftable now, or the cheapest-to-unlock when none is craftable
        yet. Replaces the level-based best-in-slot utility roots that armor
        enumeration (target_gear / near_term_gear) used to emit."""
        code = bootstrap_potion_target(state, self._game_data)
        return {"utility1_slot": code} if code is not None else {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_tiers_objective.py -v`
Expected: PASS (including pre-existing objective tests — none asserted utility in `target_gear`).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/objective.py tests/test_ai/test_tiers_objective.py
git commit -m "feat(objective): route utility slot through effect-based potion target"
```

---

### Task 3: Emit the utility-potion root in `objective_roots`

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py` (`objective_roots`, ~181)
- Test: `tests/test_ai/test_tiers_prerequisite_graph.py`

**Interfaces:**
- Consumes: `objective.utility_potion_targets(state)` from Task 2; `ObtainItem(code, slot=slot)` (existing).
- Produces: `objective_roots(objective, state)` includes exactly one `ObtainItem(code, slot="utility1_slot")` for the effect-based potion, and no `ObtainItem` for `enhanced_health_potion`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_ai/test_tiers_prerequisite_graph.py` (reuse the module's existing GameData fixture helper; if none is shared, build one inline mirroring `_gd_with_potions` from Task 2):

```python
def test_objective_roots_emit_effect_based_potion_root():
    from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
    obj = CharacterObjective.from_game_data(_gd_with_potions())
    state = make_state(level=10, skills={"alchemy": 16})
    roots = objective_roots(obj, state)
    assert ObtainItem("small_health_potion", slot="utility1_slot") in roots
    assert ObtainItem("enhanced_health_potion", slot="utility1_slot") not in roots
```

(Add `_gd_with_potions` to this test module, identical to Task 2's helper, and import `objective_roots`, `CharacterObjective`, `make_state` as the file already does for its other tests.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_tiers_prerequisite_graph.py -k "effect_based_potion" -v`
Expected: FAIL — `small_health_potion` root absent (near_term_gear no longer emits it) and/or `enhanced_health_potion` present via `target_gear` (before this task it still is; after Task 2 it is not, so the second assertion may already pass — the first still fails).

- [ ] **Step 3: Implement**

In `objective_roots`, immediately after the `near_term_gear` extend block (the `roots.extend(ObtainItem(code, slot=slot) for slot, code in objective.near_term_gear(state).items())` inside the `if state is not None:` branch), add:

```python
        # Utility potions are judged by EFFECT, not level (see
        # utility_potion_targets / bootstrap_potion_target). Emit the single
        # effect-based heal root at every level — including bootstrap, where the
        # level-gated near_term_gear emits nothing — so POTION_SUPPLY_URGENCY has
        # a craftable-now-or-cheapest target to attach to instead of an
        # aspirational high-tier potion from target_gear.
        roots.extend(ObtainItem(code, slot=slot)
                     for slot, code in objective.utility_potion_targets(state).items())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_tiers_prerequisite_graph.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/prerequisite_graph.py tests/test_ai/test_tiers_prerequisite_graph.py
git commit -m "feat(roots): emit effect-based utility-potion root at every level"
```

---

### Task 4: Gate `POTION_SUPPLY_URGENCY` to the bootstrap potion target

The load-bearing fix: the 2.5 urgency fires only for the effect-based target, never an aspirational tier.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`_marginal`, potion branch ~576-581; add import)
- Test: `tests/test_ai/test_tiers_strategy.py` (`TestPotionSupplyUrgency`)

**Interfaces:**
- Consumes: `bootstrap_potion_target(state, game_data)` from Task 1.
- Produces: no signature change; `_value(root, state, gd) == Fraction(5, 2)` only when `root.code == bootstrap_potion_target(state, gd)` and equipped-qty < baseline.

- [ ] **Step 1: Write the failing regression test**

Append to `class TestPotionSupplyUrgency` in `tests/test_ai/test_tiers_strategy.py`. Extend `_gd_potions` (the fixture used by this class, ~line 220-236) so it also carries an aspirational tier; if `_gd_potions` is shared, add the enhanced item to its `_item_stats` and `_crafting_recipes` inline in the new test's own GameData instead to avoid disturbing existing assertions:

```python
    def test_aspirational_tier_not_boosted(self):
        # An under-baseline heal potion the char CANNOT craft yet (enhanced,
        # alchemy 45 vs current 16) must NOT receive the potion-supply urgency —
        # only the effect-best craftable-now target (small) does. Prevents the
        # 16->45 alchemy grind (trace play-trace-Robby.jsonl).
        gd = _gd_potions()
        gd._item_stats["enhanced_health_potion"] = ItemStats(
            code="enhanced_health_potion", level=45, type_="utility",
            hp_restore=300, crafting_skill="alchemy", crafting_level=45)
        gd._crafting_recipes["enhanced_health_potion"] = {"sunflower": 3}
        eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
        state = make_state(level=10, skills={"alchemy": 16})
        small = ObtainItem("small_health_potion", slot="utility1_slot")
        enhanced = ObtainItem("enhanced_health_potion", slot="utility1_slot")
        assert eng._value(small, state, gd) == Fraction(5, 2)     # target -> boosted
        assert eng._value(enhanced, state, gd) < Fraction(5, 2)   # aspirational -> not
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k "aspirational_tier_not_boosted" -v`
Expected: FAIL — `enhanced` currently gets `Fraction(5, 2)` (ungated urgency).

- [ ] **Step 3: Implement the gate**

In `src/artifactsmmo_cli/ai/tiers/strategy.py`, add to the existing `potion_supply` import (already imports from that module for `POTION_SUPPLY_URGENCY`? no — add a new import line near the other `ai` imports):

```python
from artifactsmmo_cli.ai.potion_supply import bootstrap_potion_target
```

Change the potion branch condition (currently at ~576-581):

```python
            elif (stats.type_ == "utility"
                    and stats.hp_restore > 0
                    and root.code == bootstrap_potion_target(state, game_data)
                    and equipped_potion_qty(state, root.code) < potion_baseline_pure(
                        state.level, POTION_LOW_LEVEL, POTION_LOW_QTY,
                        POTION_HIGH_LEVEL, POTION_HIGH_QTY)):
                marginal = max(marginal, Fraction(1)) * POTION_SUPPLY_URGENCY
```

Update the branch comment above it to note the target gate (one line): `# Fires only for the effect-based bootstrap_potion_target — never an aspirational high-tier potion (would drive a multi-level skill grind).`

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py::TestPotionSupplyUrgency -v`
Expected: PASS — new test passes; the three pre-existing tests (`test_under_baseline_heal_potion_scores_bootstrap_band`, `test_at_baseline_no_boost`, `test_non_heal_utility_not_boosted`) still pass because `small_health_potion` is the bootstrap target in their fixture and `fire_boost_potion` never was.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_tiers_strategy.py
git commit -m "fix(strategy): gate potion-supply urgency to effect-based target"
```

---

### Task 5: Full suite, mutation/differential gate, Robby regression

**Files:**
- Verify: whole suite; `gate.sh`
- Possibly modify: strategy mutation anchors / differential fixtures if the gate flags drift.

**Interfaces:** none — verification only.

- [ ] **Step 1: Run the full test suite with coverage**

Run: `uv run pytest --cov -q`
Expected: 0 failures, 0 warnings, 0 skipped, 100% coverage. If any pre-existing test asserted a utility entry in `target_gear`/`near_term_gear` or an un-gated potion boost, fix it in place to the new behavior (curate, do not skip) and re-run.

- [ ] **Step 2: Type check**

Run: `uv run mypy src tests`
Expected: no errors.

- [ ] **Step 3: Run the decision gate**

Run: `./gate.sh` (serialized — nothing else importing `src` running).
Expected: green. The strategy layer changed: if the mutation runner reports a survived mutant on the new gate condition, add a mutation anchor / bind it to `test_aspirational_tier_not_boosted` (own group, not the traversal-diff `STRATEGY_MUTATIONS` group — see the bag-slot lesson). If a differential Lean-vs-Python anchor drifts on `target_gear`, refresh the fixture (`snapshot_game_data.py` + `generate_lean_fixture.py` + `lake build`) only if the change genuinely altered a bound decision; otherwise adjust the anchor's justification.

- [ ] **Step 4: Robby-scenario regression (integration)**

Add to `tests/test_ai/test_potion_supply_integration.py` (module already builds a potions GameData + StrategyEngine): a test asserting that at char 10 / alchemy 16 with a full small-potion stack equipped, the arbiter's `chosen_root` is NOT `enhanced_health_potion` — it is a char-level or skill-grind root. Use the module's existing engine/selection helper; assert `"enhanced_health_potion" not in repr(chosen_root)`.

Run: `uv run pytest tests/test_ai/test_potion_supply_integration.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(strategy): Robby regression + gate anchors for potion-effect priority"
```

---

## Self-Review

**Spec coverage:**
- Phase 1 §1 (level-exempt target) → Task 1. ✓
- Phase 1 §2 (emit potion root; drop utility from target_gear + near_term_gear) → Tasks 2 & 3. ✓
- Phase 1 §3 (gate urgency) → Task 4. ✓
- Testing/gate (Robby regression, gate.sh rerun, gate note about GearPolicy/gap) → Task 5. ✓
- Phase 2 is design-only in the spec — intentionally no tasks here.

**Placeholder scan:** No TBD/TODO; every code step shows full code; commands have expected output. Task 3 / Task 5 reference a `_gd_with_potions` helper and integration-selection helper — both are shown (Task 2) or exist in the target module; the plan says to mirror them explicitly rather than hand-wave.

**Type consistency:** `bootstrap_potion_target(state, game_data, effect="hp_restore") -> str | None`, `_cheapest_heal_potion(game_data, effect="hp_restore") -> str | None`, `utility_potion_targets(state) -> dict[str, str]` used identically across Tasks 1–4. `ObtainItem(code, slot="utility1_slot")` matches the existing dataclass. Slot literal `"utility1_slot"` consistent with `ITEM_TYPE_TO_SLOTS["utility"]`.
