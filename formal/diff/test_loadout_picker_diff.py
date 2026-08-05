"""Differential: the purpose-generalized live ``pick_loadout`` / ``_benefit``
per-slot selection must agree with the proved Lean
``Formal.GearValue.pickSlotForPurpose`` / ``purposeBenefit`` (the UNIFIED picker)
over a random purpose + owned-item pool.

WHAT THIS BINDS. Task 3 generalized the per-monster picker to a per-task
``Purpose`` (Combat / Gather / Rank) and re-proved per-slot optimality ∀ purpose
(``pickSlot_score_optimal_purpose``). This test runs the live picker against the
NEW oracle kind ``loadout_picker`` (``Oracle.runLoadoutPicker``), which evaluates
the HAND ``pickSlotForPurpose`` / ``purposeBenefit`` defs — closing the model↔code
loop for the two LIVE-WIRED purposes:

* **Gather** (the genuinely new live behavior — ``GatherAction.cost`` penalty +
  ``OptimizeLoadout(Gather)``). The benefit is ``-gather_score`` on BOTH sides
  (no augmentation), so the comparison is BIT-EXACT and directly exercises the
  ``_benefit`` Gather NEGATION. Dropping the negation makes the picker choose the
  WORST tool — caught here.
* **Combat** (the 4 combat callers route through ``Combat(monster)``). The live
  ``_benefit(Combat)`` for the weapon slot is the AUGMENTED ``weapon_score``
  (``2*WScore + nonToolBonus``); the oracle's combat benefit is the RAW
  ``WScore``. The augmentation is an order-preserving ``2x + c`` transform, so the
  argmax/no-downgrade DECISION is invariant — we assert at the RAW score level
  (the established ``equipment_scoring`` convention): the chosen item's
  ``weapon_score_raw`` equals the oracle's max-feasible / no-downgrade benefit.

RANK COVERAGE — BINDING. The Lean ``Purpose.rank`` carries an ABSTRACT
``rankOf : Item → Int``; it is instantiated at ``Formal.GearValue.rankValue``,
which IS ``combatValue`` against the canonical adversary and therefore reads
exactly the 18-int oracle ``Item`` block. The retired flat Rank stat sum needed 6
EXTRA out-of-block ints per item (``[combat_raw, wisdom, prospecting,
inventory_space, haste, is_tool]``, stride 26) because a stat sum has a breakdown
the ``Item`` record aggregates away into one ``flatUtil``; a monster-relative
score does not, so Rank and Combat now share ONE 20-int layout. The value-level
differential (``test_gear_value_diff.py::test_rank_matches_oracle``) pins the same
def. The
first LIVE caller ``EquipOwnedGoal`` picks a loadout with the Rank purpose (every
prior ``pick_loadout`` call site used ``Combat`` or ``Gather``), so the Rank
picker DECISION now has live behavior; ``test_rank_pick_matches_lean`` binds the
live ``pick_loadout(Rank)`` per-slot pick to the proved
``Formal.GearValue.pickSlot_purpose_rank_optimal`` benefit, BIT-EXACT — no
unproven Rank decision logic ships.

TIE-BREAK / SURROGATE NOTES carry over from ``test_equipment_scoring_diff.py``:
Python ``max(..., key=...)`` over an unordered set breaks ties arbitrarily while
the Lean ``argmaxBy`` keeps the earliest, so we assert the SCORE/BENEFIT of the
pick (== the proved optimal value), never a specific tie-winner item.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.equipment.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.loadout_picker import _benefit, pick_loadout
from artifactsmmo_cli.ai.equipment.scoring import armor_score, gather_score, weapon_score_raw
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather, Rank
from artifactsmmo_cli.ai.world_state import WorldState
from formal.diff.oracle_client import run_oracle

_WEAPON_SLOT = "weapon_slot"
_ARTIFACT_SLOT = "artifact1_slot"
_UTILITY_FILL_TYPES = frozenset({"artifact"})
_ELEM_IDX = {e: i for i, e in enumerate(ELEMENTS)}


class _FakeGameData:
    def __init__(self, table: dict[str, ItemStats]) -> None:
        self._table = table

    def item_stats(self, code: str | None) -> ItemStats | None:
        return self._table.get(code) if code else None


def _make_state(level: int, inventory: dict[str, int],
                equipment: dict[str, str | None],
                player_attack: dict[str, int] | None = None) -> WorldState:
    return WorldState(
        character="c", level=level, xp=0, max_xp=100, hp=10, max_hp=50,
        gold=0, skills={}, x=0, y=0, inventory=dict(inventory), inventory_max=1000,
        inventory_slots_max=1000,
        equipment=dict(equipment), cooldown_expires=None, task_code=None,
        task_type=None, task_progress=0, task_total=0,
        bank_items=None, bank_gold=None, pending_items=None,
        attack=dict(player_attack or {}), dmg=0, dmg_elements={}, resistance={},
        critical_strike=0, initiative=0,
    )


def _elem_block(stats: ItemStats | None, which: str) -> list[int]:
    if stats is None:
        return [0, 0, 0, 0]
    d = {"attack": stats.attack, "resistance": stats.resistance,
         "dmg_elements": stats.dmg_elements}[which]
    return [d.get(e, 0) for e in ELEMENTS]


def _item_block(code_id: int, stats: ItemStats | None, slot: str,
                skill: str | None) -> list[int]:
    """21-int extended Lean block: 18-int item block + skillEffect +
    isUtilityFill + isTool.

    flatUtil aggregates the monster-independent utility stats (== the Python
    armor/utility flat term); ``dmg`` + ``dmgElem0..3`` are the OFFENSE inputs the
    armor score prices a piece with; skillEffect is the signed per-skill gather
    effect (``gather_score``) the abstract Gather benefit reads, 0 when no skill;
    isUtilityFill flags the artifact-type utility-fill items whose Gather benefit
    is the flat utility (``armor_score(stats, {}, {}, {})``) rather than
    ``-gather_score``; isTool is the `subtype == "tool"` flag
    `PurposeRouting.CombatItem` carries, which the Rank benefit's `nonToolBonus`
    reads (the fishing_net tiebreak).
    """
    if stats is None:
        return [code_id, *([0] * 20)]
    fits = 1 if slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []) else 0
    flat = (stats.hp_restore + stats.hp_bonus + stats.wisdom + stats.prospecting
            + stats.inventory_space + stats.haste + stats.lifesteal
            + stats.combat_buff)
    eff = gather_score(stats, skill) if skill is not None else 0
    is_utility_fill = 1 if stats and stats.type_ in _UTILITY_FILL_TYPES else 0
    return [code_id, stats.level, fits, *_elem_block(stats, "attack"),
            *_elem_block(stats, "resistance"), stats.critical_strike, flat,
            stats.dmg, *_elem_block(stats, "dmg_elements"), eff,
            is_utility_fill, 1 if stats.subtype == "tool" else 0]


def _owned_codes(state: WorldState) -> set[str]:
    pool = {c for c, q in state.inventory.items() if q > 0}
    pool |= {c for c in state.equipment.values() if c}
    return pool


def _oracle_pick(purpose_kind: int, level: int, mon_res: dict[str, int],
                 cur_code: str | None, table: dict[str, ItemStats],
                 owned: list[str], skill: str | None,
                 cid, slot: str = _WEAPON_SLOT, is_weapon: int = 1,
                 mon_atk: dict[str, int] | None = None,
                 player_atk: dict[str, int] | None = None) -> dict:
    """One oracle request for `slot` under `purpose_kind`.

    Monster ATTACK (armor defense), monster RESISTANCE (weapon score + armor
    offense clamp) and the wearer's ATTACK (armor offense) are three separate
    element blocks, matching Oracle.lean's `runLoadoutPicker` layout."""
    mon_atk = mon_atk or {}
    player_atk = player_atk or {}
    cur_stats = table.get(cur_code) if cur_code else None
    cur_present = 1 if cur_stats is not None else 0
    args = [purpose_kind, level, is_weapon,
            *[mon_atk.get(e, 0) for e in ELEMENTS],
            *[mon_res.get(e, 0) for e in ELEMENTS],
            *[player_atk.get(e, 0) for e in ELEMENTS], cur_present]
    args += _item_block(cid(cur_code), cur_stats, slot, skill)
    for code in sorted(owned):
        args += _item_block(cid(code), table.get(code), slot, skill)
    return run_oracle("loadout_picker", [args])[0]


