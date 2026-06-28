# Gear Sub-project 2 — Unified Value Ruler — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the divergent gear-value functions into one proved `gear_value(stats, purpose)` over a shared `combat_raw` primitive, fixing the dominance-gate dmg/crit omission, with full formal lockstep.

**Architecture:** A new leaf core `gear_value_core.py` defines `combat_raw` (8-stat genuine-combat sum) + a `gear_value(fields, purpose)` dispatch (`Rank`/`Combat`/`Gather`). Existing scorers (`equip_value`, `weapon_score`, `armor_score`, `gather_score`, `inventory_caps._equip_value`) become specializations over it; call sites stay byte-identical except the dominance gate (which is the one intended behavior change). The Lean re-proof introduces a `combatRaw` sub-sum and keeps every existing role theorem (formulas unchanged).

**Tech Stack:** Python 3.13 (`uv` at `~/.local/bin/uv`), Lean 4 (`formal/`), Hypothesis (differential), `formal/diff/mutate.py` (mutation), pytest (`--cov-fail-under=100`).

## Global Constraints

- `uv` at `~/.local/bin/uv`; ALWAYS prefix Python with `uv run`. Run `git checkout uv.lock` before committing if `uv run` dirtied it.
- DO NOT use inline imports; imports at top. DO NOT use `if TYPE_CHECKING`. DO NOT use `...` imports. NEVER catch `Exception`.
- ONE behavioral class per file (pure data/enum groups may share a module). Pure proved cores live in `*_core.py`.
- Use only API data or fail with an error — no invented defaults.
- Tests: 0 errors, 0 warnings, 0 skipped (token-gated live tests excepted), 100% coverage. All tests in `tests/`. Real fixtures; never mock the unit under test.
- Formal lockstep: computable Lean `def` + role theorems (∀ inputs) + `Contracts.lean` exact-statement pins + `Manifest.lean` roster + differential (Python≡oracle on the HAND def) + mutation (every drop-term mutant killed). No `sorry`/`native_decide`/custom axioms; axiom lint allows only `{propext, Classical.choice, Quot.sound}`.
- NEVER run `formal/gate.sh` / `mutate.py` concurrently with anything importing `src` (incl. a live `artifactsmmo play`). `git diff src` after every mutation run.
- Branch: `feat/gear-unified-ruler` (off main `f5eabf71` = gear sub-project A merged).
- Spec: `docs/superpowers/specs/2026-06-28-gear-unified-ruler-design.md`.

**Verbatim formulas (use exactly):**
- `combat_raw` = `attack + resistance + hp_restore + hp_bonus + dmg + critical_strike + lifesteal + combat_buff` (attack/resistance = element-dict sums).
- `gear_value(Rank)` = `2 * (combat_raw + wisdom + prospecting + inventory_space + haste) + nonToolBonus`, `nonToolBonus = 0 if subtype == "tool" else 1`. **Bit-identical to today's `equip_value`.**
- `gear_value(Combat(m_atk, m_res))`: weapon type → `weapon_score` formula `(Σ atk·max(0,100−res%))·(200+crit)` then `2·raw + nonToolBonus`; else → `armor_score` formula `Σ m_atk·res% + hp_bonus + wisdom + prospecting + inventory_space + haste + lifesteal + combat_buff`.
- `gear_value(Gather(skill))` = `skill_effects.get(skill, 0)` (signed; pickers minimize).

**Existing Lean inventory (re-prove THROUGH gear_value; keep names):**
- `EquipValueAugmented.lean`: `RawStats`, `rawSum`, `nonToolBonus`, `equipValue`; theorems `rawSum_mono_in_*` (×11), `equipValue_strict_of_strict_raw`, `equipValue_tiebreaks_nontool_over_tool`.
- `EquipmentScoring.lean`: `WScore`, `AScore`, `gatherScore`, `pickSlot`, `pickGatherSlot`; `weapon_score_nonneg`, `armor_score_nonneg`, `pickslot_score_optimal`, `pickGatherSlot_score_optimal`.
- `StrategicValue.lean`: `Stats` (has `combatRaw` field), `Weights`, `strategicValue`; `strategicValue_nonneg`, `strategicValue_mono_*`.
- `PurposeRouting.lean`: `combatScore`, `gatherScore`. `DecideKey.lean`: unchanged (consumes strategic_value protection).
- Extracted: `Extracted/EquipValue.lean`, `Extracted/EquipmentScoring.lean`, `Extracted/StrategicValue.lean`; bridges `Bridges7/8/9`.

