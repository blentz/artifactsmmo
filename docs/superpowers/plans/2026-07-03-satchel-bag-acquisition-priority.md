# Satchel Bag Acquisition Priority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the empty, craftable bag slot a non-zero, below-combat ranking urgency so the arbiter pursues the satchel (via the already-merged task-currency funding route) instead of leaving the bag slot permanently empty.

**Architecture:** Add one `Fraction` constant (`BAG_SLOT_URGENCY`) and one `elif` branch to `StrategyEngine._marginal` in `ai/tiers/strategy.py`, mirroring the existing `EMPTY_SLOT_URGENCY` / `POTION_SUPPLY_URGENCY` policy branches. The bag currently ranks at `marginal = 0` (its `strategic_value` is 0 when the learned `inventory_weight` is cold, and the empty-slot boost is gated to combat slots). The new branch floors it to a value strictly below combat urgencies. No Lean/differential change — `strategy.py` is mutation-guarded by Python unit tests.

**Tech Stack:** Python 3.13, `uv`, pytest, Fractions. Formal gate: `formal/diff/mutate.py` (mutation), `formal/gate.sh`.

## Global Constraints

- Run every Python command with `uv run` (e.g. `uv run pytest`).
- Test success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- No inline imports; imports at top of file. Never catch `Exception`.
- `BAG_SLOT_URGENCY` MUST be `> 0` and strictly `< COMBAT_READINESS_URGENCY` (`Fraction(2)`) and `< EMPTY_SLOT_URGENCY` (`Fraction(5, 2)`) — "below combat" is preserved by construction.
- Do NOT run `mutate.py` or `gate.sh` concurrently with the live bot or anything importing `src` (serialize gate runs). Stop the bot first.
- The only bag item in game data is `satchel` (item level 5, gearcrafting level 5, recipe `{cowhide:5, feather:2, jasper_crystal:1}`). `jasper_crystal` is bought from `tasks_trader` for 8 `tasks_coin`.

---

### Task 1: Add `BAG_SLOT_URGENCY` constant and the `_marginal` bag-slot branch

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (constant near line 147; branch in `_marginal`, before the final `return marginal` of the `ObtainItem` branch ~line 574)
- Test: `tests/test_ai/test_tiers_strategy.py`

**Interfaces:**
- Consumes: `StrategyEngine._marginal(root, state, game_data, combat_monster=None, history=None) -> Fraction`; `StrategyEngine._value(root, state, game_data) -> Fraction`; `ObtainItem(code, slot=...)`; `ItemStats(code, level, type_, inventory_space=, hp_bonus=, crafting_skill=, crafting_level=)`; `make_state(**overrides)`; `CharacterObjective.from_game_data(gd)`; `BalancedPersonality`.
- Produces: module-level `BAG_SLOT_URGENCY: Fraction` in `strategy.py`; a new `_gd_bag()` fixture in the test module.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_tiers_strategy.py` (the `ItemStats`, `StrategyEngine`, `CharacterObjective`, `BalancedPersonality`, `ObtainItem`, `make_state`, `fill_monster_stat_defaults`, `Fraction` imports already exist at the top of this file):

```python
def _gd_bag() -> GameData:
    """GameData with the craftable bag (satchel, gearcrafting L5) plus an empty
    combat helmet, for the bag-slot urgency tests. satchel's only stat is
    inventory_space, so its equip_value and cold strategic_value are both 0 —
    the exact zero-collapse the BAG_SLOT_URGENCY floor addresses. iron_helmet
    carries hp_bonus (combat-bearing) so helmet_slot is an empty COMBAT slot,
    giving a concrete 'below combat' comparison target."""
    gd = GameData()
    gd._item_stats = {
        "satchel": ItemStats(
            code="satchel", level=5, type_="bag", inventory_space=20,
            crafting_skill="gearcrafting", crafting_level=5),
        "iron_helmet": ItemStats(
            code="iron_helmet", level=5, type_="helmet", hp_bonus=20,
            crafting_skill="gearcrafting", crafting_level=5),
        "cowhide": ItemStats(code="cowhide", level=8, type_="resource"),
    }
    gd._crafting_recipes = {"satchel": {"cowhide": 5}, "iron_helmet": {"cowhide": 5}}
    gd._monster_level = {"chicken": 1}  # gives from_game_data a combat monster
    fill_monster_stat_defaults(gd)
    return gd


def _bag_state(gearcrafting: int = 5):
    """State at level 11 with empty bag + helmet slots and the given
    gearcrafting skill. Copies make_state's default skills so only gearcrafting
    is overridden (bag branch gates on gearcrafting >= satchel.crafting_level)."""
    base = make_state(level=11)
    return make_state(
        level=11,
        skills={**base.skills, "gearcrafting": gearcrafting},
        equipment={**base.equipment, "bag_slot": None, "helmet_slot": None},
    )


