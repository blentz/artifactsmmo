"""Fight action for GOAP planning."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_fight_my_name_action_fight_post import sync as action_fight
from artifactsmmo_api_client.models.fight_request_schema import FightRequestSchema
from artifactsmmo_api_client.models.fight_result import FightResult

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.cost_core import learned_cost_pure
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.equipment.scoring import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

_MIN_FIGHT_HP_FRACTION = 0.3
"""Don't start a fight below this HP fraction — rest/heal first."""

LOADOUT_PENALTY = 5.0
"""Added to Fight cost when the loadout is suboptimal for the monster, so the
planner sequences OptimizeLoadout before the fight (player executes plan[0] only).
Must stay < one swap's cost (optimize_loadout.SWAP_COST_PER_SLOT * 2) so the
penalty orders swap-before-fight without making the swap itself non-favorable."""


def _nearest(locations: frozenset[tuple[int, int]], state: WorldState) -> tuple[int, int]:
    return min(locations, key=lambda loc: abs(loc[0] - state.x) + abs(loc[1] - state.y))


@dataclass
class FightAction(Action):
    """Move to and fight a monster. Movement is folded into cost and execute."""

    tags: ClassVar[frozenset[str]] = frozenset({"combat", "produces_char_xp"})

    monster_code: str
    locations: frozenset[tuple[int, int]] = field(default_factory=frozenset, repr=False)

    _MIN_FREE_SLOTS = 1  # combat can drop loot; need at least 1 free capacity

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.locations or state.inventory_free < self._MIN_FREE_SLOTS:
            return False
        monster_level = game_data.monster_level(self.monster_code)
        min_level = max(1, state.level - 1)
        if not (state.hp_percent > _MIN_FIGHT_HP_FRACTION and min_level <= monster_level <= state.level + 2):
            return False
        # NOTE: deliberately a CHEAP level+gear pre-filter, not the full predict_win
        # verdict. predict_win evaluates the best ON-HAND loadout, which makes a
        # fight applicable before a beneficial weapon swap and lets the planner
        # fight with a suboptimal loadout (defeating LOADOUT_PENALTY's swap-first
        # ordering). The authoritative is_winnable verdict is applied upstream at
        # target selection / feasibility / the prerequisite graph.
        best_eq = max(
            (s.level for code in state.equipment.values()
             if code and (s := game_data.item_stats(code)) is not None),
            default=0,
        )
        return best_eq >= monster_level - 1

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = _nearest(self.locations, state)
        estimated_hp_cost = max(1, state.max_hp // 5)
        new_hp = max(1, state.hp - estimated_hp_cost)
        new_progress = (
            state.task_progress + 1
            if state.task_type == "monsters" and state.task_code == self.monster_code
            else state.task_progress
        )
        return dataclasses.replace(
            state,
            xp=state.xp + 10,
            hp=new_hp,
            x=dest[0],
            y=dest[1],
            cooldown_expires=None,
            task_progress=new_progress,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = _nearest(self.locations, state)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        static = 10.0 + dist
        if history is None:
            base = learned_cost_pure(static, 0.0, 1.0, has_history=False)
        else:
            learned = history.action_cost(repr(self), default=static, window=50)
            rate = history.success_rate(repr(self), window=50)
            base = learned_cost_pure(static, learned, rate, has_history=True)
        if pick_loadout(self.monster_code, state, game_data) != state.equipment:
            base += LOADOUT_PENALTY
        return base

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        dest = _nearest(self.locations, state)
        if (state.x, state.y) != dest:
            state = MoveAction(x=dest[0], y=dest[1]).execute(state, client)
        result = action_fight(client=client, name=state.character, body=FightRequestSchema())
        result = Action._raise_for_error(result, f"Fight {self.monster_code}")
        new_state = WorldState.from_character_schema(
            result.data.characters[0],
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )
        # Detect defeat: API returns 200 OK on loss; result.data.fight.result == LOSS.
        # Raise so the player loop records outcome=error:fight_lost and learning
        # doesn't fold near-death zero-XP cycles into action_cost/success_rate.
        if result.data.fight.result == FightResult.LOSS:
            raise RuntimeError(f"fight_lost: {self.monster_code} (turns={result.data.fight.turns})")
        return new_state

    def __repr__(self) -> str:
        return f"Fight({self.monster_code})"
