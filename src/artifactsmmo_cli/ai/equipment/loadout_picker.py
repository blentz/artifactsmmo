"""Pick the best loadout from owned items for a given combat or gather purpose.

LAYERING DIRECTION: ``loadout_picker`` imports ``equipment.scoring`` (via
``gear_value``) for the per-slot scorers.  This module lives ABOVE both
``scoring`` and ``gear_value`` in the dependency graph.  No module in
``equipment.scoring`` or ``ai.gear_value`` may import from here.
"""

from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.equipment.realizable_loadout import ownership
from artifactsmmo_cli.ai.equipment.scoring import armor_score
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import Gather
from artifactsmmo_cli.ai.world_state import WorldState

_UTILITY_FILL_TYPES: frozenset[str] = frozenset({"artifact"})
"""Item types whose value is purpose-independent flat utility (wisdom/prospecting/
hp). They carry no skill_effects, so the Gather scorer values them at 0 and the
empty-slot gate discards them — this set routes them through the flat-utility
term instead. NOT `utility` (consumable/potion slots handled elsewhere)."""

_NO_MONSTER: dict[str, int] = {}
"""Empty monster attack: armor_score's defense term Σ mon_atk·res collapses to 0,
leaving exactly the flat utility sum (bit-identical to the Lean model flatUtil)."""


def _candidates_for_slot(
    slot: str, state: WorldState, game_data: GameData,
) -> list[ItemStats]:
    """Items the char owns (inventory + currently-equipped) that fit `slot`."""
    pool: set[str] = set()
    for code in state.inventory:
        if state.inventory[code] > 0:
            pool.add(code)
    for equipped_code in state.equipment.values():
        if equipped_code:
            pool.add(equipped_code)

    result: list[ItemStats] = []
    for code in pool:
        stats = game_data.item_stats(code)
        if stats is None or state.level < stats.level:
            continue
        if slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
            result.append(stats)
    return result


def _ordered_slots() -> list[str]:
    """Deterministic slot iteration order for the one-slot-per-code rule.

    Iteration order MATTERS: when two multi-slot peers (e.g. ring1_slot,
    ring2_slot) compete for the same scarce item code, the slot visited first
    takes it (the code then sits in the projected result and is infeasible for
    every later slot). We sort by (type-group, slot-name) so the order is
    stable across runs and matches the natural left-to-right convention of
    multi-slot types.
    """
    seen: set[str] = set()
    out: list[str] = []
    for slots in ITEM_TYPE_TO_SLOTS.values():
        for slot in slots:
            if slot not in seen:
                seen.add(slot)
                out.append(slot)
    return sorted(out)


def _benefit(stats: ItemStats, purpose: object) -> int:
    """Higher = better candidate for `purpose`, used as argmax key per slot.

    For Combat/Rank purposes: delegates directly to gear_value (weapon_score
    for weapons, armor_score for armor — bit-identical to the old per-slot
    weapon/armor_score branch, preserving the PurposeRouting duality proved
    in Formal/PurposeRouting.lean).

    For Gather purposes: negates gear_value (= gather_score) so that the
    tool with the most-negative skill_effect (fastest cooldown) has the
    highest benefit. Armor candidates have gather_score=0, so their benefit
    is also 0 — the empty-slot gate (best_score <= 0 → skip) and the
    strict-improvement rule (> current_score) together guarantee that armor
    slots keep their current item unchanged for Gather purposes. Exception:
    types in `_UTILITY_FILL_TYPES` (artifacts) route through the flat-utility
    term `armor_score(stats, {})` instead, since they carry no skill_effects
    but do grant purpose-independent utility that pick_loadout should equip.
    """
    if isinstance(purpose, Gather):
        if stats.type_ in _UTILITY_FILL_TYPES:
            # Artifacts grant purpose-independent utility (wisdom/prospecting/hp)
            # and carry no skill_effects, so gear_value(Gather) = 0 and the
            # empty-slot gate discards them. Score by the flat-utility term:
            # armor_score against an empty monster attack zeroes the defense term,
            # leaving hp_bonus+wisdom+prospecting+inventory_space+haste+lifesteal+
            # combat_buff — bit-identical to the Lean model's per-item flatUtil,
            # and consistent with the Combat path (armor_score includes it too).
            return armor_score(stats, _NO_MONSTER)
        return -gear_value(stats, purpose)
    return gear_value(stats, purpose)


