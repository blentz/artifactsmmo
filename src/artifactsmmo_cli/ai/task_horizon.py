"""How far out is the held task's fight? — the ONE-LEVEL PLANNING HORIZON.

`combat_deficit` answers "what gear closes this fight", and `deficit_upgrade_target`
answers it with the first item to build. Neither says what to do when the answer is
NOTHING, and until this module the bot's answer was: fall through to the
monster-blind value scan — the same scan that chose `iron_boots`, already worn and
absent from all 24 items that improved the pig margin, for ten hours.

Measured after `e6a2e37c` taught `deficit_upgrade_target` to honour `closes`, over
every (scenario, monster) losing pair in the offline corpus: the fall-through arm is
not a corner. It is most of the surface. So "what happens when gear cannot close it"
had to become a decision rather than a default.

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
  * `HORIZON_LEVEL_UP`    — one level plus gear closes it. Take the level.
  * `HORIZON_OUT_OF_REACH`— neither. The fight is not a near-term planning target:
                            stop spending cycles on gear that cannot win it, cancel
                            the task if a coin is in the pocket, and otherwise let it
                            sit INERT while the character does other work.

OUT OF REACH IS NEVER PERMANENT, AND NOTHING HAD TO BE BUILT FOR THAT. The verdict is
recomputed from live state every cycle — it is strictly fresher than the
`DoomedMemo` re-probe the rest of the bot uses for "unfindable at this level"
(`plannability_signature` is `(character level, sorted skill levels)`, so a level-up
invalidates it). "Re-check at least at each level-up" is therefore satisfied by
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

from artifactsmmo_cli.ai.combat_deficit import (
    blocked_task_monster,
    combat_deficit,
    deficit_upgrade_target,
    has_combat_deficit,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.rung_state_core import projected_max_hp
from artifactsmmo_cli.ai.per_state_memo import per_state
from artifactsmmo_cli.ai.world_state import WorldState

HORIZON_GEAR = "gear"
"""Gear alone closes the held task's fight."""

HORIZON_LEVEL_UP = "level_up"
"""One character level, plus the gear that level admits, closes it."""

HORIZON_OUT_OF_REACH = "out_of_reach"
"""Neither does. Not "impossible" — outside the one-level planning horizon."""


@dataclass(frozen=True)
class TaskHorizon:
    """The held task's fight, read against the one-level horizon.

    `gear_target` is carried ONLY as evidence for the `HORIZON_GEAR` verdict — the
    unpriced first step of the chain that closes the fight. The `GEAR_REVIEW` guard
    re-asks `deficit_upgrade_target` with its own `acquisition_actions` pricing,
    because WHICH item to build first is an economics question and this is not: see
    `resolve_task_horizon`.
    """

    monster: str
    verdict: str
    gear_target: tuple[str, str] | None


def next_level_state(state: WorldState) -> WorldState:
    """The same character one level up, with every growth the model knows about.

    A pool widening alone would have been the dishonest half of this. `state.level`
    is read in THREE places that decide a fight, and the projection has to move all
    three or it understates what the level buys:

      1. `combat_deficit._pool` admits catalogue gear at `stats.level <= state.level`
         — the ACQUISITION candidates widen.
      2. `equipment/loadout_picker` skips owned items at `state.level < stats.level`
         — gear already in the bag but level-gated becomes WEARABLE, which changes
         the fight with no acquisition at all.
      3. `max_hp` grows, which is what `combat._effective_player_hp` divides into
         `rounds_to_die`.

    The HP grant is `learning.rung_state_core.projected_max_hp`, the same published
    `+5 Max HP per level` the cycle oracle's rung walk applies — asked of that module
    rather than restated here, because a second copy of a game-rule constant is how
    the two halves of a rule drift apart.

    `hp` is set to the grown `max_hp`: this state exists to answer "can I win this
    fight", and rest is an action the planner has. Same framing as `combat_deficit`,
    which rests its own state at the top of the walk.
    """
    level = state.level + 1
    max_hp = projected_max_hp(state.max_hp, state.level, level)
    return dataclasses.replace(state, level=level, max_hp=max_hp, hp=max_hp)