def test_empty_bag_slot_scores_nonzero():
    gd = _gd_bag()
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    root = ObtainItem("satchel", slot="bag_slot")
    assert eng._value(root, _bag_state(), gd) > 0


def test_empty_bag_slot_below_empty_combat_slot():
    gd = _gd_bag()
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    state = _bag_state()
    bag = eng._value(ObtainItem("satchel", slot="bag_slot"), state, gd)
    helmet = eng._value(ObtainItem("iron_helmet", slot="helmet_slot"), state, gd)
    assert 0 < bag < helmet


def test_bag_floor_gated_on_craft_skill():
    gd = _gd_bag()
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    # gearcrafting 1 < satchel.crafting_level 5 → not craftable yet → no floor.
    root = ObtainItem("satchel", slot="bag_slot")
    assert eng._value(root, _bag_state(gearcrafting=1), gd) == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k bag -v`
Expected: `test_empty_bag_slot_scores_nonzero` and `test_empty_bag_slot_below_empty_combat_slot` FAIL (bag `_value` is `0`, so `> 0` / `0 < bag` fail). `test_bag_floor_gated_on_craft_skill` PASSES already (bag is 0 with no floor). `NameError` for `BAG_SLOT_URGENCY` will NOT occur yet since the constant isn't referenced until Step 3.

- [ ] **Step 3: Add the constant**

In `src/artifactsmmo_cli/ai/tiers/strategy.py`, immediately after the `EMPTY_SLOT_URGENCY = Fraction(5, 2)` definition (~line 147, before `POTION_SUPPLY_URGENCY`):

```python
BAG_SLOT_URGENCY = Fraction(1)
"""Empty-bag-slot marginal floor (2026-07-03). Strictly below
COMBAT_READINESS_URGENCY (2) and EMPTY_SLOT_URGENCY (5/2) so a weapon / empty
combat armor slot always outranks the bag, but non-zero so the bag is pursued
when no combat/gear upgrade is servable. A bag's strategic_value is 0 when the
learned inventory_weight is cold, so this floors the marginal directly. The
funding route (ReachCurrencyGoal) + sticky commitment then acquire the satchel.
See docs/superpowers/specs/2026-07-03-satchel-bag-acquisition-priority-design.md."""
```

- [ ] **Step 4: Add the `_marginal` branch**

In `StrategyEngine._marginal`, the `ObtainItem` branch ends with `return marginal` (~line 574) followed by the method's fallback `return Fraction(0)`. Insert the new `elif` immediately before that `return marginal`, after the potion-supply `elif`. Match on this exact text:

```python
            return marginal
        return Fraction(0)
```

Replace with:

```python
            # Bag-slot floor (2026-07-03): an empty bag slot whose bag is
            # craftable NOW (gearcrafting >= its crafting_level) is worth a
            # non-zero, BELOW-combat pursuit so the arbiter fills it in windows
            # with no combat/gear upgrade. BAG_SLOT_URGENCY < COMBAT_READINESS
            # (2) and < EMPTY_SLOT (5/2), so a weapon / empty combat slot always
            # wins. Floors marginal directly (bag strategic_value is 0 cold).
            elif (slot == "bag_slot" and current_code is None
                    and stats.level <= state.level
                    and state.skills.get(stats.crafting_skill, 0) >= stats.crafting_level):
                marginal = max(marginal, BAG_SLOT_URGENCY)
            return marginal
        return Fraction(0)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k bag -v`
Expected: all three PASS. (If `test_empty_bag_slot_below_empty_combat_slot` fails because `bag` is not `< helmet`, the bag's base-prior tier is higher than expected; this is a calibration signal handled in Task 3 — do not change the assertion, note it and continue to Step 6 first to confirm the other two pass.)

- [ ] **Step 6: Run the full strategy test module to check for regressions**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -q`
Expected: all PASS (no existing test flips — other fixtures have no bag item, so the branch never fires for them).

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(gear): non-zero below-combat urgency floor for empty craftable bag slot

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Mutation guard for the bag-slot branch

**Files:**
- Modify: `formal/diff/mutate.py` (`STRATEGY_MUTATIONS` list, ~line 2160-2190)

**Interfaces:**
- Consumes: the exact branch text added in Task 1 Step 4; the killing test `test_empty_bag_slot_scores_nonzero` from Task 1.
- Produces: one new tuple in `STRATEGY_MUTATIONS`.

- [ ] **Step 1: Add the mutation entry**

In `formal/diff/mutate.py`, append this tuple to the `STRATEGY_MUTATIONS` list (before its closing `]`):