---

### Task 1: `combat_raw` primitive + `gear_value(Rank)` core + Lean

The shared atom and the Rank ruler. `equip_value` becomes a wrapper so its 7 callers don't change.

**Files:**
- Create: `src/artifactsmmo_cli/ai/gear_value_core.py`, `src/artifactsmmo_cli/ai/gear_value.py`
- Create: `formal/Formal/GearValue.lean`
- Modify: `src/artifactsmmo_cli/ai/tiers/equip_value.py` (make `equip_value` delegate), `formal/Formal/Manifest.lean`, `formal/Formal/Contracts.lean`
- Test: `tests/ai/test_gear_value_core.py`

**Interfaces:**
- Produces (Python): in `gear_value_core.py`:
  - `combat_raw(attack: int, resistance: int, hp_restore: int, hp_bonus: int, dmg: int, critical_strike: int, lifesteal: int, combat_buff: int) -> int`
  - purpose value-objects: `Rank` (singleton/`@dataclass(frozen=True)`), `Combat(monster_attack: Mapping[str,int], monster_resistance: Mapping[str,int])`, `Gather(skill: str)` — share `gear_value_core.py` (pure data exemption).
  - `rank_value(combat_raw: int, wisdom: int, prospecting: int, inventory_space: int, haste: int, subtype: str) -> int` = `2*(combat_raw + wisdom + prospecting + inventory_space + haste) + (0 if subtype=="tool" else 1)`.
  - in `gear_value.py`: `gear_value(stats: ItemStats, purpose) -> int` dispatch (Rank branch only in Task 1; Combat/Gather added Task 3) + `combat_raw_of(stats: ItemStats) -> int` adapter.
- Produces (Lean, `Formal.GearValue`): `combatRaw`, `rankValue`, theorems `rank_eq_equipValue` (rankValue equals `EquipValueAugmented.equipValue` on the corresponding RawStats), `rawSum_decomp` (`rawSum = combatRaw + wisdom + prospecting + inventorySpace + haste`).

- [ ] **Step 1: Write the failing core tests**

```python
# tests/ai/test_gear_value_core.py
from artifactsmmo_cli.ai.gear_value_core import Rank, combat_raw, rank_value


def test_combat_raw_sums_eight_stats():
    assert combat_raw(attack=3, resistance=2, hp_restore=1, hp_bonus=4, dmg=5,
                      critical_strike=6, lifesteal=7, combat_buff=8) == 36


def test_rank_value_matches_equip_value_formula():
    # 2*(combat_raw + wisdom+prosp+inv+haste) + nonToolBonus
    cr = combat_raw(attack=10, resistance=0, hp_restore=0, hp_bonus=0, dmg=0,
                    critical_strike=0, lifesteal=0, combat_buff=0)
    assert rank_value(cr, wisdom=0, prospecting=0, inventory_space=0, haste=0,
                      subtype="weapon") == 2 * 10 + 1
    assert rank_value(cr, wisdom=0, prospecting=0, inventory_space=0, haste=0,
                      subtype="tool") == 2 * 10 + 0
```

