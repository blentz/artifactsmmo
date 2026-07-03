# Arbiter Retune — Grind Overshadow Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retune the arbiter so occupied gear slots upgrade, skill grinds stop dominating, and the L50 capstone gets a real gradient — without breaking the Lean-proven ranking/gear/liveness invariants.

**Architecture:** Five surgical edits to two proven decision files (`strategy.py` `_marginal` + `_has_empty_armor_slot`; `potion_supply.py` `_recipe_producible`), each policy tuning within the proven `RankingComposition`. New scores are validated offline via `StrategyEngine.decide` and live via `plan Robby`. Per-change unit tests + own-group mutations; the traversal differential is untouched (it tests traversal, not scoring).

**Tech Stack:** Python 3.13, `uv`, pytest; Lean 4 gate via `./formal/gate.sh`; offline analyzer `uv run artifactsmmo plan Robby` + `scratchpad/sweep_tuned.py`.

## Global Constraints

- Run every Python command with `uv run`. `./formal/gate.sh` for the decision gate (serialized — nothing else importing `src`, no concurrent bot/mutate run).
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage; `mypy src` clean; `./formal/gate.sh` green.
- One behavioral class per file. Imports at top only. No inline imports. No `if TYPE_CHECKING`. Never catch `Exception`. No triple-dot imports.
- `make_state(**overrides)` REPLACES the `skills` dict — override as `{**make_state().skills, "gearcrafting": N}`.
- Do NOT change `RankingComposition` / `GearPolicy` / `StrategyBlend` Lean files or the traversal differential — these edits are scoring policy, structurally proven-robust. Every changed `_marginal` branch must keep the marginal strictly positive.
- Mutation discipline (bag-slot lesson): each new scoring branch gets its OWN mutation group in `formal/diff/mutate.py` bound to its unit test — never folded into the traversal-diff `STRATEGY_MUTATIONS`. Adding branches does NOT change the existing `STRATEGY_MARGINAL_MUTATIONS` bag-slot anchor text (it matches by text), so leave it as-is.
- Verify runtime activation: green tests ≠ runtime-active (feedback_verify_runtime_activation). Each behavioral change must be confirmed to FIRE on `uv run artifactsmmo plan Robby`, reported in the task's evidence.

---

### Task 1: `OCCUPIED_SLOT_UPGRADE_URGENCY` + occupied-slot upgrade branch (①)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (constant near line 148; `_marginal` ObtainItem branch, after the `EMPTY_SLOT_URGENCY` elif ~567)
- Modify: `formal/diff/mutate.py` (new `OCCUPIED_UPGRADE_MUTATIONS` group)
- Test: `tests/test_ai/test_tiers_strategy.py`

**Interfaces:**
- Produces: a filled combat armor slot with a ≥`GEAR_EQUIP_SCALE` upgrade scores `PRIOR_COMBAT_GEAR × OCCUPIED_SLOT_UPGRADE_URGENCY = 5/2`. Empty-slot and weapon branches unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_tiers_strategy.py` (reuse the module's `_gd()` + `make_state` pattern; build a gd where `iron_boots` (combat armor, level ≤ char) is a ≥2×-scale upgrade over an equipped `copper_boots`):

```python
def test_occupied_slot_big_upgrade_gets_urgency():
    gd = _gd_boots()  # copper_boots equipped (sv ~10k), iron_boots craftable (sv ~50k), level 10
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    state = make_state(level=10, equipment={**make_state().equipment, "boots_slot": "copper_boots"})
    root = ObtainItem("iron_boots", slot="boots_slot")
    assert eng._value(root, state, gd, "red_slime", None) == Fraction(5, 2)

def test_occupied_slot_small_upgrade_no_urgency():
    # gain < GEAR_EQUIP_SCALE -> no urgency, marginal stays < 1
    gd = _gd_boots_small()  # iron_boots barely better than equipped
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    state = make_state(level=10, equipment={**make_state().equipment, "boots_slot": "copper_boots"})
    root = ObtainItem("iron_boots", slot="boots_slot")
    assert eng._value(root, state, gd, "red_slime", None) < Fraction(5, 2)
