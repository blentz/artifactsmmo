# Gear Sub-project A — Generic Gear Taxonomy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two hardcoded gear-type sets (`_ARMOR_TYPES`, `_COMBAT_GEAR_TYPES`) with effect-derived classification computed from live item data, add a fail-loud item-effect coverage guard, and prove the classification core in Lean under the project's full formal lockstep.

**Architecture:** A pure proved core (`gear_taxonomy_core.py`) classifies items from plain data; a leaf wrapper module (`gear_taxonomy.py`) owns the schema-derived type/slot map and adapts `ItemStats`; `GameData` exposes four memoized properties built once at load; two consumer sites switch from local constants to the GameData properties. v8 player-side rune abilities are carved+deferred, not modeled here.

**Tech Stack:** Python 3.13 (`uv run`), Lean 4 (`formal/`), Hypothesis (differential), `formal/diff/mutate.py` (mutation), pytest (`--cov-fail-under=100`).

## Global Constraints

- `uv` at `~/.local/bin/uv`; ALWAYS prefix Python with `uv run` (e.g. `uv run pytest`, `uv run mypy`). Run `git checkout uv.lock` before committing if `uv run` dirtied it.
- DO NOT use inline imports; imports at top of file. DO NOT use `if TYPE_CHECKING`. DO NOT use `...` imports. NEVER catch `Exception`.
- ONE behavioral class per file (pure data/enum groups may share). Pure proved cores live in `*_core.py`.
- Use only API data or fail with an error — no invented defaults. Multiple levels of error handling is a bug.
- Tests: 0 errors, 0 warnings, 0 skipped, 100% coverage. All tests in `tests/`. Use the real test suite + real fixtures; never mock the unit under test.
- Formal lockstep per component: computable Lean `def` + role theorems (∀ inputs) + `Contracts.lean` exact-statement pins + `Manifest.lean` roster + differential (Python≡oracle on the HAND def) + mutation (every drop-term mutant killed). No `sorry`/`native_decide`/custom axioms; axiom lint allows only `{propext, Classical.choice, Quot.sound}`.
- NEVER run `formal/gate.sh` / `mutate.py` concurrently with anything importing `src` (including a live `artifactsmmo play`). `git diff src` after every mutation run.
- Branch: `feat/gear-loadout-architecture` (already checked out; = `main` + 2 spec commits).
- Spec: `docs/superpowers/specs/2026-06-28-gear-taxonomy-design.md`.

**Classification definitions (verbatim — use these exact field/code sets):**
- `is_combat_bearing(stats)` ORs these **durable combat** `ItemStats` fields (truthy = nonzero/non-empty): `attack`, `resistance`, `hp_bonus`, `dmg`, `dmg_elements`, `critical_strike`, `initiative`, `lifesteal`.
- Consumable-family **raw** effect codes: exact `{heal, restore, splash_restore, antipoison, teleport, boost_hp}` + prefixes `{boost_dmg_, boost_res_}`.
- `combat_gear_types` = `{ type : (∃ item of type with is_combat_bearing) ∧ ¬(∃ item of type that is consumable) }`.
- `defensive_gear_types` = `combat_gear_types − {"weapon"}`.
- Deferred rune abilities (carve set): `{burn, enchanted_mirror, frenzy, greed, guard, healing, healing_aura, shell, vampiric_strike}`.

**Live-audit ground truth (must hold against real v8 data):**
```
equippable      : amulet artifact bag body_armor boots helmet leg_armor ring rune shield utility weapon
combat_gear     : amulet artifact body_armor boots helmet leg_armor ring rune shield weapon
non-combat      : bag (no combat stat), utility (consumable type)
```

---

### Task 1: Rune-ability carve + item-effect coverage guard

Adds the deferred-rune carve set and the fail-loud `else` to the item-effect ingestion so an unknown effect code on an **equippable** item raises instead of being silently dropped. Mirrors the monster guard at `game_data.py:1567`.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (carve constant near line 68 beside `_MONSTER_EFFECT_CARVEOUTS`; `else` branch after the `threat` elif at line ~1271; the loop variable is `item`, the effect is `effect`).
- Test: `tests/ai/test_game_data_item_effect_guard.py` (new).

**Interfaces:**
- Consumes: `ITEM_TYPE_TO_SLOTS` (currently `actions/equip.py`; Task 3 moves it to `gear_taxonomy.py` and re-exports — until then import from `actions.equip`). For Task 1, derive equippable types locally from the same module.
- Produces: module constant `_DEFERRED_RUNE_ABILITIES: frozenset[str]`; an item-effect guard that raises `GameDataCoverageError` naming the item + code.

- [ ] **Step 1: Write the failing tests**

