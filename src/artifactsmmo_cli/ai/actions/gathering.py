"""Gather action for GOAP planning."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_gathering_my_name_action_gathering_post import (
    sync as action_gathering,
)

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.cost_core import learned_cost_pure
from artifactsmmo_cli.ai.actions.gather_apply_core import (
    GatherInv,
    gather_apply_pure,
    gather_is_applicable_pure,
)
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.nearest_tile import nearest_tile
from artifactsmmo_cli.ai.world_state import WorldState


def _nearest(locations: frozenset[tuple[int, int]], state: WorldState) -> tuple[int, int]:
    dest = nearest_tile(state.x, state.y, locations)
    if dest is None:
        raise ValueError("no gather locations to choose from")
    return dest


@dataclass
class GatherAction(Action):
    """Move to and gather a resource. Movement is folded into cost and execute."""

    tags: ClassVar[frozenset[str]] = frozenset({"gather", "produces_skill_xp"})

    resource_code: str
    locations: frozenset[tuple[int, int]] = field(default_factory=frozenset, repr=False)

    _MIN_FREE_SLOTS = 3  # gathering can produce ore + random bonus drops simultaneously

    # Re-gathering a material that is already sitting in the bank is wasteful:
    # a WithdrawItemAction pulls it instantly (no gather cooldown) and is cheaper
    # in aggregate. Without this penalty the planner front-loads gathers whenever
    # the character is standing on the resource node (a single gather at the node,
    # cost 6, beats the bank round-trip), so the lowest-*total*-cost plan ordered
    # gathers first. Since only plan[0] executes per cycle and the character never
    # leaves the node, banked stock was never withdrawn (live bug
    # 2026-06-07: 40 banked ash_wood re-gathered for 40+ cycles). The penalty is
    # large enough to dominate any plausible bank round-trip distance, so a
    # banked-material withdraw provably sorts before re-gathering that material.
    _BANKED_REGATHER_PENALTY = 100.0

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.locations:
            return False
        inv = GatherInv(used=state.inventory_used, cap=state.inventory_max,
                        item_count=state.inventory)
        skill_req = game_data.resource_skill_level(self.resource_code)
        if skill_req is None:
            return gather_is_applicable_pure(inv, self._MIN_FREE_SLOTS)
        skill, level = skill_req
        return (state.skills.get(skill, 1) >= level
                and gather_is_applicable_pure(inv, self._MIN_FREE_SLOTS))

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = _nearest(self.locations, state)
        drop_item = game_data.resource_drop_item(self.resource_code) or self.resource_code
        inv = GatherInv(used=state.inventory_used, cap=state.inventory_max,
                        item_count=state.inventory)
        post = gather_apply_pure(inv, drop_item)
        new_inventory = dict(post.item_count)
        # Gathering NEVER advances an items-task: the server only counts items
        # when they are DELIVERED to the taskmaster (TaskTradeAction). Modelling
        # gather as +progress made FarmItems "satisfied" by a single gather, so
        # the bot gathered the task item forever without ever delivering, filled
        # its inventory, and then deadlocked (gather no longer applicable, no
        # plan). Only TaskTradeAction increments task_progress.
        # skill_xp is a server-snapshot baseline field (see WorldState docstring);
        # the planner never simulates it locally — apply preserves it. The next
        # real API call returns the updated server values. We DO advance the
        # separate `projected_skill_xp_delta` accumulator (outside the baseline
        # contract) so LevelSkillGoal.is_satisfied can read planner-projected
        # XP progress without polluting the server snapshot.
        new_delta = dict(state.projected_skill_xp_delta)
        skill_req = game_data.resource_skill_level(self.resource_code)
        if skill_req is not None:
            skill_name, _ = skill_req
            new_delta[skill_name] = new_delta.get(skill_name, 0) + 1
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
            projected_skill_xp_delta=new_delta,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = _nearest(self.locations, state)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        static = 6.0 + dist
        # Penalize re-gathering a material the bank already holds, so the
        # planner withdraws banked stock before re-gathering it (see
        # _BANKED_REGATHER_PENALTY). The penalty applies per banked unit's
        # worth: once the bank is exhausted the deficit gathers carry no
        # penalty, preserving optimal handling of the unavoidable shortfall.
        drop_item = game_data.resource_drop_item(self.resource_code) or self.resource_code
        banked = (state.bank_items or {}).get(drop_item, 0)
        if banked > 0:
            static += self._BANKED_REGATHER_PENALTY
        if history is None:
            return learned_cost_pure(static, 0.0, 1.0, has_history=False)
        learned = history.action_cost(repr(self), default=static, window=50)
        rate = history.success_rate(repr(self), window=50)
        return learned_cost_pure(static, learned, rate, has_history=True)

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        dest = _nearest(self.locations, state)
        if (state.x, state.y) != dest:
            state = MoveAction(x=dest[0], y=dest[1]).execute(state, client)
        result = action_gathering(client=client, name=state.character)
        result = Action._raise_for_error(result, f"Gather {self.resource_code}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return f"Gather({self.resource_code})"
