"""Realizable-loadout invariant for `pick_loadout` (the multi-slot bug fix).

`pick_loadout` MUST return a loadout that the character can physically wear:
for every chosen item code C, the number of slots holding C in the loadout
must not exceed `inventory[C] + |slots currently holding C|` (the ownership
pool). Before the fix, multi-slot types (ring -> ring1, ring2; artifact -> 3
slots; utility -> 2 slots) would each pick the same physical item when the
character owned only one copy.

This test pins the realizability invariant under randomized inputs (Hypothesis,
≥200 examples on the formal profile) plus the exact ring1=A + ring2=B +
inventory={} counterexample from the bug report as a regression anchor. The
post-fix `pick_loadout` enforces the server's ONE-SLOT-PER-CODE rule (HTTP 485
"This item is already equipped"): a candidate code already placed in the
projected result at any OTHER slot — kept there or assigned by an earlier
slot — is infeasible, regardless of spare copies owned. The invariant follows:
a freshly-assigned code appears exactly once and is owned; kept codes are
bounded by the worn count (Lean: `pickLoadout_realizable`,
`pickLoadout_one_slot_per_code`).

The headline property: `is_realizable(pick_loadout(...), inv, equip) == True`
ALWAYS. `OptimizeLoadoutAction.apply` asserts a per-slot consequence of this
invariant (`cur >= 1` on the inventory decrement); if the invariant is
violated, apply raises — so this differential also doubles as the apply
assertion's gating contract.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.equipment.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.realizable_loadout import is_realizable, ownership
from artifactsmmo_cli.ai.equipment.scoring import armor_score, pick_loadout, weapon_score
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.world_state import WorldState


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


def test_regression_ring1_a_ring2_b_inventory_empty_fire_100():
    """Exact counterexample from the bug report: two rings, inventory empty,
    monster all-fire 100. Pre-fix returned {ring1_slot: 'B', ring2_slot: 'B'}
    (one physical B, two slots) — non-realizable. Post-fix must return any
    realizable loadout (no code appears more than ownership allows)."""
    table = {
        "A": ItemStats(code="A", level=1, type_="ring", resistance={"fire": 5}),
        "B": ItemStats(code="B", level=1, type_="ring", resistance={"fire": 50}),
    }
    monster_atk = {"fire": 100, "earth": 0, "water": 0, "air": 0}
    monster_res = {"fire": 0, "earth": 0, "water": 0, "air": 0}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level=1, inventory={},
                        equipment={"ring1_slot": "A", "ring2_slot": "B"})
    loadout = pick_loadout("ogre", state, gd)
    assert is_realizable(loadout, state.inventory, state.equipment), loadout
    # The chosen codes are exactly the two physical rings owned (A and B), one
    # each — no slot duplicates the other's item.
    chosen = sorted(c for c in (loadout["ring1_slot"], loadout["ring2_slot"]) if c)
    assert chosen == ["A", "B"], loadout


def test_apply_asserts_on_realizable_loadout_no_raise():
    """`OptimizeLoadoutAction.apply` must NOT raise when pick_loadout's output
    is realizable. The two-pass unequip-first-then-equip apply, fed a
    realizable loadout, always sees `cur >= 1` at the decrement."""
    table = {
        "A": ItemStats(code="A", level=1, type_="ring", resistance={"fire": 5}),
        "B": ItemStats(code="B", level=1, type_="ring", resistance={"fire": 50}),
    }
    monster_atk = {"fire": 100, "earth": 0, "water": 0, "air": 0}
    monster_res = {"fire": 0, "earth": 0, "water": 0, "air": 0}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level=1, inventory={},
                        equipment={"ring1_slot": "A", "ring2_slot": "B"})
    action = OptimizeLoadoutAction(target_monster_code="ogre")
    # Apply should succeed (the assert holds because the loadout is realizable).
    new_state = action.apply(state, gd)
    # Sanity: equipment slots map to distinct codes (A and B).
    rings = sorted(c for c in
                   (new_state.equipment["ring1_slot"], new_state.equipment["ring2_slot"])
                   if c)
    assert rings == ["A", "B"], new_state.equipment


# ---- Property test: ANY pick_loadout output is realizable ----

_RES = st.integers(min_value=0, max_value=120)
_VAL = st.integers(min_value=0, max_value=30)
# Item codes -- shared multi-slot pool so the property exercises the bug locus.
_CODES = ["a", "b", "c", "d", "e"]
# Multi-slot types: ring (2 slots), artifact (3 slots), utility (2 slots).
_TYPES = ["ring", "artifact", "utility", "body_armor", "weapon"]
# Equipment slots considered in the property test: all slots, including the
# multi-slot peers that trigger the bug.
_ALL_SLOTS: list[str] = sorted({s for slots in ITEM_TYPE_TO_SLOTS.values() for s in slots})


@settings(max_examples=250, deadline=None)
@given(
    item_types=st.lists(st.sampled_from(_TYPES), min_size=len(_CODES), max_size=len(_CODES)),
    item_levels=st.lists(st.integers(min_value=1, max_value=5),
                         min_size=len(_CODES), max_size=len(_CODES)),
    item_atks=st.lists(st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    item_ress=st.lists(st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    mon_atk=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    mon_res=st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    level=st.integers(min_value=1, max_value=5),
    inv_counts=st.lists(st.integers(min_value=0, max_value=2),
                        min_size=len(_CODES), max_size=len(_CODES)),
    equip_picks=st.lists(st.sampled_from([*_CODES, None]),
                         min_size=len(_ALL_SLOTS), max_size=len(_ALL_SLOTS)),
)
def test_pick_loadout_is_always_realizable(item_types, item_levels, item_atks,
                                           item_ress, mon_atk, mon_res, level,
                                           inv_counts, equip_picks):
    table = {
        code: ItemStats(
            code=code, level=lvl, type_=ty,
            attack={e: a for e, a in zip(ELEMENTS, atk, strict=True)},
            resistance={e: r for e, r in zip(ELEMENTS, res, strict=True)},
        )
        for code, ty, lvl, atk, res in zip(
            _CODES, item_types, item_levels, item_atks, item_ress, strict=True)
    }
    monster_atk = {e: v for e, v in zip(ELEMENTS, mon_atk, strict=True)}
    monster_res = {e: v for e, v in zip(ELEMENTS, mon_res, strict=True)}
    inventory = {c: n for c, n in zip(_CODES, inv_counts, strict=True) if n > 0}
    equipment: dict[str, str | None] = {s: c for s, c in
                                         zip(_ALL_SLOTS, equip_picks, strict=True)}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level, inventory, equipment)
    loadout = pick_loadout("mon", state, gd)
    # Headline contract: every chosen code's count in the loadout is bounded
    # by its physical ownership (inventory + currently-equipped copies).
    assert is_realizable(loadout, state.inventory, state.equipment), {
        "loadout": loadout,
        "inventory": dict(state.inventory),
        "equipment": dict(state.equipment),
        "ownership": {c: ownership(c, state.inventory, state.equipment) for c in _CODES},
    }


# ---- Apply must not raise on any realizable pick_loadout output ----

@settings(max_examples=250, deadline=None)
@given(
    item_types=st.lists(st.sampled_from(_TYPES), min_size=len(_CODES), max_size=len(_CODES)),
    item_levels=st.lists(st.integers(min_value=1, max_value=5),
                         min_size=len(_CODES), max_size=len(_CODES)),
    item_atks=st.lists(st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    item_ress=st.lists(st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    mon_atk=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    mon_res=st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    level=st.integers(min_value=1, max_value=5),
    inv_counts=st.lists(st.integers(min_value=0, max_value=2),
                        min_size=len(_CODES), max_size=len(_CODES)),
    equip_picks=st.lists(st.sampled_from([*_CODES, None]),
                         min_size=len(_ALL_SLOTS), max_size=len(_ALL_SLOTS)),
)
def test_apply_never_asserts_on_pick_loadout_output(item_types, item_levels,
                                                    item_atks, item_ress,
                                                    mon_atk, mon_res, level,
                                                    inv_counts, equip_picks):
    table = {
        code: ItemStats(
            code=code, level=lvl, type_=ty,
            attack={e: a for e, a in zip(ELEMENTS, atk, strict=True)},
            resistance={e: r for e, r in zip(ELEMENTS, res, strict=True)},
        )
        for code, ty, lvl, atk, res in zip(
            _CODES, item_types, item_levels, item_atks, item_ress, strict=True)
    }
    monster_atk = {e: v for e, v in zip(ELEMENTS, mon_atk, strict=True)}
    monster_res = {e: v for e, v in zip(ELEMENTS, mon_res, strict=True)}
    inventory = {c: n for c, n in zip(_CODES, inv_counts, strict=True) if n > 0}
    equipment: dict[str, str | None] = {s: c for s, c in
                                         zip(_ALL_SLOTS, equip_picks, strict=True)}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level, inventory, equipment)
    action = OptimizeLoadoutAction(target_monster_code="mon")
    # The apply must not raise (the assert holds because pick_loadout outputs
    # a realizable loadout).
    action.apply(state, gd)


# ---- Targeted unit tests for the helper ----

def test_is_realizable_counts_currently_equipped():
    """The currently-equipped copy of a code counts toward ownership (an
    unequip during a swap returns it to inventory)."""
    loadout = {"ring1_slot": "X", "ring2_slot": None}
    inventory: dict[str, int] = {}
    equipment = {"ring1_slot": "X", "ring2_slot": None}
    assert is_realizable(loadout, inventory, equipment)


def test_is_realizable_rejects_duplicate_beyond_ownership():
    """Two slots holding code X with only one physical X owned -> NOT realizable."""
    loadout = {"ring1_slot": "X", "ring2_slot": "X"}
    inventory: dict[str, int] = {}
    equipment = {"ring1_slot": "X", "ring2_slot": None}
    assert not is_realizable(loadout, inventory, equipment)


def test_is_realizable_two_copies_two_slots():
    """Two slots, two physical copies -> realizable."""
    loadout = {"ring1_slot": "X", "ring2_slot": "X"}
    inventory = {"X": 2}
    equipment: dict[str, str | None] = {"ring1_slot": None, "ring2_slot": None}
    assert is_realizable(loadout, inventory, equipment)


def test_ownership_counts_inventory_and_equipped():
    inventory = {"X": 3}
    equipment = {"ring1_slot": "X", "ring2_slot": None, "weapon_slot": "X"}
    assert ownership("X", inventory, equipment) == 5  # 3 inv + 2 equipped


# ---- Phase-15: the full pick_loadout algorithm differential ----
#
# These tests stress the properties proved in Lean:
# 1.  Output realizability (subsumes the existing property test above).
# 1b. One slot per code: dup-free equipment ⇒ dup-free output (HTTP 485
#     unreachable; `pickLoadout_one_slot_per_code`).
# 2.  Per-slot no-downgrade, STRICT and unconditional (`pickSlotStep_no_downgrade`).
# 3.  Per-slot optimality (argmax of the feasible candidate set).
# 3b. Empty slots fill only at strictly positive score
#     (`pickSlotStep_empty_fill_positive` / `pickSlotStep_empty_zero_stays_empty`).
# 4.  Determinism (pure function of inputs — no dict iteration leakage).


def _candidate_pool(state: WorldState, gd: _FakeGameData,
                    type_to_slots: dict[str, list[str]]) -> dict[str, list[str]]:
    """For each slot, the codes that fit by type and pass the level gate.
    Mirrors `_candidates_for_slot` so we can post-validate optimality."""
    pool: set[str] = set(c for c, n in state.inventory.items() if n > 0)
    for code in state.equipment.values():
        if code:
            pool.add(code)
    per_slot: dict[str, list[str]] = {}
    for slot in sorted({s for slots in type_to_slots.values() for s in slots}):
        cands: list[str] = []
        for code in pool:
            stats = gd.item_stats(code)
            if stats is None or state.level < stats.level:
                continue
            if slot in type_to_slots.get(stats.type_, []):
                cands.append(code)
        per_slot[slot] = cands
    return per_slot


@settings(max_examples=200, deadline=None)
@given(
    item_types=st.lists(st.sampled_from(_TYPES), min_size=len(_CODES), max_size=len(_CODES)),
    item_levels=st.lists(st.integers(min_value=1, max_value=5),
                         min_size=len(_CODES), max_size=len(_CODES)),
    item_atks=st.lists(st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    item_ress=st.lists(st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    mon_atk=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    mon_res=st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    level=st.integers(min_value=1, max_value=5),
    inv_counts=st.lists(st.integers(min_value=0, max_value=2),
                        min_size=len(_CODES), max_size=len(_CODES)),
    equip_picks=st.lists(st.sampled_from([*_CODES, None]),
                         min_size=len(_ALL_SLOTS), max_size=len(_ALL_SLOTS)),
)
def test_pick_loadout_deterministic_no_dict_leak(item_types, item_levels, item_atks,
                                                  item_ress, mon_atk, mon_res, level,
                                                  inv_counts, equip_picks):
    """Property 4 (determinism). Calling pick_loadout twice with structurally-equal
    inputs must yield byte-equal outputs. This guards against any latent dict
    iteration-order dependence (the Lean fold is over a List so the modeled
    algorithm is deterministic by construction)."""
    table = {
        code: ItemStats(
            code=code, level=lvl, type_=ty,
            attack={e: a for e, a in zip(ELEMENTS, atk, strict=True)},
            resistance={e: r for e, r in zip(ELEMENTS, res, strict=True)},
        )
        for code, ty, lvl, atk, res in zip(
            _CODES, item_types, item_levels, item_atks, item_ress, strict=True)
    }
    monster_atk = {e: v for e, v in zip(ELEMENTS, mon_atk, strict=True)}
    monster_res = {e: v for e, v in zip(ELEMENTS, mon_res, strict=True)}
    inventory = {c: n for c, n in zip(_CODES, inv_counts, strict=True) if n > 0}
    equipment: dict[str, str | None] = {s: c for s, c in
                                         zip(_ALL_SLOTS, equip_picks, strict=True)}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level, inventory, equipment)
    out_a = pick_loadout("mon", state, gd)
    # Re-build a structurally identical state and call again; the result must match.
    state_b = _make_state(level, dict(inventory), dict(equipment))
    out_b = pick_loadout("mon", state_b, gd)
    assert out_a == out_b


@settings(max_examples=200, deadline=None)
@given(
    item_types=st.lists(st.sampled_from(_TYPES), min_size=len(_CODES), max_size=len(_CODES)),
    item_levels=st.lists(st.integers(min_value=1, max_value=5),
                         min_size=len(_CODES), max_size=len(_CODES)),
    item_atks=st.lists(st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    item_ress=st.lists(st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    mon_atk=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    mon_res=st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    level=st.integers(min_value=1, max_value=5),
    inv_counts=st.lists(st.integers(min_value=0, max_value=2),
                        min_size=len(_CODES), max_size=len(_CODES)),
    equip_picks=st.lists(st.sampled_from([*_CODES, None]),
                         min_size=len(_ALL_SLOTS), max_size=len(_ALL_SLOTS)),
)
def test_pick_loadout_no_downgrade_or_stolen(item_types, item_levels, item_atks,
                                              item_ress, mon_atk, mon_res, level,
                                              inv_counts, equip_picks):
    """Property 2 (no-downgrade), now STRICT and UNCONDITIONAL. For every slot
    where pick_loadout returns a code different from the current code (both
    with stats), the new code's score STRICTLY beats the current code's score.
    The old "stolen current" escape is gone: the one-slot-per-code rule means
    no peer slot can ever take a code that is still current here (Lean:
    `pickSlotStep_no_downgrade`)."""
    table = {
        code: ItemStats(
            code=code, level=lvl, type_=ty,
            attack={e: a for e, a in zip(ELEMENTS, atk, strict=True)},
            resistance={e: r for e, r in zip(ELEMENTS, res, strict=True)},
        )
        for code, ty, lvl, atk, res in zip(
            _CODES, item_types, item_levels, item_atks, item_ress, strict=True)
    }
    monster_atk = {e: v for e, v in zip(ELEMENTS, mon_atk, strict=True)}
    monster_res = {e: v for e, v in zip(ELEMENTS, mon_res, strict=True)}
    inventory = {c: n for c, n in zip(_CODES, inv_counts, strict=True) if n > 0}
    equipment: dict[str, str | None] = {s: c for s, c in
                                         zip(_ALL_SLOTS, equip_picks, strict=True)}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level, inventory, equipment)
    loadout = pick_loadout("mon", state, gd)
    for slot, chosen in loadout.items():
        current = state.equipment.get(slot)
        if chosen is None or chosen == current:
            continue
        if current is None:
            continue  # empty-slot fills are pinned by the 3b positivity property
        current_stats = gd.item_stats(current)
        chosen_stats = gd.item_stats(chosen)
        if current_stats is None or chosen_stats is None:
            continue
        if slot == "weapon_slot":
            cur_score = weapon_score(current_stats, monster_res)
            new_score = weapon_score(chosen_stats, monster_res)
        else:
            cur_score = armor_score(current_stats, monster_atk)
            new_score = armor_score(chosen_stats, monster_atk)
        assert new_score > cur_score, {
            "slot": slot, "current": current, "chosen": chosen,
            "cur_score": cur_score, "new_score": new_score,
            "loadout": loadout, "inventory": dict(state.inventory),
            "equipment": dict(state.equipment),
        }


@settings(max_examples=200, deadline=None)
@given(
    item_types=st.lists(st.sampled_from(_TYPES), min_size=len(_CODES), max_size=len(_CODES)),
    item_levels=st.lists(st.integers(min_value=1, max_value=5),
                         min_size=len(_CODES), max_size=len(_CODES)),
    item_atks=st.lists(st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    item_ress=st.lists(st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    mon_atk=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    mon_res=st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    level=st.integers(min_value=1, max_value=5),
    inv_counts=st.lists(st.integers(min_value=0, max_value=2),
                        min_size=len(_CODES), max_size=len(_CODES)),
    equip_picks=st.lists(st.sampled_from([*_CODES, None]),
                         min_size=len(_ALL_SLOTS), max_size=len(_ALL_SLOTS)),
)
def test_pick_loadout_optimal_among_feasible(item_types, item_levels, item_atks,
                                              item_ress, mon_atk, mon_res, level,
                                              inv_counts, equip_picks):
    """Property 3 (optimality). For every slot whose `chosen` code is not the
    retained current, the chosen code must come from the slot's type-and-level
    candidate pool (the feasible set is a one-slot-per-code restriction of
    this pool, so pool membership is a sound relaxation; the per-slot argmax
    itself is pinned by Lean `pickSlotStep_optimal`)."""
    table = {
        code: ItemStats(
            code=code, level=lvl, type_=ty,
            attack={e: a for e, a in zip(ELEMENTS, atk, strict=True)},
            resistance={e: r for e, r in zip(ELEMENTS, res, strict=True)},
        )
        for code, ty, lvl, atk, res in zip(
            _CODES, item_types, item_levels, item_atks, item_ress, strict=True)
    }
    monster_atk = {e: v for e, v in zip(ELEMENTS, mon_atk, strict=True)}
    monster_res = {e: v for e, v in zip(ELEMENTS, mon_res, strict=True)}
    inventory = {c: n for c, n in zip(_CODES, inv_counts, strict=True) if n > 0}
    equipment: dict[str, str | None] = {s: c for s, c in
                                         zip(_ALL_SLOTS, equip_picks, strict=True)}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level, inventory, equipment)
    pools = _candidate_pool(state, gd, ITEM_TYPE_TO_SLOTS)
    loadout = pick_loadout("mon", state, gd)
    # Sanity check: every chosen code is from the candidate pool for its slot.
    for slot, chosen in loadout.items():
        if chosen is None:
            continue
        # The chosen code is either the kept current OR was a candidate.
        current = state.equipment.get(slot)
        if chosen == current:
            continue
        assert chosen in pools.get(slot, []), (slot, chosen, pools.get(slot))


def test_pick_loadout_weapon_slot_uses_weapon_score_not_armor_score():
    """Mutation-kill: pick_loadout's weapon_slot MUST score by weapon_score
    (offense vs monster resistance), not armor_score (defense). We construct
    two weapons: WHIGH has high attack and low resistance, WLOW has the opposite.
    Against a monster with positive attack AND positive resistance, the
    weapon_score-correct choice is WHIGH (it deals more damage). If the
    algorithm picks WLOW for weapon_slot, the score function was swapped."""
    table = {
        "WHIGH": ItemStats(code="WHIGH", level=1, type_="weapon",
                           attack={"fire": 100, "earth": 0, "water": 0, "air": 0},
                           resistance={"fire": 0, "earth": 0, "water": 0, "air": 0}),
        "WLOW": ItemStats(code="WLOW", level=1, type_="weapon",
                          attack={"fire": 1, "earth": 0, "water": 0, "air": 0},
                          resistance={"fire": 50, "earth": 0, "water": 0, "air": 0}),
    }
    # Monster with fire attack > 0 (so armor_score sees a signal) AND fire
    # resistance < 100 (so weapon_score sees a signal). The two scores disagree:
    #   weapon_score(WHIGH) = 100 * (1 - 50/100) = 50   ; weapon_score(WLOW) = 0.5
    #   armor_score(WHIGH)  = 50 * 0/100           = 0  ; armor_score(WLOW)  = 25
    # Correct (weapon_score): pick WHIGH. Swapped (armor_score): pick WLOW.
    monster_atk = {"fire": 50, "earth": 0, "water": 0, "air": 0}
    monster_res = {"fire": 50, "earth": 0, "water": 0, "air": 0}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level=1, inventory={"WHIGH": 1, "WLOW": 1},
                        equipment={"weapon_slot": None})
    loadout = pick_loadout("mon", state, gd)
    assert loadout["weapon_slot"] == "WHIGH", loadout


def _dedupe_equipment(equipment: dict[str, str | None]) -> dict[str, str | None]:
    """Keep the FIRST slot wearing each code, blank later repeats — the server
    maintains one-slot-per-code on worn equipment, so dup-free inputs are the
    only realizable ones (the Lean `hdup` hypothesis)."""
    seen: set[str] = set()
    out: dict[str, str | None] = {}
    for slot in sorted(equipment):
        code = equipment[slot]
        if code is not None and code in seen:
            out[slot] = None
            continue
        if code is not None:
            seen.add(code)
        out[slot] = code
    return out


@settings(max_examples=250, deadline=None)
@given(
    item_types=st.lists(st.sampled_from(_TYPES), min_size=len(_CODES), max_size=len(_CODES)),
    item_levels=st.lists(st.integers(min_value=1, max_value=5),
                         min_size=len(_CODES), max_size=len(_CODES)),
    item_atks=st.lists(st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    item_ress=st.lists(st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    mon_atk=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    mon_res=st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    level=st.integers(min_value=1, max_value=5),
    inv_counts=st.lists(st.integers(min_value=0, max_value=2),
                        min_size=len(_CODES), max_size=len(_CODES)),
    equip_picks=st.lists(st.sampled_from([*_CODES, None]),
                         min_size=len(_ALL_SLOTS), max_size=len(_ALL_SLOTS)),
)
def test_pick_loadout_one_slot_per_code(item_types, item_levels, item_atks,
                                        item_ress, mon_atk, mon_res, level,
                                        inv_counts, equip_picks):
    """Property 1b (ONE SLOT PER CODE / 485-safety, Lean
    `pickLoadout_one_slot_per_code`). Given dup-free current equipment (the
    server guarantee), NO code may occupy two slots of the output — even when
    SPARE COPIES are owned. Plain realizability is too weak here: with one
    worn + one spare copy, a duplicate sibling-slot assignment is "owned" yet
    the server refuses it with HTTP 485 (the 2026-06-10/11 OptimizeLoadout
    livelock). This is the property that kills the ownership-count mutants."""
    table = {
        code: ItemStats(
            code=code, level=lvl, type_=ty,
            attack={e: a for e, a in zip(ELEMENTS, atk, strict=True)},
            resistance={e: r for e, r in zip(ELEMENTS, res, strict=True)},
        )
        for code, ty, lvl, atk, res in zip(
            _CODES, item_types, item_levels, item_atks, item_ress, strict=True)
    }
    monster_atk = {e: v for e, v in zip(ELEMENTS, mon_atk, strict=True)}
    monster_res = {e: v for e, v in zip(ELEMENTS, mon_res, strict=True)}
    inventory = {c: n for c, n in zip(_CODES, inv_counts, strict=True) if n > 0}
    equipment = _dedupe_equipment(
        {s: c for s, c in zip(_ALL_SLOTS, equip_picks, strict=True)})
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level, inventory, equipment)
    loadout = pick_loadout("mon", state, gd)
    counts: dict[str, int] = {}
    for code in loadout.values():
        if code is not None:
            counts[code] = counts.get(code, 0) + 1
    dups = {c: n for c, n in counts.items() if n > 1}
    assert not dups, {
        "dups": dups, "loadout": loadout,
        "inventory": dict(state.inventory), "equipment": dict(state.equipment),
    }


@settings(max_examples=250, deadline=None)
@given(
    item_types=st.lists(st.sampled_from(_TYPES), min_size=len(_CODES), max_size=len(_CODES)),
    item_levels=st.lists(st.integers(min_value=1, max_value=5),
                         min_size=len(_CODES), max_size=len(_CODES)),
    item_atks=st.lists(st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    item_ress=st.lists(st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
                       min_size=len(_CODES), max_size=len(_CODES)),
    mon_atk=st.lists(_VAL, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    mon_res=st.lists(_RES, min_size=len(ELEMENTS), max_size=len(ELEMENTS)),
    level=st.integers(min_value=1, max_value=5),
    inv_counts=st.lists(st.integers(min_value=0, max_value=2),
                        min_size=len(_CODES), max_size=len(_CODES)),
    equip_picks=st.lists(st.sampled_from([*_CODES, None]),
                         min_size=len(_ALL_SLOTS), max_size=len(_ALL_SLOTS)),
)
def test_pick_loadout_empty_fill_strictly_positive(item_types, item_levels,
                                                   item_atks, item_ress,
                                                   mon_atk, mon_res, level,
                                                   inv_counts, equip_picks):
    """Property 3b (Lean `pickSlotStep_empty_fill_positive`). Every slot that
    goes from EMPTY to FILLED carries a strictly positive score against the
    target monster: a zero-score equip buys nothing and burns the code's one
    legal slot."""
    table = {
        code: ItemStats(
            code=code, level=lvl, type_=ty,
            attack={e: a for e, a in zip(ELEMENTS, atk, strict=True)},
            resistance={e: r for e, r in zip(ELEMENTS, res, strict=True)},
        )
        for code, ty, lvl, atk, res in zip(
            _CODES, item_types, item_levels, item_atks, item_ress, strict=True)
    }
    monster_atk = {e: v for e, v in zip(ELEMENTS, mon_atk, strict=True)}
    monster_res = {e: v for e, v in zip(ELEMENTS, mon_res, strict=True)}
    inventory = {c: n for c, n in zip(_CODES, inv_counts, strict=True) if n > 0}
    equipment: dict[str, str | None] = {s: c for s, c in
                                         zip(_ALL_SLOTS, equip_picks, strict=True)}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level, inventory, equipment)
    loadout = pick_loadout("mon", state, gd)
    for slot, chosen in loadout.items():
        if state.equipment.get(slot) is not None or chosen is None:
            continue
        stats = gd.item_stats(chosen)
        assert stats is not None
        if slot == "weapon_slot":
            score = weapon_score(stats, monster_res)
        else:
            score = armor_score(stats, monster_atk)
        assert score > 0, {
            "slot": slot, "chosen": chosen, "score": score, "loadout": loadout,
            "inventory": dict(state.inventory), "equipment": dict(state.equipment),
        }


def test_485_trace_worn_ring_spare_copy_leaves_sibling_empty():
    """THE 2026-06-10/11 485-LIVELOCK TRACE (deterministic mutation anchor):
    copper_ring worn in ring1 + a SECOND copper_ring in inventory. The server
    refuses to equip a code already worn in any slot (HTTP 485) regardless of
    copies owned, so ring2 must stay EMPTY. Ownership-count feasibility (the
    pre-fix algorithm) assigned ring2 := copper_ring and livelocked every
    OptimizeLoadout cycle. Lean: `pickLoadout_485_copper_ring_regression`."""
    table = {
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                 resistance={"fire": 10}),
    }
    monster_atk = {"fire": 50, "earth": 0, "water": 0, "air": 0}
    monster_res = {"fire": 0, "earth": 0, "water": 0, "air": 0}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level=1, inventory={"copper_ring": 1},
                        equipment={"ring1_slot": "copper_ring", "ring2_slot": None})
    loadout = pick_loadout("mon", state, gd)
    assert loadout["ring1_slot"] == "copper_ring", loadout
    assert loadout["ring2_slot"] is None, loadout


def test_zero_score_candidate_leaves_empty_slot_empty():
    """Property 3b dual (deterministic; Lean `pickSlotStep_empty_zero_stays_empty`):
    the only candidate for an empty slot scores 0 against this monster (its
    resistances are all irrelevant) — the slot stays empty."""
    table = {
        "water_ring": ItemStats(code="water_ring", level=1, type_="ring",
                                resistance={"water": 20}),
    }
    monster_atk = {"fire": 50, "earth": 0, "water": 0, "air": 0}
    monster_res = {"fire": 0, "earth": 0, "water": 0, "air": 0}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level=1, inventory={"water_ring": 1},
                        equipment={"ring1_slot": None, "ring2_slot": None})
    loadout = pick_loadout("mon", state, gd)
    assert loadout["ring1_slot"] is None, loadout
    assert loadout["ring2_slot"] is None, loadout


def test_score_tie_keeps_current_no_swap():
    """Property 2 deterministic anchor: a candidate that TIES the current
    item's score must NOT displace it (strict `>` only). Kills the `>` → `>=`
    no-downgrade mutant without relying on Hypothesis finding a tie. The worn
    high_ring is LEVEL-GATED out of the candidate pool, so the sole feasible
    candidate is the tying beta_ring — the argmax is forced to a non-current
    code and only the strictness of the comparison decides the swap."""
    table = {
        # Worn but above the player's level: not a candidate, still scored.
        "high_ring": ItemStats(code="high_ring", level=10, type_="ring",
                               resistance={"fire": 20}),
        "beta_ring": ItemStats(code="beta_ring", level=1, type_="ring",
                               resistance={"fire": 20}),  # exact score tie
    }
    monster_atk = {"fire": 50, "earth": 0, "water": 0, "air": 0}
    monster_res = {"fire": 0, "earth": 0, "water": 0, "air": 0}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level=1, inventory={"beta_ring": 1},
                        equipment={"ring1_slot": "high_ring", "ring2_slot": None})
    loadout = pick_loadout("mon", state, gd)
    assert loadout["ring1_slot"] == "high_ring", loadout
    # The tying beta_ring is a DIFFERENT code, so it legitimately fills ring2.
    assert loadout["ring2_slot"] == "beta_ring", loadout


def test_single_copy_fills_only_one_empty_sibling_slot():
    """Deterministic dup-free anchor: ONE inventory copy of a positive-score
    ring with BOTH ring slots empty fills exactly one slot. An earlier slot's
    fresh assignment lives in the projected result and forbids the code for
    the later sibling — kills the mutant that scans the original equipment
    (where the code appears nowhere) instead of the projected result."""
    table = {
        "solo_ring": ItemStats(code="solo_ring", level=1, type_="ring",
                               resistance={"fire": 10}),
    }
    monster_atk = {"fire": 50, "earth": 0, "water": 0, "air": 0}
    monster_res = {"fire": 0, "earth": 0, "water": 0, "air": 0}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level=1, inventory={"solo_ring": 1},
                        equipment={"ring1_slot": None, "ring2_slot": None})
    loadout = pick_loadout("mon", state, gd)
    filled = [s for s in ("ring1_slot", "ring2_slot") if loadout[s] == "solo_ring"]
    assert len(filled) == 1, loadout
    assert is_realizable(loadout, state.inventory, state.equipment), loadout


def test_pick_loadout_armor_slot_uses_armor_score_not_weapon_score():
    """Mutation-kill (dual): an armor slot must score by armor_score (defense),
    not weapon_score (offense)."""
    table = {
        "BIGRES": ItemStats(code="BIGRES", level=1, type_="body_armor",
                            attack={"fire": 1, "earth": 0, "water": 0, "air": 0},
                            resistance={"fire": 90, "earth": 0, "water": 0, "air": 0}),
        "BIGATK": ItemStats(code="BIGATK", level=1, type_="body_armor",
                            attack={"fire": 100, "earth": 0, "water": 0, "air": 0},
                            resistance={"fire": 1, "earth": 0, "water": 0, "air": 0}),
    }
    # Correct (armor_score): pick BIGRES. Swapped (weapon_score): pick BIGATK.
    monster_atk = {"fire": 50, "earth": 0, "water": 0, "air": 0}
    monster_res = {"fire": 50, "earth": 0, "water": 0, "air": 0}
    gd = _FakeGameData(table, monster_atk, monster_res)
    state = _make_state(level=1, inventory={"BIGRES": 1, "BIGATK": 1},
                        equipment={"body_armor_slot": None})
    loadout = pick_loadout("mon", state, gd)
    assert loadout["body_armor_slot"] == "BIGRES", loadout