```python
# tests/ai/test_game_data_item_effect_guard.py
"""The item-effect coverage guard fails loudly on an unknown equippable effect."""

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.game_data_error import GameDataCoverageError


def _item(code, type_, effect_codes):
    """Minimal stand-in matching the attrs ItemSchema surface _build_items reads."""
    class _Eff:
        def __init__(self, c):
            self.code = c
            self.value = 1
    class _Item:
        pass
    it = _Item()
    it.code = code
    it.type_ = type_
    it.subtype = ""
    it.level = 1
    it.effects = [_Eff(c) for c in effect_codes]
    it.craft = None
    it.conditions = []
    it.tradeable = True
    return it


def test_unknown_equippable_effect_raises():
    gd = GameData()
    with pytest.raises(GameDataCoverageError) as exc:
        gd._build_items([_item("mystery_ring", "ring", ["totally_new_code"])])
    assert "mystery_ring" in str(exc.value)
    assert "totally_new_code" in str(exc.value)


def test_deferred_rune_ability_is_carved_not_fatal():
    gd = GameData()
    # burn/frenzy/etc. are known-deferred — must NOT raise.
    gd._build_items([_item("burn_rune", "rune", ["burn", "lifesteal"])])
    assert gd.item_stats("burn_rune") is not None


def test_unknown_effect_on_nonequippable_is_ignored():
    gd = GameData()
    # resources/consumables outside the equippable types keep today's silent-drop.
    gd._build_items([_item("weird_resource", "resource", ["totally_new_code"])])
    assert gd.item_stats("weird_resource") is not None
```

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/ai/test_game_data_item_effect_guard.py -v`
Expected: FAIL — `test_unknown_equippable_effect_raises` does not raise (code silently dropped today).

- [ ] **Step 3: Add the carve constant**

Beside `_MONSTER_EFFECT_CARVEOUTS` (game_data.py ~line 68):

```python
# v8 player-side rune abilities (effect codes carried by `rune` items). Modeling
# them in predict_win is deferred to the "Player rune abilities" sub-project; they
# are CARVED here (not silently dropped) so the equippable-effect coverage guard
# stays meaningful. A `rune` still classifies as combat_gear via `lifesteal`; until
# the follow-on lands, a rune carrying ONLY a deferred ability scores ~0 and is not
# equipped. See docs/superpowers/specs/2026-06-28-gear-taxonomy-design.md.
_DEFERRED_RUNE_ABILITIES: frozenset[str] = frozenset({
    "burn", "enchanted_mirror", "frenzy", "greed", "guard",
    "healing", "healing_aura", "shell", "vampiric_strike",
})
```

- [ ] **Step 4: Add the guard `else` branch**

Immediately after the `elif effect.code == "threat":` block (which ends in `pass`) in `_build_items`, add a final `else`. Compute the item's type robustly and the equippable-type set from `ITEM_TYPE_TO_SLOTS`:

```python
                    elif effect.code in _DEFERRED_RUNE_ABILITIES:
                        # Carved: modeling deferred to the Player-rune-abilities
                        # sub-project. Covered so the guard below stays meaningful.
                        pass
                    else:
                        item_type = getattr(item.type_, "value", item.type_)
                        if item_type in ITEM_TYPE_TO_SLOTS:
                            # Parser-coverage guard (equippable only): an unmapped
                            # effect on a wearable item would silently zero its gear
                            # score / mis-classify its type. Fail loudly so it gets
                            # modeled or carved before the bot acts on it. Mirrors the
                            # monster guard (_MONSTER_EFFECT_CARVEOUTS).
                            raise GameDataCoverageError(
                                f"equippable item {item.code!r} ({item_type}) carries "
                                f"unmapped effect code {effect.code!r}: model it or add "
                                "a documented entry to _DEFERRED_RUNE_ABILITIES")