# ---------------------------------------------------------------------------
# GATHER: bit-exact benefit agreement (kills the `_benefit` negation mutant).
# ---------------------------------------------------------------------------

_EFF = st.integers(min_value=-20, max_value=20)
_GATHER_CODES = ["t_a", "t_b", "t_c", "t_d"]
_SKILL = "woodcutting"


@settings(max_examples=300, deadline=None)
@given(
    item_levels=st.lists(st.integers(min_value=1, max_value=10),
                         min_size=len(_GATHER_CODES), max_size=len(_GATHER_CODES)),
    item_effs=st.lists(_EFF, min_size=len(_GATHER_CODES), max_size=len(_GATHER_CODES)),
    has_eff=st.lists(st.booleans(), min_size=len(_GATHER_CODES), max_size=len(_GATHER_CODES)),
    level=st.integers(min_value=1, max_value=10),
    inv_pick=st.lists(st.booleans(), min_size=len(_GATHER_CODES), max_size=len(_GATHER_CODES)),
    equip_w=st.sampled_from([*_GATHER_CODES, None]),
)
def test_gather_pick_matches_lean(item_levels, item_effs, has_eff, level,
                                  inv_pick, equip_w):
    """Live ``pick_loadout(Gather)`` weapon-slot benefit ≡ oracle
    ``pickSlotForPurpose(.gather)``, BIT-EXACT (no augmentation). Computed via
    the live ``_benefit`` core, so dropping the Gather negation diverges."""
    table = {
        code: ItemStats(
            code=code, level=lvl, type_="weapon",
            subtype="tool" if eff else "",
            skill_effects={_SKILL: e} if eff else {},
        )
        for code, lvl, e, eff in zip(_GATHER_CODES, item_levels, item_effs, has_eff,
                                     strict=True)
    }
    if equip_w is not None and table[equip_w].type_ != "weapon":
        equip_w = None
    inventory = {c: 1 for c, keep in zip(_GATHER_CODES, inv_pick, strict=True) if keep}
    equipment = {_WEAPON_SLOT: equip_w}
    gd = _FakeGameData(table)
    state = _make_state(level, inventory, equipment)
    purpose = Gather(_SKILL)
    result = pick_loadout(purpose, state, gd)

    code_ids: dict[str, int] = {}

    def cid(code: str | None) -> int:
        if code is None:
            return -1
        return code_ids.setdefault(code, len(code_ids) + 1)

    owned = sorted(_owned_codes(state))
    # Pre-intern the current code first so its id is stable across the request.
    cid(equip_w)
    res = _oracle_pick(1, level, {}, equip_w, table, owned, _SKILL, cid)

    chosen = result.get(_WEAPON_SLOT)
    chosen_stats = table.get(chosen) if chosen else None
    feasible_exists = any(
        st_.level <= level and _WEAPON_SLOT in ITEM_TYPE_TO_SLOTS.get(st_.type_, [])
        for st_ in (table.get(c) for c in owned) if st_ is not None
    )
    if chosen_stats is not None:
        py_benefit = _benefit(chosen_stats, purpose)
        if feasible_exists:
            assert py_benefit == max(res["max_benefit"], res["cur_benefit"]), (py_benefit, res)
        assert py_benefit >= res["cur_benefit"], (py_benefit, res)
    else:
        assert res["cur_benefit"] == 0, res


