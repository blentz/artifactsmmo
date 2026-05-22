# Goal Tiers P3a.3 — Best-Attainable Gear Targets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Amends P1's objective; still shadow-only, no live behavior change.

**Goal:** `CharacterObjective.target_gear` targets the best *attainable* item per slot (full craft chain bottoms out in gatherables), so reachable craftable gear becomes a root and the strategy can pursue the upgrade chain instead of a drop-gated endgame item.

**Architecture:** Add a state-independent `is_attainable(code, game_data)` (cycle-safe structural producibility closure) to `tiers/objective.py`; filter `from_game_data`'s per-slot candidates by it. Fixtures whose "best" item had no production path get recipes/drops so they stay attainable.

**Tech Stack:** Python 3.13, uv, pytest.

---

## File Structure
- Modify `src/artifactsmmo_cli/ai/tiers/objective.py` — `is_attainable`, `from_game_data` filter.
- Modify `src/artifactsmmo_cli/ai/tiers/__init__.py` — export `is_attainable`.
- Modify `tests/test_ai/test_tiers_objective.py` — fixtures attainable + `is_attainable` tests.
- Modify `tests/test_ai/test_tiers_strategy.py` — reframe `test_decide_excludes_unreachable_gear`.

---

## Task 1: `is_attainable` + target_gear filter

**Files:** Modify `src/artifactsmmo_cli/ai/tiers/objective.py`, `tiers/__init__.py`; Test `tests/test_ai/test_tiers_objective.py`.

- [ ] **Step 1: Update the objective fixture + add tests**

In `tests/test_ai/test_tiers_objective.py`, make the targeted items attainable by
giving them a recipe that bottoms out in one gatherable raw. Replace the `_gd`
body's recipe/drop setup (add these lines to the existing `_gd`, keeping the
`_item_stats`):

```python
    gd._crafting_recipes = {
        c: {"bar": 1}
        for c in ("wooden_stick", "iron_sword", "copper_ring", "gold_ring", "ruby_ring")
    }
    gd._resource_drops = {"rocks": "bar"}   # bar is gatherable → chains are attainable
    gd._resource_skill = {"rocks": ("mining", 1)}
```

In `test_slot_with_no_candidate_is_omitted`, make `only_weapon` attainable so the
"weapon_slot present" assertion still holds:

```python
    def test_slot_with_no_candidate_is_omitted(self):
        gd = GameData()
        gd._item_stats = {"only_weapon": ItemStats(code="only_weapon", level=1, type_="weapon", attack={"f": 1})}
        gd._crafting_recipes = {"only_weapon": {"bar": 1}}
        gd._resource_drops = {"rocks": "bar"}
        obj = CharacterObjective.from_game_data(gd)
        assert "weapon_slot" in obj.target_gear
        assert "boots_slot" not in obj.target_gear
```

Add `is_attainable` tests (import it from `...tiers.objective`):

```python
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, is_attainable


def test_is_attainable_gatherable_and_craftable_chain():
    gd = GameData()
    gd._crafting_recipes = {"sword": {"bar": 2}, "bar": {"ore": 3}}
    gd._resource_drops = {"rocks": "ore"}
    assert is_attainable("ore", gd) is True          # gatherable raw
    assert is_attainable("sword", gd) is True         # sword<-bar<-ore all attainable


def test_is_attainable_false_for_drop_only_and_blocked_material():
    gd = GameData()
    gd._crafting_recipes = {"cursed": {"boss_drop": 1}}
    gd._resource_drops = {"rocks": "ore"}
    assert is_attainable("boss_drop", gd) is False    # no recipe, no drop
    assert is_attainable("cursed", gd) is False        # material unattainable


def test_is_attainable_false_for_cycle():
    gd = GameData()
    gd._crafting_recipes = {"a": {"a": 1}}
    assert is_attainable("a", gd) is False


def test_target_gear_prefers_attainable_over_higher_value_drop():
    gd = GameData()
    gd._item_stats = {
        "drop_blade": ItemStats(code="drop_blade", level=1, type_="weapon", attack={"f": 99}),  # unattainable
        "iron_blade": ItemStats(code="iron_blade", level=1, type_="weapon", attack={"f": 20}),    # craftable
    }
    gd._crafting_recipes = {"iron_blade": {"bar": 1}}
    gd._resource_drops = {"rocks": "bar"}
    obj = CharacterObjective.from_game_data(gd)
    assert obj.target_gear["weapon_slot"] == "iron_blade"  # attainable wins despite lower value
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_tiers_objective.py -q`
Expected: FAIL — `is_attainable` missing; new attainable-preference test fails (still picks drop_blade).

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/tiers/objective.py`, add the module function above the
classes (after the imports):

```python
def is_attainable(code: str, game_data: GameData, _path: frozenset[str] = frozenset()) -> bool:
    """True when the item is producible in principle (at max progression): its
    craft chain bottoms out in gatherables, with no drop-only/unknown component.
    State-independent — the perfect-sheet target ignores current skills. Cycle-safe."""
    recipe = game_data.crafting_recipe(code)
    if recipe is not None:
        if code in _path:
            return False
        sub_path = _path | {code}
        return all(is_attainable(mat, game_data, sub_path) for mat in recipe)
    return code in game_data._resource_drops.values()
