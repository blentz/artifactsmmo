"""What a second of fighting earns in gold, and what spending gold costs.

One rate, two readers. `consumable_price` converts a consumable's gold price to
seconds with it; `acquisition_cost` charges every unit of gold a priced route
SPENDS — from the pocket or withdrawn from the bank — the actions it takes to
earn that unit again (S-046, the USER's ruling 2026-10-30). Before that ruling
held gold was free to the pricer (ruling T2k), so the whole bank cost one
withdraw: live Robby planned `WithdrawGold(90844)` -> `GeBuy(mithril_helm)`.

Moved here from `consumable_price` / `task_worth` (unchanged) because the
pricer reads it, and both of those modules import the pricer."""

from fractions import Fraction

from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.fight_walk import walk_seconds
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.fight_loop_cost import cycles_per_kill
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState


def fight_gold_rate(state: WorldState, game_data: GameData, monster: str,
                    fight_seconds: Fraction) -> Fraction:
    """Mean fight gold per cycle of farming `monster`, each fight lasting
    `fight_seconds` (its rests priced in fights of that length)."""
    gold = Fraction(game_data.monster_min_gold(monster) + game_data.monster_max_gold(monster), 2)
    per_kill = Fraction(cycles_per_kill(expected_damage_per_fight(state, game_data, monster),
                                        state.max_hp, fight_seconds))
    return gold / per_kill


def gold_per_second(state: WorldState, game_data: GameData, ctx: SelectionContext) -> Fraction:
    """The grind target's fight gold per second; while there is none, the gear
    objective's `m*`; 0 with neither.

    The `m*` fallback is ruling AL (final review F5): while a piece of `L*` is
    missing `farm_target` names no grind target, for days, and a 0 rate left
    every buy-only consumable unpriced for the acquisition fights it stocks.
    The rate is a PRICING input (what a second of fighting earns), not a fight
    choice, so reading `m*` here fights nothing.

    A second of fighting is one in `L*(m*)` (ruling CB): the objective's own
    fighter, wearing the loadout the rate is earned in; the character as it is
    without an objective."""
    monster = ctx.combat_monster
    if monster is None and ctx.gear_objective is not None:
        monster = ctx.gear_objective.monster
    if monster is None:
        return Fraction(0)
    fighter = state
    if ctx.gear_objective is not None:
        if ctx.gear_objective.fighter is None:
            raise ValueError("the gear objective carries no fighter to price fight gold in")
        fighter = ctx.gear_objective.fighter
    seconds = walk_seconds(fighter, game_data, monster, (), ctx.timing())
    return fight_gold_rate(fighter, game_data, monster, seconds) / seconds


def gold_spend_actions(state: WorldState, game_data: GameData,
                       ctx: SelectionContext) -> Fraction:
    """Planner actions one unit of gold costs to SPEND: the seconds it takes to
    earn it again (`1 / gold_per_second`) in the learned seconds of one action
    (`SelectionContext.action_seconds`, as `consumable_price.make_seconds`
    converts the other way).

    NO RATE, NO PRICE. With no grind target and no `m*` the rate is 0, and the
    codebase's answer for that case is `consumable_price_core.buy_seconds`':
    buying is unpriceable (None). Here that is `UNOBTAINABLE_PER_UNIT` a gold
    piece, so a route that spends gold is walled exactly as a buy is there,
    never priced at an invented rate."""
    rate = gold_per_second(state, game_data, ctx)
    if rate <= 0:
        return Fraction(UNOBTAINABLE_PER_UNIT)
    return 1 / (rate * ctx.action_seconds_of())