```python
# add to the same file
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.item_catalog import ItemStats


def test_gear_value_rank_equals_legacy_equip_value():
    s = ItemStats(code="x", level=1, type_="weapon", attack={"fire": 6},
                  critical_strike=35, hp_bonus=10, dmg=3)
    assert gear_value(s, Rank) == equip_value(s)
```

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/ai/test_gear_value_core.py -v`
Expected: FAIL — `ModuleNotFoundError: gear_value_core`.

- [ ] **Step 3: Write the pure core**

```python
# src/artifactsmmo_cli/ai/gear_value_core.py
"""PURE proved core for the unified gear value ruler (extracted; mirrors
Formal/GearValue.lean). No GameData/IO — plain data only. See
docs/superpowers/specs/2026-06-28-gear-unified-ruler-design.md."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Rank:
    """Monster-independent ranking purpose (the unified equip_value)."""


@dataclass(frozen=True)
class Combat:
    """Per-monster combat purpose."""
    monster_attack: Mapping[str, int]
    monster_resistance: Mapping[str, int]


@dataclass(frozen=True)
class Gather:
    """Per-skill gather purpose."""
    skill: str


def combat_raw(attack: int, resistance: int, hp_restore: int, hp_bonus: int,
               dmg: int, critical_strike: int, lifesteal: int,
               combat_buff: int) -> int:
    """The genuine-combat signal shared by Rank and strategic_value. Mirrors
    Formal.GearValue.combatRaw. (`_equip_value` omitted exactly dmg+crit.)"""
    return (attack + resistance + hp_restore + hp_bonus + dmg + critical_strike
            + lifesteal + combat_buff)


def rank_value(combat_raw_value: int, wisdom: int, prospecting: int,
               inventory_space: int, haste: int, subtype: str) -> int:
    """The unified Rank ruler. Bit-identical to legacy equip_value:
    2*(combat_raw + efficiency) + nonToolBonus. Mirrors Formal.GearValue.rankValue."""
    non_tool_bonus = 0 if subtype == "tool" else 1
    return 2 * (combat_raw_value + wisdom + prospecting + inventory_space + haste) + non_tool_bonus
```

Note: `Rank` is used as the singleton sentinel `Rank` instance OR the class — pick one and be consistent; the tests above pass `Rank` (the class) as the purpose tag. Use `isinstance`/identity dispatch in `gear_value`.

- [ ] **Step 4: Write the `gear_value.py` wrapper (Rank branch)**

```python
# src/artifactsmmo_cli/ai/gear_value.py
"""ItemStats adapter + dispatch for the unified gear value ruler."""

from artifactsmmo_cli.ai.gear_value_core import (
    Combat, Gather, Rank, combat_raw, rank_value,
)
from artifactsmmo_cli.ai.item_catalog import ItemStats


def combat_raw_of(stats: ItemStats) -> int:
    attack = sum(stats.attack.values()) if stats.attack else 0
    resistance = sum(stats.resistance.values()) if stats.resistance else 0
    return combat_raw(attack, resistance, stats.hp_restore, stats.hp_bonus,
                      stats.dmg, stats.critical_strike, stats.lifesteal,
                      stats.combat_buff)


def gear_value(stats: ItemStats, purpose: object) -> int:
    """Unified gear value. Rank now; Combat/Gather added in Task 3."""
    if purpose is Rank or isinstance(purpose, Rank):
        return rank_value(combat_raw_of(stats), stats.wisdom, stats.prospecting,
                          stats.inventory_space, stats.haste, stats.subtype)
    raise ValueError(f"unsupported purpose: {purpose!r}")
```

> `gear_value.py` imports only `gear_value_core` (leaf) + `ItemStats` (leaf) — no cycle.

- [ ] **Step 5: Make `equip_value` delegate**

In `tiers/equip_value.py`, replace the body of `equip_value(stats)` so it returns `gear_value(stats, Rank)` (import `Rank`, `gear_value`). Keep the docstring/name. `equip_value_pure` may stay for now (Task 5 reconciles extraction), but `equip_value` must route through the unified core so there is ONE Rank computation. Confirm the 7 callers are unaffected (no signature change).

- [ ] **Step 6: Run core tests + full suite**

Run: `~/.local/bin/uv run pytest tests/ai/test_gear_value_core.py -v` then `~/.local/bin/uv run pytest --cov-fail-under=100 -q`.
Expected: PASS, 100%. `equip_value`'s existing tests still green (Rank is bit-identical). `git checkout uv.lock`.

- [ ] **Step 7: Lean `combatRaw` + `rankValue` + decomposition**

Create `formal/Formal/GearValue.lean`. Read `formal/Formal/EquipValueAugmented.lean` for `RawStats`/`rawSum`/`equipValue`. Define:

```lean
import Formal.EquipValueAugmented
namespace Formal.GearValue
open Formal.EquipValueAugmented

def combatRaw (s : RawStats) : Int :=
  s.attack + s.resistance + s.hpRestore + s.hpBonus + s.dmg + s.crit
    + s.lifesteal + s.combatBuff

def rankValue (s : RawStats) (isTool : Bool) : Int :=
  2 * (combatRaw s + s.wisdom + s.prospecting + s.inventorySpace + s.haste)
    + nonToolBonus isTool

theorem rawSum_decomp (s : RawStats) :
    rawSum s = combatRaw s + s.wisdom + s.prospecting + s.inventorySpace + s.haste := by
  sorry

theorem rank_eq_equipValue (s : RawStats) (isTool : Bool) :
    rankValue s isTool = equipValue s isTool := by
  sorry

end Formal.GearValue
```

> Match the EXACT field names of `RawStats` (the grep shows `attack, resistance, hpBonus, crit, dmg, wisdom, prospecting, inventorySpace, haste, lifesteal, combatBuff` and an hp_restore-equivalent — open the file to confirm the precise names, e.g. `hpRestore`). Fill the two `sorry`s with `lean4:prove` (both should fall to `simp [rawSum, combatRaw, rankValue, equipValue]` + `ring`/`omega` since they are arithmetic identities). Do NOT weaken either statement.

- [ ] **Step 8: Prove + build + pin**

Run: `cd formal && lake build Formal.GearValue`. Verify axioms standard. Add the two theorem names to `Manifest.lean` and exact-statement pins to `Contracts.lean` (follow the existing idiom). `cd formal && lake build`.

- [ ] **Step 9: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add src/artifactsmmo_cli/ai/gear_value_core.py src/artifactsmmo_cli/ai/gear_value.py src/artifactsmmo_cli/ai/tiers/equip_value.py tests/ai/test_gear_value_core.py formal/Formal/GearValue.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean
git commit -m "feat(gear): combat_raw primitive + gear_value(Rank) core + Lean"
```

---

### Task 2: Dominance migration + divergence fix (the behavior change)

Delete `inventory_caps._equip_value`; route the dominance gate through `gear_value(Rank)` via the leaf (breaking the cycle that forced the duplicate). This is where dmg+crit enter dominance.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/inventory_caps.py` (delete `_equip_value` ~341-358; sites 301, 321 call `gear_value(stats, Rank)`)
- Test: `tests/ai/test_dominance_dmg_crit.py` (new) + update any existing `_equip_value` test

**Interfaces:**
- Consumes: `gear_value(stats, Rank)` from `gear_value.py` (Task 1).

- [ ] **Step 1: Write the behavior-change regression tests**

```python
# tests/ai/test_dominance_dmg_crit.py
"""The delete-dominance gate now scores dmg+crit (the fixed divergence), but the
skill-coverage guard still blocks a non-tool from dominating an uncovered tool."""

from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.item_catalog import ItemStats


def test_higher_dmg_crit_now_outvalues_at_gate():
    plain = ItemStats(code="plain", level=1, type_="ring", hp_bonus=5)
    sharp = ItemStats(code="sharp", level=1, type_="ring", hp_bonus=5, dmg=10,
                      critical_strike=20)
    # Under the OLD _equip_value (no dmg/crit) these tied; now sharp strictly wins.
    assert gear_value(sharp, Rank) > gear_value(plain, Rank)
```

> Also add a test (or extend the existing `_is_equippable_dominated` test in `tests/ai/test_inventory_caps*.py`) that a non-tool does NOT dominate a tool whose `skill_effects` it fails to cover — asserting the tool-coverage guard still gates the verdict after the ruler swap. Open the dominance test file and mirror its fixture style.

- [ ] **Step 2: Run to verify the new test passes already (it uses Task 1's core) and the OLD dominance still uses `_equip_value`**

Run: `~/.local/bin/uv run pytest tests/ai/test_dominance_dmg_crit.py -v`
Expected: the dmg/crit value test PASSES (it exercises gear_value). The dominance-gate swap isn't done yet — proceed.

- [ ] **Step 3: Delete `_equip_value`, route to `gear_value(Rank)`**

In `inventory_caps.py`: remove the `_equip_value` function (lines ~341-358). At line ~301 (`my_value = _equip_value(stats)`) and ~321 (`higher = _equip_value(peer) > my_value`), import and call `gear_value(stats, Rank)` / `gear_value(peer, Rank)`. Add `from artifactsmmo_cli.ai.gear_value import gear_value` + `from artifactsmmo_cli.ai.gear_value_core import Rank` at the top (leaf imports — no cycle; this is the structural fix that retires the duplicate).

- [ ] **Step 4: Run the dominance suites + full suite**

Run: `~/.local/bin/uv run pytest tests/ai/test_dominance_dmg_crit.py tests/ai/test_inventory_caps.py -v` then `~/.local/bin/uv run pytest --cov-fail-under=100 -q`.
Expected: PASS. Any existing test asserting the OLD dominance verdict (where dmg/crit were ignored) must be updated to the new behavior with a comment citing this spec's documented change. If a failure is NOT explained by the dmg/crit/nonToolBonus change, STOP and report it. `~/.local/bin/uv run mypy --strict src/artifactsmmo_cli/ai/inventory_caps.py`. `git checkout uv.lock`.

- [ ] **Step 5: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add src/artifactsmmo_cli/ai/inventory_caps.py tests/ai/test_dominance_dmg_crit.py
git commit -m "feat(gear): dominance gate uses unified gear_value(Rank) — fixes dmg/crit divergence"
```

---

### Task 3: `gear_value(Combat/Gather)` + EquipmentScoring re-proof

Add the Combat/Gather branches to `gear_value`; make `weapon_score`/`armor_score`/`gather_score` thin specializations. `pick_loadout`/`pick_gather` call sites unchanged.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/gear_value_core.py` (Combat/Gather scoring), `src/artifactsmmo_cli/ai/gear_value.py` (Combat/Gather dispatch), `src/artifactsmmo_cli/ai/equipment/scoring.py` (`weapon_score`/`armor_score`/`gather_score` delegate)
- Modify: `formal/Formal/GearValue.lean` (Combat/Gather defs + restated trio), `formal/Formal/PurposeRouting.lean` (align), `Manifest.lean`, `Contracts.lean`
- Test: extend `tests/ai/test_gear_value_core.py`

**Interfaces:**
- Consumes: `combat_raw` (Task 1), existing `weapon_score_raw_pure`/`armor_score_pure`/`gather_score_pure` (`equipment/scoring.py`).
- Produces: `gear_value(stats, Combat(...))`, `gear_value(stats, Gather(skill))` returning EXACTLY today's `weapon_score`/`armor_score`/`gather_score` values.

- [ ] **Step 1: Write the equivalence tests (gear_value ≡ legacy scorers)**

```python
# add to tests/ai/test_gear_value_core.py
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather
from artifactsmmo_cli.ai.equipment.scoring import armor_score, gather_score, weapon_score


def test_combat_purpose_matches_weapon_and_armor_score():
    weapon = ItemStats(code="w", level=1, type_="weapon", attack={"fire": 6},
                       critical_strike=20)
    armor = ItemStats(code="a", level=1, type_="body_armor", resistance={"fire": 30},
                      hp_bonus=15)
    m_res = {"fire": 25}
    m_atk = {"fire": 40}
    assert gear_value(weapon, Combat(m_atk, m_res)) == weapon_score(weapon, m_res)
    assert gear_value(armor, Combat(m_atk, m_res)) == armor_score(armor, m_atk)


def test_gather_purpose_matches_gather_score():
    tool = ItemStats(code="axe", level=1, type_="weapon",
                     skill_effects={"woodcutting": -10})
    assert gear_value(tool, Gather("woodcutting")) == gather_score(tool, "woodcutting")
```

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/ai/test_gear_value_core.py -k "combat_purpose or gather_purpose" -v`
Expected: FAIL — `gear_value` raises `ValueError` for Combat/Gather.

- [ ] **Step 3: Implement Combat/Gather dispatch**

In `gear_value.py`, extend `gear_value`: for `Combat`, dispatch on `stats.type_` — `"weapon"` → `weapon_score(stats, purpose.monster_resistance)`, else → `armor_score(stats, purpose.monster_attack)`; for `Gather`, → `gather_score(stats, purpose.skill)`. Import these from `equipment/scoring.py`.

> Layering check: `equipment/scoring.py` must not import `gear_value.py` if `gear_value.py` imports it (cycle). Resolve by having `gear_value(Combat/Gather)` delegate to the existing `*_score` functions (gear_value → scoring, one direction), and DO NOT make the `*_score` functions call back into `gear_value` in this task — the wrapper direction is gear_value→scoring. The "scorers become specializations" framing is satisfied by gear_value delegating to them; B will invert this when it generalizes pick_loadout. Document this direction in a comment.

- [ ] **Step 4: Run equivalence tests + full suite**

Run: `~/.local/bin/uv run pytest tests/ai/test_gear_value_core.py -v` then `~/.local/bin/uv run pytest --cov-fail-under=100 -q`. Expected: PASS. `git checkout uv.lock`.

- [ ] **Step 5: Lean Combat/Gather + restate the trio**

In `GearValue.lean`, define `combatValue`/`gatherValue` mirroring `EquipmentScoring.WScore`/`AScore`/`gatherScore`, and restate the four role theorems (`weapon_score_nonneg`, `armor_score_nonneg`, `pickslot_score_optimal`, `pickGatherSlot_score_optimal`) as corollaries on the `gear_value` Combat/Gather forms (they should follow by `rfl`/unfolding to the existing `EquipmentScoring` theorems since the formulas are identical). Align `PurposeRouting.combatScore`/`gatherScore` as the dispatch. Pin in `Contracts.lean`, roster in `Manifest.lean`. `cd formal && lake build`.

> Use `lean4:prove`; read `EquipmentScoring.lean` + `PurposeRouting.lean` first. Keep every existing theorem name; do not weaken.

- [ ] **Step 6: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add src/artifactsmmo_cli/ai/gear_value_core.py src/artifactsmmo_cli/ai/gear_value.py src/artifactsmmo_cli/ai/equipment/scoring.py tests/ai/test_gear_value_core.py formal/Formal/GearValue.lean formal/Formal/PurposeRouting.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean
git commit -m "feat(gear): gear_value(Combat/Gather) unifies per-monster scorers + Lean trio re-proof"
```

---

### Task 4: `strategic_value` shares `combat_raw`

Make `strategic_value`'s `combat_raw` input the one shared definition so it cannot drift; re-prove/re-pin StrategicValue + Bridges9.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategic_value.py` (compute `combat_raw` via `gear_value_core.combat_raw`)
- Modify: `formal/Formal/StrategicValue.lean` (its `combatRaw` ties to `GearValue.combatRaw`), `formal/Formal/Extracted/StrategicValue.lean` + `Bridges9.lean` if extraction shifts, `Manifest.lean`/`Contracts.lean` as needed
- Test: extend `tests/ai/test_strategic_value*.py`

**Interfaces:**
- Consumes: `gear_value_core.combat_raw` (Task 1).

- [ ] **Step 1: Write the shared-primitive test**

```python
# tests/ai/test_strategic_value_shared_combat_raw.py
"""strategic_value's combat_raw equals the shared combat_raw primitive."""

