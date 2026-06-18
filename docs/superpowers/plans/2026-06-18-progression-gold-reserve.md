# Progression Gold Reserve Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat `GOLD_RESERVE = 500` with a calculated per-character progression reserve (gold kept for near-term gear/crafting upgrades) using deduction accounting, with the reserve arithmetic proven in Lean.

**Architecture:** A pure, kernel-proven core (`progression_reserve_core.py` ↔ `ProgressionReserve.lean`) does the reserve total / effective-floor / affordability arithmetic. An impure layer (`progression_reserve.py`) identifies and prices unmet near-term BUY targets via pluggable category sources (gear, crafting-unlock, boss-stub). The three buy-gates replace the flat constant with the deduction-aware floor.

**Tech Stack:** Python 3.13 (uv), Lean 4 (lake), Hypothesis differential testing, pytest (100% coverage gate).

## Global Constraints

- All Python commands prefixed with `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- No inline imports; imports at top of file. No `if TYPE_CHECKING`. Never catch `Exception`. One behavioral class per file.
- Use only API/game data or fail with an error — no defaulting that hides missing data.
- Exact-integer arithmetic in the proven core (gold/prices are ints ≥ 0). The Lean model uses `Nat`; affordability is expressed as `gold ≥ price + floor` (NO signed subtraction) on both sides.
- Coverage: 0 errors, 0 warnings, 0 skipped, 100% coverage. Tests live in `tests/`.
- Formal gate: serialize gate.sh / mutate.py runs — never concurrent with anything importing `src`. `git diff src` after each formal run.
- Spec: `docs/superpowers/specs/2026-06-18-progression-gold-reserve-design.md`.

---

## File Structure

- Create `src/artifactsmmo_cli/ai/progression_reserve_core.py` — pure proven arithmetic.
- Create `src/artifactsmmo_cli/ai/progression_reserve.py` — impure target identification + pricing + sources.
- Create `formal/Formal/ProgressionReserve.lean` — Lean model + role theorems.
- Modify `formal/Formal/Manifest.lean` — roster the role theorems.
- Modify `formal/Formal/Contracts.lean` — pin the role statements.
- Modify `formal/Oracle.lean` — `runProgressionReserve` handler + dispatch.
- Create `formal/diff/test_progression_reserve_diff.py` — differential harness.
- Modify `formal/diff/mutate.py` — mutation anchors for the core.
- Create `tests/test_ai/test_progression_reserve_core.py` — core unit tests.
- Create `tests/test_ai/test_progression_reserve.py` — impure-layer unit tests.
- Modify `src/artifactsmmo_cli/ai/goals/gathering.py`, `src/artifactsmmo_cli/ai/actions/ge_fill_sell.py`, `src/artifactsmmo_cli/ai/goals/expand_bank.py` — wire the floor.
- Modify `src/artifactsmmo_cli/ai/craft_vs_buy.py` — remove `GOLD_RESERVE`.

---

### Task 1: Pure core — reserve arithmetic + deduction accounting

**Files:**
- Create: `src/artifactsmmo_cli/ai/progression_reserve_core.py`
- Test: `tests/test_ai/test_progression_reserve_core.py`

**Interfaces:**
- Produces:
  - `reserve_total(reserved: Mapping[str, int]) -> int`
  - `effective_floor(reserved: Mapping[str, int], buying: str | None) -> int`
  - `affordable(gold: int, price: int, reserved: Mapping[str, int], buying: str | None) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai/test_progression_reserve_core.py
from artifactsmmo_cli.ai.progression_reserve_core import (
    affordable,
    effective_floor,
    reserve_total,
)


def test_reserve_total_sums_costs():
    assert reserve_total({"a": 30, "b": 50}) == 80
    assert reserve_total({}) == 0


def test_effective_floor_deducts_the_bought_reserved_item():
    reserved = {"a": 30, "b": 50}
    assert effective_floor(reserved, "a") == 50   # 80 - 30
    assert effective_floor(reserved, "b") == 30    # 80 - 50


def test_effective_floor_full_for_nonreserved_or_none():
    reserved = {"a": 30, "b": 50}
    assert effective_floor(reserved, "z") == 80     # not reserved -> full
    assert effective_floor(reserved, None) == 80    # discretionary -> full


def test_affordable_reserved_item_not_blocked_by_itself():
    reserved = {"a": 30, "b": 50}
    # gold 60, buying reserved "a" at price 30: floor 50, need gold >= 30+50=80 -> NO
    assert affordable(60, 30, reserved, "a") is False
    # gold 80: 80 >= 80 -> YES (a's own 30 deducted, only b's 50 protected)
    assert affordable(80, 30, reserved, "a") is True


def test_affordable_discretionary_protects_full_floor():
    reserved = {"a": 30, "b": 50}
    # buying non-reserved "z" price 10: need gold >= 10 + 80 = 90
    assert affordable(89, 10, reserved, "z") is False
    assert affordable(90, 10, reserved, "z") is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_progression_reserve_core.py -q --no-cov`
Expected: FAIL with `ModuleNotFoundError: ... progression_reserve_core`.

- [ ] **Step 3: Write the implementation**

```python
# src/artifactsmmo_cli/ai/progression_reserve_core.py
"""Pure progression-reserve arithmetic with deduction accounting.

`reserved` maps each unmet near-term progression item to the gold it would cost
to BUY (already deduped and priced by the impure layer). The reserve is a
protective FLOOR on discretionary spending, but buying a RESERVED item fulfills
its own reservation — so that item's cost is deducted from the floor for THAT
purchase (it is never blocked by itself); a non-reserved (discretionary) buy
protects the full reserve. Mirrored by `formal/Formal/ProgressionReserve.lean`.

P4a: gold/prices are exact ints (>= 0); affordability is written `gold >= price
+ floor` (no signed subtraction) to match the Lean `Nat` model exactly.
"""
from collections.abc import Mapping


