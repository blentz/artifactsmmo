"""PURE proved core for the unified gear value ruler (extracted; mirrors
Formal/GearValue.lean). No GameData/IO — plain data only. See
docs/superpowers/specs/2026-06-28-gear-unified-ruler-design.md."""

from collections.abc import Mapping
from dataclasses import dataclass

from artifactsmmo_cli.ai.elements import ELEMENTS


@dataclass(frozen=True)
class Rank:
    """Monster-independent ranking purpose: "is this piece worth having at all?"

    ONE ALGORITHM, TWO PURPOSES. Rank is NOT a second formula. It is the
    `Combat` scorer evaluated against the CANONICAL ADVERSARY
    (`rank_adversary()` below) — the same `weapon_score`/`armor_score`
    functions, the same units, the same stat weights. Rank and Combat differ
    only in what the caller knows: Combat is handed a real monster and a real
    wearer; Rank has neither, so it supplies the catalog's typical adversary
    instead.

    Two rulers over the same slot is a livelock (see
    `equipment/slot_occupancy.py`): live 2026-08-04 Robby alternated
    `life_amulet` / `fire_and_earth_amulet` forever because the acquisition
    path ranked on a stat sum that could not see per-element damage % while
    the picker ranked on `armor_score`, which could. Routing Rank through the
    SAME function removes the possibility of that disagreement by
    construction, rather than re-tuning two formulas to agree.
    """


@dataclass(frozen=True)
class Combat:
    """Per-monster combat purpose: WHO is fighting WHAT.

    `player_attack` is the fighter's current per-element attack
    (`state.attack`). It is part of the purpose, not of the item, because a
    piece's `dmg`/`dmg_elements`/`critical_strike` percentages scale the
    PLAYER'S output — `armor_score` cannot price them without it. Two
    characters fighting the same monster with different weapons genuinely
    should rank the same +damage% armor differently, and `pick_loadout_cached`
    keys on the purpose, so it is also what keeps that memo sound.
    """

    monster_attack: Mapping[str, int]
    monster_resistance: Mapping[str, int]
    player_attack: Mapping[str, int]


@dataclass(frozen=True)
class Gather:
    """Per-skill gather purpose."""

    skill: str


# --- The canonical adversary (the Rank purpose's stand-in for "any monster") ---
#
# Every constant below is the MEDIAN of the pinned live catalog
# (`formal/sim/game_data_snapshot.json`, 58 monsters / 232 per-element
# resistance entries), not a taste call. `tests/test_ai/test_gear_value.py`
# re-derives them from that snapshot, so a catalog shift fails the suite
# instead of silently leaving Rank calibrated against a game that no longer
# exists.

RANK_MONSTER_TOTAL_ATTACK = 135
"""Median TOTAL per-element attack over all 58 monsters in the pinned catalog
(min 4 = chicken, max 1250 = flameche). The median is the honest point estimate
of "the monster you will meet" when Rank is asked before any monster is known."""

RANK_MONSTER_RESISTANCE = 0
"""Median of all 232 monster per-element resistance entries in the pinned
catalog (range -80..115). Zero is the empirical centre, and it is also the
value that leaves `armor_score`'s `max(0, 100 - mon_res[e])` offense clamp at
its natural maximum. NOTE the clamp makes any UNIFORM resistance a pure scale
factor `(100-r)/100` on the offense term, so this choice moves the
offense-vs-defense balance only, never the within-term ordering."""

RANK_REFERENCE_ATTACK = RANK_MONSTER_TOTAL_ATTACK // len(ELEMENTS)
"""The canonical adversary's per-element attack — the median total spread
UNIFORMLY over the elements. Uniform because a monster-independent ruler has no
evidence for preferring one element: concentrating the reference attack in, say,
fire would price fire resistance above water resistance for no reason in the
data.

The SAME magnitude is handed back as the reference WEARER's attack, making the
canonical duel SYMMETRIC. That is what fixes the defense-vs-offense exchange
rate without inventing a constant: with both sides at `m` per element, a piece
with `r`% resistance in every element stops `4*m*r/100` HP per turn, and a piece
with `r`% global damage adds `0.01*r*4*m` HP per turn — EQUAL. A level-
appropriate fight is by definition one where the two sides' output is
comparable, so the mirror duel is the level-appropriate reference.

The magnitude `m` itself only trades the two monster-relative terms against
`armor_score`'s monster-INDEPENDENT `flat_utility` block (both required orderings
in `tests/test_ai/test_gear_value.py` hold for every `m >= 2`, so `m` is not
load-bearing for them). It IS what stops `wisdom` being weighted 1:1 against
combat: at `m = 33` one point of per-element resistance is worth 33 wisdom and
one point of global `dmg` is worth 132, where the retired flat `rank_value` sum
made all three worth exactly 1 each — the bug that ranked `adventurer_vest`
(hp 60, wisdom 20) above `mushmush_jacket` (hp 60, dmg 10, crit 3)."""


def rank_adversary() -> Combat:
    """The `Combat` purpose the `Rank` purpose evaluates against.

    Rank IS Combat here — this function is the whole of the difference between
    the two purposes, and it is pure data derived from the live catalog. See
    the constants above for each field's derivation."""
    return Combat(
        monster_attack={e: RANK_REFERENCE_ATTACK for e in ELEMENTS},
        monster_resistance={e: RANK_MONSTER_RESISTANCE for e in ELEMENTS},
        player_attack={e: RANK_REFERENCE_ATTACK for e in ELEMENTS},
    )


# RETIRED: `combat_raw(attack, resistance, hp_restore, hp_bonus, dmg,
# critical_strike, lifesteal, combat_buff)` — a flat 8-stat sum that was
# `strategic_value`/`pursuit_value`'s "how much combat is in this item" scalar.
# It added a resistance PERCENTAGE to an HP amount to a damage figure 1:1, the
# same category error the Rank/Combat unification removed from the gear ruler,
# surviving one layer up in the ECONOMICS layer. The economics layer now reads
# the ruler's OWN combat term (`ai/gear_value.gear_components`), so there is one
# scoring algorithm and no flat sum left to disagree with it.
