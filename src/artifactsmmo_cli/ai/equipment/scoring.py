"""Score equipment against a monster's element profile and pick the best loadout."""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.equipment.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.realizable_loadout import ownership
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState


def weapon_score(weapon: ItemStats, monster_resistance: dict[str, int]) -> int:
    """Estimated damage-per-hit a weapon deals against a monster.

    Returns the EXACT integer surrogate ``Σ atk * max(0, 100 - res%)`` (i.e.
    100× the float expression ``Σ atk * max(0, 1 - res%/100)``). The score is
    only ever COMPARED (``argmax`` and the strict-improvement test inside
    ``pick_loadout``); since ``100 > 0``, the surrogate preserves every
    ``<``/``=``/``>`` comparison exactly. This is BIT-EQUIVALENT to the Lean
    ``WScore`` model — no floating-point rounding, no order disagreement.
    """
    score = 0
    for elem in ELEMENTS:
        atk = weapon.attack.get(elem, 0)
        res_pct = monster_resistance.get(elem, 0)
        score += atk * max(0, 100 - res_pct)
    return score


def armor_score(armor: ItemStats, monster_attack: dict[str, int]) -> int:
    """Estimated damage REDUCED per hit by an armor piece. Higher = better defense.

    Returns the EXACT integer surrogate ``Σ mon_atk * armor_res%`` (i.e. 100×
    the float expression ``Σ mon_atk * armor_res%/100``). BIT-EQUIVALENT to the
    Lean ``AScore`` model — argmax / comparison results are identical to the
    rescaled float form.
    """
    score = 0
    for elem in ELEMENTS:
        mon_atk = monster_attack.get(elem, 0)
        armor_res_pct = armor.resistance.get(elem, 0)
        score += mon_atk * armor_res_pct
    return score


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
    """Deterministic slot iteration order for the claimed-codes accumulator.

    Iteration order MATTERS: when two multi-slot peers (e.g. ring1_slot,
    ring2_slot) compete for the same scarce item code, the slot visited first
    claims it. We sort by (type-group, slot-name) so the order is stable across
    runs and matches the natural left-to-right convention of multi-slot types.
    """
    seen: set[str] = set()
    out: list[str] = []
    for slots in ITEM_TYPE_TO_SLOTS.values():
        for slot in slots:
            if slot not in seen:
                seen.add(slot)
                out.append(slot)
    return sorted(out)


def pick_loadout(
    monster_code: str, state: WorldState, game_data: GameData,
) -> dict[str, str | None]:
    """Best {slot: item_code | None} loadout from owned items against `monster_code`.

    Each slot is optimized in a deterministic order with a CLAIMED-CODES
    accumulator: an item code C can only be picked for a slot if its remaining
    ownership (inventory[C] + slots currently holding C) exceeds the number of
    times it has already been claimed by earlier slots in the iteration. This
    prevents the multi-slot bug where ring1_slot and ring2_slot would both pick
    the same physical item when only one copy exists.

    Slots whose feasible argmax does not strictly beat their current item keep
    the current item (and that current code is claimed). Slots that swap claim
    the new code. Slots where every candidate is exhausted by prior claims
    fall back to the current equipment (a no-op).

    Caller compares with `state.equipment` to find the swap delta.
    """
    monster_atk = game_data.monster_attack(monster_code)
    monster_res = game_data.monster_resistance(monster_code)

    result: dict[str, str | None] = dict(state.equipment)
    claimed_codes: dict[str, int] = {}

    def _effective_available(code: str) -> int:
        return ownership(code, state.inventory, state.equipment) - claimed_codes.get(code, 0)

    def _claim(code: str | None) -> None:
        if code is None:
            return
        claimed_codes[code] = claimed_codes.get(code, 0) + 1

    for slot in _ordered_slots():
        candidates = _candidates_for_slot(slot, state, game_data)
        current_code = state.equipment.get(slot)

        # Filter candidates by remaining (unclaimed) ownership. NO exception
        # for the current code: if a peer slot earlier "swapped TO" the current
        # code, this slot's current copy has been spoken for and is no longer
        # physically available here. Treat current code identically to every
        # other candidate.
        feasible: list[ItemStats] = [
            cand for cand in candidates if _effective_available(cand.code) >= 1
        ]

        if not feasible:
            # No feasible candidate at all — leave the slot as-is. If current
            # code is still physically available, claim it. Otherwise the slot
            # is effectively empty (peer slot stole the last copy); fall back
            # to None.
            if current_code is not None and _effective_available(current_code) >= 1:
                _claim(current_code)
            else:
                result[slot] = None
            continue

        if slot == "weapon_slot":
            best = max(feasible, key=lambda s: weapon_score(s, monster_res))
        else:
            best = max(feasible, key=lambda s: armor_score(s, monster_atk))

        if current_code == best.code:
            _claim(current_code)
            continue

        current_stats = game_data.item_stats(current_code) if current_code else None
        if current_stats is None:
            result[slot] = best.code
            _claim(best.code)
            continue
        if slot == "weapon_slot":
            improves = weapon_score(best, monster_res) > weapon_score(current_stats, monster_res)
        else:
            improves = armor_score(best, monster_atk) > armor_score(current_stats, monster_atk)
        if improves:
            result[slot] = best.code
            _claim(best.code)
        elif _effective_available(current_code) >= 1:
            _claim(current_code)
        else:
            # Current code was stolen by a peer slot's swap. We can't keep it.
            # Take the best feasible candidate (a downgrade) rather than leave
            # the slot empty — a downgrade still beats unequipping.
            result[slot] = best.code
            _claim(best.code)
    return result