```

Build `_gd_boots`/`_gd_boots_small` fixtures so `iron_boots` is combat-bearing (resistance/hp_bonus) and craftable; the small variant has gain < `GEAR_EQUIP_SCALE`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k occupied_slot -v`
Expected: FAIL — occupied upgrade currently scores 1.0, not 5/2.

- [ ] **Step 3: Implement**

Add the constant after `EMPTY_SLOT_URGENCY` (strategy.py ~148) with a docstring:

```python
OCCUPIED_SLOT_UPGRADE_URGENCY = Fraction(5, 2)
"""Urgency for replacing an OCCUPIED combat armor slot when the candidate beats
the equipped item by at least GEAR_EQUIP_SCALE (a ~2x strategic-value jump).
Ties EMPTY_SLOT_URGENCY so a large upgrade interrupts grinding/leveling and the
bot re-gears (copper->iron). Self-limits: per-tier gains shrink below the gate as
gear improves, so char-leveling resumes once well-geared. Gate at
gain >= GEAR_EQUIP_SCALE keeps minor upgrades from winning."""
```

Add the branch immediately AFTER the `EMPTY_SLOT_URGENCY` elif (strategy.py ~567), BEFORE the potion-supply elif:

```python
            elif (slot in self._combat_gear_slots(game_data) and slot != "weapon_slot"
                    and current_code is not None
                    and stats.level <= state.level
                    and gain >= GEAR_EQUIP_SCALE):
                marginal = max(marginal, Fraction(1)) * OCCUPIED_SLOT_UPGRADE_URGENCY
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k occupied_slot -v`
Expected: PASS.

- [ ] **Step 5: Add mutation group**

In `formal/diff/mutate.py` add (own group, bound to the unit test):

```python
OCCUPIED_UPGRADE_MUTATIONS = [
    ("strategy: drop occupied-slot upgrade urgency",
     "                    and gain >= GEAR_EQUIP_SCALE):\n"
     "                marginal = max(marginal, Fraction(1)) * OCCUPIED_SLOT_UPGRADE_URGENCY\n",
     "                    and gain >= GEAR_EQUIP_SCALE):\n"
     "                marginal = marginal\n"),
    ("strategy: occupied-upgrade gate >= -> >",
     "and gain >= GEAR_EQUIP_SCALE):", "and gain > GEAR_EQUIP_SCALE):"),
]
```
and a `run_group(STRATEGY_SRC, OCCUPIED_UPGRADE_MUTATIONS, "tests/test_ai/test_tiers_strategy.py", survivors)` next to the existing `STRATEGY_MARGINAL_MUTATIONS` run_group (~mutate.py:4332). Confirm both mutants are killed by the two tests.

- [ ] **Step 6: Verify runtime + commit**

Run: `uv run artifactsmmo plan Robby` — confirm an occupied-slot upgrade (e.g. `iron_boots`/`iron_helm`) now appears at score `5/2` in the ranking (was 1). Record the ranking snippet in the report.

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py formal/diff/mutate.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(arbiter): occupied-slot gear upgrade urgency (re-gear copper->iron)"
```

---

### Task 2: Skill-grind progress-decay (②)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`_marginal` ReachSkillLevel ~541-544)
- Modify: `formal/diff/mutate.py` (new `SKILL_DECAY_MUTATIONS` group)
- Test: `tests/test_ai/test_tiers_strategy.py`

**Interfaces:**
- Produces: near-term skill-grind marginal = `SKILL_MARGINAL + (1 - current/root.level) × min(gap, SKILL_GAP_CAP) × SKILL_GAP_PER_LEVEL`. Endgame (root.level ≥ max) branch unchanged.

- [ ] **Step 1: Write the failing test**

```python
def test_skill_grind_decays_with_progress():
    gd = _gd()  # existing helper; gearcrafting near-term target exists
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    # skill far from target -> higher; near target -> lower; both below char-level 1.48 band.
    lo = eng._value(ObtainItem_or_skill(...), ...)  # see below — use ReachSkillLevel roots
    from artifactsmmo_cli.ai.tiers.meta_goal import ReachSkillLevel
    far = make_state(level=10, skills={**make_state().skills, "gearcrafting": 1})
    near = make_state(level=10, skills={**make_state().skills, "gearcrafting": 8})
    root = ReachSkillLevel("gearcrafting", 10)
    v_far = eng._value(root, far, gd, "red_slime", None)
    v_near = eng._value(root, near, gd, "red_slime", None)
    assert v_far > v_near                  # decays as skill approaches target
    assert v_far < Fraction(37, 25)        # below the ungeared char-level bootstrap (1.48)