def reserve_total(reserved: Mapping[str, int]) -> int:
    """Total gold reserved for unmet near-term progression purchases."""
    return sum(reserved.values())


def effective_floor(reserved: Mapping[str, int], buying: str | None) -> int:
    """The reserve floor that applies while buying `buying`: the total minus the
    reservation credited to `buying` itself (0 when `buying` is None or not a
    reserved item)."""
    return reserve_total(reserved) - reserved.get(buying or "", 0)


def affordable(gold: int, price: int, reserved: Mapping[str, int],
               buying: str | None) -> bool:
    """Whether buying `buying` for `price` leaves gold at or above the effective
    reserve floor: `gold >= price + effective_floor(...)`."""
    return gold >= price + effective_floor(reserved, buying)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_progression_reserve_core.py -q --no-cov`
Expected: PASS (5 passed).

- [ ] **Step 5: Typecheck**

Run: `uv run mypy src/artifactsmmo_cli/ai/progression_reserve_core.py`
Expected: `Success: no issues found in 1 source file`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/progression_reserve_core.py tests/test_ai/test_progression_reserve_core.py
git commit -m "feat(ai): pure progression-reserve core (reserve/floor/affordable)"
```

---

### Task 2: Lean model + role theorems

**Files:**
- Create: `formal/Formal/ProgressionReserve.lean`
- Modify: `formal/Formal/Manifest.lean` (add the `#check` roster lines)
- Modify: `formal/Formal/Contracts.lean` (pin the statements)

**Interfaces:**
- Produces Lean defs `Formal.ProgressionReserve.{reserveTotal, costOf, effectiveFloor, affordable}` and theorems `effectiveFloor_le_total`, `costOf_le_total`, `floor_plus_cost`, `nonreserved_full`, `total_le_append`, `affordable_antitone_floor`.

- [ ] **Step 1: Write the Lean model**

```lean
-- formal/Formal/ProgressionReserve.lean
-- @concept: core, economy @property: deduction-accounting, monotonicity
/-
Formal model of the progression-reserve arithmetic extracted from
`src/artifactsmmo_cli/ai/progression_reserve_core.py`. `reserved` is an assoc
list (code -> buy-cost); the impure layer dedups so `costOf` (first match) is
the item's reservation. Costs are `Nat` (gold prices are non-negative); the
affordability predicate is `gold ≥ price + effectiveFloor` (no signed sub),
matching the Python form exactly.
-/
namespace Formal.ProgressionReserve

abbrev Reserved := List (String × Nat)

/-- Total reserved gold = sum of costs. -/
def reserveTotal (reserved : Reserved) : Nat := (reserved.map (·.2)).sum

/-- The reservation credited to `buying` (first match), 0 if not reserved. -/
def costOf (reserved : Reserved) (buying : String) : Nat :=
  match reserved.find? (fun p => p.1 == buying) with
  | some p => p.2
  | none => 0

/-- Floor while buying `buying`: total minus its own reservation. -/
def effectiveFloor (reserved : Reserved) (buying : String) : Nat :=
  reserveTotal reserved - costOf reserved buying

/-- Affordability: gold covers price plus the effective floor. -/
def affordable (gold price : Nat) (reserved : Reserved) (buying : String) : Bool :=
  decide (gold ≥ price + effectiveFloor reserved buying)

/-! ### Role theorems. -/

/-- The credited reservation is a summand, so never exceeds the total. -/
theorem costOf_le_total (reserved : Reserved) (buying : String) :
    costOf reserved buying ≤ reserveTotal reserved := by
  unfold costOf reserveTotal
  cases h : reserved.find? (fun p => p.1 == buying) with
  | none => simp
  | some p =>
    have hmem : p ∈ reserved := List.find?_some h ▸ List.mem_of_find?_eq_some h
    calc p.2 = (fun q : String × Nat => q.2) p := rfl
      _ ≤ (reserved.map (·.2)).sum := List.le_sum_of_mem (List.mem_map_of_mem _ hmem)

/-- DEDUCTION IDENTITY: the floor plus the bought item's reservation is the full
total — a reserved item's own cost is exactly credited toward buying it. -/
theorem floor_plus_cost (reserved : Reserved) (buying : String) :
    effectiveFloor reserved buying + costOf reserved buying = reserveTotal reserved := by
  unfold effectiveFloor
  exact Nat.sub_add_cancel (costOf_le_total reserved buying)

/-- The floor never exceeds the total (the deduction only lowers it). -/
theorem effectiveFloor_le_total (reserved : Reserved) (buying : String) :
    effectiveFloor reserved buying ≤ reserveTotal reserved := by
  unfold effectiveFloor; exact Nat.sub_le _ _

/-- A non-reserved (cost 0) buy protects the FULL reserve. -/
theorem nonreserved_full (reserved : Reserved) (buying : String)
    (h : costOf reserved buying = 0) :
    effectiveFloor reserved buying = reserveTotal reserved := by
  unfold effectiveFloor; rw [h]; exact Nat.sub_zero _

/-- MONOTONE: appending more unmet targets never lowers the total (so never
loosens a discretionary gate). -/
theorem total_le_append (reserved extra : Reserved) :
    reserveTotal reserved ≤ reserveTotal (reserved ++ extra) := by
  unfold reserveTotal; simp [List.map_append, List.sum_append]

/-- ANTITONE IN FLOOR: a higher floor never turns an unaffordable buy
affordable. Stated on the underlying arithmetic the predicate decides. -/
theorem affordable_antitone_floor (gold price f1 f2 : Nat)
    (hle : f1 ≤ f2) (h : gold ≥ price + f2) : gold ≥ price + f1 := by
  omega

end Formal.ProgressionReserve
```

- [ ] **Step 2: Build the module (repair proofs if needed)**