# ---------------------------------------------------------------------------
# GATHER + ARTIFACT: the utility-fill branch. Artifacts carry NO skill_effects,
# so ``-gather_score`` is 0; the live ``_benefit`` routes them through the flat
# utility ``armor_score(stats, {}, {}, {})`` instead, and the oracle mirrors it via the
# per-item ``isUtilityFill`` flag → ``purposeBenefit(.gather) = flatUtil``. This
# binds the live flat-utility score to the oracle benefit BIT-EXACT and kills the
# mutant that reverts the artifact arm to ``-gather_score`` (0 → slot stays empty).
# ---------------------------------------------------------------------------

_UTIL = st.integers(min_value=0, max_value=30)
_ARTIFACT_CODES = ["a_a", "a_b", "a_c", "a_d"]


@settings(max_examples=300, deadline=None)
@given(
    item_levels=st.lists(st.integers(min_value=1, max_value=10),
                         min_size=len(_ARTIFACT_CODES), max_size=len(_ARTIFACT_CODES)),
    item_hp=st.lists(_UTIL, min_size=len(_ARTIFACT_CODES), max_size=len(_ARTIFACT_CODES)),
    item_wis=st.lists(_UTIL, min_size=len(_ARTIFACT_CODES), max_size=len(_ARTIFACT_CODES)),
    item_pros=st.lists(_UTIL, min_size=len(_ARTIFACT_CODES), max_size=len(_ARTIFACT_CODES)),
    level=st.integers(min_value=1, max_value=10),
    inv_pick=st.lists(st.booleans(), min_size=len(_ARTIFACT_CODES), max_size=len(_ARTIFACT_CODES)),
    equip_a=st.sampled_from([*_ARTIFACT_CODES, None]),
)
def test_gather_artifact_pick_matches_lean(item_levels, item_hp, item_wis, item_pros,
                                           level, inv_pick, equip_a):
    """Live ``pick_loadout(Gather)`` artifact-slot benefit ≡ oracle
    ``pickSlotForPurpose(.gather)`` under the utility-fill flag, BIT-EXACT. The
    chosen artifact's live ``armor_score(stats, {})`` equals the oracle's returned
    flatUtil benefit — reverting the artifact arm to ``-gather_score`` diverges."""
    table = {
        code: ItemStats(
            code=code, level=lvl, type_="artifact",
            hp_bonus=hp, wisdom=wis, prospecting=pros,
        )
        for code, lvl, hp, wis, pros in zip(_ARTIFACT_CODES, item_levels, item_hp,
                                            item_wis, item_pros, strict=True)
    }
    inventory = {c: 1 for c, keep in zip(_ARTIFACT_CODES, inv_pick, strict=True) if keep}
    equipment = {_ARTIFACT_SLOT: equip_a}
    gd = _FakeGameData(table)
    state = _make_state(level, inventory, equipment)
    purpose = Gather(_SKILL)
    result = pick_loadout(purpose, state, gd)

    code_ids: dict[str, int] = {}

    def cid(code: str | None) -> int:
        if code is None:
            return -1
        return code_ids.setdefault(code, len(code_ids) + 1)

    owned = sorted(_owned_codes(state))
    cid(equip_a)
    res = _oracle_pick(1, level, {}, equip_a, table, owned, _SKILL, cid,
                       slot=_ARTIFACT_SLOT, is_weapon=0)

    chosen = result.get(_ARTIFACT_SLOT)
    chosen_stats = table.get(chosen) if chosen else None
    feasible_exists = any(
        st_.level <= level and _ARTIFACT_SLOT in ITEM_TYPE_TO_SLOTS.get(st_.type_, [])
        for st_ in (table.get(c) for c in owned) if st_ is not None
    )
    if chosen_stats is not None:
        py_benefit = _benefit(chosen_stats, purpose)
        # The utility-fill benefit is exactly the flat utility term.
        assert py_benefit == armor_score(chosen_stats, {}, {}, {}), (py_benefit, chosen)
        if feasible_exists:
            assert py_benefit == max(res["max_benefit"], res["cur_benefit"]), (py_benefit, res)
        assert py_benefit >= res["cur_benefit"], (py_benefit, res)
    else:
        assert res["cur_benefit"] == 0, res