```python
    # bag-slot floor: dropping the branch reverts an empty craftable bag slot to
    # marginal 0 (never pursued) — killed by test_empty_bag_slot_scores_nonzero.
    ("strategy: drop bag-slot urgency floor",
     "            elif (slot == \"bag_slot\" and current_code is None\n"
     "                    and stats.level <= state.level\n"
     "                    and state.skills.get(stats.crafting_skill, 0) >= stats.crafting_level):\n"
     "                marginal = max(marginal, BAG_SLOT_URGENCY)\n",
     ""),
```

- [ ] **Step 2: Confirm the bot is stopped, then run the strategy mutation group**

The gate runs all of `mutate.py`; to check just this group quickly, run the whole mutation pass (it is the only supported entrypoint) with the bot stopped:

Run: `uv run python formal/diff/mutate.py`
Expected: `0 survivors` overall; the summary line for `STRATEGY_SRC` includes the new `strategy: drop bag-slot urgency floor` mutation as KILLED. If it SURVIVES, the killing test is not exercising the branch — revisit Task 1 tests.

- [ ] **Step 3: Commit**

```bash
git add formal/diff/mutate.py
git commit -m "test(gear): mutation guard for bag-slot urgency floor

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: End-to-end verification and calibration

**Files:** none modified unless calibration is needed (`src/artifactsmmo_cli/ai/tiers/strategy.py` `BAG_SLOT_URGENCY` only).

**Interfaces:**
- Consumes: `uv run artifactsmmo plan Robby` (offline planner dump, see `docs`/`project_plan_cli`).

- [ ] **Step 1: Full test suite + coverage**

Run: `uv run pytest -q`
Expected: 0 failures, 0 warnings, 0 skipped, 100% coverage. Fix any coverage gap on the new branch (all three states — fires, gated-off by skill, non-bag — are covered by Task 1 tests).

- [ ] **Step 2: Offline planner check — bag becomes reachable/selected**

Run: `uv run artifactsmmo plan Robby`
Expected: the plan output now surfaces the satchel path — either `ReachCurrency(tasks_coin, 8)` (funding the jasper purchase) or `ObtainItem(satchel, ...)` selected/ranked above pure grind, in a state where no combat/gear upgrade is servable. Previously (`play-trace-Robby.jsonl`) `GatherMaterials(satchel)` sat at priority 0.0 and `ReachCurrency` never appeared.

- [ ] **Step 3: Calibration (only if Step 2 shows the bag still never selected)**

If the bag is reachable but still loses to char-level grind in every window (bag never chosen), raise `BAG_SLOT_URGENCY` toward — but strictly below — `Fraction(2)`:

```python
BAG_SLOT_URGENCY = Fraction(3, 2)
```

Then re-run `uv run pytest tests/test_ai/test_tiers_strategy.py -k bag -q` (the `< helmet` assertion must still hold — 3/2 < 5/2) and repeat Step 2. Do NOT exceed `Fraction(2)`; if the bag needs a value ≥ 2 to be selected, stop and escalate to Approach B (proved affordability-gated escalation) per the spec — that is a signal the fill-in model is insufficient.

- [ ] **Step 4: Formal gate (bot stopped)**

Run: `bash formal/gate.sh`
Expected: `ALL GATE PARTS PASSED` (kernel build, no-sorry, axiom lint, manifest, differential, mutation — the mutation phase includes the Task 2 entry). No Lean files changed, so build/differential are unaffected; this confirms no regression.

- [ ] **Step 5: Commit any calibration change**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py
git commit -m "tune(gear): calibrate BAG_SLOT_URGENCY so the bag is pursued in idle windows

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

(Skip if Step 3 was not needed.)

---

## Self-Review

**Spec coverage:**
- "Non-zero, below-combat value for empty craftable bag slot" → Task 1 (constant + branch + tests asserting `> 0` and `< helmet`). ✓
- "Gated on gearcrafting ≥ 5" → Task 1 branch condition `state.skills.get(stats.crafting_skill, 0) >= stats.crafting_level` + `test_bag_floor_gated_on_craft_skill`. ✓
- "Proved cores untouched; mutation-guarded by unit tests" → Task 2 (mutation entry) + Task 3 Step 4 (gate). ✓
- "Funding route + sticky commit acquire the satchel" → Task 3 Step 2 (`artifactsmmo plan Robby` end-to-end). ✓
- "Fallback to Approach B if fill-in insufficient" → Task 3 Step 3 (escalation trigger at the `Fraction(2)` bound). ✓
- Non-goals (general task cadence, NPC-buy-over-gather) → not in any task. ✓

**Placeholder scan:** No TBD/TODO; all code blocks complete; the one conditional (Task 3 Step 3) has exact values and bounds. ✓

**Type consistency:** `BAG_SLOT_URGENCY: Fraction` defined in Task 1, referenced in Task 1 branch and Task 2 mutation string identically; `_gd_bag`/`_bag_state` defined and used within Task 1; branch condition text in Task 1 Step 4 matches the mutation `old` string in Task 2 Step 1 exactly (indentation included). ✓