Run: `cd formal && lake build Formal.ProgressionReserve`
Expected: `Build completed successfully`. If `List.le_sum_of_mem` / `List.mem_of_find?_eq_some` lemma names differ in this mathlib-free core, use the lean4 proof-repair flow: replace the `costOf_le_total` body with a `List.find?`-membership + `List.single_le_sum`/induction proof until it compiles. The theorem STATEMENTS must not change.

- [ ] **Step 3: Add the import to the manifest aggregator**

In `formal/Formal.lean` (the root import file), add `import Formal.ProgressionReserve` alongside the other module imports (find the existing `import Formal.DecideKey` line and add after it).

- [ ] **Step 4: Roster the roles in the manifest**

In `formal/Formal/Manifest.lean`, after the DecideKey block, add:

```lean
-- ProgressionReserve required roles:
#check @Formal.ProgressionReserve.floor_plus_cost                  -- deduction identity: floor + own cost = total
#check @Formal.ProgressionReserve.effectiveFloor_le_total          -- floor never exceeds total
#check @Formal.ProgressionReserve.nonreserved_full                 -- discretionary buy protects full reserve
#check @Formal.ProgressionReserve.total_le_append                  -- monotone: more targets never lowers the floor
#check @Formal.ProgressionReserve.affordable_antitone_floor        -- higher floor never makes a buy affordable
```

- [ ] **Step 5: Pin the statements in Contracts**

In `formal/Formal/Contracts.lean`, after the DecideKey contracts, add:

```lean
/-! ### ProgressionReserve role contracts. -/
example : ∀ (r : Formal.ProgressionReserve.Reserved) (b : String),
    Formal.ProgressionReserve.effectiveFloor r b + Formal.ProgressionReserve.costOf r b
      = Formal.ProgressionReserve.reserveTotal r :=
  @Formal.ProgressionReserve.floor_plus_cost
example : ∀ (r : Formal.ProgressionReserve.Reserved) (b : String),
    Formal.ProgressionReserve.effectiveFloor r b ≤ Formal.ProgressionReserve.reserveTotal r :=
  @Formal.ProgressionReserve.effectiveFloor_le_total
example : ∀ (r : Formal.ProgressionReserve.Reserved) (b : String),
    Formal.ProgressionReserve.costOf r b = 0 →
    Formal.ProgressionReserve.effectiveFloor r b = Formal.ProgressionReserve.reserveTotal r :=
  @Formal.ProgressionReserve.nonreserved_full
example : ∀ (r extra : Formal.ProgressionReserve.Reserved),
    Formal.ProgressionReserve.reserveTotal r
      ≤ Formal.ProgressionReserve.reserveTotal (r ++ extra) :=
  @Formal.ProgressionReserve.total_le_append
example : ∀ (gold price f1 f2 : Nat), f1 ≤ f2 → gold ≥ price + f2 → gold ≥ price + f1 :=
  @Formal.ProgressionReserve.affordable_antitone_floor
```

- [ ] **Step 6: Build manifest + contracts**

Run: `cd formal && lake build Formal.Manifest Formal.Contracts`
Expected: `Build completed successfully`.

- [ ] **Step 7: Commit**

```bash
git add formal/Formal/ProgressionReserve.lean formal/Formal.lean formal/Formal/Manifest.lean formal/Formal/Contracts.lean
git commit -m "feat(formal): ProgressionReserve Lean model + role theorems"
```

---

### Task 3: Oracle handler + differential harness

**Files:**
- Modify: `formal/Oracle.lean`
- Create: `formal/diff/test_progression_reserve_diff.py`

**Interfaces:**
- Consumes: the Task 1 Python core and the Task 2 Lean defs.
- Produces: oracle `kind == "progression_reserve"` emitting `{"floor": Int, "affordable": Bool}`.

- [ ] **Step 1: Add the oracle handler**

In `formal/Oracle.lean`, add a `runProgressionReserve` def near the other `run*` handlers (e.g. after `runDecideKey`):

```lean
/-- progression_reserve: args layout (all Nat ≥ 0):
* `[0]`               nReserved (number of (code, cost) pairs)
* `[1 .. 2*nReserved]` pairs flat: code0 cost0 code1 cost1 ...  (codes are ints,
  stringified to match the Python str keys)
* next: gold, price, buyingCode (buyingCode = -1 encodes None / non-reserved)
Emits `{"floor", "affordable"}` against the proved core. -/
def runProgressionReserve (args : Array Json) : Json :=
  let g := fun i => intArg args i
  let n := (g 0).toNat
  let reserved : Formal.ProgressionReserve.Reserved :=
    (List.range n).map (fun k => (toString (g (1 + 2*k)), (g (2 + 2*k)).toNat))
  let p := 1 + 2*n
  let gold := (g p).toNat
  let price := (g (p+1)).toNat
  let bRaw := g (p+2)
  let buying : String := if bRaw < 0 then "" else toString bRaw
  Json.mkObj [
    ("floor", Json.num (Int.ofNat (Formal.ProgressionReserve.effectiveFloor reserved buying))),
    ("affordable", Json.bool (Formal.ProgressionReserve.affordable gold price reserved buying))]
```

Add the dispatch line in the `kind ==` chain (next to `else if kind == "decide_key" then runDecideKey args`):

```lean
  else if kind == "progression_reserve" then
    runProgressionReserve args
```

Also add `open Formal.ProgressionReserve` is NOT required (fully-qualified above); ensure `import Formal.ProgressionReserve` is present at the top of `Oracle.lean` (add it next to `import Formal.DecideKey`).

- [ ] **Step 2: Build the oracle executable**

Run: `cd formal && lake build oracle`
Expected: `Build completed successfully`.

- [ ] **Step 3: Write the differential harness**

