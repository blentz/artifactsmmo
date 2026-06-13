"""Score equipment against a monster's element profile and pick the best loadout."""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.equipment.elements import ELEMENTS
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState


def weapon_score_raw_pure(elements: list[str], attack: dict[str, int],
                          critical_strike: int,
                          monster_resistance: dict[str, int]) -> int:
    """PURE CORE (mechanically extracted, P4b): ``(Σ atk * max(0, 100 -
    res%)) * (200 + crit)``.

    The crit factor is the exact-integer form of predict_win's expected
    critical-strike multiplier ``1 + crit/100 * 0.5 = (200 + crit)/200``
    (combat._expected_hit), scaled by 200 to stay in ℤ. Without it the
    loadout picker and the win predictor disagreed about the same
    quantity — run-18 trace 2026-06-12: vs green_slime (res_air 25)
    copper_pickaxe (earth 5, crit 0) out-scored copper_dagger (air 6,
    crit 35) and Robby ground slimes bare-handed-with-a-pickaxe at
    180/230 HP loss per fight.

    The ItemStats reads (``weapon.attack``, ``weapon.critical_strike``)
    and the module-level ``ELEMENTS`` tuple are hoisted to plain-data
    parameters by the ``weapon_score_raw`` wrapper, so this body is
    inside the extraction subset. Extracted to
    ``Formal/Extracted/EquipmentScoring.lean``; the bridge proves it equal
    to the hand ``Formal.EquipmentScoring.WScore`` over an injective
    element encoding, transferring ``weapon_score_nonneg`` (the clamp
    theorem) onto the extracted definition.
    """
    score = 0
    for elem in elements:
        score = score + attack.get(elem, 0) * max(0, 100 - monster_resistance.get(elem, 0))
    return score * (200 + critical_strike)


def weapon_score_pure(elements: list[str], attack: dict[str, int], subtype: str,
                      critical_strike: int,
                      monster_resistance: dict[str, int]) -> int:
    """PURE CORE (mechanically extracted, P4b): ``2 * raw + nonToolBonus``.

    Bridged to the hand ``Formal.PurposeRouting.combatScore`` (strict-raw
    preservation + the non-tool tie-break, the fishing_net invariant).
    """
    non_tool_bonus = 0 if subtype == "tool" else 1
    return 2 * weapon_score_raw_pure(elements, attack, critical_strike,
                                     monster_resistance) + non_tool_bonus


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
    """Raw crit-augmented attack surrogate ``(Σ atk * max(0, 100 - res%)) *
    (200 + crit)``.

    BIT-EQUIVALENT to the Lean ``EquipmentScoring.WScore`` (no subtype
    augmentation). The composite ``weapon_score`` adds the non-tool
    tiebreaker on top of this; this raw value is exported for the
    differential gate against the kernel-checked WScore oracle.
    """
    return weapon_score_raw_pure(list(ELEMENTS), weapon.attack,
                                 weapon.critical_strike, monster_resistance)


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
    return weapon_score_pure(list(ELEMENTS), weapon.attack, weapon.subtype,
                             weapon.critical_strike, monster_resistance)


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


def pick_loadout(
    monster_code: str, state: WorldState, game_data: GameData,
) -> dict[str, str | None]:
    """Best {slot: item_code | None} loadout from owned items against `monster_code`.

    Each slot is optimized in a deterministic order against the PROJECTED
    RESULT, enforcing the server's ONE-SLOT-PER-CODE rule (HTTP 485 "This item
    is already equipped"): an item code C is infeasible for slot S whenever C
    already sits in the projected result at any OTHER slot — kept there or
    newly assigned by an earlier iteration. Owning a second physical copy does
    NOT legalize a duplicate: the server refuses to equip a code that is worn
    anywhere, so e.g. a spare copper_ring can never go into ring2_slot while
    ring1_slot wears copper_ring (the 2026-06-10 OptimizeLoadout 485 livelock).
    Iteration order matters — `result` starts as a copy of `state.equipment`,
    so at slot S the "other slots" are earlier slots' final picks plus later
    slots' current items. A code DISPLACED by an earlier swap (no longer in the
    result anywhere) is legal to re-assign: the two-pass execute unequips every
    outgoing slot before any equip.

    The realizability invariant (`equipment/realizable_loadout.is_realizable`)
    follows directly: a newly-assigned code appears exactly once in the result
    and is owned (>= 1); kept codes are bounded by the worn count.

    Empty slots are only filled by a candidate whose score is strictly
    positive: a zero-score equip buys nothing against this monster and burns
    the code's single legal slot.

    Slots whose feasible argmax does not strictly beat their current item keep
    the current item. Slots with no feasible candidate stay as-is.

    Caller compares with `state.equipment` to find the swap delta.
    """
    monster_atk = game_data.monster_attack(monster_code)
    monster_res = game_data.monster_resistance(monster_code)

    result: dict[str, str | None] = dict(state.equipment)

    def _in_result_elsewhere(code: str, slot: str) -> bool:
        return any(worn == code for s, worn in result.items() if s != slot)

    for slot in _ordered_slots():
        candidates = _candidates_for_slot(slot, state, game_data)
        current_code = state.equipment.get(slot)

        # ONE SLOT PER CODE: drop every candidate whose code the projected
        # result already places at another slot (kept or assigned earlier).
        feasible: list[ItemStats] = [
            cand for cand in candidates if not _in_result_elsewhere(cand.code, slot)
        ]
        if not feasible:
            # Nothing equippable here — leave the slot as-is. The current item
            # (if any) is always retainable: it is worn HERE, and the duplicate
            # rule prevents any other slot from having taken its code.
            continue

        weapon = slot == "weapon_slot"
        if weapon:
            best = max(feasible, key=lambda s: weapon_score(s, monster_res))
        else:
            best = max(feasible, key=lambda s: armor_score(s, monster_atk))
        best_score = (weapon_score(best, monster_res) if weapon
                      else armor_score(best, monster_atk))

        if current_code == best.code:
            continue

        current_stats = game_data.item_stats(current_code) if current_code else None
        if current_stats is None:
            if current_code is None and best_score <= 0:
                # Zero-score fill of an empty slot buys nothing against this
                # monster and burns the code's one legal slot — skip it.
                continue
            result[slot] = best.code
            continue
        current_score = (weapon_score(current_stats, monster_res) if weapon
                         else armor_score(current_stats, monster_atk))
        if best_score > current_score:
            result[slot] = best.code
    return result
