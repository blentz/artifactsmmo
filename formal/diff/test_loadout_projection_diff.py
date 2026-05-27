"""Differential test: real Python `project_loadout_stats` must agree with the
proved Lean `projectedField` on EVERY projected stat field.

The Python routine computes projected combat stats as a delta from current
totals: for each loadout slot whose picked item differs from the equipped item
(`new_code == old_code: continue`), it adds the picked item's contribution and
subtracts the equipped item's contribution to each field. Per field:

    projected.field = current.field + Σ_changed_slot (new.field − old.field)

CONTROLLED ITEM STATS. We construct a fake `GameData` whose `item_stats` returns
crafted `ItemStats` from a fixed table (item_code -> ItemStats), and a
`WorldState` with crafted current totals + equipment. Loadouts map slot ->
item_code | None. This isolates the differential against fully known inputs.

For each field/element we build the Lean oracle args
`[current, (newCode, oldCode, newC, oldC) per slot]` where codes are interned to
ints (so `new == old` matches the Python `new_code == old_code` guard) and the
contributions are the resolved per-field values (0 for a `None` / absent item or
absent element). We then assert the Lean `projected` equals Python's field value,
treating dropped-zero element keys as 0 (`dict.get(k, 0)`), which is exactly the
pre-drop accumulator the Lean model computes.

Cases covered: identity (loadout = equipment), single swap, double swap,
unequip (new = None), equip into empty slot (old = None), and downgrade (a
picked item strictly worse than the equipped one -> negative deltas).
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.world_state import ELEMENTS, WorldState
from formal.diff.oracle_client import run_oracle

# A fixed slot set (a subset of the real loadout keys; the projection is uniform
# over slots). Each slot may hold one of several item codes or None.
SLOTS = ["weapon", "helmet", "body_armor", "ring1"]

# Item codes used; interned to small ints for the Lean `changed` guard. None ->
# a distinct sentinel int so "no item in this slot" never accidentally equals a
# real code (and equals itself, so None==None is unchanged).
_CODE_IDS: dict[str | None, int] = {None: 0}


def _code_id(code: str | None) -> int:
    if code not in _CODE_IDS:
        _CODE_IDS[code] = len(_CODE_IDS)
    return _CODE_IDS[code]


def _make_item(code: str, vals: dict) -> ItemStats:
    """Craft an ItemStats with per-element attack/dmg_elements/resistance and the
    scalar fields, drawn from `vals` (a dict of small ints)."""
    return ItemStats(
        code=code,
        level=1,
        type_="weapon",
        attack={e: vals[f"attack_{e}"] for e in ELEMENTS if vals.get(f"attack_{e}", 0)},
        resistance={e: vals[f"res_{e}"] for e in ELEMENTS if vals.get(f"res_{e}", 0)},
        dmg=vals.get("dmg", 0),
        dmg_elements={e: vals[f"dmg_{e}"] for e in ELEMENTS if vals.get(f"dmg_{e}", 0)},
        critical_strike=vals.get("critical_strike", 0),
        initiative=vals.get("initiative", 0),
        hp_bonus=vals.get("hp_bonus", 0),
    )


class _FakeGameData:
    def __init__(self, table: dict[str, ItemStats]) -> None:
        self._table = table

    def item_stats(self, code: str | None) -> ItemStats | None:
        return self._table.get(code) if code else None


def _make_state(equipment: dict[str, str | None], current: dict) -> WorldState:
    return WorldState(
        character="c", level=1, xp=0, max_xp=100, hp=10, max_hp=current["max_hp"],
        gold=0, skills={}, x=0, y=0, inventory={}, inventory_max=1000,
        equipment=equipment, cooldown_expires=None, task_code=None,
        task_type=None, task_progress=0, task_total=0,
        bank_items=None, bank_gold=None, pending_items=None,
        attack=dict(current["attack"]), dmg=current["dmg"],
        dmg_elements=dict(current["dmg_elements"]), resistance=dict(current["resistance"]),
        critical_strike=current["critical_strike"], initiative=current["initiative"],
    )


def _item_contrib(stats: ItemStats | None, field: str, elem: str | None) -> int:
    """Resolve one item's contribution to one (field[, elem]), 0 if None/absent."""
    if stats is None:
        return 0
    if field == "attack":
        return stats.attack.get(elem, 0)
    if field == "dmg_elements":
        return stats.dmg_elements.get(elem, 0)
    if field == "resistance":
        return stats.resistance.get(elem, 0)
    if field == "dmg":
        return stats.dmg
    if field == "critical_strike":
        return stats.critical_strike
    if field == "initiative":
        return stats.initiative
    if field == "max_hp":
        return stats.hp_bonus
    raise AssertionError(field)