```

Add the import at the top of `game_data.py` (top-level, no cycle — `actions.equip` already imports `GameData`, so guard against the cycle by importing the constant lazily-safe module; if an ImportError surfaces, this is the signal to do Task 3's leaf-module move first):

```python
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
```

> NOTE: `actions/equip.py` imports `GameData` from `game_data`, so this top-level import **will** cycle. Resolve by doing the leaf-module extraction (Task 3, Step A) FIRST if the import fails, then importing `ITEM_TYPE_TO_SLOTS` from `gear_taxonomy`. If you hit the cycle, jump to Task 3 Step A, land it, then return here.

- [ ] **Step 5: Run tests to verify pass**

Run: `~/.local/bin/uv run pytest tests/ai/test_game_data_item_effect_guard.py -v`
Expected: PASS (3/3).

- [ ] **Step 6: Verify live boot still works (guard not over-firing)**

Run: `~/.local/bin/uv run python -c "from artifactsmmo_cli.client_manager import ClientManager; from artifactsmmo_cli.ai.game_data import GameData; from artifactsmmo_cli.config import Config; cm=ClientManager(); cm.initialize(Config.from_token_file()); GameData.load(cm.client, force_refresh=True); print('LOAD OK')"`
Expected: `LOAD OK` (the 9 rune codes are carved; nothing else unmodeled). Then `git checkout uv.lock`.

- [ ] **Step 7: Commit**

```bash
git checkout uv.lock 2>/dev/null; git add src/artifactsmmo_cli/ai/game_data.py tests/ai/test_game_data_item_effect_guard.py
git commit -m "feat(gear): item-effect coverage guard + deferred-rune carve"
```

---

### Task 2: Pure classification core + Lean lockstep

The proved heart of A: `is_combat_bearing`, `is_consumable`, and `combat_gear_types` as pure functions over plain data, mirrored by `Formal/GearTaxonomy.lean` with four role theorems, pinned in `Contracts.lean`/`Manifest.lean`, extracted, and bridged.

**Files:**
- Create: `src/artifactsmmo_cli/ai/gear_taxonomy_core.py`
- Create: `formal/Formal/GearTaxonomy.lean`
- Modify: `formal/Formal/Manifest.lean` (add the 4 role-theorem names), `formal/Formal/Contracts.lean` (exact-statement pins), `formal/Oracle.lean` (numbered dispatch handler for the core), `scripts/extract_lean.py` (register the core for extraction if it auto-discovers; else add `formal/Formal/Extracted/GearTaxonomy.lean`).
- Test: `tests/ai/test_gear_taxonomy_core.py`

**Interfaces:**
- Produces (Python, plain-data signatures):
  - `is_combat_bearing(attack: Mapping[str,int], resistance: Mapping[str,int], hp_bonus: int, dmg: int, dmg_elements: Mapping[str,int], critical_strike: int, initiative: int, lifesteal: int) -> bool`
  - `is_consumable(effect_codes: Sequence[str]) -> bool`
  - `combat_gear_types(rows: Sequence[tuple[str, bool, bool]]) -> frozenset[str]` where each row is `(type, combat_bearing, consumable)`.
- Produces (Lean, in `Formal.GearTaxonomy`): `isCombatBearing`, `isConsumable`, `combatGearTypes`, and theorems `combatGear_mem_iff`, `combatGear_combat_mono`, `combatGear_consumable_anti`, `combatGear_subset_equippable`.

- [ ] **Step 1: Write the failing core tests**

```python
# tests/ai/test_gear_taxonomy_core.py
from artifactsmmo_cli.ai.gear_taxonomy_core import (
    combat_gear_types, is_combat_bearing, is_consumable,
)


def test_combat_bearing_each_field_independently():
    base = dict(attack={}, resistance={}, hp_bonus=0, dmg=0, dmg_elements={},
                critical_strike=0, initiative=0, lifesteal=0)
    assert not is_combat_bearing(**base)
    for field, val in [("attack", {"fire": 1}), ("resistance", {"air": 1}),
                       ("hp_bonus", 1), ("dmg", 1), ("dmg_elements", {"earth": 1}),
                       ("critical_strike", 1), ("initiative", 1), ("lifesteal", 1)]:
        assert is_combat_bearing(**{**base, field: val}), field


def test_is_consumable_families():
    assert is_consumable(["restore"])
    assert is_consumable(["boost_dmg_fire"])
    assert is_consumable(["boost_res_air"])
    assert is_consumable(["boost_hp"])
    assert is_consumable(["antipoison"])
    assert is_consumable(["teleport"])
    assert not is_consumable(["res_fire"])      # durable armor res, not consumable
    assert not is_consumable([])


def test_combat_gear_excludes_consumable_and_noncombat_types():
    rows = [
        ("weapon", True, False),
        ("ring", True, False),
        ("utility", True, True),    # combat-bearing boost potion BUT consumable
        ("bag", False, False),      # not combat-bearing
    ]
    assert combat_gear_types(rows) == frozenset({"weapon", "ring"})


def test_combat_gear_any_consumable_item_carves_the_type():
    # A type with a durable combat item AND a consumable item is still carved.
    rows = [("utility", True, False), ("utility", False, True)]
    assert combat_gear_types(rows) == frozenset()
```

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/ai/test_gear_taxonomy_core.py -v`
Expected: FAIL — `ModuleNotFoundError: gear_taxonomy_core`.

- [ ] **Step 3: Write the pure core**

```python
# src/artifactsmmo_cli/ai/gear_taxonomy_core.py
"""PURE proved core for gear taxonomy (extracted, mirrors Formal/GearTaxonomy.lean).

No GameData/IO — operates on plain data so the differential harness can call it
directly. See docs/superpowers/specs/2026-06-28-gear-taxonomy-design.md.
"""

from collections.abc import Mapping, Sequence

# Raw consumable-family effect codes (exact + prefixes). The boost_* family are
# temporary fight buffs (the consumable axis), distinct from durable gear stats.
_CONSUMABLE_EXACT = frozenset({"heal", "restore", "splash_restore", "antipoison",
                               "teleport", "boost_hp"})
_CONSUMABLE_PREFIX = ("boost_dmg_", "boost_res_")


def is_combat_bearing(attack: Mapping[str, int], resistance: Mapping[str, int],
                      hp_bonus: int, dmg: int, dmg_elements: Mapping[str, int],
                      critical_strike: int, initiative: int,
                      lifesteal: int) -> bool:
    """True iff the item carries any DURABLE combat stat (the OR of gear combat
    fields). Mirrors Formal.GearTaxonomy.isCombatBearing."""
    return bool(attack or resistance or hp_bonus or dmg or dmg_elements
                or critical_strike or initiative or lifesteal)


def is_consumable(effect_codes: Sequence[str]) -> bool:
    """True iff any raw effect code is in the consumable family (temporary
    buffs / restores). Mirrors Formal.GearTaxonomy.isConsumable."""
    for code in effect_codes:
        if code in _CONSUMABLE_EXACT or code.startswith(_CONSUMABLE_PREFIX):
            return True
    return False


def combat_gear_types(rows: Sequence[tuple[str, bool, bool]]) -> frozenset[str]:
    """Types that are durable combat gear: have a combat-bearing item AND no
    consumable item. Each row is (type, combat_bearing, consumable). Mirrors
    Formal.GearTaxonomy.combatGearTypes."""
    combat: set[str] = set()
    consumable: set[str] = set()
    for type_, is_combat, is_cons in rows:
        if is_combat:
            combat.add(type_)
        if is_cons:
            consumable.add(type_)
    return frozenset(combat - consumable)
```

