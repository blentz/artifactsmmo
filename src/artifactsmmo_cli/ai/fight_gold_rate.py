"""The fight gold a farmed monster pays per cycle: the one rate a task's gold
worth (`task_worth`) and a consumable's gold price (`consumable_price`) read.

Its own module, below both: `consumable_price` is under the gear objective's
loop rate, and `task_worth` reads the task horizon, which reads the gear
objective (`gear_objective_for`), so `consumable_price` cannot import it from
`task_worth` without closing that cycle.
"""

from fractions import Fraction

from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.fight_loop_cost import cycles_per_kill
from artifactsmmo_cli.ai.world_state import WorldState


def fight_gold_rate(state: WorldState, game_data: GameData, monster: str,
                    fight_seconds: Fraction) -> Fraction:
    """Mean fight gold per cycle of farming `monster`, each fight lasting
    `fight_seconds` (its rests priced in fights of that length)."""
    gold = Fraction(game_data.monster_min_gold(monster) + game_data.monster_max_gold(monster), 2)
    per_kill = Fraction(cycles_per_kill(expected_damage_per_fight(state, game_data, monster),
                                        state.max_hp, fight_seconds))
    return gold / per_kill
