"""Score equipment against a monster's element profile.

LAYERING DIRECTION: ``ai/gear_value.gear_value`` delegates TO the
``weapon_score``/``armor_score``/``gather_score`` functions here for its
Combat/Gather purposes (gear_value -> scoring, one direction). This module must
NOT import ``gear_value`` — that would cycle.  The loadout picker
(``equipment.loadout_picker``) imports these scorers from here.
"""

from artifactsmmo_cli.ai.equipment.elements import ELEMENTS
from artifactsmmo_cli.ai.game_data import ItemStats

RULER_SCALE = 2
"""THE RULER'S QUANTUM. Every term of the gear ruler — the weapon slot's combat
term, the armor slots' combat term, and the shared efficiency term both slots
read — is carried at this multiple of its NATURAL unit, and nothing else in the
ruler is.

WHY IT EXISTS: the ``nonToolBonus`` (0 for a tool, 1 for a real weapon) is the
one sub-unit quantity in the ruler. Because ``0 <= nonToolBonus < RULER_SCALE``
and every other term is a MULTIPLE of ``RULER_SCALE``, the bonus can never flip
a strict inequality between two ruler terms: two distinct terms differ by at
least ``RULER_SCALE``, and the bonus moves a score by at most
``RULER_SCALE - 1``. That is the fishing_net invariant, and it is a fact about
the arithmetic, not about today's catalog. See ``weapon_score_combat_pure``.

WHY IT MULTIPLIES *EVERY* TERM: it used to multiply only the weapon term
(``weapon_score = 2 * raw + nonToolBonus`` against ``armor_score = 1 *`` its
terms), which left weapons at twice armor's magnitude for the same real swing.
Live witness on the pinned bundle at the canonical adversary: ``copper_dagger``
(level 1) scored 282_001 and ``steel_armor`` (level 20) scored 282_000 — a tie —
while the dagger's true contribution is 7.05 HP of swing per turn and the
armor's is 14.10, exactly 2x. Cross-slot rankings (``tiers/pursuit_value``,
``tiers/progression_tree``) compare the two by design, so the factor was an
unearned thumb on the scale for every weapon. Applying it to the WHOLE ruler
keeps the tie-break safe AND makes the two slots commensurable, because
commensurability is then a property of the definition (one constant, one place)
rather than of the numbers happening to line up.

UNIT: the two monster-relative terms are ``1/20000`` of one HP of damage swing
per combat turn BEFORE this factor (see ``armor_score_pure`` for the
derivation), so the ruler's unit is ``1/(RULER_SCALE * 20000)`` = ``1/40000`` of
one HP of swing per turn. The ruler is an ORDERING, so the absolute unit matters
only where an absolute threshold reads it; ``tiers/prerequisite_graph.
RECYCLE_LEAF_VALUE_FLOOR`` is the only one, and it consumes
``pursuit_value``'s COMBAT term, which this change leaves bit-identical on the
weapon branch (its four calibration witnesses are all weapons)."""


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

    UNIT — this is the ruler's NATURAL unit, ``1/20000`` of one HP of damage
    swing per combat turn, the SAME unit ``armor_score_combat_pure``'s two
    monster-relative sums are in. Per element the wielder deals
    ``atk[e] * max(0, 100 - res[e])/100`` HP per turn and the crit factor
    ``(200 + crit)/200`` multiplies it, so ``atk * clamp * (200 + crit)`` is that
    product over the common denominator 20000, exactly as
    ``armor_score_combat_pure``'s offense sum is. The RULER carries it at
    ``RULER_SCALE *`` this (``weapon_score_combat_pure``), as it carries every
    other term.

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


def gear_score_efficiency_pure(wisdom: int, prospecting: int,
                               inventory_space: int, haste: int) -> int:
    """PURE CORE (mechanically extracted): the ruler's flat-utility EFFICIENCY
    term — ``RULER_SCALE * 200 * (wisdom + prospecting + inventory_space +
    haste)``.

    ONE FUNCTION FOR EVERY SLOT. Both ``weapon_score_pure`` and
    ``armor_score_pure`` add THIS term, so the ruler prices a point of wisdom (or
    prospecting, or inventory space, or haste) identically no matter which slot
    carries it. It used to be an armor-only block (``armor_score_efficiency_pure``),
    which meant a weapon's efficiency stats were invisible to the ruler
    altogether — live witnesses: the four voidstone tools
    (``voidstone_pickaxe`` / ``_axe`` / ``_gloves`` / ``_fishing_rod``, 100
    prospecting each) contributed nothing from that prospecting to any purpose,
    and ``obsidian_battleaxe``'s ``inventory_space`` −25 penalty was free.

    These four are the stats that buy TIME rather than damage: an XP rate, a
    drop rate, carrying capacity and a cooldown reduction. Splitting them out is
    what lets ``tiers/pursuit_value`` read the ONE ruler with combat dominating
    utility WITHOUT recomputing utility on a second scale — the pursuit score
    reuses this exact term instead of re-summing the stats, so utility cannot be
    counted twice. See ``armor_score_combat_pure`` / ``weapon_score_combat_pure``
    for the other halves, and ``armor_score_pure`` / ``weapon_score_pure`` for
    the identities that they partition the score.

    The ``200 *`` is the SAME scale the flat-utility block has always been
    carried at (the defense sum's factor); the ``RULER_SCALE *`` is the factor
    EVERY ruler term carries, so this is a re-association plus the one uniform
    rescale, not a re-weighting: no item's ruler value changes RELATIVE to
    another item's because of this term's scale.
    """
    return RULER_SCALE * 200 * (wisdom + prospecting + inventory_space + haste)


