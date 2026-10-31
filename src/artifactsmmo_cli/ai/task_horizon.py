"""How far out is the held task's fight? — the ONE-LEVEL PLANNING HORIZON.

The gear that closes the held task's fight is `L*` of the task monster
(`gear_objective.gear_objective_for`, plan C Task 2): the best loadout of achievable
gear for that monster, its missing pieces in pursuit order. What to do when even
`L*` does not close it is this module's question. Until it existed the bot's answer
was: fall through to the monster-blind value scan — the same scan that chose
`iron_boots`, already worn and absent from all 24 items that improved the pig
margin, for ten hours.

Measured over every (scenario, monster) losing pair in the offline corpus, the
fall-through arm is not a corner. It is most of the surface. So "what happens when
gear cannot close it" had to become a decision rather than a default.

USER (2026-08-25), stating the rule this module implements:

    "cancel tasks that we can't meet through gear upgrade, or (level-up by exactly
    1 level and gear upgrade). anything beyond a 1-level horizon is too far out to
    be a reasonable near-term planning target."

and, refining what "cancel" means when the coin to cancel with is not in the pocket:

    "It is a known condition that Tasks might be uncancelable until we get a coin.
    Tasks can remain inert until that condition is met. There isn't ever going to be
    a truly uncompletable task. But, it is conceivable that the task's completion may
    lie outside the level+1 horizon."

So the verdict is a HORIZON READING, not a sentence:

  * `HORIZON_GEAR`        — gear alone closes the fight. Build it.
  * `HORIZON_LEVEL_UP`    — one level plus gear closes it: `L*` one level up wins
                            the fight `L*`'s gate reads (`drop_fight_winnable`).
                            Take the level.
  * `HORIZON_OUT_OF_REACH`— neither. The fight is not a near-term planning target:
                            stop spending cycles on gear that cannot win it, cancel
                            the task if a coin is in the pocket, and otherwise let it
                            sit INERT while the character does other work.

OUT OF REACH IS NEVER PERMANENT, AND NOTHING HAD TO BE BUILT FOR THAT. The verdict is
recomputed from live state every cycle, as every goal's answer has been since
Phase 3-1 retired the arbiter's doomed-memo. "Re-check at least at each level-up" is therefore satisfied by
construction, with no memo entry, no expiry and no state to get stuck in.

WHY A ONE-LEVEL BOUND AND NOT TWO. It is what makes the question decidable at all.
Each extra level is another whole catalogue walk over a body that does not exist yet,
and the answer decays: a projection two levels out is a guess about gear the
character cannot craft, at a skill level it has not reached, against a body whose
only modelled growth is +5 HP. One level is the distance over which the projection is
still a fact rather than a forecast.
"""

import dataclasses
from dataclasses import dataclass

from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.combat_deficit import blocked_task_monster, has_combat_deficit
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective import gear_closes_for, gear_fighter_for
from artifactsmmo_cli.ai.learning.rung_state_core import projected_max_hp
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_fight_winnable
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

HORIZON_GEAR = "gear"
"""Gear alone closes the held task's fight: `L*` of the task monster wins it,
and a piece of it is missing."""

HORIZON_LEVEL_UP = "level_up"
"""One character level, plus the gear that level admits, closes it."""

HORIZON_OUT_OF_REACH = "out_of_reach"
"""Neither does. Not "impossible" — outside the one-level planning horizon."""


@dataclass(frozen=True)
class TaskHorizon:
    """The held task's fight, read against the one-level horizon.

    The gear to build on the `HORIZON_GEAR` verdict is not carried: it is the
    first missing piece of `L*(monster)` (`gear_objective_for`), priced, which
    only the task root asks (`decisions.root._task_root`); every other reader
    asks only the verdict (ruling C2-perf).
    """

    monster: str
    verdict: str