# ---------------------------------------------------------------------------
# COMBAT: raw-score agreement through the SAME unified oracle handler.
# ---------------------------------------------------------------------------

_VAL = st.integers(min_value=0, max_value=30)
_RES = st.integers(min_value=0, max_value=120)
_COMBAT_CODES = ["w_a", "w_b", "w_c", "w_d"]


@settings(max_examples=250, deadline=None)
@given(
    mon_res=st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    item_levels=st.lists(st.integers(min_value=1, max_value=10),
                         min_size=len(_COMBAT_CODES), max_size=len(_COMBAT_CODES)),
    item_atks=st.lists(st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_COMBAT_CODES), max_size=len(_COMBAT_CODES)),
    item_crits=st.lists(st.integers(min_value=0, max_value=100),
                        min_size=len(_COMBAT_CODES), max_size=len(_COMBAT_CODES)),
    level=st.integers(min_value=1, max_value=10),
    inv_pick=st.lists(st.booleans(), min_size=len(_COMBAT_CODES), max_size=len(_COMBAT_CODES)),
    equip_w=st.sampled_from([*_COMBAT_CODES, None]),
)
def test_combat_pick_matches_lean(mon_res, item_levels, item_atks, item_crits,
                                  level, inv_pick, equip_w):
    """Live ``pick_loadout(Combat)`` weapon-slot pick ≡ oracle
    ``pickSlotForPurpose(.combat)``. The picker's augmented ``weapon_score`` is an
    order-preserving transform of the oracle's raw ``WScore``, so we assert the
    chosen item's RAW score equals the proved optimal / no-downgrade value."""
    monster_res = {e: v for e, v in zip(ELEMENTS, mon_res, strict=True)}
    table = {
        code: ItemStats(
            code=code, level=lvl, type_="weapon",
            attack={e: a for e, a in zip(ELEMENTS, atk, strict=True)},
            critical_strike=crit,
        )
        for code, lvl, atk, crit in zip(_COMBAT_CODES, item_levels, item_atks,
                                        item_crits, strict=True)
    }
    inventory = {c: 1 for c, keep in zip(_COMBAT_CODES, inv_pick, strict=True) if keep}
    equipment = {_WEAPON_SLOT: equip_w}
    gd = _FakeGameData(table)
    state = _make_state(level, inventory, equipment)
    # Combat purpose: monster_attack irrelevant to the weapon branch (uses res).
    purpose = Combat({}, monster_res, {})
    result = pick_loadout(purpose, state, gd)

    code_ids: dict[str, int] = {}

    def cid(code: str | None) -> int:
        if code is None:
            return -1
        return code_ids.setdefault(code, len(code_ids) + 1)

    owned = sorted(_owned_codes(state))
    cid(equip_w)
    res = _oracle_pick(0, level, monster_res, equip_w, table, owned, None, cid)

    chosen = result.get(_WEAPON_SLOT)
    chosen_stats = table.get(chosen) if chosen else None
    feasible_exists = any(
        st_.level <= level and _WEAPON_SLOT in ITEM_TYPE_TO_SLOTS.get(st_.type_, [])
        for st_ in (table.get(c) for c in owned) if st_ is not None
    )
    if chosen_stats is not None:
        py_raw = weapon_score_raw(chosen_stats, monster_res)
        if feasible_exists:
            assert py_raw == max(res["max_benefit"], res["cur_benefit"]), (py_raw, res)
        assert py_raw >= res["cur_benefit"], (py_raw, res)
    else:
        assert res["cur_benefit"] == 0, res