```

(Drop the `lo`/`ObtainItem_or_skill` placeholder line — use only the `ReachSkillLevel` assertions shown. Import `ReachSkillLevel` at top of the test file if not already imported.)

Compute the exact expected fractions from the formula and assert them precisely (e.g. `v_far == Fraction(93,100)` when balancing=1; if `_gd()` produces balancing=2, use `93/50`) — read the fixture's balancing to pin the exact value rather than only the inequality.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k skill_grind_decays -v`
Expected: FAIL — currently flat (v_far == v_near).

- [ ] **Step 3: Implement**

Replace strategy.py:542-544:

```python
            current = state.skills.get(root.skill, 1)
            gap = max(0, root.level - current)
            progress = Fraction(current, max(1, root.level))
            boost = (1 - progress) * min(Fraction(gap), SKILL_GAP_CAP) * SKILL_GAP_PER_LEVEL
            return SKILL_MARGINAL + boost
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k skill_grind_decays -v`
Expected: PASS. Also run the whole file — pre-existing skill-score assertions may need updating to the decayed values; fix them in place to the new behavior (curate, do not weaken) and note which in the report.

- [ ] **Step 5: Add mutation group**

```python
SKILL_DECAY_MUTATIONS = [
    ("strategy: drop skill-grind progress decay",
     "boost = (1 - progress) * min(Fraction(gap), SKILL_GAP_CAP) * SKILL_GAP_PER_LEVEL",
     "boost = min(Fraction(gap), SKILL_GAP_CAP) * SKILL_GAP_PER_LEVEL"),
]
```
+ `run_group(STRATEGY_SRC, SKILL_DECAY_MUTATIONS, "tests/test_ai/test_tiers_strategy.py", survivors)`. Confirm killed.

- [ ] **Step 6: Verify runtime + commit**

Run: `uv run artifactsmmo plan Robby` — confirm the three crafting-skill grinds no longer sit at a flat `51/25` (they now spread/decay). Record snippet.

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py formal/diff/mutate.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(arbiter): progress-decay skill-grind urgency (stop flat 2.04 domination)"
```

---

### Task 3: Capstone gradient (④)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (constant near line 106; `_marginal` ReachCharLevel ~521-533)
- Modify: `formal/diff/mutate.py` (new `CAPSTONE_GRADIENT_MUTATIONS`)
- Test: `tests/test_ai/test_tiers_strategy.py`

**Interfaces:**
- Produces: `ReachCharLevel(target)` with `gap > CHAR_REACHABLE_HORIZON` scores `CHAR_MARGINAL + (state.level/root.level) × CHAR_CAPSTONE_SCALE`. The `gap ≤ horizon` path (the +2 bootstrap) is unchanged.

- [ ] **Step 1: Write the failing test**

```python
def test_capstone_has_progress_gradient():
    gd = _gd()
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    root = ReachCharLevel(50)
    v10 = eng._value(root, make_state(level=10), gd, "red_slime", None)
    v40 = eng._value(root, make_state(level=40), gd, "red_slime", None)
    assert v40 > v10                    # rises with progress toward 50
    assert v10 > Fraction(1)            # above the old flat 1.0
    assert v40 < Fraction(37, 25)       # stays below the +2 bootstrap (1.48)
```

Pin exact fractions from the formula (v10 = `1 + (10/50)(2/5)` = `1 + 2/25` = `27/25`; v40 = `1 + (40/50)(2/5)` = `1 + 8/25` = `33/25`), accounting for `_base_prior × balancing` on char roots (both 1 for char-level).

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k capstone -v`
Expected: FAIL — capstone currently flat 1.0 (v10 == v40).

- [ ] **Step 3: Implement**

Add constant near CHAR_GAP_PER_LEVEL_GEARED (strategy.py ~106):

