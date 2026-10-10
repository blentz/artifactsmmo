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

THE RANK IS XP PER SECOND OVER THE BEST LOADOUT (USER 2026-10-10: "loadout
picks the monster, but we don't pick sub-standard loadouts just because they're
available"). A monster is ranked by the XP per second of farming it, so a
consumable loadout changes WHICH monster is fought only when it pays more per
second, its price included (`best_loadout`). A monster beaten only with a
potion — held or priced — is a candidate at that loop's rate; a monster
lost to on the learned record (`combat.loss_vetoed`) is not, whatever the
model says a potion would do. Which monster pays more is the ONLY question
asked of the consumables: every GEAR decision keeps judging bare gear
(`BandTarget.bare_fight`, `SelectionContext.combat_propped`), so a
potion-propped win never hides a gear upgrade.

None is returned in four cases: the ladder is fully cleared, the tier's band
holds no monster winnable by stats or by a loadout, every winnable monster in
the band sits above the executor's level ceiling, or every one pays no XP — a
gear wall in every case but the first. A consumer
needing to distinguish them (e.g. to report different user messages) must add
the distinction rather than guessing from None. Do not change the signature
speculatively.
"""

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from functools import cache, partial

from artifactsmmo_cli.ai.actions.combat import FIGHT_LEVEL_GAP_CEILING
from artifactsmmo_cli.ai.best_loadout import BestLoadout
from artifactsmmo_cli.ai.combat import is_winnable, loss_vetoed
from artifactsmmo_cli.ai.consumable_price import FIGHT_SECONDS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.fight_upkeep_core import FightUpkeep, xp_per_action
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loop_rate import LoopRate
from artifactsmmo_cli.ai.tiers.tier_ladder import normal_band
from artifactsmmo_cli.ai.tiers.tier_progress import next_uncleared_tier
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass(frozen=True)
class BandTarget:
    """The band's pick and what bare gear says about the band.

    `monster` is the fightable monster with the most XP per second (`rate`).
    `bare_fight` is whether ANY fightable monster in the band is winnable on
    bare gear (`is_winnable`) — the band's answer to every gear decision, which
    never reads a consumable: False means the band is fought only on potions."""

    monster: str
    rate: Fraction
    bare_fight: bool


def loop_seconds(rate: LoopRate) -> Fraction:
    """Seconds of one modelled loop: the fight, its recovery and the price of
    what it consumed."""
    return rate.fight_seconds + rate.recovery_seconds + rate.consumed_seconds


def rank_rate(xp_per_kill: int, upkeep: FightUpkeep | None, best: Callable[[], BestLoadout],
              price_of: Callable[[str], Fraction]) -> Fraction:
    """XP per second of farming a monster: MEASURED where the store has its
    upkeep, MODELLED otherwise — one key for both.

    * Measured: `fight_upkeep_core.xp_per_action` (every cycle the grind spent
      per kill, and its consumables at `price_of`, acquisition actions per unit)
      over `FIGHT_SECONDS`, the seconds of one fight-equivalent action — the
      unit both the acquisition walk and the model's prices are counted in.
    * Modelled: the kill's XP over the seconds of the best loadout's loop
      (`best_loadout`, `loop_seconds`). A monster the record says is beaten
      (`is_winnable`'s monotonic-win inference) while the model's walk loses is
      ranked on the walk's seconds all the same: the record decides the win,
      the model only the time."""
    if upkeep is not None:
        return xp_per_action(xp_per_kill, upkeep, price_of) / FIGHT_SECONDS
    return Fraction(xp_per_kill) / loop_seconds(best().rate)


def target_rate(state: WorldState, game_data: GameData, history: LearningStore | None,
                code: str, price_of: Callable[[str], Fraction],
                loadout: Callable[[], BestLoadout]) -> Fraction:
    """`rank_rate` of farming `code` at the character's level and wisdom, its
    upkeep read from the store; `loadout` is its best loadout, asked only when
    there is no measurement."""
    upkeep = history.fight_upkeep(code) if history is not None else None
    return rank_rate(game_data.xp_per_kill(code, state.level, state.wisdom), upkeep,
                     loadout, price_of)


def band_combat_target(state: WorldState, game_data: GameData,
                       history: LearningStore | None,
                       price_of: Callable[[str], Fraction],
                       loadout_of: Callable[[str], BestLoadout]) -> BandTarget | None:
    """Best winnable, FIGHTABLE normal monster in the next uncleared tier's
    band, by XP per SECOND over its best loadout (USER 2026-10-10), its measured
    upkeep where there is one (USER 2026-10-07: Lor's death_knight grind used
    ~3 small_health_potion a fight, 46% of 5.8h gathering sunflowers): see
    `rank_rate`. `loadout_of` is `best_loadout` against one monster; ties go to
    the higher level, then the band's order.

    Evaluated at RESTORABLE HP, never current — route existence must not
    depend on incidental damage. A character resting to full is always an
    option, so "is this tier's band winnable" must not flip with transient HP.

    A candidate must be WINNABLE — `is_winnable` (bare gear: a stat
    prediction and the learned record), or, failing that, its best loadout's
    loop wins and the learned-loss veto does not refuse it — AND clear both of
    `FightAction`'s structural level gates: the `state.level +
    FIGHT_LEVEL_GAP_CEILING` ceiling (the executor's suicide guard, blind to
    gear strength) and the `xp_per_kill > 0` floor (an XP fight is refused
    against a grey). A monster that passes the first but fails either of the
    others is winnable and still never gets fought — see the module
    docstring. A monster must also SPAWN somewhere now
    (`GameData.monster_locations`): the action factory builds a `FightAction`
    only for those, so an event monster that is not up is no target either
    (live 2026-10-04: Robby's band named `full_moon_vampire` and
    `GrindCharacterXP` failed 23 of 23 searches).

    The loadout search runs only where it is read: a monster winnable bare
    with a measured upkeep is ranked on the measurement alone.
    """
    tier = next_uncleared_tier(state, game_data, history)
    if tier is None:
        return None
    rested = dataclasses.replace(state, hp=state.max_hp)
    level_ceiling = state.level + FIGHT_LEVEL_GAP_CEILING
    fightable = [code for code in normal_band(game_data, tier)
                 if game_data.monster_levels[code] <= level_ceiling
                 and game_data.xp_per_kill(code, state.level) > 0
                 and game_data.monster_locations(code)]
    scored: list[tuple[str, Fraction]] = []
    bare_fight = False
    for code in fightable:
        bare = is_winnable(rested, game_data, code, history)
        loadout = cache(partial(loadout_of, code))
        if not bare and (not loadout().rate.win or (
                history is not None and loss_vetoed(rested, game_data, code, history))):
            continue
        bare_fight = bare_fight or bare
        scored.append((code, target_rate(state, game_data, history, code, price_of, loadout)))
    if not scored:
        return None
    code, rate = max(scored, key=lambda item: (item[1], game_data.monster_levels[item[0]]))
    return BandTarget(code, rate, bare_fight)
