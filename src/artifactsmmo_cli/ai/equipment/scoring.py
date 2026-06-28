"""Score equipment against a monster's element profile.

LAYERING DIRECTION: ``ai/gear_value.gear_value`` delegates TO the
``weapon_score``/``armor_score``/``gather_score`` functions here for its
Combat/Gather purposes (gear_value -> scoring, one direction). This module must
NOT import ``gear_value`` — that would cycle.  The loadout picker
(``equipment.loadout_picker``) imports these scorers from here.
"""

from artifactsmmo_cli.ai.equipment.elements import ELEMENTS
from artifactsmmo_cli.ai.game_data import ItemStats


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
                     monster_attack: dict[str, int],
                     hp_bonus: int, wisdom: int, prospecting: int,
                     inventory_space: int, haste: int, lifesteal: int,
                     combat_buff: int) -> int:
    """PURE CORE (mechanically extracted, P4b): ``Σ mon_atk * armor_res% +
    hp_bonus + wisdom + prospecting + inventory_space + haste + lifesteal +
    combat_buff``.

    The leading term is the monster-relative defense (damage reduced per hit).
    The trailing flat terms are monster-INDEPENDENT utility the piece grants
    regardless of target — hp (survivability), wisdom (+xp), prospecting
    (+drops). They make a flat-utility item with no resistance (an ARTIFACT like
    novice_guide: res 0, hp 25, wisdom 25, prospecting 25 → score 75) pickable
    instead of scoring 0 and being skipped by pick_loadout's empty-slot >0 gate
    (and then discarded as worthless). For real armor the defense term dominates;
    the utility terms tiebreak.

    Bridged to the hand ``Formal.EquipmentScoring.AScore`` over the same
    injective element encoding.
    """
    score = 0
    for elem in elements:
        score = score + monster_attack.get(elem, 0) * resistance.get(elem, 0)
    return (score + hp_bonus + wisdom + prospecting + inventory_space + haste
            + lifesteal + combat_buff)


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


def armor_score(armor: ItemStats, monster_attack: dict[str, int]) -> int:
    """Estimated damage REDUCED per hit by an armor piece. Higher = better defense.

    Returns the EXACT integer surrogate ``Σ mon_atk * armor_res% + hp_bonus +
    wisdom + prospecting`` — monster-relative defense plus flat monster-
    independent utility. BIT-EQUIVALENT to the Lean ``AScore`` model.
    """
    return armor_score_pure(list(ELEMENTS), armor.resistance, monster_attack,
                            armor.hp_bonus, armor.wisdom, armor.prospecting,
                            armor.inventory_space, armor.haste, armor.lifesteal,
                            armor.combat_buff)