def _current_field(current: dict, field: str, elem: str | None) -> int:
    if field == "attack":
        return current["attack"].get(elem, 0)
    if field == "dmg_elements":
        return current["dmg_elements"].get(elem, 0)
    if field == "resistance":
        return current["resistance"].get(elem, 0)
    if field == "dmg":
        return current["dmg"]
    if field == "critical_strike":
        return current["critical_strike"]
    if field == "initiative":
        return current["initiative"]
    if field == "max_hp":
        return current["max_hp"]
    raise AssertionError(field)


def _projected_field(proj, field: str, elem: str | None) -> int:
    """Read a projected field, treating dropped-zero element keys as 0."""
    if field == "attack":
        return proj.attack.get(elem, 0)
    if field == "dmg_elements":
        return proj.dmg_elements.get(elem, 0)
    if field == "resistance":
        return proj.resistance.get(elem, 0)
    if field == "dmg":
        return proj.dmg
    if field == "critical_strike":
        return proj.critical_strike
    if field == "initiative":
        return proj.initiative
    if field == "max_hp":
        return proj.max_hp
    raise AssertionError(field)


# All (field, elem) pairs the projection emits.
FIELDS: list[tuple[str, str | None]] = (
    [("attack", e) for e in ELEMENTS]
    + [("dmg_elements", e) for e in ELEMENTS]
    + [("resistance", e) for e in ELEMENTS]
    + [("dmg", None), ("critical_strike", None), ("initiative", None), ("max_hp", None)]
)


def _check(table, equipment, loadout, current):
    game_data = _FakeGameData(table)
    state = _make_state(equipment, current)
    proj = project_loadout_stats(state, loadout, game_data)

    # Build one oracle request per field; batch them.
    requests: list[list[int]] = []
    for field, elem in FIELDS:
        cur = _current_field(current, field, elem)
        args = [cur]
        for slot in SLOTS:
            new_code = loadout.get(slot)
            old_code = equipment.get(slot)
            new_s = table.get(new_code) if new_code else None
            old_s = table.get(old_code) if old_code else None
            args += [
                _code_id(new_code), _code_id(old_code),
                _item_contrib(new_s, field, elem),
                _item_contrib(old_s, field, elem),
            ]
        requests.append(args)

    lean = run_oracle("loadout_projection", requests)
    for (field, elem), res in zip(FIELDS, lean, strict=True):
        py_val = _projected_field(proj, field, elem)
        assert py_val == res["projected"], (field, elem, py_val, res["projected"])


_VAL = st.integers(min_value=-20, max_value=20)
_FIELD_KEYS = (
    [f"attack_{e}" for e in ELEMENTS]
    + [f"dmg_{e}" for e in ELEMENTS]
    + [f"res_{e}" for e in ELEMENTS]
    + ["dmg", "critical_strike", "initiative", "hp_bonus"]
)


@st.composite
def _vals(draw):
    return {k: draw(_VAL) for k in _FIELD_KEYS}


# A pool of item codes; each slot's equipped / loadout pick is chosen from the
# pool or None (unequip / empty).
_ITEM_CODES = ["i_a", "i_b", "i_c", "i_d", "i_e"]


@settings(max_examples=250, deadline=None)
@given(
    table_vals=st.lists(_vals(), min_size=len(_ITEM_CODES), max_size=len(_ITEM_CODES)),
    equipment_pick=st.lists(st.sampled_from([*_ITEM_CODES, None]),
                            min_size=len(SLOTS), max_size=len(SLOTS)),
    loadout_pick=st.lists(st.sampled_from([*_ITEM_CODES, None]),
                          min_size=len(SLOTS), max_size=len(SLOTS)),
    cur_attack=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    cur_dmg_el=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    cur_res=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    cur_dmg=_VAL, cur_crit=_VAL, cur_init=_VAL,
    cur_max_hp=st.integers(min_value=1, max_value=200),
)
def test_python_matches_lean(table_vals, equipment_pick, loadout_pick,
                             cur_attack, cur_dmg_el, cur_res,
                             cur_dmg, cur_crit, cur_init, cur_max_hp):
    table = {code: _make_item(code, vals)
             for code, vals in zip(_ITEM_CODES, table_vals, strict=True)}
    equipment = {slot: pick for slot, pick in zip(SLOTS, equipment_pick, strict=True)}
    loadout = {slot: pick for slot, pick in zip(SLOTS, loadout_pick, strict=True)}
    current = {
        "attack": {e: v for e, v in zip(ELEMENTS, cur_attack, strict=True) if v},
        "dmg_elements": {e: v for e, v in zip(ELEMENTS, cur_dmg_el, strict=True) if v},
        "resistance": {e: v for e, v in zip(ELEMENTS, cur_res, strict=True) if v},
        "dmg": cur_dmg, "critical_strike": cur_crit, "initiative": cur_init,
        "max_hp": cur_max_hp,
    }
    _check(table, equipment, loadout, current)


