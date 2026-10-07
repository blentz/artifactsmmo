"""The monster to farm: the best winnable NORMAL monster in the next uncleared
tier's band.

Replaces an unbounded argmax. `cheapest_path_to_level` filtered candidates with
`1 <= lvl <= sim_level + 1` — a floor of literally 1, dating to ed676b81
(2026-05-18) — and it is tier 2 of `GamePlayer._winnable_farm_target`, ranking
above the windowed picker at tier 3. So `combat_picker`'s correct
`[char_level - 1, char_level + 2]` window never got a vote and four of five live
characters were grinding 4 to 10 levels below themselves (2026-08-23).

No explicit level floor appears here, and none is wanted. The band IS the floor:
a tier's monsters sit between that rung and the next, so a target far below the
character cannot be drawn in the first place. A character whose LEVEL has
outrun its TIER — Robby at 30 with T20 uncleared — keeps fighting the tier it
is stuck on while that tier still pays XP; once every monster in it is grey the
answer is None, because its constraint is gear, not target selection.

A CEILING is also required, and it is not this module's to invent: it is
`FightAction`'s own `state.level + FIGHT_LEVEL_GAP_CEILING` structural gate
(`ai.actions.combat._structurally_applicable`). `is_winnable` answers a pure
STAT question — would this loadout beat that monster — and says nothing about
whether the executor will ever attempt the fight. Fix round 1 (task 5.2,
2026-08-23) found the gap live: at L10, tier 10 (flying_snake L12, mushmush)
reads CLEARED (both stat-winnable), so the next uncleared tier is 15, whose
band (highwayman L15, pig L19, skeleton L18, wolf L15) is ALSO stat-winnable
with a strong loadout — but every one of those levels exceeds `10 + 2`, so
`FightAction` refuses all of them outright. `GrindCharacterXP` for that target
then plans to zero nodes, and — because a NON-None, "winnable" path_monster
outranks tier 3 in `GamePlayer._winnable_farm_target` — the windowed picker
that WOULD have found flying_snake never even runs. An unfightable target is
worse than a too-low one: too-low still grinds, unfightable grinds nothing.
So the two gates MUST agree: a monster this function offers has to be one
`FightAction` will actually accept, which means importing the executor's own
constant rather than re-deriving or copying its value.

The FLOOR is the same agreement from below. `FightAction` refuses an XP fight
against a monster that pays no XP (`xp_per_kill > 0`), so a band whose
winnable monsters are all grey is as unfightable as one above the ceiling.
Live 2026-10-03: four of five characters (L29-31 against T15/T20) were handed
pig, spider or skeleton at 0 XP, and `GrindCharacterXP` failed at one node on
561 of 561 searches in three hours.

None is returned in four cases: the ladder is fully cleared, the tier's band
holds no monster winnable by stats, every stat-winnable monster in the band
sits above the executor's level ceiling, or every one pays no XP — a gear wall
in every case but the first. A consumer
needing to distinguish them (e.g. to report different user messages) must add
the distinction rather than guessing from None. Do not change the signature
speculatively.
"""

import dataclasses
from collections.abc import Callable
from fractions import Fraction

from artifactsmmo_cli.ai.actions.combat import FIGHT_LEVEL_GAP_CEILING
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.fight_upkeep_core import NO_UPKEEP, xp_per_action
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.tier_ladder import normal_band
from artifactsmmo_cli.ai.tiers.tier_progress import next_uncleared_tier
from artifactsmmo_cli.ai.world_state import WorldState


def band_combat_target(state: WorldState, game_data: GameData,
                       history: LearningStore | None,
                       price_of: Callable[[str], Fraction]) -> str | None:
    """Best winnable, FIGHTABLE normal monster in the next uncleared tier's
    band, by XP per ACTION, its upkeep included (USER 2026-10-07).

    The rank used to be XP per KILL, where upkeep is invisible. Live, Lor's
    death_knight grind used ~3 small_health_potion a fight: 46% of 5.8h went to
    gathering sunflowers, 40% to resting, 11% to fighting. The key is
    `fight_upkeep_core.xp_per_action` over the measured `fight_upkeep`
    (actions and consumables per kill), each consumable at `price_of` — its
    acquisition actions per unit. A monster without a measurement counts one
    action a kill and is tried. Ties go to the higher level.

    Evaluated at RESTORABLE HP, never current — route existence must not
    depend on incidental damage. A character resting to full is always an
    option, so "is this tier's band winnable" must not flip with transient HP.

    A candidate must clear `is_winnable` (a stat prediction) AND both of
    `FightAction`'s structural level gates: the `state.level +
    FIGHT_LEVEL_GAP_CEILING` ceiling (the executor's suicide guard, blind to
    gear strength) and the `xp_per_kill > 0` floor (an XP fight is refused
    against a grey). A monster that passes the first but fails either of the
    others is stat-winnable and still never gets fought — see the module
    docstring. A monster must also SPAWN somewhere now
    (`GameData.monster_locations`): the action factory builds a `FightAction`
    only for those, so an event monster that is not up is no target either
    (live 2026-10-04: Robby's band named `full_moon_vampire` and
    `GrindCharacterXP` failed 23 of 23 searches).
    """
    tier = next_uncleared_tier(state, game_data, history)
    if tier is None:
        return None
    rested = dataclasses.replace(state, hp=state.max_hp)
    level_ceiling = state.level + FIGHT_LEVEL_GAP_CEILING
    winnable = [code for code in normal_band(game_data, tier)
                if game_data.monster_levels[code] <= level_ceiling
                and game_data.xp_per_kill(code, state.level) > 0
                and game_data.monster_locations(code)
                and is_winnable(rested, game_data, code, history)]
    if not winnable:
        return None
    def key(code: str) -> tuple[Fraction, int]:
        upkeep = history.fight_upkeep(code) if history is not None else None
        rate = xp_per_action(game_data.xp_per_kill(code, state.level),
                             upkeep or NO_UPKEEP, price_of)
        return rate, game_data.monster_levels[code]

    return max(winnable, key=key)