from artifactsmmo_cli.ai.gear_value import combat_raw_of
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.tiers.strategic_value import _combat_raw_of_stats  # introduced below


def test_strategic_value_uses_shared_combat_raw():
    s = ItemStats(code="x", level=1, type_="weapon", attack={"fire": 6},
                  critical_strike=20, hp_bonus=10, dmg=3, lifesteal=2)
    assert _combat_raw_of_stats(s) == combat_raw_of(s)
```

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/ai/test_strategic_value_shared_combat_raw.py -v`
Expected: FAIL (`_combat_raw_of_stats` not defined).

- [ ] **Step 3: Route strategic_value's combat_raw through the shared adapter**

In `strategic_value.py`, replace the inline `combat_raw` summation in `strategic_value(stats, ...)` with a call to `combat_raw_of(stats)` (import from `gear_value.py`). If a small helper `_combat_raw_of_stats` is convenient for the test, define it as an alias delegating to `combat_raw_of`. The efficiency-stat handling, weights, budget cap, and horizon scaling are UNCHANGED. `strategic_value`'s public signature and value (for the default weights) must be IDENTICAL to before — verify the existing strategic_value tests still pass.

- [ ] **Step 4: Run tests + full suite + mypy**

Run: `~/.local/bin/uv run pytest tests/ai/test_strategic_value_shared_combat_raw.py tests/ai/test_strategic_value.py -v` then `~/.local/bin/uv run pytest --cov-fail-under=100 -q` and `~/.local/bin/uv run mypy --strict src/artifactsmmo_cli/ai/tiers/strategic_value.py`. Expected: PASS. `git checkout uv.lock`.