```python
# formal/diff/test_progression_reserve_diff.py
"""Differential: the live `progression_reserve_core` must agree with the proved
Lean `ProgressionReserve` on the effective floor and the affordability decision.
Codes are integers 0..n-1 (stringified on both sides); buying = -1 encodes
None / a non-reserved code."""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.progression_reserve_core import affordable, effective_floor
from formal.diff.oracle_client import run_oracle


def _oracle_args(reserved: dict[str, int], gold: int, price: int, buying: int) -> list[int]:
    pairs: list[int] = []
    for code, cost in reserved.items():
        pairs.extend([int(code), cost])
    return [len(reserved), *pairs, gold, price, buying]


@settings(max_examples=300, deadline=None)
@given(
    costs=st.lists(st.integers(min_value=0, max_value=500), min_size=0, max_size=6),
    gold=st.integers(min_value=0, max_value=5000),
    price=st.integers(min_value=0, max_value=2000),
    buying=st.integers(min_value=-1, max_value=8),
)
def test_floor_and_affordable_match_lean(costs, gold, price, buying):
    reserved = {str(i): c for i, c in enumerate(costs)}
    py_buying = None if buying < 0 else str(buying)
    py_floor = effective_floor(reserved, py_buying)
    py_aff = affordable(gold, price, reserved, py_buying)
    lean = run_oracle("progression_reserve",
                      [_oracle_args(reserved, gold, price, buying)])[0]
    assert lean["floor"] == py_floor, (reserved, buying, py_floor, lean)
    assert lean["affordable"] == py_aff, (reserved, gold, price, buying, py_aff, lean)


def test_reserved_item_deduction_witness():
    reserved = {"0": 30, "1": 50}
    # buying reserved "0": floor 50; gold 80 affordable, 79 not.
    assert effective_floor(reserved, "0") == 50
    lean = run_oracle("progression_reserve", [_oracle_args(reserved, 80, 30, 0)])[0]
    assert lean["floor"] == 50 and lean["affordable"] is True
    lean2 = run_oracle("progression_reserve", [_oracle_args(reserved, 79, 30, 0)])[0]
    assert lean2["affordable"] is False
```

- [ ] **Step 4: Run the differential**

Run: `uv run pytest formal/diff/test_progression_reserve_diff.py -q --no-cov`
Expected: PASS (2 passed; property + witness).

- [ ] **Step 5: Commit**

```bash
git add formal/Oracle.lean formal/diff/test_progression_reserve_diff.py
git commit -m "feat(formal): progression_reserve oracle + differential harness"
```

---

### Task 4: Mutation anchors for the core

**Files:**
- Modify: `formal/diff/mutate.py`

**Interfaces:**
- Consumes: Task 1 core text, Task 3 differential.

- [ ] **Step 1: Add the mutation group**

In `formal/diff/mutate.py`, near the other mutation lists (e.g. after `DECIDE_KEY_MUTATIONS`), add:

```python
# progression_reserve_core mutations -- each breaks the deduction-accounting
# floor so the Python decision diverges from the proved Lean oracle. Killed by
# formal/diff/test_progression_reserve_diff.py.
PROGRESSION_RESERVE_MUTATIONS = [
    # Drop the deduction: a reserved item's own cost no longer credited, so its
    # purchase is wrongly blocked by its own reservation.
    ("progression_reserve: drop deduction (floor = full total)",
     "    return reserve_total(reserved) - reserved.get(buying or \"\", 0)",
     "    return reserve_total(reserved)"),
    # Flip the affordability comparison: spends below the floor.
    ("progression_reserve: invert affordability (>= -> <)",
     "    return gold >= price + effective_floor(reserved, buying)",
     "    return gold < price + effective_floor(reserved, buying)"),
    # Ignore price in affordability -> overspends by the item's price.
    ("progression_reserve: drop price from affordability",
     "    return gold >= price + effective_floor(reserved, buying)",
     "    return gold >= effective_floor(reserved, buying)"),
]
```

Register the group with the runner. Find where `DECIDE_KEY_MUTATIONS` is registered (the runner builds a list of `(mutations, src_path, test_path)` groups) and add an analogous entry:

```python
    (PROGRESSION_RESERVE_MUTATIONS,
     ROOT / "src" / "artifactsmmo_cli" / "ai" / "progression_reserve_core.py",
     "formal/diff/test_progression_reserve_diff.py"),
```

(Mirror the exact registration shape used for `decide_key` — see the call site near `formal/diff/mutate.py` end that references `test_decide_key_diff.py`.)

- [ ] **Step 2: Run the mutation group**

Run: `cd formal && python3 diff/mutate.py --only progression_reserve`
Expected: ends with `mutation gate OK`; all 3 mutants `killed`. (The committed `progression_reserve_core.py` must be clean — commit Task 1 first.)

- [ ] **Step 3: Commit**

```bash
git add formal/diff/mutate.py
git commit -m "test(formal): progression_reserve mutation anchors"
```

---

### Task 5: Impure layer — buy-pricing helper + gear source

**Files:**
- Create: `src/artifactsmmo_cli/ai/progression_reserve.py`
- Test: `tests/test_ai/test_progression_reserve.py`

**Interfaces:**
- Consumes: `game_data.npcs_selling_item(code) -> list[(npc, price)]` (cheapest first), `game_data.ge_best_buy_order(code) -> (id, price, qty)|None`, `game_data.all_item_stats -> Mapping[str, ItemStats]`, `game_data.item_stats(code)`, `craft_vs_buy.acquisition_method(item, needed, state, game_data, reserve) -> Method`, `equip_value(stats)`, `ITEM_TYPE_TO_SLOTS`.
- Produces:
  - `buy_price(code, game_data) -> int | None` (cheapest gold buy price, or None if unsellable)
  - `gear_targets(state, game_data) -> dict[str, int]` (unmet, buy-method gear codes → buy price)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai/test_progression_reserve.py
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.progression_reserve import buy_price, gear_targets
from tests.test_ai.fixtures import make_state