def next_level_state(state: WorldState) -> WorldState:
    """The same character one level up, with every growth the model knows about.

    A pool widening alone would have been the dishonest half of this. `state.level`
    is read in THREE places that decide a fight, and the projection has to move all
    three or it understates what the level buys:

      1. `gear_objective`'s universe admits gear at `stats.level <= state.level`
         — the ACHIEVABLE set `L*` is picked from widens.
      2. `equipment/loadout_picker` skips owned items at `state.level < stats.level`
         — gear already in the bag but level-gated becomes WEARABLE, which changes
         the fight with no acquisition at all.
      3. `max_hp` grows, which is what `fight_terms_core.effective_player_hp` divides into
         `rounds_to_die`.

    The HP grant is `learning.rung_state_core.projected_max_hp`, the same published
    `+5 Max HP per level` the cycle oracle's rung walk applies — asked of that module
    rather than restated here, because a second copy of a game-rule constant is how
    the two halves of a rule drift apart.

    `hp` is set to the grown `max_hp`: this state exists to answer "can I win this
    fight", and rest is an action the planner has (the `L*` fighter is at max HP).
    """
    level = state.level + 1
    max_hp = projected_max_hp(state.max_hp, state.level, level)
    return dataclasses.replace(state, level=level, max_hp=max_hp, hp=max_hp)


def resolve_task_horizon(state: WorldState, game_data: GameData, ctx: SelectionContext,
                         history: LearningStore | None) -> TaskHorizon | None:
    """Read the held task's fight against the one-level horizon, or None.

    None means there is no reading to take: no monsters task in progress, or one the
    character already beats securely (`has_combat_deficit`, `secure_win` on bare
    gear at max HP). Callers that must distinguish "no task" from "out of reach"
    get that for free — a verdict exists only where a fight is lost.

    GEAR is `L*` of the task monster clearing the same bar the deficit is read
    at (`gear_closes_for`): its fighter, wearing `L*` on bare gear at max HP,
    `secure_win`s, and a piece of it is missing (the objective's own gain
    filter). A missing `L*` that still loses closes
    nothing, so it is no gear verdict: the level-up and out-of-reach arms read
    it. Nor is a monster with no tile the fight pool reaches
    (`monster_spawn_known`, the gate every `L*` candidate passes): its `R`
    prices the walk back after a loss from its tile, so it has no `L*`, and
    the same two arms read it.

    The verdict prices no piece and reads gains only once `L*` secures the
    fight, up to the first missing piece; the achievable set it is read over
    is computed once per `search_cache` episode for the character
    (`gear_objective._cycle_inputs`, ruling C2-perf): every task-worth probe of
    a cycle shares it.
    """
    monster = blocked_task_monster(state)
    if monster is None or not has_combat_deficit(state, game_data):
        return None
    if (game_data.monster_spawn_known(monster)
            and gear_closes_for(monster, state, game_data, ctx, history)):
        return TaskHorizon(monster=monster, verdict=HORIZON_GEAR)
    if predict_win(dataclasses.replace(state, hp=state.max_hp), game_data, monster):
        # A fight the gate takes (P(win) at least θ) that no gear secures: the
        # task is workable now, not a level away (post-merge review
        # 2026-10-16; the gear deficit is the SECURE_WIN bar's, the gate's is θ).
        return None
    # One level up (ruling C2-one-model): `L*` of the task monster over the
    # character one level up — its achievable set at the next level, worn by
    # the grown body — passes the gate `L*`'s own candidates pass
    # (`drop_fight_winnable`: the bare odds or a stockable potion loadout, the
    # learned record, a party; ruling C2-R m3). With nothing left to build
    # (`L*` held and lost) that is the level alone, a level-up verdict all
    # the same.
    fighter = gear_fighter_for(monster, next_level_state(state), game_data, ctx, history)
    if drop_fight_winnable(fighter, game_data, monster):
        return TaskHorizon(monster=monster, verdict=HORIZON_LEVEL_UP)
    return TaskHorizon(monster=monster, verdict=HORIZON_OUT_OF_REACH)