def weapon_score_combat_pure(elements: list[str], attack: dict[str, int],
                             subtype: str, critical_strike: int,
                             monster_resistance: dict[str, int]) -> int:
    """PURE CORE (mechanically extracted, P4b): the weapon slot's COMBAT term,
    ``RULER_SCALE * raw + nonToolBonus``.

    THE FISHING_NET INVARIANT LIVES HERE. ``nonToolBonus`` is ``0`` for a
    ``subtype == "tool"`` piece and ``1`` otherwise; since ``raw`` is an integer
    and every ruler term is a multiple of ``RULER_SCALE``, a ``+1`` can never
    flip a strict raw inequality, and on a raw TIE it strictly orders the real
    weapon above the tool. Without it a tool tied on raw attack (fishing_net at
    5 water vs wooden_stick at 5 earth against a zero-resistance slime) was
    picked by the left-fold argmax purely on iteration order — the 2026-06-06
    trace bug where Robby kept fishing_net equipped for combat against slimes.

    This is the term ``gear_components`` hands the economics layer as the
    weapon branch's COMBAT half, so it is what
    ``Formal.StrategicValue.pursuit_combat_dominates`` dominates utility with.
    Bridged to the hand ``Formal.PurposeRouting.combatScore``.
    """
    non_tool_bonus = 0 if subtype == "tool" else 1
    return RULER_SCALE * weapon_score_raw_pure(elements, attack, critical_strike,
                                               monster_resistance) + non_tool_bonus


def weapon_score_pure(elements: list[str], attack: dict[str, int], subtype: str,
                      critical_strike: int,
                      monster_resistance: dict[str, int],
                      wisdom: int, prospecting: int,
                      inventory_space: int, haste: int) -> int:
    """PURE CORE (mechanically extracted, P4b): the weapon slot's ruler value,
    expressed as its COMBAT term plus the SHARED EFFICIENCY term.

    The two summands PARTITION the score exactly as they do for armor
    (``armor_score_pure``): every stat reaches exactly one of them, so nothing is
    dropped and nothing is double-counted. ``weapon_score_combat_pure`` takes no
    efficiency stat at all — there is no parameter through which one could reach
    it — which is the mechanical guarantee the pursuit ruler's combat term is
    utility-free on the weapon branch just as it is on the armor branch.

    Bridged to the hand ``Formal.PurposeRouting.weaponScore``.
    """
    return (weapon_score_combat_pure(elements, attack, subtype, critical_strike,
                                     monster_resistance)
            + gear_score_efficiency_pure(wisdom, prospecting, inventory_space, haste))


def gather_score_pure(skill_effects: dict[str, int], skill: str) -> int:
    """PURE CORE (mechanically extracted, P4b): the signed per-skill effect.

    Bridged to the hand ``Formal.PurposeRouting.gatherScore`` (the gather
    picker minimizes it; ``pickGatherSlot_score_optimal`` is restated on
    this extracted definition).
    """
    return skill_effects.get(skill, 0)