def _gd_buyable_armor() -> GameData:
    gd = GameData()
    gd._item_stats = {
        # a body-armor upgrade usable at level<=7, sold by an npc, not craftable
        "iron_armor": ItemStats(code="iron_armor", level=5, type_="body_armor", hp_bonus=40),
        # currently equipped (worse)
        "rags": ItemStats(code="rags", level=1, type_="body_armor", hp_bonus=5),
    }
    gd._npc_sell_prices = {"merchant": {"iron_armor": 120}}
    gd._monster_level = {"chicken": 1}
    return gd


def test_buy_price_is_cheapest_seller():
    gd = _gd_buyable_armor()
    assert buy_price("iron_armor", gd) == 120
    assert buy_price("nonexistent", gd) is None


def test_gear_targets_reserves_unmet_buyable_upgrade():
    gd = _gd_buyable_armor()
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    targets = gear_targets(state, gd)
    assert targets == {"iron_armor": 120}


def test_gear_targets_skips_already_equipped_best():
    gd = _gd_buyable_armor()
    state = make_state(level=5, equipment={"body_armor_slot": "iron_armor"})
    assert gear_targets(state, gd) == {}


def test_gear_targets_skips_out_of_horizon():
    gd = _gd_buyable_armor()
    gd._item_stats["iron_armor"].level = 99  # far above level+2
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    assert gear_targets(state, gd) == {}
```

Note: confirm `make_state` accepts `equipment=`; if the fixture differs, set `state.equipment` per the existing `tests/test_ai/fixtures.py` API (it is used with `equipment=` elsewhere in this suite). Confirm `GameData._npc_sell_prices` is the backing store read by `npcs_selling_item` (check `game_data.py` `npc_sell_prices` property and the `world.npcs_selling_item` source; if `npcs_selling_item` reads a different field, populate that field in the fixture instead).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ai/test_progression_reserve.py -q --no-cov`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the gear source + helper**

```python
# src/artifactsmmo_cli/ai/progression_reserve.py
"""Impure progression-reserve target identification and pricing.

Each category SOURCE yields the unmet near-term (level..level+2) progression
items the bot would BUY, mapped to their cheapest gold buy price. The pure
`progression_reserve_core` then sums them and applies the deduction-aware floor.
Craftable-now / unsellable items contribute nothing (no gold needed).
"""
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.craft_vs_buy import Method, acquisition_method
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.world_state import WorldState

_HORIZON = 2  # reserve for upgrades usable within the next 2 character levels


def buy_price(code: str, game_data: GameData) -> int | None:
    """Cheapest gold price to BUY one `code` (min over NPC sellers and the GE
    best buy order), or None when nothing sells it."""
    prices: list[int] = [p for _npc, p in game_data.npcs_selling_item(code)]
    ge = game_data.ge_best_buy_order(code)
    if ge is not None:
        prices.append(ge[1])
    return min(prices) if prices else None


def gear_targets(state: WorldState, game_data: GameData) -> dict[str, int]:
    """Unmet gear upgrades usable within the horizon that the bot would BUY,
    mapped to their buy price. Per combat slot, the best equippable of the slot's
    type at level <= state.level + _HORIZON whose value beats the equipped item,
    included only when its acquisition method is BUY and a seller exists."""
    out: dict[str, int] = {}
    max_level = state.level + _HORIZON
    for slot, codes in _best_per_slot(state, game_data, max_level).items():
        code = codes
        price = buy_price(code, game_data)
        if price is None:
            continue
        if acquisition_method(code, 1, state, game_data, 0) is not Method.BUY:
            continue
        out[code] = price
    return out


def _best_per_slot(state: WorldState, game_data: GameData,
                   max_level: int) -> dict[str, str]:
    """{slot: best_upgrade_code} for combat slots where an in-horizon item beats
    the equipped one. Scans all item stats by the slot's item type."""
    best: dict[str, str] = {}
    for code, stats in game_data.all_item_stats.items():
        slots = ITEM_TYPE_TO_SLOTS.get(stats.type_)
        if not slots or stats.level > max_level:
            continue
        for slot in slots:
            equipped = state.equipment.get(slot)
            cur = game_data.item_stats(equipped) if equipped else None
            cur_val = equip_value(cur) if cur is not None else 0
            if equip_value(stats) <= cur_val:
                continue
            incumbent = best.get(slot)
            inc_val = equip_value(game_data.item_stats(incumbent)) if incumbent else cur_val
            if equip_value(stats) > inc_val:
                best[slot] = code
    return best
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ai/test_progression_reserve.py -q --no-cov`
Expected: PASS (4 passed). If a fixture field name is wrong (see Step 1 note), fix the fixture, not the source.

- [ ] **Step 5: Typecheck**

Run: `uv run mypy src/artifactsmmo_cli/ai/progression_reserve.py`
Expected: `Success`.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/progression_reserve.py tests/test_ai/test_progression_reserve.py
git commit -m "feat(ai): gear source + buy-pricing for progression reserve"
```

---

### Task 6: Crafting-unlock source

**Files:**
- Modify: `src/artifactsmmo_cli/ai/progression_reserve.py`
- Test: `tests/test_ai/test_progression_reserve.py`

**Interfaces:**
- Consumes: `game_data.crafting_recipe(code)`, `game_data.item_stats`, `skill_target_curve`, `buy_price` (Task 5), `acquisition_method`.
- Produces: `crafting_unlock_targets(state, game_data) -> dict[str, int]`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_ai/test_progression_reserve.py
from artifactsmmo_cli.ai.progression_reserve import crafting_unlock_targets


def test_crafting_unlock_reserves_buyable_recipe_input():
    gd = GameData()
    # a craftable gear item gated by a recipe whose input must be bought
    gd._item_stats = {
        "steel_sword": ItemStats(code="steel_sword", level=6, type_="weapon",
                                 attack={"fire": 30}, crafting_skill="weaponcrafting",
                                 crafting_level=1),
        "steel_bar": ItemStats(code="steel_bar", level=6, type_="resource"),
    }
    gd._crafting_recipes = {"steel_sword": {"steel_bar": 3}}
    gd._npc_sell_prices = {"smith": {"steel_bar": 25}}  # input is buyable, not gatherable
    gd._monster_level = {"chicken": 1}
    state = make_state(level=5, skills={"weaponcrafting": 1})
    targets = crafting_unlock_targets(state, gd)
    # the buyable recipe input is reserved at its buy price (qty * price)
    assert targets == {"steel_bar": 75}


def test_crafting_unlock_skips_gatherable_inputs():
    gd = GameData()
    gd._item_stats = {
        "steel_sword": ItemStats(code="steel_sword", level=6, type_="weapon",
                                 attack={"fire": 30}, crafting_skill="weaponcrafting",
                                 crafting_level=1),
        "iron_ore": ItemStats(code="iron_ore", level=6, type_="resource"),
    }
    gd._crafting_recipes = {"steel_sword": {"iron_ore": 3}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}  # gatherable -> not a gold need
    gd._resource_skill = {"iron_rocks": ("mining", 1)}
    gd._monster_level = {"chicken": 1}
    state = make_state(level=5, skills={"weaponcrafting": 1})
    assert crafting_unlock_targets(state, gd) == {}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_progression_reserve.py -q --no-cov -k crafting_unlock`