def _flat_current(attack=None, dmg_el=None, res=None, dmg=0, crit=0, init=0, max_hp=50):
    return {
        "attack": attack or {}, "dmg_elements": dmg_el or {}, "resistance": res or {},
        "dmg": dmg, "critical_strike": crit, "initiative": init, "max_hp": max_hp,
    }


def test_identity_projects_to_current():
    """loadout = equipment -> projected = current (every field)."""
    table = {
        "i_a": _make_item("i_a", {"attack_fire": 5, "dmg": 3, "hp_bonus": 10,
                                  "critical_strike": 2, "initiative": 1, "res_air": 4}),
    }
    equipment = {"weapon": "i_a", "helmet": None, "body_armor": None, "ring1": None}
    loadout = dict(equipment)
    current = _flat_current(attack={"fire": 12}, res={"air": 7}, dmg=8,
                            crit=5, init=3, max_hp=40)
    _check(table, equipment, loadout, current)


def test_single_swap():
    """One slot changes weapon -> per-field delta = new − old."""
    table = {
        "i_a": _make_item("i_a", {"attack_fire": 5, "dmg": 2}),
        "i_b": _make_item("i_b", {"attack_fire": 9, "dmg": 1, "attack_water": 3}),
    }
    equipment = {"weapon": "i_a", "helmet": None, "body_armor": None, "ring1": None}
    loadout = {"weapon": "i_b", "helmet": None, "body_armor": None, "ring1": None}
    current = _flat_current(attack={"fire": 20}, dmg=10, max_hp=30)
    _check(table, equipment, loadout, current)


def test_double_swap():
    """Two slots change simultaneously -> deltas sum across slots."""
    table = {
        "i_a": _make_item("i_a", {"attack_fire": 5}),
        "i_b": _make_item("i_b", {"attack_fire": 9}),
        "i_c": _make_item("i_c", {"res_earth": 4, "hp_bonus": 6}),
        "i_d": _make_item("i_d", {"res_earth": 1, "hp_bonus": 2}),
    }
    equipment = {"weapon": "i_a", "helmet": "i_c", "body_armor": None, "ring1": None}
    loadout = {"weapon": "i_b", "helmet": "i_d", "body_armor": None, "ring1": None}
    current = _flat_current(attack={"fire": 15}, res={"earth": 9}, max_hp=50)
    _check(table, equipment, loadout, current)


def test_unequip_new_none():
    """Picking None for an equipped slot subtracts the old item's contribution."""
    table = {"i_a": _make_item("i_a", {"attack_fire": 5, "hp_bonus": 10, "dmg": 4})}
    equipment = {"weapon": "i_a", "helmet": None, "body_armor": None, "ring1": None}
    loadout = {"weapon": None, "helmet": None, "body_armor": None, "ring1": None}
    current = _flat_current(attack={"fire": 11}, dmg=9, max_hp=45)
    _check(table, equipment, loadout, current)


def test_equip_into_empty():
    """Equipping into a previously empty slot adds the new item's contribution."""
    table = {"i_b": _make_item("i_b", {"attack_water": 7, "critical_strike": 3})}
    equipment = {"weapon": None, "helmet": None, "body_armor": None, "ring1": None}
    loadout = {"weapon": "i_b", "helmet": None, "body_armor": None, "ring1": None}
    current = _flat_current(attack={"water": 4}, crit=10)
    _check(table, equipment, loadout, current)


def test_downgrade_negative_delta():
    """A strictly worse pick yields negative deltas (kept, not floored, in the
    accumulator); max_hp may fall below current. Pins the negative path."""
    table = {
        "i_strong": _make_item("i_strong", {"attack_fire": 20, "hp_bonus": 30, "dmg": 12}),
        "i_weak": _make_item("i_weak", {"attack_fire": 2, "hp_bonus": 1, "dmg": 1}),
    }
    equipment = {"weapon": "i_strong", "helmet": None, "body_armor": None, "ring1": None}
    loadout = {"weapon": "i_weak", "helmet": None, "body_armor": None, "ring1": None}
    current = _flat_current(attack={"fire": 25}, dmg=15, max_hp=60)
    _check(table, equipment, loadout, current)