- [ ] **Step 4: Run core tests to verify pass**

Run: `~/.local/bin/uv run pytest tests/ai/test_gear_taxonomy_core.py -v`
Expected: PASS (4/4).

- [ ] **Step 5: Write the Lean def + theorem statements**

Create `formal/Formal/GearTaxonomy.lean`. Model a row as `(String × Bool × Bool)` (type, combatBearing, consumable). Use the project's existing `List`-based style (see `Formal/RecipeClosure.lean` for fold conventions). Theorem statements (prove with `lean4:prove`):

```lean
namespace Formal.GearTaxonomy

structure Row where
  type : String
  combatBearing : Bool
  consumable : Bool

def combatGearTypes (rows : List Row) : List String :=
  let combat := rows.filterMap (fun r => if r.combatBearing then some r.type else none)
  let cons := rows.filterMap (fun r => if r.consumable then some r.type else none)
  combat.filter (fun t => ¬ cons.contains t) |>.dedup

-- (a) membership characterization
theorem combatGear_mem_iff (rows : List Row) (t : String) :
    t ∈ combatGearTypes rows ↔
      (∃ r ∈ rows, r.type = t ∧ r.combatBearing = true) ∧
      ¬ (∃ r ∈ rows, r.type = t ∧ r.consumable = true) := by
  sorry

-- (b) combat-monotonicity: flipping a row's combatBearing false→true never removes a type
theorem combatGear_combat_mono (rows rows' : List Row)
    (h : ∀ t, (∃ r ∈ rows, r.type = t ∧ r.combatBearing = true) →
              (∃ r ∈ rows', r.type = t ∧ r.combatBearing = true))
    (hcons : ∀ t, (∃ r ∈ rows', r.type = t ∧ r.consumable = true) →
                  (∃ r ∈ rows, r.type = t ∧ r.consumable = true)) :
    ∀ t, t ∈ combatGearTypes rows → t ∈ combatGearTypes rows' := by
  sorry

-- (c) consumable-antitonicity: adding a consumable item can only remove a type
theorem combatGear_consumable_anti (rows : List Row) (t : String)
    (h : t ∈ combatGearTypes rows) :
    ¬ (∃ r ∈ rows, r.type = t ∧ r.consumable = true) := by
  sorry

-- (d) subset of equippable: every classified type appears as some row's type
theorem combatGear_subset_equippable (rows : List Row) (t : String)
    (h : t ∈ combatGearTypes rows) : ∃ r ∈ rows, r.type = t := by
  sorry

end Formal.GearTaxonomy
```

> Use `superpowers:formal-development` discipline + `lean4:prove` to fill the four `sorry`s. Keep the `def` computable (it runs in the oracle). Do NOT weaken a statement to make it compile — if a statement is wrong, fix the `def`, not the theorem.

- [ ] **Step 6: Prove the theorems**