def pick_loadout(
    purpose: object, state: WorldState, game_data: GameData,
) -> dict[str, str | None]:
    """Best {slot: item_code | None} loadout from owned items for `purpose`.

    `purpose` is one of ``Combat(monster_attack, monster_resistance)``,
    ``Gather(skill)``, or ``Rank`` (see ``ai/gear_value_core.py``).  Each slot
    is scored by ``_benefit(candidate, purpose)`` — an argmax that is
    bit-identical to the old per-slot ``weapon_score``/``armor_score`` branch
    for Combat purposes (proven in Formal/PurposeRouting.lean), and extends
    naturally to Gather (weapon slot takes the best tool; armor slots stay
    unchanged due to zero benefit).

    Each slot is optimized in a deterministic order against the PROJECTED
    RESULT, enforcing a per-code OCCUPANCY CAP: an item code C is infeasible for
    slot S once the projected result already holds C at its cap in OTHER slots —
    kept there or newly assigned by an earlier iteration. The cap is 1 for every
    type EXCEPT duplicate-allowed types (rings), whose cap is physical
    `ownership(C)`. So a non-ring code keeps the strict server ONE-SLOT-PER-CODE
    rule (HTTP 485 "This item is already equipped"), while a spare copper_ring
    MAY fill ring2_slot while ring1_slot wears copper_ring — but only when a 2nd
    copy is owned (live-server probe 2026-06-14: a duplicate ring returns HTTP
    200; without a 2nd copy the cap-1-per-owned-copy rule leaves ring2 empty,
    avoiding the inverse of the 2026-06-10 485 livelock — an unrealizable
    double-equip).
    Iteration order matters — `result` starts as a copy of `state.equipment`,
    so at slot S the "other slots" are earlier slots' final picks plus later
    slots' current items. A code DISPLACED by an earlier swap (no longer in the
    result anywhere) is legal to re-assign: the two-pass execute unequips every
    outgoing slot before any equip.

    The realizability invariant (`equipment/realizable_loadout.is_realizable`)
    follows directly: a code is assigned to a further slot only while the
    projected count is below `ownership(C)`, so total demand never exceeds
    ownership. Mirrors Formal.RealizableLoadout (capOf / pickLoadout_realizable
    + pickLoadout_one_slot_per_code → dupFreeExcept).

    Empty slots are only filled by a candidate whose benefit is strictly
    positive: a zero-benefit equip buys nothing for this purpose and burns
    the code's single legal slot.

    Slots whose feasible argmax does not strictly beat their current item keep
    the current item. Slots with no feasible candidate stay as-is.

    Caller compares with `state.equipment` to find the swap delta.
    """
    result: dict[str, str | None] = dict(state.equipment)

    def _dup_allowed(code: str) -> bool:
        stats = game_data.item_stats(code)
        return stats is not None and stats.type_ in DUPLICATE_SLOT_TYPES

    def _forbidden(code: str, slot: str) -> bool:
        # ONE SLOT PER CODE, generalized to a per-code occupancy CAP: a code is
        # forbidden for `slot` once the projected result already holds it at its
        # cap in OTHER slots. cap = physical ownership for duplicate-allowed
        # types (rings — server returns HTTP 200 on a 2nd copy, probe
        # 2026-06-14), else 1 (every other code keeps the strict HTTP 485 rule).
        # For non-dup codes cap=1, so `worn_elsewhere >= 1` is exactly the old
        # "present elsewhere" membership test. Mirrors
        # Formal.RealizableLoadout.forbiddenIn (capOf) — the kernel-proved
        # dupFreeExcept / realizability invariant.
        worn_elsewhere = sum(
            1 for s, worn in result.items() if s != slot and worn == code
        )
        cap = (ownership(code, state.inventory, state.equipment)
               if _dup_allowed(code) else 1)
        return worn_elsewhere >= cap

    for slot in _ordered_slots():
        candidates = _candidates_for_slot(slot, state, game_data)
        current_code = state.equipment.get(slot)

        # ONE SLOT PER CODE (rings: up to ownership): drop every candidate whose
        # code the projected result already places at its cap in other slots.
        feasible: list[ItemStats] = [
            cand for cand in candidates if not _forbidden(cand.code, slot)
        ]
        if not feasible:
            # Nothing equippable here — leave the slot as-is. The current item
            # (if any) is always retainable: it is worn HERE, and the duplicate
            # rule prevents any other slot from having taken its code.
            continue

        best = max(feasible, key=lambda s: _benefit(s, purpose))
        best_score = _benefit(best, purpose)

        if current_code == best.code:
            continue

        current_stats = game_data.item_stats(current_code) if current_code else None
        if current_stats is None:
            if current_code is None and best_score <= 0:
                # Zero-benefit fill of an empty slot buys nothing for this
                # purpose and burns the code's one legal slot — skip it.
                continue
            result[slot] = best.code
            continue
        current_score = _benefit(current_stats, purpose)
        if best_score > current_score:
            result[slot] = best.code
    return result
