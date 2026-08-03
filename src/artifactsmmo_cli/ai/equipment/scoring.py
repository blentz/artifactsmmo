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
                     monster_resistance: dict[str, int],
                     player_attack: dict[str, int],
                     dmg: int, dmg_elements: dict[str, int],
                     critical_strike: int,
                     hp_bonus: int, wisdom: int, prospecting: int,
                     inventory_space: int, haste: int, lifesteal: int,
                     combat_buff: int) -> int:
    """PURE CORE (mechanically extracted, P4b): ``200*defense + offense +
    200*flatUtility``.

    UNIT — the two monster-relative terms are BOTH in **1/20000 of one HP of
    damage swing per combat turn**; nothing else in this function is, and the
    docstring says so rather than pretending otherwise.

    * ``defense = Σ_e mon_atk[e] * armor_res[e]``. The real damage a hit loses to
      this piece is ``Σ_e mon_atk[e] * res[e]/100`` HP per turn, so ``defense``
      is ``100x`` damage-reduced-per-turn and ``200*defense`` is ``20000x``.
    * ``offense = Σ_e p_atk[e] * max(0, 100 - mon_res[e]) *
      (2*(dmg + dmg_elements[e]) + critical_strike)``. The piece's global/elemental
      damage % and crit % act on the PLAYER'S OWN output, which is why this
      function needs ``player_attack`` — a damage percentage is meaningless
      without the attack it multiplies. Per element the player deals
      ``p_atk[e] * max(0, 100 - mon_res[e])/100`` HP per turn (the SAME clamped
      form ``weapon_score_raw_pure`` uses); ``dmg`` adds ``(dmg+dmg_elements[e])/100``
      of it and crit adds ``crit/200`` of it (the expected 1.5x-on-crit multiplier
      ``1 + crit/100 * 0.5``, exactly as ``combat._expected_hit`` and
      ``weapon_score_raw_pure``'s ``(200 + crit)`` factor model it). Summing those
      two fractions over a common denominator of 20000 gives the integer above,
      with NO division anywhere — so this is exact, not a rounded surrogate.

    The factor 200 on ``defense`` is what puts it on the offense term's
    denominator (100 for the percent, 2 for crit's half-multiplier); it is the
    house convention already used by ``weapon_score_raw_pure`` (``200 + crit``)
    and ``combat._kill_step_net`` (``50 * raw * (200 + crit)``).

    WHY OFFENSE AT ALL: without it the score reduced to ``hp + wisdom`` for two
    resistance-free body armors, so a level-21 character swapped mushmush_jacket
    (hp 60, dmg 10, crit 3, wisdom 10 → 70) for adventurer_vest (hp 60, dmg 6,
    wisdom 20 → 80) — a clear combat downgrade bought with 10 wisdom, because
    4 points of global damage and 3 points of crit were invisible to the formula.
    ``dmg_elements`` is included because it is how the game expresses ELEMENT
    SPECIALIZATION on armor (copper_armor +5 fire/+5 earth, feather_coat +5
    air/+5 water), and it is monster-relative through the same
    ``max(0, 100 - mon_res[e])`` clamp: a +fire piece is worth more against a
    fire-weak monster, which is exactly the signal the flat formula destroyed.

    ``initiative`` is deliberately NOT included. It is not a per-turn rate but a
    THRESHOLD: ``predict_win`` uses ``p.initiative >= monster_initiative`` to
    decide only whether a tie in rounds goes to the player. Converting a
    threshold to damage-per-turn would need an invented exchange rate, so it
    stays out rather than entering the sum on a made-up scale.

    NOT IN THE UNIT — ``flat_utility`` (hp_bonus + wisdom + prospecting +
    inventory_space + haste + lifesteal + combat_buff) is monster-INDEPENDENT
    per-item utility carried over unconverted (each is scaled by the same 200 as
    ``defense``, so its weight RELATIVE to defense is exactly what it was before
    this term existed). wisdom is an XP rate, prospecting a drop rate, hp a pool
    not a rate — none is damage-per-turn and none is claimed to be. Its
    load-bearing formal role is the empty-slot gate: it makes a resistance-free
    ARTIFACT (novice_guide: res 0, hp 25, wisdom 25, prospecting 25 → 200*75 =
    15000) score > 0 so ``pick_loadout`` fills the slot instead of discarding it
    as worthless.

    Bridged to the hand ``Formal.EquipmentScoring.AScore`` over the same
    injective element encoding.
    """
    defense = 0
    for elem in elements:
        defense = defense + monster_attack.get(elem, 0) * resistance.get(elem, 0)
    offense = 0
    for elem in elements:
        offense = offense + (player_attack.get(elem, 0)
                             * max(0, 100 - monster_resistance.get(elem, 0))
                             * (2 * (dmg + dmg_elements.get(elem, 0)) + critical_strike))
    flat_utility = (hp_bonus + wisdom + prospecting + inventory_space + haste
                    + lifesteal + combat_buff)
    return 200 * defense + offense + 200 * flat_utility


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


def armor_score(armor: ItemStats, monster_attack: dict[str, int],
                monster_resistance: dict[str, int],
                player_attack: dict[str, int]) -> int:
    """Combat value of a NON-WEAPON piece against one monster, for one fighter.

    UNIT: **1/20000 of one HP of damage swing per combat turn**, for the two
    monster-relative terms (see ``armor_score_pure`` for the full derivation and
    for the terms that are deliberately NOT in that unit).

    Both halves of the swing are counted and they are commensurate by
    construction — the piece's DEFENSE (damage it stops the monster dealing,
    weighted by the monster's attack) and its OFFENSE (damage its ``dmg`` /
    ``dmg_elements`` / ``critical_strike`` add to what WE deal, weighted by the
    player's own attack through the monster's resistance). Judging armor on
    defense alone made a strictly worse jacket lose to a vest carrying 10 more
    wisdom.

    ``player_attack`` is the fighter's CURRENT per-element attack
    (``state.attack``), carried on the ``Combat`` purpose. It is a constant
    across the candidates for a slot, so it scales the offense term uniformly
    and cannot distort the within-slot argmax; it cannot be the POST-pick attack
    without making ``pick_loadout`` depend on its own output.

    BIT-EQUIVALENT to the Lean ``EquipmentScoring.AScore`` model.
    """
    return armor_score_pure(list(ELEMENTS), armor.resistance, monster_attack,
                            monster_resistance, player_attack,
                            armor.dmg, armor.dmg_elements, armor.critical_strike,
                            armor.hp_bonus, armor.wisdom, armor.prospecting,
                            armor.inventory_space, armor.haste, armor.lifesteal,
                            armor.combat_buff)