```

In `from_game_data`, filter the ranked candidates to attainable before assigning
slots:

```python
        for type_, items in by_type.items():
            slots = [s for s in ITEM_TYPE_TO_SLOTS[type_] if s in EQUIPMENT_SLOTS]
            ranked = sorted(items, key=lambda vc: (-vc[0], vc[1]))
            attainable = [(value, code) for (value, code) in ranked
                          if is_attainable(code, game_data)]
            for slot, (_value, code) in zip(slots, attainable):
                target_gear[slot] = code
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_tiers_objective.py -q`
Expected: PASS.

- [ ] **Step 5: Export + commit**

Add `is_attainable` to `tiers/__init__.py` imports (from `...objective`) and
`__all__`. Then:

```bash
git add src/artifactsmmo_cli/ai/tiers/objective.py src/artifactsmmo_cli/ai/tiers/__init__.py tests/test_ai/test_tiers_objective.py
git commit -m "feat(ai): target best-attainable gear per slot (reachable craft chain)"
```

---

## Task 2: Reframe strategy test + full verification

**Files:** Modify `tests/test_ai/test_tiers_strategy.py`.

- [ ] **Step 1: Reframe `test_decide_excludes_unreachable_gear`**

`_reach_gd`'s `drop_blade` (no recipe/drop) is now excluded at target-build via
attainability, not at `decide` via reachability. Replace the test:

```python
def test_unattainable_gear_not_targeted_but_craftable_is():
    gd = _reach_gd()  # drop_blade unattainable; iron_helm craftable-from-gatherables
    obj = CharacterObjective.from_game_data(gd)
    assert "weapon_slot" not in obj.target_gear           # drop_blade excluded at build
    assert obj.target_gear.get("helmet_slot") == "iron_helm"
    d = StrategyEngine(obj, BalancedPersonality()).decide(make_state(level=5), gd)
    reprs = [rs.root_repr for rs in d.ranking]
    assert any("iron_helm" in r for r in reprs)            # craftable gear is a candidate
    assert all("drop_blade" not in r for r in reprs)
```

- [ ] **Step 2: Run the affected files**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py tests/test_ai/test_tiers_prerequisite_graph.py tests/test_ai/test_player_strategy_shadow.py -q`
Expected: PASS (copper_dagger / iron_helm chains are attainable; shadow `_gd` has no gear).

- [ ] **Step 3: Full verification**

Run: `uv run pytest -q` → all pass, 0 skipped.
Run: `uv run pytest tests/test_ai -q --cov=artifactsmmo_cli.ai.tiers --cov-report=term-missing`
→ `tiers/*` 100% (add a test for any missed branch — e.g. `is_attainable` gatherable-leaf path).
Run: `uv run ruff check src/artifactsmmo_cli/ai/tiers tests/test_ai/test_tiers_*.py` → clean.
Run: `uv run mypy src/artifactsmmo_cli/ai/tiers` → no errors.

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "test(ai): reframe gear-exclusion test for attainability; verify"
```

---

## Self-review notes
- **Spec coverage:** `is_attainable` gatherable/craftable-chain/drop-only/blocked-
  material/cycle (T1); `target_gear` prefers attainable over higher-value drop +
  omits slot with no attainable item (T1); strategy reframe (T2). All mapped.
- **No live behavior change:** only the (shadow) objective/strategy; player loop
  decisions untouched.
- **Layering:** `is_attainable` in `objective.py` imports only `game_data`; no
  cycle (objective is below `prerequisite_graph`/`strategy`).
- **Type consistency:** `is_attainable(str, GameData, frozenset[str]) -> bool`;
  `from_game_data` unchanged signature; downstream gap/strategy operate on the
  filtered `target_gear`.
- **Fallout handled:** every `from_game_data` fixture (objective, strategy,
  prerequisite_graph, shadow) reviewed — only the objective `_gd`/no-candidate
  test and the strategy exclusion test needed edits; copper_dagger/iron_helm
  chains were already attainable.