Expected: FAIL (`ImportError: cannot import name 'crafting_unlock_targets'`).

- [ ] **Step 3: Implement the source**

```python
# append to src/artifactsmmo_cli/ai/progression_reserve.py
def crafting_unlock_targets(state: WorldState, game_data: GameData) -> dict[str, int]:
    """Buyable recipe INPUTS for in-horizon craftable gear whose final craft is
    skill-reachable: an input the bot must BUY (no gather/craft path) is a real
    upcoming gold need. Maps each such input to qty * buy price."""
    out: dict[str, int] = {}
    max_level = state.level + _HORIZON
    for code, stats in game_data.all_item_stats.items():
        if ITEM_TYPE_TO_SLOTS.get(stats.type_) is None or stats.level > max_level:
            continue
        recipe = game_data.crafting_recipe(code)
        if not recipe:
            continue
        for material, qty in recipe.items():
            if game_data.resource_drop_item is not None and _is_gatherable(material, game_data):
                continue
            price = buy_price(material, game_data)
            if price is None:
                continue
            if acquisition_method(material, qty, state, game_data, 0) is not Method.BUY:
                continue
            out[material] = qty * price
    return out


def _is_gatherable(material: str, game_data: GameData) -> bool:
    """True when some resource node drops `material` (so it costs gathering, not
    gold)."""
    return any(drop == material for drop in game_data.resource_drops.values())
```