def armor_score_combat_pure(elements: list[str], resistance: dict[str, int],
                            monster_attack: dict[str, int],
                            monster_resistance: dict[str, int],
                            player_attack: dict[str, int],
                            dmg: int, dmg_elements: dict[str, int],
                            critical_strike: int,
                            hp_restore: int, hp_bonus: int, lifesteal: int,
                            combat_buff: int) -> int:
    """PURE CORE (mechanically extracted): the COMBAT slice of the armor score
    — ``RULER_SCALE * (200*defense + offense + 200*(hp_restore + hp_bonus +
    lifesteal + combat_buff))``.

    Everything ``armor_score_pure`` computes EXCEPT the four efficiency stats.
    The two monster-relative sums are unchanged and carry the full derivation
    in ``armor_score_pure``'s docstring; the four flat stats kept here are the
    ones that act inside a FIGHT — an HP pool (``hp_restore``/``hp_bonus``),
    a heal-on-crit fraction (``lifesteal``) and a utility-slot damage/antipoison
    buff (``combat_buff``).

    This function does NOT take ``wisdom``/``prospecting``/``inventory_space``/
    ``haste`` at all, which is the mechanical guarantee that the pursuit
    ruler's combat term is free of utility: there is no parameter through which
    a utility stat could reach it.

    NOTE the split re-prices nothing WITHIN this term. ``hp_restore`` used to sit
    in a flat 8-stat sum (``combat_raw``) that added a resistance PERCENTAGE to
    an HP amount 1:1; here it is 200 per point while one point of per-element
    resistance is ``200 * monster_attack[e]`` — 6600 at the canonical
    adversary's 33 attack. That 33:1 exchange rate is the canonical duel's,
    not an invented constant.

    The ``RULER_SCALE *`` is the ruler's quantum, carried by every term on every
    slot (see ``RULER_SCALE``). It is what makes this term COMMENSURABLE with
    ``weapon_score_combat_pure``: both are ``RULER_SCALE`` times a value in
    ``1/20000`` of one HP of swing per turn, so a weapon that adds one HP of
    swing and a piece of armor that stops one HP of swing now score the same
    number. Before it lived here, armor was at HALF the weapon's magnitude for
    the same real effect.
    """
    defense = 0
    for elem in elements:
        defense = defense + monster_attack.get(elem, 0) * resistance.get(elem, 0)
    offense = 0
    for elem in elements:
        offense = offense + (player_attack.get(elem, 0)
                             * max(0, 100 - monster_resistance.get(elem, 0))
                             * (2 * (dmg + dmg_elements.get(elem, 0)) + critical_strike))
    flat_combat = hp_restore + hp_bonus + lifesteal + combat_buff
    return RULER_SCALE * (200 * defense + offense + 200 * flat_combat)


def armor_score_pure(elements: list[str], resistance: dict[str, int],
                     monster_attack: dict[str, int],
                     monster_resistance: dict[str, int],
                     player_attack: dict[str, int],
                     dmg: int, dmg_elements: dict[str, int],
                     critical_strike: int,
                     hp_restore: int, hp_bonus: int, wisdom: int, prospecting: int,
                     inventory_space: int, haste: int, lifesteal: int,
                     combat_buff: int) -> int:
    """PURE CORE (mechanically extracted, P4b): ``RULER_SCALE * (200*defense +
    offense + 200*flatUtility)``, expressed as its COMBAT slice plus the SHARED
    EFFICIENCY slice.

    The two summands PARTITION the score: every stat reaches exactly one of
    them, so ``armor_score_combat_pure + gear_score_efficiency_pure`` is the
    whole score and nothing is double-counted. That identity is what
    ``tiers/pursuit_value`` rides — it re-reads these two existing terms
    lexicographically instead of building a second scorer. ``weapon_score_pure``
    is the SAME two-term shape over the SAME efficiency function, which is why a
    stat prices identically whichever slot carries it.

    UNIT — the two monster-relative terms are BOTH in **1/20000 of one HP of
    damage swing per combat turn** before the ``RULER_SCALE`` factor every ruler
    term carries (so ``1/40000`` after it); nothing else in this function is, and
    the docstring says so rather than pretending otherwise.

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

    NOT IN THE UNIT — ``flat_utility`` (hp_restore + hp_bonus + wisdom +
    prospecting + inventory_space + haste + lifesteal + combat_buff) is
    monster-INDEPENDENT per-item utility carried over unconverted (each is scaled
    by the same 200 as ``defense``, so its weight RELATIVE to defense is exactly
    what it was before this term existed). wisdom is an XP rate, prospecting a
    drop rate, hp a pool not a rate — none is damage-per-turn and none is claimed
    to be. Its load-bearing formal role is the empty-slot gate: it makes a
    resistance-free ARTIFACT (novice_guide: res 0, hp 25, wisdom 25,
    prospecting 25 → 200*75 = 15000) score > 0 so ``pick_loadout`` fills the slot
    instead of discarding it as worthless.

    ``hp_restore`` JOINED that block when Rank was unified onto this function.
    It is a per-item HP pool, exactly like ``hp_bonus``, and it was the ONE stat
    the two rulers disagreed about EXISTING: the retired flat Rank sum counted
    it, this function did not, and `equipment/slot_occupancy._flat_utility`
    already had to add it back by hand ("plus hp_restore, which no scorer
    reads") to keep its displacement rule sound. With Rank routed through here,
    omitting it would have scored every healing potion 0, which also means
    ``pick_loadout(Combat)`` can finally see a utility-slot heal, which it
    previously priced at 0 and would never equip.

    Bridged to the hand ``Formal.EquipmentScoring.AScore`` over the same
    injective element encoding.
    """
    return (armor_score_combat_pure(elements, resistance, monster_attack,
                                    monster_resistance, player_attack, dmg,
                                    dmg_elements, critical_strike, hp_restore,
                                    hp_bonus, lifesteal, combat_buff)
            + gear_score_efficiency_pure(wisdom, prospecting, inventory_space, haste))


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