# ---------------------------------------------------------------------------
# COMBAT / ARMOR: the piece is priced on BOTH halves of the swing. Binds the
# live `gear_value(Combat)` armor branch (= `armor_score`) to the oracle's
# `purposeBenefit(.combat … isWeapon=false)` = `AScore`, BIT-EXACT, over random
# monsters AND random wearer attacks. A mutant that drops the offense sum, the
# `dmg_elements` read, the crit read or the `200 *` defense scaling diverges.
# ---------------------------------------------------------------------------

_ARMOR_CODES = ["b_a", "b_b", "b_c", "b_d"]
_ARMOR_SLOT = "body_armor_slot"


@settings(max_examples=250, deadline=None)
@given(
    mon_atk=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    mon_res=st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    player_atk=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    item_levels=st.lists(st.integers(min_value=1, max_value=10),
                         min_size=len(_ARMOR_CODES), max_size=len(_ARMOR_CODES)),
    item_ress=st.lists(st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_ARMOR_CODES), max_size=len(_ARMOR_CODES)),
    item_dmgs=st.lists(_VAL, min_size=len(_ARMOR_CODES), max_size=len(_ARMOR_CODES)),
    item_dmg_elems=st.lists(st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                            min_size=len(_ARMOR_CODES), max_size=len(_ARMOR_CODES)),
    item_crits=st.lists(st.integers(min_value=0, max_value=100),
                        min_size=len(_ARMOR_CODES), max_size=len(_ARMOR_CODES)),
    item_hps=st.lists(_VAL, min_size=len(_ARMOR_CODES), max_size=len(_ARMOR_CODES)),
    level=st.integers(min_value=1, max_value=10),
    inv_pick=st.lists(st.booleans(), min_size=len(_ARMOR_CODES), max_size=len(_ARMOR_CODES)),
    equip_b=st.sampled_from([*_ARMOR_CODES, None]),
)
def test_combat_armor_pick_matches_lean(mon_atk, mon_res, player_atk, item_levels,
                                        item_ress, item_dmgs, item_dmg_elems,
                                        item_crits, item_hps, level, inv_pick,
                                        equip_b):
    """Live `pick_loadout(Combat)` armor-slot benefit == oracle `AScore`, bit-exact."""
    monster_atk = {e: v for e, v in zip(ELEMENTS, mon_atk, strict=True)}
    monster_res = {e: v for e, v in zip(ELEMENTS, mon_res, strict=True)}
    wearer_atk = {e: v for e, v in zip(ELEMENTS, player_atk, strict=True)}
    table = {
        code: ItemStats(
            code=code, level=lvl, type_="body_armor",
            resistance={e: r for e, r in zip(ELEMENTS, res, strict=True)},
            dmg=dmg,
            dmg_elements={e: d for e, d in zip(ELEMENTS, dmg_el, strict=True)},
            critical_strike=crit, hp_bonus=hp,
        )
        for code, lvl, res, dmg, dmg_el, crit, hp in zip(
            _ARMOR_CODES, item_levels, item_ress, item_dmgs, item_dmg_elems,
            item_crits, item_hps, strict=True)
    }
    inventory = {c: 1 for c, keep in zip(_ARMOR_CODES, inv_pick, strict=True) if keep}
    equipment = {_ARMOR_SLOT: equip_b}
    gd = _FakeGameData(table)
    state = _make_state(level, inventory, equipment, wearer_atk)
    purpose = Combat(monster_atk, monster_res, wearer_atk)
    result = pick_loadout(purpose, state, gd)

    code_ids: dict[str, int] = {}

    def cid(code: str | None) -> int:
        if code is None:
            return -1
        return code_ids.setdefault(code, len(code_ids) + 1)

    owned = sorted(_owned_codes(state))
    cid(equip_b)
    res = _oracle_pick(0, level, monster_res, equip_b, table, owned, None, cid,
                       slot=_ARMOR_SLOT, is_weapon=0, mon_atk=monster_atk,
                       player_atk=wearer_atk)

    chosen = result.get(_ARMOR_SLOT)
    chosen_stats = table.get(chosen) if chosen else None
    feasible_exists = any(
        st_.level <= level and _ARMOR_SLOT in ITEM_TYPE_TO_SLOTS.get(st_.type_, [])
        for st_ in (table.get(c) for c in owned) if st_ is not None
    )
    if chosen_stats is not None:
        py = armor_score(chosen_stats, monster_atk, monster_res, wearer_atk)
        assert py == _benefit(chosen_stats, purpose), (py, chosen)
        if feasible_exists:
            assert py == max(res["max_benefit"], res["cur_benefit"]), (py, res)
        assert py >= res["cur_benefit"], (py, res)
    else:
        assert res["cur_benefit"] == 0, res


