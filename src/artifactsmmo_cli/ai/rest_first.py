"""Rest before a fight, or fight now, read from the world (`rest_first_core`).

A try's seconds are the fight (`FIGHT_SECONDS`, the loop rate's per-fight
duration), the expected rest back to full over the fight's endings (a win
from the HP it ends at, a loss from `LOSS_HP`) and, when a loss is possible,
its share of the walk back from `RESPAWN_TILE` to the monster's nearest tile.
Recovery is priced as a Rest (`loop_rate_core.rest_part`) on both sides of
the comparison, the goal the rest guards map to (`RestoreHPGoal`); food would
shorten both. Read at the two places a fight is about to run at less than full
HP: the cached plan's next Fight (`GamePlayer._fight_ready`) and the
REST_FOR_COMBAT guard, so a fight the cache refuses is one the guard rests
for."""

from dataclasses import replace
from fractions import Fraction

from artifactsmmo_cli.ai.actions.cost_core import travel_seconds
from artifactsmmo_cli.ai.combat import fight_endings
from artifactsmmo_cli.ai.consumable_price import FIGHT_SECONDS
from artifactsmmo_cli.ai.fight_odds_core import win_probability as odds_win
from artifactsmmo_cli.ai.fight_terms_core import SCALE
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.loop_rate import LOSS_HP, RESPAWN_TILE, monster_tile
from artifactsmmo_cli.ai.loop_rate_core import rest_part
from artifactsmmo_cli.ai.rest_first_core import kill_seconds, rest_first
from artifactsmmo_cli.ai.world_state import WorldState


def fight_kill_seconds(state: WorldState, game_data: GameData, monster: str) -> Fraction | None:
    """Expected seconds to one kill of `monster` from `state.hp` and back to
    full (see the module doc); None when the fight cannot be won."""
    endings = fight_endings(state, game_data, monster)
    p_win = odds_win(endings)
    recovery = sum((e.prob * rest_part(state.max_hp - (e.hp_end // SCALE if e.win else LOSS_HP),
                                       state.max_hp)
                    for e in endings), Fraction(0))
    walk = Fraction(0)
    if 0 < p_win < 1:
        walk = (1 - p_win) * travel_seconds(RESPAWN_TILE, monster_tile(state, game_data, monster))
    return kill_seconds(p_win, FIGHT_SECONDS + recovery + walk)


def rest_pays(state: WorldState, game_data: GameData, monster: str) -> bool:
    """Resting to full before fighting `monster` costs less per kill than
    fighting now (`rest_first_core.rest_first`); never at full HP."""
    if state.hp >= state.max_hp:
        return False
    rest = rest_part(state.max_hp - state.hp, state.max_hp)
    return rest_first(rest, fight_kill_seconds(state, game_data, monster),
                      fight_kill_seconds(replace(state, hp=state.max_hp), game_data, monster))