- [ ] **Step 5: Lean — tie StrategicValue.combatRaw to GearValue.combatRaw**

In `StrategicValue.lean`, add a lemma/`def` connecting its `Stats.combatRaw` to `Formal.GearValue.combatRaw` over a shared `RawStats` (e.g. `def combatRawOf (s : RawStats) := Formal.GearValue.combatRaw s` and a theorem that `strategicValue` with this input is well-defined). Keep `strategicValue_nonneg` + all `strategicValue_mono_*`. Re-pin `Bridges9` if the extracted `strategic_value_pure` input shifts. `cd formal && lake build`.

> `lean4:prove`; read `StrategicValue.lean` + `Bridges9.lean` first. No theorem weakened.

- [ ] **Step 6: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add src/artifactsmmo_cli/ai/tiers/strategic_value.py tests/ai/test_strategic_value_shared_combat_raw.py formal/Formal/StrategicValue.lean formal/Formal/Extracted/StrategicValue.lean formal/Formal/Extracted/Bridges9.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean
git commit -m "feat(gear): strategic_value shares the combat_raw primitive (no third ruler)"
```

---

### Task 5: Integration — extraction regen, differential, mutation, DecideKey check, full gate

Bind the unified core to the proved Lean defs over random inputs, give it mutation teeth, verify DecideKey still elaborates, and certify the full gate.

**Files:**
- Create: `formal/diff/test_gear_value_diff.py`
- Modify: `formal/Oracle.lean` (handlers for `combatRaw`/`rankValue`/`combatValue`/`gatherValue`), `formal/diff/mutate.py` (drop-term mutants for `gear_value_core.py`), `scripts/extract_lean.py` / `formal/Formal/Extracted/*` as needed for any extracted core that shifted
- Modify (verify only): `formal/Formal/DecideKey.lean` / its `Contracts.lean` pin

**Interfaces:**
- Consumes: the cores (Tasks 1,3), the oracle, `gear_value` (all purposes).

- [ ] **Step 1: Oracle handlers**

In `formal/Oracle.lean`, add numbered handlers evaluating `Formal.GearValue.rankValue` (and `combatRaw`, and the Combat/Gather forms) on JSON input, following the existing `g NN` dispatch + the JSON parse helpers of a sibling handler (e.g. the EquipValue/EquipmentScoring area). Build + smoke-test: `cd formal && lake build Oracle` then a sample invocation returns the expected int.

- [ ] **Step 2: Differential harness**

```python
# formal/diff/test_gear_value_diff.py
"""Unified gear_value core ≡ Lean oracle over random stats/monsters/skills."""

from hypothesis import given, strategies as st

from artifactsmmo_cli.ai.gear_value_core import combat_raw, rank_value
from formal.diff.oracle_client import run_oracle   # match the sibling helper import


ints = st.integers(min_value=0, max_value=500)


@given(ints, ints, ints, ints, ints, ints, ints, ints, ints, ints, ints, ints,
       st.sampled_from(["weapon", "tool", "body_armor", "ring"]))
def test_rank_matches_oracle(a, r, hpr, hpb, d, c, ls, cb, wis, pro, inv, ha, sub):
    cr = combat_raw(a, r, hpr, hpb, d, c, ls, cb)
    py = rank_value(cr, wis, pro, inv, ha, sub)
    oracle = run_oracle({"op": "rank_value", "combat_raw": cr, "wisdom": wis,
                         "prospecting": pro, "inventory_space": inv, "haste": ha,
                         "is_tool": sub == "tool"})
    assert py == oracle
```

> Add a second `@given` binding `combat_raw` itself to the oracle's `combatRaw`. Match `oracle_client`'s actual name/signature. NO `unique=True`.

Run: `cd formal && ~/.local/bin/uv run pytest diff/test_gear_value_diff.py -v` → PASS.

- [ ] **Step 3: Mutation**

In `formal/diff/mutate.py`, register drop-term mutants for `gear_value_core.py`: each of the 8 `combat_raw` summands, the `nonToolBonus` term, and the `2 *` scale in `rank_value`. Run the mutation runner (match its flag) → all killed; `git diff src` empty afterward.

- [ ] **Step 4: DecideKey contract verification**

Confirm `DecideKey.lean` and its `Contracts.lean` pin still elaborate unchanged (strategic_value's interface was preserved): `cd formal && lake build Formal.DecideKey Formal.Contracts`. If it fails, the strategic_value interface drifted — STOP and report.

- [ ] **Step 5: Full suite + full gate**

Run: `~/.local/bin/uv run pytest --cov-fail-under=100` (all pass, 100%; new cores fully covered). Then, with nothing else importing `src`: `cd formal && ./gate.sh` → green end-to-end (build, no-sorry, axiom-lint, manifest, contracts, differential incl. the new one, mutation incl. the new mutants, extraction-drift). `git diff src` empty; `git checkout uv.lock`.

- [ ] **Step 6: Commit**

```bash
git checkout uv.lock 2>/dev/null
git add formal/ tests/
git commit -m "test(gear): differential + mutation + full-gate lock for unified value ruler"
```

---

## Final review (after all tasks)

Dispatch the whole-branch reviewer over `git merge-base main HEAD..HEAD`. Verify:
- ONE Rank computation: `equip_value` + the dominance gate both route through `gear_value(Rank)`; `_equip_value` is gone; no `tiers→inventory_caps` cycle (leaf `gear_value.py`).
- `strategic_value` consumes the shared `combat_raw`; no third raw-sum remains. Grep for any surviving independent `attack + resistance + ...` combat sum.
- Combat/Gather: `pick_loadout`/`pick_gather` call sites unchanged; `gear_value(Combat/Gather)` returns today's scorer values exactly (regression tests prove no loadout changes).
- The ONLY behavior change is the dominance gate (dmg+crit+nonToolBonus), guarded by the skill-coverage check, with a documented test.
- Soundness chain: differential calls the live core; oracle runs the hand `GearValue` defs; every restated theorem pinned in `Contracts.lean`, none weakened; mutation kills every combat_raw summand + nonToolBonus + scale.
- Then `superpowers:finishing-a-development-branch`.

## Self-review notes (plan author)

- **Spec coverage:** combat_raw atom + Rank → Task 1; dominance divergence fix → Task 2; Combat/Gather + trio re-proof → Task 3; strategic_value sharing → Task 4; PurposeRouting/DecideKey/extraction/bridges/differential/mutation/gate → Tasks 3+5. All covered.
- **Cycle:** the leaf `gear_value.py` (imports only `gear_value_core` + `ItemStats`) is what lets `inventory_caps` drop its local `_equip_value` — the structural reason the duplicate existed. Layering note in Task 3 prevents a new scoring↔gear_value cycle (direction: gear_value→scoring).
- **Naming consistency:** `combat_raw`/`combat_raw_of`/`rank_value`/`gear_value`/`Rank`/`Combat`/`Gather` (Python); `combatRaw`/`rankValue`/`rank_eq_equipValue`/`rawSum_decomp` (Lean) — used identically across tasks.
- **Honest open seams** (match-the-sibling, not placeholders): exact `RawStats` field names, `Oracle.lean`/`Manifest.lean`/`Contracts.lean` idioms, `oracle_client` helper name, `mutate.py` flag — each says "open the existing file and match," the correct instruction for in-file conventions.
- **Bit-identical Rank** means Tasks 1 & 3 add NO behavior change; the sole intended change is Task 2's dominance gate — the regression-lock tests enforce this.