# ---------------------------------------------------------------------------
# Targeted deterministic anchors.
# ---------------------------------------------------------------------------

def test_gather_swaps_in_best_tool():
    """Negation anchor: a woodcutting tool (skill_effect -10, benefit +10) beats a
    plain sword (benefit 0), so pick_loadout(Gather) swaps it into the weapon slot.
    DROPPING the negation flips the benefit sign → the sword (0) out-ranks the tool
    (-10) → the picker keeps the sword → this assert fails (mutant killed)."""
    table = {
        "sword": ItemStats(code="sword", level=1, type_="weapon", attack={"earth": 4}),
        "axe": ItemStats(code="axe", level=1, type_="weapon", subtype="tool",
                         skill_effects={"woodcutting": -10}),
    }
    gd = _FakeGameData(table)
    state = _make_state(5, {"axe": 1}, {_WEAPON_SLOT: "sword"})
    result = pick_loadout(Gather("woodcutting"), state, gd)
    assert result[_WEAPON_SLOT] == "axe", result


def test_gather_empty_slot_filled_only_by_positive_benefit():
    """Empty-slot >0 gate: a tool with a real woodcutting effect (benefit > 0)
    fills the empty weapon slot; a plain weapon (benefit 0) does NOT. Kills the
    gate-strictness mutant for the gather purpose."""
    tool_only = {"axe": ItemStats(code="axe", level=1, type_="weapon", subtype="tool",
                                  skill_effects={"woodcutting": -10})}
    gd = _FakeGameData(tool_only)
    state = _make_state(5, {"axe": 1}, {_WEAPON_SLOT: None})
    assert pick_loadout(Gather("woodcutting"), state, gd)[_WEAPON_SLOT] == "axe"

    plain_only = {"sword": ItemStats(code="sword", level=1, type_="weapon",
                                     attack={"earth": 4})}
    gd2 = _FakeGameData(plain_only)
    state2 = _make_state(5, {"sword": 1}, {_WEAPON_SLOT: None})
    # gather_score(sword)=0 → benefit 0 → empty slot stays empty.
    assert pick_loadout(Gather("woodcutting"), state2, gd2)[_WEAPON_SLOT] is None