@per_state
def resolve_task_horizon(state: WorldState, game_data: GameData) -> TaskHorizon | None:
    """Read the held task's fight against the one-level horizon, or None.

    None means there is no reading to take: no monsters task in progress, or one the
    character already beats. Callers that must distinguish "no task" from "out of
    reach" get that for free — a verdict exists only where a fight is lost.

    UNPRICED — AND THAT IS A COST DECISION, NOT A SOUNDNESS ONE. `combat_deficit`
    ranks its greedy walk on margin gain PER ACTION when an `actions_of` is supplied,
    which changes WHICH item is picked at each step and can therefore change whether
    the chain closes inside `MAX_CHAIN`. The first version of this docstring
    justified the unpriced call by claiming that maximising raw margin gain per step
    is the walk's best shot at closing. **That claim is false and was measured false
    on 2026-08-25.** Over the four (character, monster) pairs where the two
    orderings disagree, the PRICED walk closes and the unpriced one does not, every
    time — and it does so by going DEEPER, not by picking better:

        l35_artifact_fill          demon        unpriced stalls at 2  priced closes at 4
        l35_boots_drop_farm        demon        unpriced stalls at 2  priced closes at 5
        l35_boots_drop_farm        cursed_tree  unpriced stalls at 3  priced closes at 7
        l25_currency_leaf_unfunded vampire      unpriced stalls at 2  priced closes at 5

    (all four first steps are utility-slot boost potions — the cheapest thing the
    priced ranking can reach, which the raw-margin ranking passes over.)

    Greedy is greedy: neither ordering is an existence oracle, and the unpriced one
    is simply the one that is affordable here. It stays for two reasons that are
    about cost and coherence rather than accuracy:

      * The priced call is NOT a function of `(state, game_data)` — `_deficit_actions`
        closes over a `SelectionContext` and a `LearningStore`
        (`strategy_driver.map_guard`). Asking it here would make the verdict
        ctx-dependent and break the `per_state` identity memo below, which is the
        only thing keeping the latch, the guard mapper and the cancel rung from
        disagreeing with each other. Trading a two-oracle divergence for a
        three-consumer one is a bad trade.
      * Measured on those same four pairs, the priced walk costs 85-193 ms against
        58-88 ms unpriced, on a path that runs every cycle.

    THE RESIDUAL THIS LEAVES, stated rather than hidden: over the 1,375 non-GEAR
    derived pairs, two would be read OUT_OF_REACH although a priced chain closes
    them (0.15 %). That is only reachable at all once a `tasks_coin` is in a pocket,
    and as of 84,590 live cycles in `learning.db` no fleet character has ever held
    one (0 task completions, 0 coin drops, 5 accepts). If it ever does matter, the
    fix is to thread the WHOLE verdict on `SelectionContext` — the seam
    `supply_target` and `turn_in` use — computed once by the player with the guard's
    own pricing. It is NOT a second pricing path into `tiers/means.py`, whose own
    header records the import cycle that would reopen.

    The `GEAR_REVIEW` guard keeps its own priced call for the target it commits to —
    that answer is pinned by `test_the_task_triple_moves_the_gear_review_target` and
    does not move here.

    ONE READING PER CYCLE, SHARED. Memoised on the IDENTITY of `(state, game_data)`
    (`per_state_memo`, the pattern the keep authority uses): the gear latch, the
    `GEAR_REVIEW` guard mapper and the `TASK_CANCEL` means rung all ask within one
    cycle and must not be able to disagree, and the walk costs a catalogue sweep per
    chain step. `combat_deficit`'s own docstring says a per-cycle caller must
    memoise; this is that caller.
    """
    monster = blocked_task_monster(state)
    if monster is None or not has_combat_deficit(state, game_data):
        return None
    target = deficit_upgrade_target(state, game_data)
    if target is not None:
        return TaskHorizon(monster=monster, verdict=HORIZON_GEAR, gear_target=target)
    at_next = combat_deficit(next_level_state(state), game_data, monster)
    if at_next is None or at_next.closes:
        # `None` is the level-alone case: the +5 HP (or a level-gated item already in
        # the bag) wins the fight with nothing to acquire. It is a level-up verdict
        # exactly as much as a closing chain is, and dropping it would have made the
        # cheapest instance of this rule the one it missed.
        return TaskHorizon(monster=monster, verdict=HORIZON_LEVEL_UP, gear_target=None)
    return TaskHorizon(monster=monster, verdict=HORIZON_OUT_OF_REACH, gear_target=None)