```python
CHAR_CAPSTONE_SCALE = Fraction(2, 5)
"""Weak long-range attractor for the L50 capstone (ReachCharLevel(target)) when
its gap exceeds CHAR_REACHABLE_HORIZON. Scales with progress (level/target) from
~1.08 (L10) to ~1.32 (L40), staying strictly below the +2 bootstrap (1.48) so it
never triggers the e27779e items-task stand-down and below EMPTY_SLOT_URGENCY so
gear-first holds — but non-flat, so the capstone can win flat windows and the bot
is pulled toward 50 instead of only local +2 hops."""
```

In `_marginal` ReachCharLevel, before the existing `reach` computation (strategy.py ~521):

```python
            gap = max(0, root.level - state.level)
            if gap > CHAR_REACHABLE_HORIZON:
                return CHAR_MARGINAL + Fraction(state.level, root.level) * CHAR_CAPSTONE_SCALE
            reach = max(0, CHAR_REACHABLE_HORIZON - gap)
            # ... existing geared/per_level path unchanged ...
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k capstone -v`
Expected: PASS.

- [ ] **Step 5: Add mutation group**

```python
CAPSTONE_GRADIENT_MUTATIONS = [
    ("strategy: drop capstone gradient (flatten to CHAR_MARGINAL)",
     "                return CHAR_MARGINAL + Fraction(state.level, root.level) * CHAR_CAPSTONE_SCALE",
     "                return CHAR_MARGINAL"),
]
```
+ `run_group(..., "tests/test_ai/test_tiers_strategy.py", survivors)`. Confirm killed.

- [ ] **Step 6: Verify runtime + commit**

Run: `uv run artifactsmmo plan Robby` — confirm `ReachCharLevel(50)` score rose above 1.0. Record snippet.

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py formal/diff/mutate.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(arbiter): weak L50 capstone progress gradient"
```

---

### Task 4: Geared-gate premise on near_term_gear (⑥)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`_has_empty_armor_slot` ~443-458)
- Modify: `formal/diff/mutate.py` (new `GEARED_GATE_MUTATIONS`)
- Test: `tests/test_ai/test_tiers_strategy.py`

**Interfaces:**
- Produces: `_has_empty_armor_slot` returns True when a combat armor slot targeted by `near_term_gear(state)` is empty (usable-now premise), instead of iterating endgame `target_gear`.

- [ ] **Step 1: Write the failing test**

```python
def test_geared_gate_uses_near_term_not_bis():
    # A near-term-usable armor item exists for an EMPTY slot; BiS for that slot is
    # high-level (not usable now). Old code (target_gear BiS, level > char) said
    # geared=False-or-True incorrectly; new code must report the empty near-term slot.
    gd = _gd_near_term_armor()
    eng = StrategyEngine(CharacterObjective.from_game_data(gd), BalancedPersonality())
    empty = make_state(level=10, equipment={**make_state().equipment, "boots_slot": None})
    assert eng._has_empty_armor_slot(empty, gd) is True
    filled = make_state(level=10)  # all near-term slots occupied
    assert eng._has_empty_armor_slot(filled, gd) is False
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k geared_gate_uses_near_term -v`
Expected: FAIL (or wrong verdict) under the current `target_gear` iteration.

- [ ] **Step 3: Implement**

In `_has_empty_armor_slot`, iterate `self.objective.near_term_gear(state)` instead of `self.objective.target_gear` (near_term_gear is already keyed to `stats.level <= state.level`, so the inner level check becomes redundant but keep the slot/combat/empty checks):

```python
    def _has_empty_armor_slot(self, state, game_data):
        combat_slots = self._combat_gear_slots(game_data)
        for slot, code in self.objective.near_term_gear(state).items():
            if slot == "weapon_slot" or slot not in combat_slots:
                continue
            if state.equipment.get(slot) is None:
                return True
        return False
```

- [ ] **Step 4: Run to verify pass + no spurious geared flip**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k geared_gate -v`
Expected: PASS. Then re-run `scratchpad/sweep_tuned.py` (or `plan Robby`) and confirm the LIVE fully-equipped Robby is still reported geared (char-level 2.25 in geared contexts) — this change must NOT flip a fully-armored state to ungeared. Record in report.

