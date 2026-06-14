"""Differential test for `Formal.Phase7Invariants` (Phase-7 batch: A, D, E).

Pins three contracts surfaced during the Phase-6 recon:

* **Target A — GatherMaterialsGoal._compute_base_value div-by-zero defense.**
  Probe: `needed = {a:-5, b:5}` summing to 0 reaches the divide pre-fix and
  raises `ZeroDivisionError`. Post-fix guard returns 0.0. The Lean
  `baseValue` models the structural shape; the differential agreement is
  exercised at the boundaries the Python reaches (positive totalNeeded, zero
  totalNeeded, negative totalNeeded).

* **Target D — EquipAction.is_applicable slot/type compatibility.**
  Pre-fix `is_applicable` only checked inventory + level. A slot/type mismatch
  (e.g. ring code into helmet slot) projected successfully but failed on the
  server. Post-fix adds the `slot ∈ ITEM_TYPE_TO_SLOTS[stats.type_]` gate.
  2026-06-10 extension: the code-already-worn gate (HTTP 485 "This item is
  already equipped") — a code worn in ANOTHER slot refuses; a DIFFERENT code
  in a sibling slot and own-slot re-equip stay legal (the Robby utility2
  livelock fix). Differential: the Lean `isApplicable` agrees with the Python
  on every combination of (inventory, level, slot, type, table, equipment).

* **Target E — WorldState property regression-locks.**
  Pin `inventory_used`, `inventory_free`, and the `hp_percent` div-zero guard.
"""
from fractions import Fraction

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.actions.equip import (
    DUPLICATE_SLOT_TYPES,
    EquipAction,
    ITEM_TYPE_TO_SLOTS,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.oracle_client import run_oracle


def _mkstate(
    inventory: dict[str, int] | None = None,
    inventory_max: int = 100,
    level: int = 1,
    hp: int = 100,
    max_hp: int = 100,
    bank_items: dict[str, int] | None = None,
    equipment: dict[str, str | None] | None = None,
) -> WorldState:
    return WorldState(
        character="probe", level=level, xp=0, max_xp=10, hp=hp, max_hp=max_hp, gold=0,
        skills={}, x=0, y=0,
        inventory=dict(inventory or {}),
        inventory_max=inventory_max,
        equipment=dict(equipment or {}),
        cooldown_expires=None,
        task_code=None, task_type=None,
        task_progress=0, task_total=0,
        bank_items=dict(bank_items or {}),
        bank_gold=0, pending_items=None,
    )


# ─── Target A: GatherMaterials div-by-zero guard ─────────────────────────────


def test_gather_total_needed_zero_returns_zero():
    """Pre-fix probe: needed sums to 0 but is_satisfied is False → ZeroDivisionError.
    Post-fix returns 0 (the guard catches `total_needed <= 0`)."""
    g = GatherMaterialsGoal(target_item="x", needed={"a": -5, "b": 5})
    state = _mkstate()
    gd = GameData()
    # The post-fix returns 0.0 without crashing.
    assert g.value(state, gd) == 0.0
    lean = run_oracle("phase7_invariants", [[0, 0, 0, 1]])[0]
    # Lean baseValue(0, 0) = 0.
    assert lean["value_num"] == 0


def test_gather_total_needed_negative_returns_zero():
    """Pre-fix: negative totalNeeded would also divide (1 - x/-n). The guard
    catches the `<= 0` branch."""
    g = GatherMaterialsGoal(target_item="x", needed={"a": -3})
    state = _mkstate()
    gd = GameData()
    assert g.value(state, gd) == 0.0
    lean = run_oracle("phase7_invariants", [[0, -3, 0, 1]])[0]
    assert lean["value_num"] == 0


@settings(max_examples=200)
@given(
    needed_qty=st.integers(min_value=1, max_value=50),
    have_qty=st.integers(min_value=0, max_value=50),
)
def test_gather_positive_branch_matches_lean(needed_qty, have_qty):
    """Positive `total_needed` branch: Python and Lean agree on the clamped
    value. The Python `_compute_base_value` is `max(1.0, 40 * (1 - effective /
    needed))` where `effective = min(have, needed)`. The Lean `baseValue`
    matches this exactly (in the positive-totalNeeded branch)."""
    # target_item must differ from the material code: holding >=1 of the
    # finished target trips is_satisfied's finished-target short-circuit
    # (ash-wood preemption fix), which would zero the value upstream of the
    # baseValue math under test.
    g = GatherMaterialsGoal(target_item="x", needed={"mat": needed_qty})
    state = _mkstate(inventory={"mat": have_qty})
    gd = GameData()
    py = g.value(state, gd)
    # If satisfied, Python returns 0; Lean (with effective >= needed) gives
    # max(1, 40 * (1 - 1)) = max(1, 0) = 1 — these don't agree at boundary.
    # The is_satisfied early-exit is upstream of the structural baseValue
    # model, so we only test the unsatisfied positive branch.
    if have_qty >= needed_qty:
        assert py == 0.0
        return
    # Unsatisfied: Python's effective = min(have, needed) = have.
    effective_frac = Fraction(have_qty, 1)
    lean = run_oracle(
        "phase7_invariants",
        [[0, needed_qty, effective_frac.numerator, effective_frac.denominator]],
    )[0]
    # Reconstruct the Lean rational and compare to Python's float.
    lean_val = Fraction(lean["value_num"], lean["value_den"])
    # Python computes: max(1.0, 40 * (1 - have/needed))
    expected = max(1.0, 40.0 * (1 - have_qty / needed_qty))
    assert abs(float(lean_val) - expected) < 1e-9
    assert abs(py - expected) < 1e-9


# ─── Target D: EquipAction slot/type gate ────────────────────────────────────


def _mk_gd_with_item(code: str, item_type: str, level: int = 1) -> GameData:
    gd = GameData()
    gd._item_stats = {
        code: ItemStats(code=code, level=level, type_=item_type),
    }
    return gd


def test_equip_slot_mismatch_refused():
    """Target D regression-pin: a ring code attempted into a helmet slot must
    be refused post-fix. Pre-fix this projected through."""
    gd = _mk_gd_with_item("ring_x", "ring", level=1)
    state = _mkstate(inventory={"ring_x": 1}, level=1)
    action = EquipAction(code="ring_x", slot="helmet_slot")
    assert action.is_applicable(state, gd) is False


def test_equip_slot_match_accepted():
    """Boundary witness: a ring code into a ring slot is accepted."""
    gd = _mk_gd_with_item("ring_x", "ring", level=1)
    state = _mkstate(inventory={"ring_x": 1}, level=1)
    action = EquipAction(code="ring_x", slot="ring1_slot")
    assert action.is_applicable(state, gd) is True


def test_equip_no_inventory_refused():
    gd = _mk_gd_with_item("ring_x", "ring", level=1)
    state = _mkstate(inventory={}, level=1)
    action = EquipAction(code="ring_x", slot="ring1_slot")
    assert action.is_applicable(state, gd) is False


def test_equip_level_short_refused():
    gd = _mk_gd_with_item("ring_x", "ring", level=10)
    state = _mkstate(inventory={"ring_x": 1}, level=1)
    action = EquipAction(code="ring_x", slot="ring1_slot")
    assert action.is_applicable(state, gd) is False


# The Lean model inputs: (inv, level, slot, type, equipment). The Lean tbl is
# constructed from ITEM_TYPE_TO_SLOTS for the queried type; equipment is the
# worn (slot, code) map with only OCCUPIED slots encoded (Python's None-valued
# empty slots can never equal a real item code).
_TYPE_TO_INT = {"weapon": 0, "shield": 1, "helmet": 2, "body_armor": 3,
                "leg_armor": 4, "boots": 5, "ring": 6, "amulet": 7,
                "artifact": 8, "utility": 9, "bag": 10, "rune": 11}
_SLOT_TO_INT = {
    "weapon_slot": 100, "shield_slot": 101, "helmet_slot": 102,
    "body_armor_slot": 103, "leg_armor_slot": 104, "boots_slot": 105,
    "ring1_slot": 106, "ring2_slot": 107, "amulet_slot": 108,
    "artifact1_slot": 109, "artifact2_slot": 110, "artifact3_slot": 111,
    "utility1_slot": 112, "utility2_slot": 113, "bag_slot": 114, "rune_slot": 115,
}
_CODE_TO_INT = {"probe_item": 500, "other_item": 501}


def _equip_args(
    inv_qty: int, char_level: int, item_level: int, item_type: str, slot: str,
    code: str, equipment: dict[str, str | None],
) -> list[int]:
    """Encode one isApplicable probe as oracle args (sub-query 1)."""
    slot_ints = [_SLOT_TO_INT[s] for s in ITEM_TYPE_TO_SLOTS.get(item_type, [])]
    pairs: list[int] = []
    for eq_slot, eq_code in equipment.items():
        if eq_code is not None:
            pairs.extend([_SLOT_TO_INT[eq_slot], _CODE_TO_INT[eq_code]])
    return [1, inv_qty, char_level, 1, _TYPE_TO_INT[item_type], item_level,
            _SLOT_TO_INT[slot], len(slot_ints), *slot_ints,
            _CODE_TO_INT[code], len(pairs) // 2, *pairs,
            int(item_type in DUPLICATE_SLOT_TYPES)]


def test_equip_code_worn_elsewhere_refused():
    """2026-06-10 regression-pin (the Robby utility2 livelock): the candidate
    code already worn in utility1 refuses a second copy into the empty
    utility2 — pre-fix this projected through and 485'd forever."""
    gd = _mk_gd_with_item("probe_item", "utility", level=1)
    state = _mkstate(inventory={"probe_item": 1}, level=1,
                     equipment={"utility1_slot": "probe_item"})
    action = EquipAction(code="probe_item", slot="utility2_slot")
    assert action.is_applicable(state, gd) is False
    args = _equip_args(1, 1, 1, "utility", "utility2_slot", "probe_item",
                       {"utility1_slot": "probe_item"})
    assert run_oracle("phase7_invariants", [args])[0]["applicable"] is False


def test_equip_different_code_sibling_accepted():
    """Boundary witness promised by the gate's comment: a DIFFERENT code in
    the sibling utility slot does not block the equip."""
    gd = _mk_gd_with_item("probe_item", "utility", level=1)
    state = _mkstate(inventory={"probe_item": 1}, level=1,
                     equipment={"utility1_slot": "other_item"})
    action = EquipAction(code="probe_item", slot="utility2_slot")
    assert action.is_applicable(state, gd) is True
    args = _equip_args(1, 1, 1, "utility", "utility2_slot", "probe_item",
                       {"utility1_slot": "other_item"})
    assert run_oracle("phase7_invariants", [args])[0]["applicable"] is True


def test_equip_own_slot_reequip_accepted():
    """Own-slot exemption: the code worn in the TARGET slot itself (utility
    stacking / re-equip) is not 'worn elsewhere'; with a spare copy held the
    precondition still accepts."""
    gd = _mk_gd_with_item("probe_item", "utility", level=1)
    state = _mkstate(inventory={"probe_item": 1}, level=1,
                     equipment={"utility1_slot": "probe_item"})
    action = EquipAction(code="probe_item", slot="utility1_slot")
    assert action.is_applicable(state, gd) is True
    args = _equip_args(1, 1, 1, "utility", "utility1_slot", "probe_item",
                       {"utility1_slot": "probe_item"})
    assert run_oracle("phase7_invariants", [args])[0]["applicable"] is True


def test_equip_ring_worn_elsewhere_with_spare_accepted():
    """2026-06-14 ring carve-out: a 2nd identical ring (dup-allowed type) whose
    code is already worn in ring1 is NOT blocked from ring2 — the live probe
    proved the server returns HTTP 200. The inventory clause requires a spare,
    which is present (inv_qty 1), so both Python and the Lean oracle accept."""
    gd = _mk_gd_with_item("probe_item", "ring", level=1)
    state = _mkstate(inventory={"probe_item": 1}, level=1,
                     equipment={"ring1_slot": "probe_item"})
    action = EquipAction(code="probe_item", slot="ring2_slot")
    assert action.is_applicable(state, gd) is True
    args = _equip_args(1, 1, 1, "ring", "ring2_slot", "probe_item",
                       {"ring1_slot": "probe_item"})
    assert run_oracle("phase7_invariants", [args])[0]["applicable"] is True


def test_equip_ring_worn_elsewhere_no_spare_refused():
    """The ring carve-out lifts only the worn-elsewhere gate, not the inventory
    gate: with NO spare copy held (inv_qty 0) the equip is refused by both
    Python and the Lean oracle — the realizability cap (a physical spare must
    exist) still bites, mirroring Formal.RealizableLoadout's ownership cap."""
    gd = _mk_gd_with_item("probe_item", "ring", level=1)
    state = _mkstate(inventory={}, level=1,
                     equipment={"ring1_slot": "probe_item"})
    action = EquipAction(code="probe_item", slot="ring2_slot")
    assert action.is_applicable(state, gd) is False
    args = _equip_args(0, 1, 1, "ring", "ring2_slot", "probe_item",
                       {"ring1_slot": "probe_item"})
    assert run_oracle("phase7_invariants", [args])[0]["applicable"] is False


@settings(max_examples=200, deadline=None)
@given(
    inv_qty=st.integers(min_value=0, max_value=5),
    char_level=st.integers(min_value=1, max_value=20),
    item_level=st.integers(min_value=1, max_value=20),
    item_type=st.sampled_from(list(_TYPE_TO_INT.keys())),
    slot=st.sampled_from(list(_SLOT_TO_INT.keys())),
    equipment=st.dictionaries(
        keys=st.sampled_from(list(_SLOT_TO_INT.keys())),
        values=st.sampled_from([None, "probe_item", "other_item"]),
        max_size=4,
    ),
)
def test_equip_matches_lean(inv_qty, char_level, item_level, item_type, slot, equipment):
    code = "probe_item"
    gd = _mk_gd_with_item(code, item_type, level=item_level)
    inv = {code: inv_qty} if inv_qty > 0 else {}
    state = _mkstate(inventory=inv, level=char_level, equipment=equipment)
    action = EquipAction(code=code, slot=slot)
    py = action.is_applicable(state, gd)
    args = _equip_args(inv_qty, char_level, item_level, item_type, slot, code, equipment)
    lean = run_oracle("phase7_invariants", [args])[0]
    assert py == lean["applicable"]


# ─── Target E: WorldState property regression-locks ──────────────────────────


@settings(max_examples=200)
@given(
    inv_qtys=st.lists(st.integers(min_value=0, max_value=100), min_size=0, max_size=10),
    inv_max=st.integers(min_value=0, max_value=200),
    hp=st.integers(min_value=0, max_value=500),
    max_hp=st.integers(min_value=0, max_value=500),
)
def test_world_state_used_free_matches_lean(inv_qtys, inv_max, hp, max_hp):
    inventory = {f"item_{i}": q for i, q in enumerate(inv_qtys) if q > 0}
    state = _mkstate(inventory=inventory, inventory_max=inv_max, hp=hp, max_hp=max_hp)
    # Build the Lean args: [2, subq=0, nInv, code0, qty0, …, invMax, hp, maxHp].
    inv_flat = []
    for i, q in enumerate(inv_qtys):
        if q > 0:
            inv_flat.extend([i, q])
    n_inv = len(inv_flat) // 2
    used_args = [2, 0, n_inv, *inv_flat, inv_max, hp, max_hp]
    free_args = [2, 1, n_inv, *inv_flat, inv_max, hp, max_hp]
    hp_args = [2, 2, n_inv, *inv_flat, inv_max, hp, max_hp]
    out = run_oracle("phase7_invariants", [used_args, free_args, hp_args])
    used_lean = out[0]["used"]
    free_lean = out[1]["free"]
    hp_num = out[2]["hp_percent_num"]
    hp_den = out[2]["hp_percent_den"]
    assert state.inventory_used == used_lean
    # Python's inventory_free can go negative if max < used; Lean's is Nat
    # (truncated). The Phase-6 fix ensures producers never overflow, but the
    # property itself uses signed Int. We compare via the bookkeeping equality
    # when used <= max.
    if state.inventory_used <= inv_max:
        assert state.inventory_free == free_lean
    # hp_percent: Python returns 1.0 when max_hp == 0 else hp/max_hp.
    if max_hp == 0:
        assert state.hp_percent == 1.0
        assert Fraction(hp_num, hp_den) == 1
    else:
        py_frac = Fraction(hp, max_hp)
        assert Fraction(hp_num, hp_den) == py_frac
        assert abs(state.hp_percent - hp / max_hp) < 1e-9


def test_world_state_max_hp_zero_returns_one():
    """Regression-pin for the hp_percent div-zero guard."""
    state = _mkstate(hp=0, max_hp=0)
    assert state.hp_percent == 1.0
    lean = run_oracle("phase7_invariants", [[2, 2, 0, 0, 0, 0]])[0]
    assert Fraction(lean["hp_percent_num"], lean["hp_percent_den"]) == 1


def test_world_state_inventory_free_at_full_is_zero():
    """Regression-pin: at used = max, free = 0 (Phase-6 chain_safe corollary)."""
    state = _mkstate(inventory={"x": 10}, inventory_max=10)
    assert state.inventory_used == 10
    assert state.inventory_free == 0
    free_args = [2, 1, 1, 0, 10, 10, 10, 10]
    out = run_oracle("phase7_invariants", [free_args])
    assert out[0]["free"] == 0