def test_gather_no_downgrade_on_tie_keeps_current():
    """Strict-improvement anchor: a candidate tool whose effect TIES the equipped
    tool's effect must not displace it (`>` not `>=`). The worn tool is LEVEL-GATED
    out of the candidate pool, so the sole feasible candidate is the tying spare —
    the argmax is forced to a non-current code and only the comparison strictness
    decides the swap (kills the `>` → `>=` mutant without relying on tie order)."""
    table = {
        # Worn but above the player's level: scored, but not a candidate.
        "axe_worn": ItemStats(code="axe_worn", level=10, type_="weapon", subtype="tool",
                              skill_effects={"woodcutting": -10}),
        "axe_spare": ItemStats(code="axe_spare", level=1, type_="weapon", subtype="tool",
                               skill_effects={"woodcutting": -10}),  # exact benefit tie
    }
    gd = _FakeGameData(table)
    state = _make_state(5, {"axe_spare": 1}, {_WEAPON_SLOT: "axe_worn"})
    # Tie (both benefit 10) → keep the worn axe (strict `>` only).
    assert pick_loadout(Gather("woodcutting"), state, gd)[_WEAPON_SLOT] == "axe_worn"


# ---------------------------------------------------------------------------
# RANK: the monster-independent ruler picker (purposeKind == 2). Closes the
# previously-deferred Rank differential for the ``EquipOwnedGoal`` live caller.
# The oracle reads the SAME 20-int extended block Combat reads and reassembles the
# abstract ``rankOf`` via ``Formal.GearValue.rankValue`` — which IS ``combatValue``
# at the canonical adversary. The 6 out-of-block ``rankValue`` inputs (stride 26)
# the retired flat Rank sum needed are gone: a stat sum has a breakdown the ``Item``
# record cannot carry, a monster-relative score does not.
# ---------------------------------------------------------------------------

# Single-slot types so each item code fits exactly one slot → no cross-slot
# one-slot-per-code contention; each slot is bound independently.
_RANK_TYPES = ["weapon", "helmet", "body_armor", "boots"]
_RANK_TYPE_SLOT = {"weapon": "weapon_slot", "helmet": "helmet_slot",
                   "body_armor": "body_armor_slot", "boots": "boots_slot"}
_RANK_CODES = ["r_a", "r_b", "r_c", "r_d", "r_e", "r_f", "r_g", "r_h"]


def _rank_item_block(code_id: int, stats: ItemStats | None, slot: str) -> list[int]:
    """The Rank block IS the shared 20-int extended block — Rank reads exactly what
    the Combat purpose reads, which is the whole content of the unification."""
    return _item_block(code_id, stats, slot, None)


def _oracle_rank_pick(level: int, cur_code: str | None,
                      table: dict[str, ItemStats], owned: list[str],
                      cid, slot: str, is_weapon: int) -> dict:
    """One ``purposeKind == 2`` oracle request for ``slot`` (monster-independent:
    the monster element block is all zeros)."""
    cur_stats = table.get(cur_code) if cur_code else None
    cur_present = 1 if cur_stats is not None else 0
    args = [2, level, is_weapon, *[0 for _ in ELEMENTS * 3], cur_present]
    args += _rank_item_block(cid(cur_code), cur_stats, slot)
    for code in sorted(owned):
        args += _rank_item_block(cid(code), table.get(code), slot)
    return run_oracle("loadout_picker", [args])[0]


