"""Score equipment against a monster's element profile and pick the best loadout."""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.equipment.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.realizable_loadout import ownership
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState


def weapon_score_raw_pure(elements: list[str], attack: dict[str, int],
                          monster_resistance: dict[str, int]) -> int:
    """PURE CORE (mechanically extracted, P4b): ``Σ atk * max(0, 100 - res%)``.

    The ItemStats read (``weapon.attack``) and the module-level ``ELEMENTS``
    tuple are hoisted to plain-data parameters by the ``weapon_score_raw``
    wrapper, so this body is inside the extraction subset. Extracted to
    ``Formal/Extracted/EquipmentScoring.lean``; the bridge proves it equal
    to the hand ``Formal.EquipmentScoring.WScore`` over an injective
    element encoding, transferring ``weapon_score_nonneg`` (the clamp
    theorem) onto the extracted definition.
    """
    score = 0
    for elem in elements:
        score = score + attack.get(elem, 0) * max(0, 100 - monster_resistance.get(elem, 0))
    return score


def weapon_score_pure(elements: list[str], attack: dict[str, int], subtype: str,
                      monster_resistance: dict[str, int]) -> int:
    """PURE CORE (mechanically extracted, P4b): ``2 * raw + nonToolBonus``.

    Bridged to the hand ``Formal.PurposeRouting.combatScore`` (strict-raw
    preservation + the non-tool tie-break, the fishing_net invariant).
    """
    non_tool_bonus = 0 if subtype == "tool" else 1
    return 2 * weapon_score_raw_pure(elements, attack, monster_resistance) + non_tool_bonus


def gather_score_pure(skill_effects: dict[str, int], skill: str) -> int:
    """PURE CORE (mechanically extracted, P4b): the signed per-skill effect.

    Bridged to the hand ``Formal.PurposeRouting.gatherScore`` (the gather
    picker minimizes it; ``pickGatherSlot_score_optimal`` is restated on
    this extracted definition).
    """
    return skill_effects.get(skill, 0)


def armor_score_pure(elements: list[str], resistance: dict[str, int],
                     monster_attack: dict[str, int]) -> int:
    """PURE CORE (mechanically extracted, P4b): ``Σ mon_atk * armor_res%``.

    Bridged to the hand ``Formal.EquipmentScoring.AScore`` (no clamp —
    armor scoring has none) over the same injective element encoding.
    """
    score = 0
    for elem in elements:
        score = score + monster_attack.get(elem, 0) * resistance.get(elem, 0)
    return score


def weapon_score_raw(weapon: ItemStats, monster_resistance: dict[str, int]) -> int:
    """Raw element-discounted attack surrogate ``Σ atk * max(0, 100 - res%)``.

    BIT-EQUIVALENT to the Lean ``EquipmentScoring.WScore`` (no subtype
    augmentation). The composite ``weapon_score`` adds the non-tool
    tiebreaker on top of this; this raw value is exported for the
    differential gate against the kernel-checked WScore oracle.
    """
    return weapon_score_raw_pure(list(ELEMENTS), weapon.attack, monster_resistance)


def weapon_score(weapon: ItemStats, monster_resistance: dict[str, int]) -> int:
    """Estimated damage-per-hit a weapon deals against a monster.

    Returns the EXACT integer surrogate ``2 * weapon_score_raw +
    nonToolBonus``, where ``nonToolBonus = 0 if subtype == "tool" else 1``.
    BIT-EQUIVALENT to the Lean ``PurposeRouting.combatScore`` model
    (Formal/PurposeRouting.lean), which proves:

    * any strict WScore ordering is PRESERVED in the augmented score
      (``combatScore_strict_of_strict_wscore``) — multiplying the raw
      WScore by 2 protects every strict inequality from the +0/+1
      tiebreaker;
    * on a WScore TIE, the non-tool weapon strictly outranks the tool
      (``combatScore_tiebreaks_nontool_over_tool``).

    Without the tiebreaker, a tool tied on raw attack (e.g. fishing_net at
    5 water vs wooden_stick at 5 earth against a zero-resistance slime)
    would be picked by the left-fold argmax purely on iteration order —
    the formal closure of the 2026-06-06 trace bug where Robby kept
    fishing_net equipped for combat against slimes despite owning combat
    weapons that scored equal.
    """
    return weapon_score_pure(list(ELEMENTS), weapon.attack, weapon.subtype, monster_resistance)


def gather_score(item: ItemStats, skill: str) -> int:
    """Gather-purpose surrogate: how much this item boosts the named skill.

    Returns the (signed) ``skill_effects[skill]`` entry; MORE NEGATIVE is
    BETTER (the game encodes a -10 entry as "10% faster cooldown for this
    skill"). BIT-EQUIVALENT to Lean ``PurposeRouting.gatherScore``.

    Spec from Formal/PurposeRouting.lean: the gather picker minimizes this
    score over feasible candidates. A non-gathering item (no skill_effects
    entry for `skill`) returns 0 — every gather tool beats it.
    """
    return gather_score_pure(item.skill_effects, skill)


def pick_gather_loadout(
    skill: str, state: WorldState, game_data: GameData,
) -> dict[str, str | None]:
    """Best {slot: code | None} loadout for the gather skill `skill`.

    Mirrors `pick_loadout` but uses `gather_score` (argmin) for the
    weapon slot — pick the tool with the most-negative skill_effect on
    `skill`. Armor slots fall through to the existing combat picker
    against an empty monster_attack (no monster). Strict-improvement
    semantics are preserved per slot (no-downgrade, ties keep current).

    Spec: Formal/PurposeRouting.lean's pickGatherSlot_score_optimal —
    the chosen item minimizes gatherScore over feasible candidates.
    """
    result: dict[str, str | None] = dict(state.equipment)
    candidates = _candidates_for_slot("weapon_slot", state, game_data)
    if not candidates:
        return result
    # argmin of gather_score across owned weapon-slot candidates.
    best = min(candidates, key=lambda s: gather_score(s, skill))
    current_code = state.equipment.get("weapon_slot")
    current_stats = game_data.item_stats(current_code) if current_code else None
    if current_stats is None:
        result["weapon_slot"] = best.code
        return result
    if gather_score(best, skill) < gather_score(current_stats, skill):
        result["weapon_slot"] = best.code
    return result


def armor_score(armor: ItemStats, monster_attack: dict[str, int]) -> int:
    """Estimated damage REDUCED per hit by an armor piece. Higher = better defense.

    Returns the EXACT integer surrogate ``Σ mon_atk * armor_res%`` (i.e. 100×
    the float expression ``Σ mon_atk * armor_res%/100``). BIT-EQUIVALENT to the
    Lean ``AScore`` model — argmax / comparison results are identical to the
    rescaled float form.
    """
    return armor_score_pure(list(ELEMENTS), armor.resistance, monster_attack)


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
            return  # pragma: no cover — call sites always pass non-None; defensive guard
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
        elif current_code is not None and _effective_available(current_code) >= 1:
            _claim(current_code)
        else:
            # Current code was stolen by a peer slot's swap. We can't keep it.
            # Take the best feasible candidate (a downgrade) rather than leave
            # the slot empty — a downgrade still beats unequipping.
            result[slot] = best.code
            _claim(best.code)
    return result
