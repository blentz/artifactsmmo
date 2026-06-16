"""Differential test: real Python `pick_loadout` must agree with the proved Lean
`pickSlot` on the SCORE of each slot's pick and the no-downgrade guarantee.

`pick_loadout` optimizes each equipment slot independently: it gathers owned items
that fit the slot AND are level-feasible (`_candidates_for_slot`), takes the
argmax-score candidate, and swaps to it ONLY on a STRICT score improvement over the
currently-equipped item (ties / downgrades keep the current item; an empty slot is
filled by any feasible candidate; no candidates leaves the slot as-is).

SURROGATE. Python scores are now EXACT integers, computed via the same surrogate
the Lean oracle uses: `weapon_score = Σ atk * max(0, 100 - res)` and
`armor_score = Σ mon_atk * armor_res`. Python and Lean compute IDENTICAL integers
for every input — this differential test now asserts BIT-EQUIVALENCE on the score
values themselves (no rescaling, no rounding). The old float-vs-Int order-preserving
caveat is closed.

TIE-BREAK NONDETERMINISM. Python `max(candidates, key=score)` over an unordered set
breaks ties arbitrarily; the Lean argmax keeps the earliest. So we do NOT assert a
specific tie-winner item. Instead we assert exactly what the theorems prove:
  * the SCORE of pick_loadout's chosen item for the slot equals the MAX feasible
    score (pickslot_score_optimal), and
  * the chosen score is ≥ the currently-equipped item's score (pickslot_no_downgrade).
We compute the Lean max/no-downgrade facts via the oracle (`max_score`, `cur_score`)
and compare against the Python-chosen item's score.

CONTROLLED STATS. A fake GameData returns crafted `ItemStats` from a fixed table and
fixed monster attack/resistance dicts. WorldState carries the inventory (owned item
codes), the equipment map (current per-slot codes), and the player level — exactly
the inputs `pick_loadout` / `_candidates_for_slot` read.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.equipment.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.scoring import armor_score, pick_loadout, weapon_score_raw
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.oracle_client import run_oracle

# Element key -> small int index, matching the Lean oracle's 0..3 element keys.
_ELEM_IDX = {e: i for i, e in enumerate(ELEMENTS)}

# A weapon slot (scored with weapon_score) vs every other (armor_score).
_WEAPON_SLOT = "weapon_slot"


class _FakeGameData:
    def __init__(self, table: dict[str, ItemStats],
                 monster_atk: dict[str, int], monster_res: dict[str, int]) -> None:
        self._table = table
        self._atk = monster_atk
        self._res = monster_res

    def item_stats(self, code: str | None) -> ItemStats | None:
        return self._table.get(code) if code else None

    def monster_attack(self, code: str) -> dict[str, int]:
        return dict(self._atk)

    def monster_resistance(self, code: str) -> dict[str, int]:
        return dict(self._res)


def _make_state(level: int, inventory: dict[str, int],
                equipment: dict[str, str | None]) -> WorldState:
    return WorldState(
        character="c", level=level, xp=0, max_xp=100, hp=10, max_hp=50,
        gold=0, skills={}, x=0, y=0, inventory=dict(inventory), inventory_max=1000,
        equipment=dict(equipment), cooldown_expires=None, task_code=None,
        task_type=None, task_progress=0, task_total=0,
        bank_items=None, bank_gold=None, pending_items=None,
        attack={}, dmg=0, dmg_elements={}, resistance={},
        critical_strike=0, initiative=0,
    )


def _elem_block(stats: ItemStats | None, which: str) -> list[int]:
    """4 element ints for a block (attack or resistance), 0-filled, 0 if None."""
    if stats is None:
        return [0, 0, 0, 0]
    d = stats.attack if which == "attack" else stats.resistance
    return [d.get(e, 0) for e in ELEMENTS]


def _item_block(code_id: int, stats: ItemStats | None, slot: str) -> list[int]:
    """13-int Lean Item block: [code, level, fits, atk0..3, res0..3, crit, flatUtil].
    flatUtil = hp_bonus + wisdom + prospecting (the monster-independent utility the
    armor/artifact score adds; novice_guide: 25+25+25 = 75)."""
    if stats is None:
        return [code_id, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    fits = 1 if slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []) else 0
    return [code_id, stats.level, fits, *_elem_block(stats, "attack"),
            *_elem_block(stats, "resistance"), stats.critical_strike,
            stats.hp_bonus + stats.wisdom + stats.prospecting]


def _py_score(stats: ItemStats, slot: str, monster_atk: dict, monster_res: dict) -> int:
    # Compare against RAW WScore (no nonToolBonus). The augmented combat
    # score (composite weapon_score) is verified in a separate diff against
    # the PurposeRouting.combatScore oracle.
    return (weapon_score_raw(stats, monster_res) if slot == _WEAPON_SLOT
            else armor_score(stats, monster_atk))


def _owned_codes(state: WorldState) -> set[str]:
    pool = {c for c, q in state.inventory.items() if q > 0}
    pool |= {c for c in state.equipment.values() if c}
    return pool


def _check(table, monster_atk, monster_res, level, inventory, equipment, slots):
    game_data = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level, inventory, equipment)
    result = pick_loadout("mon", state, game_data)

    # Intern codes to small ints so the Lean `changed`/identity guards line up.
    code_ids: dict[str, int] = {}

    def cid(code: str | None) -> int:
        if code is None:
            return -1
        if code not in code_ids:
            code_ids[code] = len(code_ids) + 1
        return code_ids[code]

    owned = _owned_codes(state)
    requests: list[list[int]] = []
    meta: list[tuple] = []
    for slot in slots:
        is_weapon = slot == _WEAPON_SLOT
        mon = monster_res if is_weapon else monster_atk
        args = [level, 0 if is_weapon else 1,
                *[mon.get(e, 0) for e in ELEMENTS]]
        cur_code = equipment.get(slot)
        cur_stats = table.get(cur_code) if cur_code else None
        cur_present = 1 if cur_stats is not None else 0
        args.append(cur_present)
        args += _item_block(cid(cur_code), cur_stats, slot)
        # Candidates: all owned items (the Lean `feasible` filter mirrors Python's
        # level + slot-fit filter, so we pass ALL owned items and let Lean filter).
        for code in sorted(owned):
            args += _item_block(cid(code), table.get(code), slot)
        requests.append(args)
        meta.append((slot, cur_stats))

    lean = run_oracle("equipment_scoring", requests)

    for (slot, cur_stats), res in zip(meta, lean, strict=True):
        is_weapon = slot == _WEAPON_SLOT
        chosen_code = result.get(slot)
        chosen_stats = table.get(chosen_code) if chosen_code else None
        # Python score is now the EXACT integer surrogate — same int as Lean.
        py_chosen_score = (_py_score(chosen_stats, slot, monster_atk, monster_res)
                           if chosen_stats is not None else None)

        feasible_exists = any(
            (st_.level <= level) and (slot in ITEM_TYPE_TO_SLOTS.get(st_.type_, []))
            for st_ in (table.get(c) for c in _owned_codes(state)) if st_ is not None
        )
        if feasible_exists:
            assert py_chosen_score is not None, (slot, chosen_code)
            # score-optimal + no-downgrade together (tie-order-independent): the
            # result's score is the BETTER of the max feasible candidate score and
            # the retained current item's score. This is exactly pickSlot's value:
            # swap to the feasible argmax iff it strictly beats current, else keep
            # current. Pinning to max(cur, best) covers both branches without
            # asserting any specific tie-winner item.
            assert py_chosen_score == max(res["max_score"], res["cur_score"]), \
                (slot, py_chosen_score, res)
        # no-downgrade (independent restatement): chosen score >= current's score.
        if py_chosen_score is not None:
            assert py_chosen_score >= res["cur_score"], (slot, py_chosen_score, res)
        else:
            # slot stays empty only when it was empty and no candidate exists
            assert res["cur_score"] == 0, (slot, res)


# ---- Property test: random tables, monsters, levels, inventories, equipment ----

_VAL = st.integers(min_value=0, max_value=30)
_RES = st.integers(min_value=0, max_value=120)  # >100 exercises the weapon clamp
_ITEM_CODES = ["i_a", "i_b", "i_c", "i_d", "i_e"]
# Types: a weapon and a body_armor so both score paths are exercised.
_TYPES = ["weapon", "body_armor"]


@settings(max_examples=250, deadline=None)
@given(
    mon_atk=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    mon_res=st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    level=st.integers(min_value=1, max_value=10),
    item_types=st.lists(st.sampled_from(_TYPES), min_size=len(_ITEM_CODES),
                        max_size=len(_ITEM_CODES)),
    item_levels=st.lists(st.integers(min_value=1, max_value=10),
                         min_size=len(_ITEM_CODES), max_size=len(_ITEM_CODES)),
    item_atks=st.lists(st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_ITEM_CODES), max_size=len(_ITEM_CODES)),
    item_ress=st.lists(st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_ITEM_CODES), max_size=len(_ITEM_CODES)),
    item_crits=st.lists(st.integers(min_value=0, max_value=100),
                        min_size=len(_ITEM_CODES), max_size=len(_ITEM_CODES)),
    inv_pick=st.lists(st.booleans(), min_size=len(_ITEM_CODES), max_size=len(_ITEM_CODES)),
    equip_w=st.sampled_from([*_ITEM_CODES, None]),
    equip_b=st.sampled_from([*_ITEM_CODES, None]),
)
def test_python_matches_lean(mon_atk, mon_res, level, item_types, item_levels,
                             item_atks, item_ress, item_crits, inv_pick,
                             equip_w, equip_b):
    table = {
        code: ItemStats(
            code=code, level=lvl, type_=ty,
            attack={e: a for e, a in zip(ELEMENTS, atk, strict=True)},
            resistance={e: r for e, r in zip(ELEMENTS, res, strict=True)},
            critical_strike=crit,
        )
        for code, ty, lvl, atk, res, crit in zip(
            _ITEM_CODES, item_types, item_levels, item_atks, item_ress,
            item_crits, strict=True)
    }
    monster_atk = {e: v for e, v in zip(ELEMENTS, mon_atk, strict=True)}
    monster_res = {e: v for e, v in zip(ELEMENTS, mon_res, strict=True)}
    inventory = {code: 1 for code, keep in zip(_ITEM_CODES, inv_pick, strict=True) if keep}
    # Post-fix realizability: pick_loadout's claimed-codes accumulator threads
    # across slots, so a code equipped into a SLOT IT DOESN'T FIT (a malformed
    # state) is claimed by that slot's fallback and becomes unavailable to its
    # natural slot. To keep this per-slot scoring test independent (the Lean
    # `pickslot` oracle has no cross-slot view), restrict each slot's current
    # code to items that actually fit it; otherwise the diff would compare
    # cross-slot-aware Python against per-slot-only Lean and (correctly) flag
    # them as different at malformed states.
    if equip_w is not None and table[equip_w].type_ != "weapon":
        equip_w = None
    if equip_b is not None and table[equip_b].type_ != "body_armor":
        equip_b = None
    equipment = {"weapon_slot": equip_w, "body_armor_slot": equip_b}
    _check(table, monster_atk, monster_res, level, inventory, equipment,
           ["weapon_slot", "body_armor_slot"])


# ---- Targeted scenario cases ----

def _table(*items: ItemStats) -> dict[str, ItemStats]:
    return {it.code: it for it in items}


def test_below_level_not_chosen():
    """A higher-scoring item ABOVE the player's level must NOT be chosen
    (feasibility). The feasible lower-score item wins instead."""
    table = _table(
        ItemStats(code="w_lo", level=1, type_="weapon", attack={"fire": 10}),
        ItemStats(code="w_hi", level=99, type_="weapon", attack={"fire": 99}),
    )
    monster_atk = {"fire": 5}
    monster_res = {"fire": 0}
    inventory = {"w_lo": 1, "w_hi": 1}
    equipment = {"weapon_slot": None, "body_armor_slot": None}
    game_data = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(5, inventory, equipment)
    result = pick_loadout("mon", state, game_data)
    assert result["weapon_slot"] == "w_lo"
    _check(table, monster_atk, monster_res, 5, inventory, equipment, ["weapon_slot"])


def test_utility_artifact_fills_empty_slot():
    """A utility-only ARTIFACT (no resistance, hp_bonus+wisdom+prospecting = 75)
    scores its flatUtil > 0, so pick_loadout fills the empty artifact slot instead
    of skipping it as a zero-score fill — and Python agrees with the Lean oracle.
    The novice_guide regression (was valued 0 → never equipped → discarded). Also
    EXERCISES the flatUtil term so a mutation dropping it is killed."""
    table = _table(
        ItemStats(code="novice_guide", level=1, type_="artifact",
                  hp_bonus=25, wisdom=25, prospecting=25),
    )
    monster_atk = {"fire": 5}
    monster_res = {"fire": 0}
    inventory = {"novice_guide": 1}
    equipment = {"artifact1_slot": None}
    game_data = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(10, inventory, equipment)
    result = pick_loadout("mon", state, game_data)
    assert result.get("artifact1_slot") == "novice_guide"
    _check(table, monster_atk, monster_res, 10, inventory, equipment, ["artifact1_slot"])


def test_upgrade_swaps():
    """A strictly better owned weapon replaces the equipped one."""
    table = _table(
        ItemStats(code="w_old", level=1, type_="weapon", attack={"fire": 5}),
        ItemStats(code="w_new", level=1, type_="weapon", attack={"fire": 20}),
    )
    monster_atk = {"fire": 3}
    monster_res = {"fire": 10}
    inventory = {"w_new": 1}
    equipment = {"weapon_slot": "w_old", "body_armor_slot": None}
    game_data = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(5, inventory, equipment)
    result = pick_loadout("mon", state, game_data)
    assert result["weapon_slot"] == "w_new"
    _check(table, monster_atk, monster_res, 5, inventory, equipment, ["weapon_slot"])


def test_downgrade_rejected():
    """A strictly worse owned weapon does NOT replace the equipped one."""
    table = _table(
        ItemStats(code="w_good", level=1, type_="weapon", attack={"fire": 30}),
        ItemStats(code="w_bad", level=1, type_="weapon", attack={"fire": 2}),
    )
    monster_atk = {"fire": 3}
    monster_res = {"fire": 0}
    inventory = {"w_bad": 1}
    equipment = {"weapon_slot": "w_good", "body_armor_slot": None}
    game_data = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(5, inventory, equipment)
    result = pick_loadout("mon", state, game_data)
    assert result["weapon_slot"] == "w_good"
    _check(table, monster_atk, monster_res, 5, inventory, equipment, ["weapon_slot"])


def test_empty_slot_fill():
    """An empty slot is filled by any feasible candidate."""
    table = _table(
        ItemStats(code="b_armor", level=1, type_="body_armor", resistance={"fire": 40}),
    )
    monster_atk = {"fire": 8}
    monster_res = {"fire": 0}
    inventory = {"b_armor": 1}
    equipment = {"weapon_slot": None, "body_armor_slot": None}
    game_data = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(5, inventory, equipment)
    result = pick_loadout("mon", state, game_data)
    assert result["body_armor_slot"] == "b_armor"
    _check(table, monster_atk, monster_res, 5, inventory, equipment, ["body_armor_slot"])


def test_weapon_clamp_high_resistance():
    """Monster resistance > 100 must clamp the weapon term at 0 (no negative score):
    a high-attack weapon vs a fully-resistant monster scores 0, not negative."""
    table = _table(
        ItemStats(code="w_big", level=1, type_="weapon", attack={"fire": 50}),
        ItemStats(code="w_small", level=1, type_="weapon", attack={"fire": 1}),
    )
    monster_atk = {"fire": 0}
    monster_res = {"fire": 120}  # > 100: clamp engages
    inventory = {"w_big": 1, "w_small": 1}
    equipment = {"weapon_slot": None, "body_armor_slot": None}
    # Both score 0 (clamped); the chosen score must equal the max (0), never negative.
    _check(table, monster_atk, monster_res, 5, inventory, equipment, ["weapon_slot"])