@settings(max_examples=300, deadline=None)
@given(
    item_types=st.lists(st.sampled_from(_RANK_TYPES),
                        min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    item_levels=st.lists(st.integers(min_value=1, max_value=10),
                         min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    item_atk=st.lists(_VAL, min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    item_res=st.lists(_VAL, min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    item_crit=st.lists(st.integers(min_value=0, max_value=100),
                       min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    item_hp=st.lists(_UTIL, min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    item_wis=st.lists(_UTIL, min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    item_pros=st.lists(_UTIL, min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    item_inv=st.lists(_UTIL, min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    item_haste=st.lists(_UTIL, min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    item_tool=st.lists(st.booleans(), min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    inv_pick=st.lists(st.booleans(), min_size=len(_RANK_CODES), max_size=len(_RANK_CODES)),
    level=st.integers(min_value=1, max_value=10),
)
def test_rank_pick_matches_lean(item_types, item_levels, item_atk, item_res,
                                item_crit, item_hp, item_wis, item_pros, item_inv,
                                item_haste, item_tool, inv_pick, level):
    """Live ``pick_loadout(Rank)`` per-slot pick ≡ oracle
    ``pickSlotForPurpose(.rank rankOf)``, BIT-EXACT. The chosen item's live
    ``gear_value(chosen, Rank)`` equals the oracle's proved-optimal rank benefit —
    binding the monster-independent Rank picker DECISION to
    ``Formal.GearValue.pickSlot_purpose_rank_optimal``. A random multi-slot-type
    owned pool mixes combat-contributing stats (attack/resistance/crit, folded
    into ``combat_raw``) and utility stats (wisdom/prospecting/hp/inventory_space/
    haste) plus tool/non-tool subtype, so every ``rankValue`` summand is
    exercised."""
    table = {
        code: ItemStats(
            code=code, level=lvl, type_=typ,
            subtype="tool" if tool else "",
            attack={"earth": atk}, resistance={"fire": res},
            critical_strike=crit, hp_bonus=hp, wisdom=wis, prospecting=pros,
            inventory_space=inv, haste=haste,
        )
        for code, typ, lvl, atk, res, crit, hp, wis, pros, inv, haste, tool in zip(
            _RANK_CODES, item_types, item_levels, item_atk, item_res, item_crit,
            item_hp, item_wis, item_pros, item_inv, item_haste, item_tool,
            strict=True)
    }
    inventory = {c: 1 for c, keep in zip(_RANK_CODES, inv_pick, strict=True) if keep}
    equipment: dict[str, str | None] = {s: None for s in _RANK_TYPE_SLOT.values()}
    gd = _FakeGameData(table)
    state = _make_state(level, inventory, equipment)
    result = pick_loadout(Rank(), state, gd)

    owned = sorted(_owned_codes(state))
    for typ, slot in _RANK_TYPE_SLOT.items():
        code_ids: dict[str, int] = {}

        def cid(code: str | None, _ids=code_ids) -> int:
            if code is None:
                return -1
            return _ids.setdefault(code, len(_ids) + 1)

        is_weapon = 1 if typ == "weapon" else 0
        res = _oracle_rank_pick(level, None, table, owned, cid, slot, is_weapon)

        chosen = result.get(slot)
        chosen_stats = table.get(chosen) if chosen else None
        feasible_exists = any(
            st_.level <= level and slot in ITEM_TYPE_TO_SLOTS.get(st_.type_, [])
            for st_ in (table.get(c) for c in owned) if st_ is not None
        )
        if chosen_stats is not None:
            py_benefit = gear_value(chosen_stats, Rank())
            assert py_benefit == _benefit(chosen_stats, Rank()), (py_benefit, chosen)
            if feasible_exists:
                assert py_benefit == max(res["max_benefit"], res["cur_benefit"]), (py_benefit, res)
            assert py_benefit >= res["cur_benefit"], (py_benefit, res)
        else:
            assert res["cur_benefit"] == 0, res
