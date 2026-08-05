"""Shared equippable-item value: combat score + per-skill tool score."""

from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.gear_value import gear_value
from artifactsmmo_cli.ai.gear_value_core import Rank


def tool_value_pure(skill_effects: dict[str, int], skill: str) -> int:
    """PURE CORE (mechanically extracted, P4b): ``abs(skill_effects[skill])``.

    Definitionally ``|gather_score_pure|`` — the bridge pins the duality:
    on the tool domain (non-positive effects) maximizing this value is
    exactly minimizing the gather score the combat-side picker minimizes.
    """
    effect = skill_effects.get(skill, 0)
    return abs(effect)


def equip_value(stats: ItemStats) -> int:
    """Combat/utility value of an equippable, absent any particular monster —
    the public name for ``gear_value(stats, Rank)``. Single source shared by the
    UpgradeEquipment goal, the Tier-1 objective, the delete-dominance gate and
    the progression reserve.

    Rank is NOT its own formula. It is the SAME `weapon_score`/`armor_score`
    the combat loadout picker maximizes, evaluated against the catalog-median
    canonical adversary (``gear_value_core.rank_adversary``) — so the
    acquisition path and the picker can no longer reach opposite verdicts about
    the same slot. See ``ai/gear_value.gear_value`` for the unification and
    ``ai/gear_value_core`` for how every constant of that adversary is derived
    from the pinned live catalog.

    The non-tool tiebreak survives unchanged: the weapon branch is
    ``weapon_score`` = ``2 * WScore + nonToolBonus`` (Formal/PurposeRouting.
    combatScore), so a non-tool weapon strictly outranks an attack-equivalent
    tool and any strict attack inequality is preserved (the 2x factor protects
    the tiebreaker). Without it, copper_dagger (5 earth atk, non-tool) tied
    fishing_net (5 water atk, tool, -10 fishing skill effect) → gain 0 → root
    invisible in ranking — the bot never prioritized crafting it. Trace
    2026-06-06 session 09:59 cycles 56-110: Robby level 4 hp 135/135, no
    winnable monster at his level, ObtainItem(copper_dagger) scored 0 → no gear
    progression visible to the ranker → 50+ cycles of pure PursueTask.

    SCALE: Rank now returns the ``armor_score``/``weapon_score`` scale (1/20000
    HP of damage swing per turn for the monster-relative terms; ~10^4-10^6, not
    ~10^2). Every consumer compares Rank values WITHIN one slot or one item
    type, or against 0 — see the per-consumer audit in
    ``tests/test_ai/test_gear_value_rank_consumers.py``. No consumer carries an
    absolute Rank threshold.
    """
    return gear_value(stats, Rank)


def tool_value(stats: ItemStats, skill: str) -> int:
    """Tool benefit for a given gathering skill. The API encodes tools as
    `type_="weapon"` with `skill_effects[skill] = -cooldown_reduction_pct`
    (negative because the effect reduces a cost). We score by the absolute
    magnitude — bigger reduction wins. Returns 0 when the item has no
    effect for this skill. P4a: skill_effects values are ints — exact."""
    if not stats.skill_effects:
        return 0
    return tool_value_pure(stats.skill_effects, skill)