Run: `cd formal && lake build Formal.GearTaxonomy`
Expected: builds with no `sorry`. Verify axioms:
`cd formal && lake env lean --run scripts/print_axioms.lean` (or the gate's axiom-lint step) lists only `{propext, Classical.choice, Quot.sound}` for the 4 theorems.

- [ ] **Step 7: Pin statements + roster**

Add to `formal/Formal/Manifest.lean` the 4 theorem names (follow the file's existing `example : True := by trivial -- <name>` or import-and-reference pattern already used). Add to `formal/Formal/Contracts.lean` the exact-statement pins:

```lean
example : (∀ (rows : List Formal.GearTaxonomy.Row) (t : String),
    t ∈ Formal.GearTaxonomy.combatGearTypes rows ↔
      (∃ r ∈ rows, r.type = t ∧ r.combatBearing = true) ∧
      ¬ (∃ r ∈ rows, r.type = t ∧ r.consumable = true)) :=
  @Formal.GearTaxonomy.combatGear_mem_iff
-- (repeat for combatGear_combat_mono, combatGear_consumable_anti, combatGear_subset_equippable)
```

- [ ] **Step 8: Build the full formal package**

Run: `cd formal && lake build`
Expected: `Build completed successfully`.

- [ ] **Step 9: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add src/artifactsmmo_cli/ai/gear_taxonomy_core.py tests/ai/test_gear_taxonomy_core.py formal/Formal/GearTaxonomy.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean
git commit -m "feat(gear): proved gear-taxonomy core + Lean lockstep (4 role theorems)"
```

---

### Task 3: GameData properties + leaf wrapper module

Moves the schema-derived type/slot map into a leaf module (breaking the `game_data → equip` cycle), adds the `ItemStats`→core adapters, and exposes four memoized `GameData` properties built once at load.

**Files:**
- Create: `src/artifactsmmo_cli/ai/gear_taxonomy.py` (leaf: imports `attrs`, `CharacterSchema`, `item_catalog.ItemStats`, `gear_taxonomy_core` — NOT `game_data`).
- Modify: `src/artifactsmmo_cli/ai/actions/equip.py` (re-export `ITEM_TYPE_TO_SLOTS`/`ITEM_TYPE_TO_SLOT` from `gear_taxonomy`).
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (import `ITEM_TYPE_TO_SLOTS` from `gear_taxonomy`; add 4 memoized properties; record raw effect codes per item during `_build_items` for consumable detection).
- Test: `tests/ai/test_gear_taxonomy.py`, extend `tests/ai/test_game_data*.py` as needed.

**Interfaces:**
- Consumes: `gear_taxonomy_core.{is_combat_bearing, is_consumable, combat_gear_types}` (Task 2).
- Produces:
  - `gear_taxonomy.ITEM_TYPE_TO_SLOTS`, `ITEM_TYPE_TO_SLOT`, `_derive_type_to_slots` (moved from equip.py).
  - `gear_taxonomy.stats_is_combat_bearing(stats: ItemStats) -> bool` (adapts ItemStats fields into the core).
  - `GameData.equippable_types: frozenset[str]`, `GameData.consumable_types: frozenset[str]`, `GameData.combat_gear_types: frozenset[str]`, `GameData.defensive_gear_types: frozenset[str]` (all memoized properties).

- [ ] **Step A (do FIRST if Task 1 hit the import cycle): move the slot map to the leaf**

Create `src/artifactsmmo_cli/ai/gear_taxonomy.py`, moving `_SLOT_SUFFIX`, `_item_type_of_slot`, `_derive_type_to_slots`, `ITEM_TYPE_TO_SLOTS`, `ITEM_TYPE_TO_SLOT` verbatim from `actions/equip.py`. Then in `actions/equip.py` replace those definitions with:

```python
from artifactsmmo_cli.ai.gear_taxonomy import (
    ITEM_TYPE_TO_SLOT, ITEM_TYPE_TO_SLOTS, _derive_type_to_slots,
)
```

Run: `~/.local/bin/uv run python -c "import artifactsmmo_cli.ai.game_data; import artifactsmmo_cli.ai.actions.equip; print('NO CYCLE')"`
Expected: `NO CYCLE`.

- [ ] **Step 1: Write the failing wrapper + property tests**

```python
# tests/ai/test_gear_taxonomy.py
from artifactsmmo_cli.ai.gear_taxonomy import ITEM_TYPE_TO_SLOTS, stats_is_combat_bearing
from artifactsmmo_cli.ai.item_catalog import ItemStats


def test_stats_is_combat_bearing_reads_itemstats():
    plain = ItemStats(code="x", level=1, type_="ring")
    assert not stats_is_combat_bearing(plain)
    plain.hp_bonus = 10
    assert stats_is_combat_bearing(plain)


def test_equippable_types_are_slot_map_keys():
    assert "weapon" in ITEM_TYPE_TO_SLOTS and "rune" in ITEM_TYPE_TO_SLOTS
```

```python
# tests/ai/test_game_data_gear_taxonomy.py
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats


def _gd_with(items):
    gd = GameData()
    for s in items:
        gd._item_stats[s.code] = s
    return gd


def test_properties_classify_durable_vs_consumable(monkeypatch):
    weapon = ItemStats(code="sword", level=1, type_="weapon", attack={"fire": 5})
    ring = ItemStats(code="ring1", level=1, type_="ring", hp_bonus=3)
    potion = ItemStats(code="boostpot", level=1, type_="utility", dmg_elements={"fire": 5})
    bag = ItemStats(code="bag1", level=1, type_="bag", inventory_space=10)
    gd = _gd_with([weapon, ring, potion, bag])
    # consumable_types is built from raw effect codes; inject for the utility potion.
    gd._consumable_effect_codes = {"boostpot": ["boost_dmg_fire"]}
    assert "weapon" in gd.combat_gear_types
    assert "ring" in gd.combat_gear_types
    assert "utility" not in gd.combat_gear_types     # consumable
    assert "bag" not in gd.combat_gear_types          # not combat-bearing
    assert "weapon" not in gd.defensive_gear_types
    assert "ring" in gd.defensive_gear_types
```

> The exact memoization/seam (`_consumable_effect_codes`) is finalized in Step 3; adjust the test's injection to match the field you choose, keeping the asserted classifications identical.

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/ai/test_gear_taxonomy.py tests/ai/test_game_data_gear_taxonomy.py -v`
Expected: FAIL (missing `stats_is_combat_bearing` / properties).

- [ ] **Step 3: Implement the wrapper adapter + GameData properties**

In `gear_taxonomy.py`:

```python
from artifactsmmo_cli.ai.gear_taxonomy_core import is_combat_bearing
from artifactsmmo_cli.ai.item_catalog import ItemStats


def stats_is_combat_bearing(stats: ItemStats) -> bool:
    """Adapt ItemStats fields into the pure core's combat-bearing predicate."""
    return is_combat_bearing(
        attack=stats.attack, resistance=stats.resistance, hp_bonus=stats.hp_bonus,
        dmg=stats.dmg, dmg_elements=stats.dmg_elements,
        critical_strike=stats.critical_strike, initiative=stats.initiative,
        lifesteal=stats.lifesteal)
```

In `game_data.py`: during `_build_items`, accumulate raw effect codes per item into a dict `self._consumable_effect_codes[item.code] = [<raw codes>]` (collect inside the existing `for effect in item.effects` loop, before the elif-chain). Add the four memoized properties (mirror the `craft_yields` property style at line 858-870):

```python
@property
def equippable_types(self) -> frozenset[str]:
    return frozenset(ITEM_TYPE_TO_SLOTS)

@property
def consumable_types(self) -> frozenset[str]:
    return frozenset(
        self.item_stats(code).type_
        for code, codes in self._consumable_effect_codes.items()
        if self.item_stats(code) is not None and is_consumable(codes))

@property
def combat_gear_types(self) -> frozenset[str]:
    rows = [
        (s.type_, stats_is_combat_bearing(s), s.type_ in self.consumable_types)
        for s in self.all_item_stats.values()
        if s.type_ in self.equippable_types
    ]
    return combat_gear_types(rows)

@property
def defensive_gear_types(self) -> frozenset[str]:
    return self.combat_gear_types - frozenset({"weapon"})
```

Add top-level imports to `game_data.py`: `from artifactsmmo_cli.ai.gear_taxonomy import ITEM_TYPE_TO_SLOTS, stats_is_combat_bearing`, `from artifactsmmo_cli.ai.gear_taxonomy_core import combat_gear_types, is_consumable`. Initialize `self._consumable_effect_codes: dict[str, list[str]] = {}` in `_build_items` setup (and as an instance field default).

> If these properties are hot, memoize with `functools.cached_property` consistent with how `GameData` caches elsewhere; otherwise plain `@property` is acceptable since callers read them per-cycle on static data. Match the surrounding convention.

- [ ] **Step 4: Run to verify pass + live check**

Run: `~/.local/bin/uv run pytest tests/ai/test_gear_taxonomy.py tests/ai/test_game_data_gear_taxonomy.py -v`
Expected: PASS. Then live: load real data and assert the ground-truth sets:

`~/.local/bin/uv run python -c "from artifactsmmo_cli.client_manager import ClientManager; from artifactsmmo_cli.ai.game_data import GameData; from artifactsmmo_cli.config import Config; cm=ClientManager(); cm.initialize(Config.from_token_file()); gd=GameData.load(cm.client, force_refresh=True); print('combat', sorted(gd.combat_gear_types)); print('def', sorted(gd.defensive_gear_types))"`
Expected `combat` = `['amulet','artifact','body_armor','boots','helmet','leg_armor','ring','rune','shield','weapon']`; `def` = same minus `weapon`. Then `git checkout uv.lock`.

- [ ] **Step 5: mypy + commit**

Run: `~/.local/bin/uv run mypy --strict src/artifactsmmo_cli/ai/gear_taxonomy.py src/artifactsmmo_cli/ai/game_data.py src/artifactsmmo_cli/ai/actions/equip.py`
Expected: clean.

```bash
git checkout uv.lock 2>/dev/null
git add src/artifactsmmo_cli/ai/gear_taxonomy.py src/artifactsmmo_cli/ai/actions/equip.py src/artifactsmmo_cli/ai/game_data.py tests/ai/test_gear_taxonomy.py tests/ai/test_game_data_gear_taxonomy.py
git commit -m "feat(gear): GameData gear-taxonomy properties + leaf wrapper (breaks cycle)"
```

---

### Task 4: Consumer migration

Switch the two hardcoded sets to the GameData properties. This is where the approved reclassification (ring/amulet/rune/artifact IN) takes effect.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/inventory_caps.py` (delete `_ARMOR_TYPES` line 46; rewrite the `per_monster` predicate at line ~302).
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (delete `_COMBAT_GEAR_TYPES`/`_COMBAT_GEAR_SLOTS` lines 152-157; derive `_COMBAT_GEAR_SLOTS` from `game_data.combat_gear_types` at the call sites 409, 422).
- Test: `tests/ai/test_inventory_caps*.py`, `tests/ai/tiers/test_strategy*.py` (extend with reclassification regression tests).

**Interfaces:**
- Consumes: `GameData.combat_gear_types`, `GameData.defensive_gear_types` (Task 3).

- [ ] **Step 1: Write reclassification regression tests**

```python
# tests/ai/test_gear_reclassification.py
"""Approved behavior changes: rune/artifact join combat gear; the dominance gate
treats ring/amulet/rune/artifact as defensive (per-monster) gear."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats


def _gd(items, consumable_codes=None):
    gd = GameData()
    for s in items:
        gd._item_stats[s.code] = s
    gd._consumable_effect_codes = consumable_codes or {}
    return gd


def test_rune_and_artifact_are_combat_gear():
    rune = ItemStats(code="vampiric_rune", level=1, type_="rune", lifesteal=10)
    artifact = ItemStats(code="novice_guide", level=1, type_="artifact", hp_bonus=25)
    gd = _gd([rune, artifact])
    assert "rune" in gd.combat_gear_types
    assert "artifact" in gd.combat_gear_types


def test_ring_amulet_are_defensive_for_dominance_gate():
    ring = ItemStats(code="r", level=1, type_="ring", hp_bonus=5)
    amulet = ItemStats(code="a", level=1, type_="amulet", resistance={"fire": 10})
    gd = _gd([ring, amulet])
    assert {"ring", "amulet"} <= gd.defensive_gear_types
```

- [ ] **Step 2: Migrate `inventory_caps.py`**

Delete line 46 (`_ARMOR_TYPES = ...`). At line ~302 the function already has `game_data` and `state`. Replace:

```python
    per_monster = bool(monsters) and stats.type_ in game_data.combat_gear_types
```

(weapon ∈ `combat_gear_types`, so the old `type_ == "weapon" or type_ in _ARMOR_TYPES` is subsumed; `_score_vector` still branches weapon→offense / else→defense.)

- [ ] **Step 3: Migrate `strategy.py`**

Delete `_COMBAT_GEAR_TYPES` and `_COMBAT_GEAR_SLOTS` (lines 152-157). At the two call sites, derive the slot set from `game_data.combat_gear_types` (the methods at 392 `_base_prior` and 414 `_has_empty_armor_slot` both receive `game_data`):

```python
        combat_gear_slots = frozenset(
            slot for t in game_data.combat_gear_types
            for slot in ITEM_TYPE_TO_SLOTS.get(t, []))
```

Use `combat_gear_slots` where `_COMBAT_GEAR_SLOTS` was used (409, 422). If both methods need it, add a small private helper `self._combat_gear_slots(game_data)` to avoid duplication (DRY).

- [ ] **Step 4: Run the affected suites + full suite**

Run: `~/.local/bin/uv run pytest tests/ai/test_gear_reclassification.py tests/ai/test_inventory_caps.py tests/ai/tiers/ -v`
Expected: PASS. Fix any test that encoded the OLD ring/amulet-scalar or rune/artifact-utility classification — update it to the new behavior and add a comment citing this reclassification (these are the documented intentional changes).

- [ ] **Step 5: mypy + commit**

```bash
git checkout uv.lock 2>/dev/null
~/.local/bin/uv run mypy --strict src/artifactsmmo_cli/ai/inventory_caps.py src/artifactsmmo_cli/ai/tiers/strategy.py
git add src/artifactsmmo_cli/ai/inventory_caps.py src/artifactsmmo_cli/ai/tiers/strategy.py tests/ai/test_gear_reclassification.py
git commit -m "feat(gear): migrate consumers to effect-derived combat_gear (reclassify rune/artifact IN)"
```

---

### Task 5: Differential + mutation + live-audit + final gate

Binds the Python core to the Lean def over random inputs, gives the theorems teeth via mutation, and locks the live-data classification as a regression test.

**Files:**
- Create: `formal/diff/test_gear_taxonomy_diff.py` (Hypothesis differential against the oracle).
- Modify: `formal/Oracle.lean` (numbered handler evaluating `combatGearTypes`/`isCombatBearing`/`isConsumable` on JSON input — follow the existing `g NN` dispatch).
- Modify: `formal/diff/mutate.py` (register drop-term mutants for each `is_combat_bearing` field + the consumable families).
- Test: `tests/ai/test_gear_taxonomy_live_audit.py` (asserts the ground-truth sets on real v8 data — gated like other live-data tests in the suite).

**Interfaces:**
- Consumes: the core (Task 2), the oracle executable, `GameData` properties (Task 3).

- [ ] **Step 1: Add the oracle handler**

In `formal/Oracle.lean`, add a numbered dispatch case that parses `{rows: [[type, combatBearing, consumable]]}` and emits `combatGearTypes`, plus cases for `isCombatBearing`/`isConsumable` on a single record. Mirror the JSON parse/print helpers used by the nearest existing handler (e.g. RecipeClosure's `parseYieldFn`). Build: `cd formal && lake build Oracle && lake exe oracle <<< '{"op":"combat_gear","rows":[["weapon",true,false],["utility",true,true]]}'` → `["weapon"]`.

- [ ] **Step 2: Write the differential harness**

```python
# formal/diff/test_gear_taxonomy_diff.py
"""Python gear-taxonomy core ≡ Lean oracle over random catalogs."""

from hypothesis import given, strategies as st

from artifactsmmo_cli.ai.gear_taxonomy_core import combat_gear_types
from formal.diff.oracle_client import run_oracle   # match the existing helper import


types = st.sampled_from(["weapon", "ring", "amulet", "rune", "artifact",
                         "utility", "bag", "helmet"])
rows = st.lists(st.tuples(types, st.booleans(), st.booleans()), max_size=30)


@given(rows)
def test_combat_gear_matches_oracle(catalog):
    py = sorted(combat_gear_types(catalog))
    oracle = sorted(run_oracle({"op": "combat_gear",
                                "rows": [list(r) for r in catalog]}))
    assert py == oracle
```

> Do NOT use `unique=True` on the row strategy — duplicate-type rows are the realistic case (many items per type) and exercise the dedup + the any-consumable carve. Match `oracle_client` to the actual helper name/signature used by the sibling diff tests.

- [ ] **Step 3: Run the differential**

Run: `cd formal && ~/.local/bin/uv run pytest diff/test_gear_taxonomy_diff.py -v`
Expected: PASS (Python ≡ oracle).

- [ ] **Step 4: Register + run mutation**

In `formal/diff/mutate.py`, add drop-term mutants for `gear_taxonomy_core.py`: each disjunct of `is_combat_bearing` (drop `attack`, `resistance`, `hp_bonus`, `dmg`, `dmg_elements`, `critical_strike`, `initiative`, `lifesteal`), each consumable family member, and the `combat - consumable` set difference (mutate to `combat`). Each mutant MUST be killed by the differential or a unit test.

Run: `cd formal && ~/.local/bin/uv run python diff/mutate.py --target gear_taxonomy_core` (match the runner's actual flag). Then `git diff src` to confirm sources are restored.
Expected: all mutants killed; `git diff src` empty.

- [ ] **Step 5: Write the live-audit regression test**

```python
# tests/ai/test_gear_taxonomy_live_audit.py
"""Locks the effect-derived classification against real v8 data."""

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.config import Config

EXPECTED_COMBAT = frozenset({
    "amulet", "artifact", "body_armor", "boots", "helmet", "leg_armor",
    "ring", "rune", "shield", "weapon"})


def test_live_combat_gear_classification():
    cm = ClientManager()
    cm.initialize(Config.from_token_file())
    gd = GameData.load(cm.client, force_refresh=True)
    assert gd.combat_gear_types == EXPECTED_COMBAT
    assert "utility" not in gd.combat_gear_types   # consumable carve
    assert "bag" not in gd.combat_gear_types        # not combat-bearing
    assert gd.defensive_gear_types == EXPECTED_COMBAT - frozenset({"weapon"})
```

> Gate this with the same marker/skip-without-TOKEN mechanism the existing live-data tests use (search `tests/` for `from_token_file` to match the pattern), so CI without a token stays green and coverage rules are respected.

- [ ] **Step 6: Full suite + full formal gate**

Run: `~/.local/bin/uv run pytest --cov-fail-under=100`
Expected: all pass, 100% coverage. Ensure `gear_taxonomy_core.py`/`gear_taxonomy.py` are fully covered (carve any genuinely-unreachable line only with a written justification).

Run (nothing else importing `src` running): `cd formal && ./gate.sh`
Expected: green — kernel build, no-sorry, axiom-lint (only standard axioms on the 4 theorems), manifest, contracts, differential, mutation. Then `git diff src` empty; `git checkout uv.lock`.

- [ ] **Step 7: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add formal/ tests/ai/test_gear_taxonomy_live_audit.py
git commit -m "test(gear): differential + mutation + live-audit lock for gear taxonomy"
```

---

## Final review (after all tasks)

Dispatch the whole-branch reviewer (`superpowers:requesting-code-review`) over `git merge-base main HEAD..HEAD`. Specific things to verify:
- The two hardcoded sets are gone; every former consumer reads the GameData properties.
- No import cycle (`game_data` ↔ `equip` via `gear_taxonomy` leaf).
- The coverage guard fires ONLY for equippable items and ONLY on neither-modeled-nor-carved codes; non-equippable unknown codes keep today's silent-drop.
- The 4 Lean theorems are statement-pinned in `Contracts.lean` and none was weakened to compile.
- Differential calls the live core (not an inlined formula); mutation kills every dropped combat field and the set-difference; no `unique=True` masking.
- Every intentional behavior change (ring/amulet → per-monster gate; rune/artifact → combat prior) has a test that documents it as intentional.
- Then `superpowers:finishing-a-development-branch`.

## Self-review notes (plan author)

- **Spec coverage:** architecture→Tasks 3; classification semantics→Tasks 2,3; coverage guard + rune defer→Task 1; consumer migration→Task 4; formal lockstep→Tasks 2,5; testing/rollout→Task 5. All covered.
- **Cycle risk** is called out explicitly (Task 1 Step 4 note + Task 3 Step A) — the leaf-module move is the resolution; do it first if the cycle bites.
- **Naming consistency:** `combat_gear_types` (core fn + GameData property), `defensive_gear_types`, `is_combat_bearing`/`stats_is_combat_bearing` (core vs ItemStats adapter), `_DEFERRED_RUNE_ABILITIES`, `_consumable_effect_codes` — used identically across tasks.
- **Open seams the implementer finalizes against real code** (flagged inline, not placeholders): exact `Manifest.lean`/`Oracle.lean` dispatch idiom, `oracle_client` helper name, `mutate.py` flag, the live-test skip marker — each says "match the existing sibling pattern," which is the honest instruction for conventions that live in files the implementer will open.