- [ ] **Step 5: Add mutation group**

```python
GEARED_GATE_MUTATIONS = [
    ("strategy: geared-gate empty check inverted",
     "            if state.equipment.get(slot) is None:\n                return True",
     "            if state.equipment.get(slot) is not None:\n                return True"),
]
```
+ `run_group(..., "tests/test_ai/test_tiers_strategy.py", survivors)`. Confirm killed. (If a pre-existing `_has_empty_armor_slot` mutation lives in `STRATEGY_MUTATIONS`/`STRATEGY_MARGINAL_MUTATIONS`, update its anchor text to the new body.)

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py formal/diff/mutate.py tests/test_ai/test_tiers_strategy.py
git commit -m "fix(arbiter): geared-gate keys on near_term_gear not endgame BiS"
```

---

### Task 5: Recipe-producible per-ingredient obtainability (⑤)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/potion_supply.py` (`_recipe_producible` ~53-68)
- Modify: `formal/diff/mutate.py` (extend the boost/potion mutation coverage OR a new group bound to a unit test)
- Test: `tests/test_ai/test_potion_supply.py` (or `test_craft_potions_boost.py`)

**Interfaces:**
- Produces: `_recipe_producible(recipe, state, game_data)` returns True iff EVERY ingredient is obtainable by (inventory+bank ≥ qty) OR (all-gold-buyable) OR (gatherable). No longer True when only one ingredient is gatherable.

- [ ] **Step 1: Write the failing test**

```python
def test_recipe_not_producible_when_one_ingredient_unobtainable():
    # recipe {gatherable_mat:1, unobtainable_mat:1}: old any() said True, new all() says False
    gd = _gd_mixed_recipe()
    state = make_state(level=10)
    from artifactsmmo_cli.ai.potion_supply import _recipe_producible
    assert _recipe_producible({"sunflower": 1, "rare_crystal": 1}, state, gd) is False

def test_recipe_producible_when_all_ingredients_obtainable():
    gd = _gd_all_gatherable()
    state = make_state(level=10)
    from artifactsmmo_cli.ai.potion_supply import _recipe_producible
    assert _recipe_producible({"sunflower": 3}, state, gd) is True
```

