# Goal Tiers P3a.2 — Reachability of Obtain-Leaves — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). Refines the P3a engine; still shadow-only, no behavior change.

**Goal:** Exclude unreachable roots from the strategy ranking — a root is a candidate only if its entire prerequisite chain bottoms out in obtainable (craftable/gatherable) leaves. Stops the engine choosing drop-only gear it can't make.

**Architecture:** Add `_producible` (craftable|gatherable) and a cycle-safe full-closure `is_reachable` to `tiers/strategy.py`; guard `actionable_step` against non-producible leaves; filter `decide` candidates by `is_reachable`.

**Tech Stack:** Python 3.13, uv, pytest.

---

## File Structure
- Modify `src/artifactsmmo_cli/ai/tiers/strategy.py` — `_producible`, `is_reachable`, `actionable_step` guard, `decide` filter.
- Modify `tests/test_ai/test_tiers_strategy.py`.

---

## Task 1: Producibility + full-closure reachability

**Files:** Modify `src/artifactsmmo_cli/ai/tiers/strategy.py`; Test `tests/test_ai/test_tiers_strategy.py`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai/test_tiers_strategy.py` (extend the `from ...strategy import (...)` with `is_reachable`):

```python
def _reach_gd():
    gd = GameData()
    gd._item_stats = {
        "drop_blade": ItemStats(code="drop_blade", level=1, type_="weapon", attack={"f": 50}),
        "iron_helm": ItemStats(code="iron_helm", level=1, type_="helmet", resistance={"fire": 10},
                               crafting_skill="gearcrafting", crafting_level=1),
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource"),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"iron_helm": {"iron_bar": 5}, "iron_bar": {"iron_ore": 3}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._resource_skill = {"iron_rocks": ("mining", 1)}
    gd._monster_level = {"chicken": 1}
    return gd


def test_producible():
    from artifactsmmo_cli.ai.tiers.strategy import _producible
    gd = _reach_gd()
    assert _producible("iron_helm", gd) is True   # craftable
    assert _producible("iron_ore", gd) is True     # gatherable (iron_rocks drops it)
    assert _producible("drop_blade", gd) is False   # no recipe, no drop


def test_is_reachable_gatherable_and_craftable_chain():
    gd = _reach_gd()
    s = make_state(level=1)
    assert is_reachable(ObtainItem("iron_ore"), s, gd) is True
    assert is_reachable(ObtainItem("iron_helm"), s, gd) is True   # helm<-bar<-ore all producible


def test_is_reachable_false_for_unproducible_and_blocked_material():
    gd = _reach_gd()
    s = make_state(level=1)
    assert is_reachable(ObtainItem("drop_blade"), s, gd) is False
    # craftable item whose material is unobtainable → unreachable
    gd._crafting_recipes["cursed_helm"] = {"drop_blade": 1}
    gd._item_stats["cursed_helm"] = ItemStats(code="cursed_helm", level=1, type_="helmet")
    assert is_reachable(ObtainItem("cursed_helm"), s, gd) is False


def test_is_reachable_skill_and_char_level():
    gd = _reach_gd()
    assert is_reachable(ReachSkillLevel("mining", 50), make_state(level=1), gd) is True
    assert is_reachable(ReachCharLevel(50), make_state(level=1), gd) is True  # chicken beatable


def test_is_reachable_char_level_false_when_underequipped_and_no_makeable_weapon():
    gd = GameData()
    gd._monster_level = {"dragon": 40}  # nothing beatable at L1
    gd._item_stats = {"drop_blade": ItemStats(code="drop_blade", level=1, type_="weapon", attack={"f": 9})}
    assert is_reachable(ReachCharLevel(50), make_state(level=1), gd) is False


def test_is_reachable_satisfied_and_cycle():
    gd = _reach_gd()
    assert is_reachable(ReachCharLevel(1), make_state(level=5), gd) is True  # satisfied
    cyc = GameData()
    cyc._crafting_recipes = {"a": {"a": 1}}
    cyc._item_stats = {"a": ItemStats(code="a", level=1, type_="resource")}
    assert is_reachable(ObtainItem("a"), make_state(), cyc) is False


def test_actionable_step_none_for_unproducible_leaf():
    gd = _reach_gd()
    assert actionable_step(ObtainItem("drop_blade"), make_state(), gd) is None


def test_decide_excludes_unreachable_gear():
    gd = _reach_gd()  # weapon target drop_blade (unreachable); helmet iron_helm (craftable)
    obj = CharacterObjective.from_game_data(gd)
    assert obj.target_gear.get("weapon_slot") == "drop_blade"
    d = StrategyEngine(obj, BalancedPersonality()).decide(make_state(level=5), gd)
    reprs = [rs.root_repr for rs in d.ranking]
    assert all("drop_blade" not in r for r in reprs)             # unreachable, dropped
    assert any("iron_helm" in r for r in reprs)                  # reachable craftable kept
```

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -k "producible or reachable or unproducible or unreachable" -q`
Expected: FAIL — `_producible`/`is_reachable` missing; `actionable_step`/`decide` don't filter.

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/tiers/strategy.py`, add helpers (after `instrumental_skills`):

```python
def _producible(code: str, game_data: GameData) -> bool:
    """True when the item can be made by known means: craftable (has a recipe)
    or gatherable (some resource drops it). Buying / monster-drops are not
    modelled yet, so such items read as not-producible."""
    return (game_data.crafting_recipe(code) is not None
            or code in game_data._resource_drops.values())


def is_reachable(root: MetaGoal, state: WorldState, game_data: GameData,
                 path: frozenset[MetaGoal] = frozenset()) -> bool:
    """True when `root`'s entire prerequisite chain bottoms out in obtainable
    leaves. Cycle-safe (a node on the current path can't bottom out)."""
    if root.is_satisfied(state, game_data):
        return True
    if root in path:
        return False
    if isinstance(root, ReachSkillLevel):
        return True  # grinding the skill is always an available action
    prereqs = prerequisites(root, state, game_data)
    if isinstance(root, ObtainItem) and not prereqs:
        return _producible(root.code, game_data)
    sub_path = path | {root}
    return all(is_reachable(p, state, game_data, sub_path) for p in prereqs)
```

Guard `actionable_step`'s base case (the `if not unmet:` block):

```python
        if not unmet:
            if isinstance(node, ObtainItem) and not _producible(node.code, game_data):
                return None
            return node
```

Filter `decide`'s candidate loop — add the reachability check after the
satisfied skip:

```python
        for root in objective_roots(self.objective):
            if root.is_satisfied(state, game_data):
                continue
            if not is_reachable(root, state, game_data):
                continue
            step = actionable_step(root, state, game_data)
            if step is None:
                continue
            ...
```

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_ai/test_tiers_strategy.py -q`
Expected: PASS (new + existing).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/strategy.py tests/test_ai/test_tiers_strategy.py
git commit -m "feat(ai): exclude unreachable roots (full-closure obtainability)"
```

---

## Task 2: Full verification

- [ ] **Step 1: Full suite + lint + coverage**

Run: `uv run pytest -q` → all pass, 0 skipped.
Run: `uv run pytest tests/test_ai -q --cov=artifactsmmo_cli.ai.tiers.strategy --cov-report=term-missing`
→ `strategy.py` 100% (add a test for any missed branch).
Run: `uv run ruff check src/artifactsmmo_cli/ai/tiers tests/test_ai/test_tiers_strategy.py` → clean.
Run: `uv run mypy src/artifactsmmo_cli/ai/tiers` → no errors.

- [ ] **Step 2: Commit any fixups**

```bash
git add -A && git commit -m "test(ai): close coverage/lint gaps for P3a.2 reachability"
```

---

## Self-review notes
- **Spec coverage:** `_producible` craftable/gatherable/unknown (T1);
  `is_reachable` gatherable/craftable-chain/unproducible/blocked-material/skill/
  char-capable/char-underequipped/satisfied/cycle (T1); `actionable_step` guard
  (T1); `decide` excludes unreachable gear, keeps craftable (T1). All mapped.
- **No behavior change:** still shadow-only; only `decide`/`actionable_step`
  consumed by `_emit_trace`.
- **Cycle safety:** `is_reachable` uses an immutable `path` (`path | {root}`),
  so sibling branches don't poison each other (diamonds OK) and cycles return
  False.
- **Type consistency:** `_producible(str, GameData) -> bool`;
  `is_reachable(MetaGoal, WorldState, GameData, frozenset) -> bool`; integrates
  with existing `prerequisites`/`actionable_step`/`decide` signatures.