def weapon_score_combat(weapon: ItemStats, monster_resistance: dict[str, int]) -> int:
    """The COMBAT slice of ``weapon_score`` — the same score minus its efficiency
    slice.

    Returns the EXACT integer surrogate ``RULER_SCALE * weapon_score_raw +
    nonToolBonus``, where ``nonToolBonus = 0 if subtype == "tool" else 1``.
    BIT-EQUIVALENT to the Lean ``PurposeRouting.combatScore`` model
    (Formal/PurposeRouting.lean), which proves:

    * any strict WScore ordering is PRESERVED in the augmented score
      (``combatScore_strict_of_strict_wscore``) — the ``RULER_SCALE`` factor
      protects every strict inequality from the +0/+1 tiebreaker;
    * on a WScore TIE, the non-tool weapon strictly outranks the tool
      (``combatScore_tiebreaks_nontool_over_tool``).

    Without the tiebreaker, a tool tied on raw attack (e.g. fishing_net at
    5 water vs wooden_stick at 5 earth against a zero-resistance slime)
    would be picked by the left-fold argmax purely on iteration order —
    the formal closure of the 2026-06-06 trace bug where Robby kept
    fishing_net equipped for combat against slimes despite owning combat
    weapons that scored equal.

    See ``weapon_score_combat_pure``.
    """
    return weapon_score_combat_pure(list(ELEMENTS), weapon.attack, weapon.subtype,
                                    weapon.critical_strike, monster_resistance)


def weapon_score(weapon: ItemStats, monster_resistance: dict[str, int]) -> int:
    """Ruler value of a WEAPON against a monster: its combat term plus the
    efficiency term every slot shares.

    ``= weapon_score_combat + gear_score_efficiency``, the same two-term shape
    ``armor_score`` has, over the same two functions. A weapon's
    ``wisdom``/``prospecting``/``inventory_space``/``haste`` used to reach no
    purpose at all; now they price exactly as they do on armor. BIT-EQUIVALENT
    to the Lean ``PurposeRouting.weaponScore``.
    """
    return weapon_score_pure(list(ELEMENTS), weapon.attack, weapon.subtype,
                             weapon.critical_strike, monster_resistance,
                             weapon.wisdom, weapon.prospecting,
                             weapon.inventory_space, weapon.haste)


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

    UNIT: **1/40000 of one HP of damage swing per combat turn** for the two
    monster-relative terms — ``RULER_SCALE`` times the natural ``1/20000`` (see
    ``armor_score_pure`` for the full derivation and for the terms that are
    deliberately NOT in that unit, and ``RULER_SCALE`` for the factor). The SAME
    unit ``weapon_score`` is in, which is the point of the factor.

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
                            armor.hp_restore, armor.hp_bonus, armor.wisdom,
                            armor.prospecting, armor.inventory_space, armor.haste,
                            armor.lifesteal, armor.combat_buff)


def gear_score_efficiency(item: ItemStats) -> int:
    """The EFFICIENCY slice of the ruler, for ANY slot — monster-independent, so
    it takes no adversary. The weapon branch and the armor branch of
    ``ai/gear_value.gear_components`` both read THIS function, which is what
    makes a stat cost the same wherever it is carried. See
    ``gear_score_efficiency_pure``."""
    return gear_score_efficiency_pure(item.wisdom, item.prospecting,
                                      item.inventory_space, item.haste)


def armor_score_combat(armor: ItemStats, monster_attack: dict[str, int],
                       monster_resistance: dict[str, int],
                       player_attack: dict[str, int]) -> int:
    """The COMBAT slice of ``armor_score`` — the same score minus its
    efficiency slice. See ``armor_score_combat_pure``."""
    return armor_score_combat_pure(list(ELEMENTS), armor.resistance, monster_attack,
                                   monster_resistance, player_attack,
                                   armor.dmg, armor.dmg_elements, armor.critical_strike,
                                   armor.hp_restore, armor.hp_bonus,
                                   armor.lifesteal, armor.combat_buff)