Note: confirm `game_data.resource_drops` is the `{resource_code: drop_item}` map (it is — used in Task #1's gather work). Drop the `game_data.resource_drop_item is not None and` guard if it does not typecheck; the intent is simply "skip gatherable inputs via `_is_gatherable`". Keep `_is_gatherable` as the single check.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_progression_reserve.py -q --no-cov`
Expected: PASS (6 passed).

- [ ] **Step 5: Typecheck + commit**

```bash
uv run mypy src/artifactsmmo_cli/ai/progression_reserve.py
git add src/artifactsmmo_cli/ai/progression_reserve.py tests/test_ai/test_progression_reserve.py
git commit -m "feat(ai): crafting-unlock source for progression reserve"
```

---

### Task 7: Boss stub + union + public reserve/floor API

**Files:**
- Modify: `src/artifactsmmo_cli/ai/progression_reserve.py`
- Test: `tests/test_ai/test_progression_reserve.py`

**Interfaces:**
- Consumes: Tasks 5-6 sources + the Task 1 core (`reserve_total`, `effective_floor`).
- Produces:
  - `boss_targets(state, game_data) -> dict[str, int]` (stub → `{}`)
  - `reserved_targets(state, game_data) -> dict[str, int]`
  - `progression_reserve(state, game_data) -> int`
  - `reserve_floor(state, game_data, buying) -> int`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_ai/test_progression_reserve.py
from artifactsmmo_cli.ai.progression_reserve import (
    boss_targets,
    progression_reserve,
    reserve_floor,
    reserved_targets,
)


def test_boss_targets_is_stub_empty():
    gd = _gd_buyable_armor()
    assert boss_targets(make_state(level=5), gd) == {}


def test_reserved_targets_unions_sources():
    gd = _gd_buyable_armor()
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    assert reserved_targets(state, gd) == {"iron_armor": 120}
    assert progression_reserve(state, gd) == 120


def test_reserve_floor_deducts_when_buying_a_reserved_item():
    gd = _gd_buyable_armor()
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    # buying the reserved iron_armor -> its 120 is credited -> floor 0
    assert reserve_floor(state, gd, "iron_armor") == 0
    # buying something else -> full floor 120
    assert reserve_floor(state, gd, "copper_ore") == 120
    assert reserve_floor(state, gd, None) == 120
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_ai/test_progression_reserve.py -q --no-cov -k "boss or reserved_targets or reserve_floor"`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implement union + public API**

```python
# append to src/artifactsmmo_cli/ai/progression_reserve.py (add the core import at top)
from artifactsmmo_cli.ai.progression_reserve_core import effective_floor, reserve_total


def boss_targets(state: WorldState, game_data: GameData) -> dict[str, int]:
    """Boss-odds reservation — STUB. Reserving for boss-fight items needs the
    boss-pursuit machinery (winnability + event/boss drop identification) that is
    not yet built (docs/PLAN_calculate_not_hardcode.md #9, roadmap5). Returns no
    targets until that lands; this is the documented extension point."""
    return {}


def reserved_targets(state: WorldState, game_data: GameData) -> dict[str, int]:
    """All unmet near-term BUY-acquired progression targets -> buy price, unioned
    across the category sources. Same code from two sources prices identically
    (min npc/ge), so dict union is unambiguous."""
    targets: dict[str, int] = {}
    for source in (gear_targets, crafting_unlock_targets, boss_targets):
        targets.update(source(state, game_data))
    return targets


def progression_reserve(state: WorldState, game_data: GameData) -> int:
    """Total gold reserved for near-term progression (replaces GOLD_RESERVE)."""
    return reserve_total(reserved_targets(state, game_data))


def reserve_floor(state: WorldState, game_data: GameData,
                  buying: str | None) -> int:
    """The deduction-aware reserve floor that applies while buying `buying`."""
    return effective_floor(reserved_targets(state, game_data), buying)
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_ai/test_progression_reserve.py -q --no-cov`
Expected: PASS (9 passed).

- [ ] **Step 5: Typecheck + commit**

```bash
uv run mypy src/artifactsmmo_cli/ai/progression_reserve.py
git add src/artifactsmmo_cli/ai/progression_reserve.py tests/test_ai/test_progression_reserve.py
git commit -m "feat(ai): boss stub + reserved_targets union + reserve_floor API"
```

---

### Task 8: Wire the gathering acquisition gate

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/gathering.py` (the `acquisition_method(... GOLD_RESERVE)` call ~:257)
- Test: existing `tests/test_ai/test_goals.py` (or the gathering test module)

**Interfaces:**
- Consumes: `reserve_floor(state, game_data, buying)` from Task 7.

- [ ] **Step 1: Write a failing test** that a discretionary material buy is blocked when it would breach the gear reserve, and a reserved item buy is not. Add to the gathering goal's test module (mirror an existing `acquisition_method` test there):

```python
def test_buy_gate_respects_progression_reserve(self):
    # gear reserve = 120 (iron_armor); gold 130; a 20-gold material buy must
    # leave >= 120 -> 130-20 = 110 < 120 -> not BUY.
    gd = _gd_with_reserve_and_material()  # builds buyable iron_armor + cheap material
    state = make_state(level=5, gold=130, equipment={"body_armor_slot": "rags"})
    goal = GatherMaterialsGoal(target_item="thing", needed={"material": 1})
    # the material is NPC-sold and cheaper-to-buy, but the reserve blocks it
    assert "material" not in _bought_items(goal, state, gd)
```

(Use the gathering test module's existing helpers for constructing the goal and reading which items it routes to BUY; if none exist, assert via `acquisition_method(material, 1, state, gd, reserve_floor(state, gd, "material"))` returning `Method.CRAFT`.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_goals.py -q --no-cov -k progression_reserve`
Expected: FAIL (buy still allowed — flat reserve gone but new floor not wired).

- [ ] **Step 3: Wire the call**

In `src/artifactsmmo_cli/ai/goals/gathering.py`, replace the import and the call:

```python
# was: from artifactsmmo_cli.ai.craft_vs_buy import GOLD_RESERVE, Method, acquisition_method
from artifactsmmo_cli.ai.craft_vs_buy import Method, acquisition_method
from artifactsmmo_cli.ai.progression_reserve import reserve_floor
```

```python
# was: if acquisition_method(item, qty, state, game_data, GOLD_RESERVE) is not Method.BUY:
if acquisition_method(item, qty, state, game_data,
                      reserve_floor(state, game_data, item)) is not Method.BUY:
    continue
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_goals.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/gathering.py tests/test_ai/test_goals.py
git commit -m "feat(ai): gathering buy-gate honors the progression reserve floor"
```

---

### Task 9: Wire the ge_fill_sell gate

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/ge_fill_sell.py` (the `GOLD_RESERVE` gate ~:51)
- Test: existing ge_fill_sell test module.

- [ ] **Step 1: Write a failing test** that the GE resale buy is blocked when it would breach the progression reserve (mirror the module's existing gold-gate test, swapping in a state with an unmet buyable gear upgrade so the reserve is nonzero).

```python
def test_ge_fill_sell_respects_progression_reserve():
    gd = _gd_buyable_armor_and_ge_item()
    state = make_state(level=5, gold=130, equipment={"body_armor_slot": "rags"})
    action = GEFillSellAction(item_code="widget", price=20, quantity=1, ...)
    assert action.is_applicable(state, gd) is False  # 130-20=110 < 120 reserve
```

- [ ] **Step 2: Run to verify it fails.**

Run: `uv run pytest tests/test_ai/<ge_fill_sell test>.py -q --no-cov -k progression_reserve`
Expected: FAIL.

- [ ] **Step 3: Wire the gate**

In `src/artifactsmmo_cli/ai/actions/ge_fill_sell.py`:

```python
# was: from artifactsmmo_cli.ai.craft_vs_buy import GOLD_RESERVE
from artifactsmmo_cli.ai.progression_reserve import reserve_floor
```

```python
# was: if state.gold - self.price * self.quantity < GOLD_RESERVE:
if state.gold - self.price * self.quantity < reserve_floor(state, game_data, self.item_code):
    return False
```

- [ ] **Step 4: Run to verify it passes.**

Run: `uv run pytest tests/test_ai/<ge_fill_sell test>.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/ge_fill_sell.py tests/test_ai/<ge_fill_sell test>.py
git commit -m "feat(ai): ge_fill_sell buy-gate honors the progression reserve floor"
```

---

### Task 10: Wire the expand_bank gate

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/expand_bank.py` (the `should_expand_bank(... GOLD_RESERVE ...)` call ~:47)
- Test: existing expand_bank test module.

- [ ] **Step 1: Write a failing test** that bank expansion is withheld when buying it would breach the progression reserve (a bank expansion is never a reserved gear code, so the FULL floor applies):

```python
def test_expand_bank_respects_progression_reserve():
    gd = _gd_buyable_armor_and_full_bank()  # next_expansion_cost low, but reserve high
    state = make_state(level=5, gold=130, equipment={"body_armor_slot": "rags"})
    # expansion cost 20, but 130-20=110 < 120 gear reserve -> do not expand
    assert ExpandBankGoal().priority(state, gd) == 0.0
```

- [ ] **Step 2: Run to verify it fails.**

Run: `uv run pytest tests/test_ai/<expand_bank test>.py -q --no-cov -k progression_reserve`
Expected: FAIL.

- [ ] **Step 3: Wire the gate**

In `src/artifactsmmo_cli/ai/goals/expand_bank.py`:

```python
# was: from artifactsmmo_cli.ai.craft_vs_buy import GOLD_RESERVE
from artifactsmmo_cli.ai.progression_reserve import reserve_floor
```

```python
# was: game_data.next_expansion_cost, GOLD_RESERVE,
        game_data.next_expansion_cost, reserve_floor(state, game_data, None),
```

- [ ] **Step 4: Run to verify it passes.**

Run: `uv run pytest tests/test_ai/<expand_bank test>.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/expand_bank.py tests/test_ai/<expand_bank test>.py
git commit -m "feat(ai): expand_bank gate honors the progression reserve floor"
```

---

### Task 11: Remove GOLD_RESERVE + optional minimum safety floor + full gate

**Files:**
- Modify: `src/artifactsmmo_cli/ai/craft_vs_buy.py` (remove `GOLD_RESERVE`)
- Modify: `src/artifactsmmo_cli/ai/progression_reserve.py` (minimum floor decision)

**Decision (minimum safety floor):** retain the original safety intent by flooring the reserve at a small documented minimum so the bot never spends to zero when nothing is reserved. Implement `progression_reserve` / `reserve_floor` to apply `max(..., _MIN_SAFETY_FLOOR)` where `_MIN_SAFETY_FLOOR = 100`. (If the team prefers a pure calculated value with no minimum, set `_MIN_SAFETY_FLOOR = 0` — the tests below assume 100; adjust the two assertions accordingly.)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_ai/test_progression_reserve.py
from artifactsmmo_cli.ai.progression_reserve import progression_reserve


def test_minimum_safety_floor_when_nothing_reserved():
    gd = GameData()
    gd._item_stats = {}
    gd._monster_level = {"chicken": 1}
    state = make_state(level=5)
    assert progression_reserve(state, gd) == 100   # _MIN_SAFETY_FLOOR
```

- [ ] **Step 2: Run to verify it fails.**

Run: `uv run pytest tests/test_ai/test_progression_reserve.py -q --no-cov -k minimum_safety`
Expected: FAIL (reserve is 0).

- [ ] **Step 3: Apply the minimum floor + remove GOLD_RESERVE**

In `src/artifactsmmo_cli/ai/progression_reserve.py`:

```python
_MIN_SAFETY_FLOOR = 100  # never spend to zero even when nothing is reserved
```

```python
def progression_reserve(state: WorldState, game_data: GameData) -> int:
    return max(_MIN_SAFETY_FLOOR, reserve_total(reserved_targets(state, game_data)))


def reserve_floor(state: WorldState, game_data: GameData,
                  buying: str | None) -> int:
    reserved = reserved_targets(state, game_data)
    return max(_MIN_SAFETY_FLOOR, effective_floor(reserved, buying))
```

In `src/artifactsmmo_cli/ai/craft_vs_buy.py`, delete the `GOLD_RESERVE = 500` constant and its docstring (Tasks 8-10 removed all importers). Verify no importers remain:

Run: `grep -rn GOLD_RESERVE src/ formal/ tests/`
Expected: no output.

- [ ] **Step 4: Run the full unit suite with coverage**

Run: `uv run pytest -q`
Expected: all pass, 100% coverage (the `--cov-fail-under` gate green). Add focused tests for any uncovered new lines (e.g. `buy_price` GE branch, `_is_gatherable` true/false, the boss stub) until coverage is 100%.

- [ ] **Step 5: Run the full formal gate (serialized)**

Run: `cd formal && ./gate.sh`
Expected: `ALL GATE PARTS PASSED` (kernel build, axioms, manifest, contracts, drift, differential incl. progression_reserve, mutation incl. progression_reserve). `git diff src` shows no stray mutation residue.

- [ ] **Step 6: Adversarial proof review (formal-development Phase 4)**

Read `formal/Formal/ProgressionReserve.lean` against reachable states: are the theorem statements honest (no vacuous hypotheses, the deduction identity is the real `floor + cost = total`, the differential calls the LIVE `effective_floor`/`affordable` not an inlined copy)? Confirm the mutation group actually kills via the differential. Fix any dishonest-proof finding at the source.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/progression_reserve.py src/artifactsmmo_cli/ai/craft_vs_buy.py tests/test_ai/test_progression_reserve.py
git commit -m "feat(ai): replace flat GOLD_RESERVE with calculated progression reserve"
```

- [ ] **Step 8: Update the audit tracker**

Mark #9 done in `docs/PLAN_calculate_not_hardcode.md` and the status log; commit `docs:`.

---

## Self-Review

**Spec coverage:** floor+deduction role (Task 1-4), gear source (Task 5), crafting-unlock (Task 6), boss stub (Task 7), all-3 gates uniform (Tasks 8-10), proven core + differential + mutation (Tasks 2-4), buy-only cost basis (Tasks 5-6 `acquisition_method` BUY gate + `buy_price`), +2 horizon (`_HORIZON`), migration/min-floor (Task 11). All covered.

**Placeholder scan:** the only deferred items are explicit (boss stub by design; the `<ge_fill_sell test>` / `<expand_bank test>` module names and the gathering buy-readout helper are to be matched to the existing test modules at implementation time — the test BODIES and assertions are concrete). The minimum-floor value is a stated decision (100) with an explicit alternative.

**Type consistency:** `reserved: Mapping[str,int]` / `dict[str,int]` throughout; `buying: str | None`; `buy_price -> int | None`; sources `-> dict[str,int]`; `reserve_floor -> int`. Lean `Reserved = List (String × Nat)`; oracle encodes codes as ints stringified on both sides. Consistent.