(Put the `_recipe_producible` import at the top of the test module, not inline.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_ai/test_potion_supply.py -k recipe -v`
Expected: FAIL — the first test currently returns True (`any` gatherable).

- [ ] **Step 3: Implement**

Replace `_recipe_producible` (potion_supply.py:53-68):

```python
def _recipe_producible(recipe: dict[str, int], state: WorldState, game_data: GameData) -> bool:
    """True when EVERY ingredient is obtainable by some tier: available in
    inventory+bank, OR fully buyable from an NPC for gold, OR gatherable from a
    resource node. Matches what the GOAP craft search actually requires — the
    guard's exclusive-gating invariant (never fire when the goal has no plannable
    path). Previously used a per-tier any() on gatherable, which admitted recipes
    the planner could not complete (149-node no-plan spin)."""
    bank = state.bank_items or {}
    drop_items = set(game_data.resource_drops.values())
    def obtainable(mat: str, qty: int) -> bool:
        if state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty:
            return True
        if any(currency == "gold" for _npc, _price, currency in game_data.npc_purchases(mat)):
            return True
        return mat in drop_items
    return all(obtainable(mat, qty) for mat, qty in recipe.items())
```

- [ ] **Step 4: Run to verify pass + no heal regression**

Run: `uv run pytest tests/test_ai/test_potion_supply.py tests/test_ai/test_craft_potions.py tests/test_ai/test_craft_potions_boost.py tests/test_ai/test_potion_supply_integration.py -v`
Expected: PASS — heal path (fully gatherable) still produces; only mixed-obtainability recipes now correctly rejected.

- [ ] **Step 5: Mutation coverage**

Add a group binding the `all(...)` semantics to the new unit test:

```python
RECIPE_PRODUCIBLE_MUTATIONS = [
    ("potion_supply: recipe producible all -> any",
     "    return all(obtainable(mat, qty) for mat, qty in recipe.items())",
     "    return any(obtainable(mat, qty) for mat, qty in recipe.items())"),
]
```
+ `run_group(POTION_SUPPLY_SRC, RECIPE_PRODUCIBLE_MUTATIONS, "tests/test_ai/test_potion_supply.py", survivors)` (define `POTION_SUPPLY_SRC` if not present). Confirm killed.

- [ ] **Step 6: Verify runtime + commit**

Run: `uv run artifactsmmo plan Robby` — confirm `CraftPotionsGoal` no longer reports `149 nodes → NO PLAN` (the goal is not attempted, or produces a real plan). Record the goals_tried line.

```bash
git add src/artifactsmmo_cli/ai/potion_supply.py formal/diff/mutate.py tests/test_ai/test_potion_supply.py
git commit -m "fix(potion): recipe-producible requires all ingredients obtainable (kill no-plan spin)"
```

---

### Task 6: Full suite, gate, liveness verify, live-plan sign-off

**Files:**
- Verify: whole suite; `./formal/gate.sh`; `uv run artifactsmmo plan Robby`.
- Possibly modify: mutation anchors / a pre-existing strategy test broken by the retune.

- [ ] **Step 1: Full suite + coverage**

Run: `uv run pytest --cov -q`
Expected: 0 failures/warnings/skips, 100% coverage. Fix any pre-existing strategy test that asserted the OLD flat scores in place to the new tuned values (curate; do not weaken/skip); list them in the report.

- [ ] **Step 2: Type check**

Run: `uv run mypy src`
Expected: clean.

- [ ] **Step 3: Decision gate**

Run: `./formal/gate.sh` (serialized).
Expected: green. Confirm: all new mutation groups (`OCCUPIED_UPGRADE`, `SKILL_DECAY`, `CAPSTONE_GRADIENT`, `GEARED_GATE`, `RECIPE_PRODUCIBLE`) killed; existing `STRATEGY_MARGINAL_MUTATIONS` + traversal `STRATEGY_MUTATIONS` still killed; the traversal differential and `RankingComposition`/`GearPolicy` Lean builds unchanged and green with no `sorry`/new axioms; **liveness axiom check passes** (LevelingDescent / WinnableAcrossBand). If the liveness check flags a regression from ① (gear preempting char-level), STOP and report — the self-limiting gate should keep `GrindCharacterXP` reachable, but this is the load-bearing verification.

- [ ] **Step 4: Live runtime sign-off (mandatory)**

Run: `uv run artifactsmmo plan Robby` and record the full ranking + goals_tried. Confirm as one report block:
- an occupied-slot upgrade scores `5/2` (① fires),
- crafting-skill grinds are no longer a flat `51/25` (② fires),
- `ReachCharLevel(50)` > 1.0 (④ fires),
- `CraftPotionsGoal` no longer `149 nodes → NO PLAN` (⑤ fires),
- Robby (fully armored) still reads geared where expected (⑥ no spurious flip).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(arbiter): full-suite + gate + live-plan sign-off for grind-overshadow retune"
```

---

## Self-Review

**Spec coverage:** ① Task 1; ② Task 2; ④ Task 3; ⑥ Task 4; ⑤ Task 5; formal/liveness/live-plan verify Task 6. Deferred ③ intentionally has no task (documented residual in the spec). ✓

**Placeholder scan:** The Task-2 test has a `lo`/`ObtainItem_or_skill(...)` placeholder line explicitly called out to DELETE, with the real `ReachSkillLevel` assertions given — flagged, not left dangling. Fixture helpers (`_gd_boots`, `_gd_near_term_armor`, `_gd_mixed_recipe`) are described by exact required properties. No TBD/TODO; every implementation step shows full code and an exact command with expected output.

**Type consistency:** `OCCUPIED_SLOT_UPGRADE_URGENCY`, `CHAR_CAPSTONE_SCALE` are `Fraction`s used identically across tasks. `_recipe_producible(recipe, state, game_data) -> bool` signature unchanged. `_has_empty_armor_slot(state, game_data) -> bool` unchanged. New mutation groups each bound to `tests/test_ai/...` unit tests (bag-slot lesson), never the traversal-diff group.
