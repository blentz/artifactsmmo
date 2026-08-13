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
    gather_apply_batch_pure,
    gather_batch_size_pure,
    gather_is_applicable_pure,
)
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Gather
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.nearest_tile import nearest_or_error
from artifactsmmo_cli.ai.world_state import WorldState

GATHER_LOADOUT_PENALTY = 6.0
"""Added to GatherAction cost when the equipped loadout is suboptimal for the
resource's skill, so the planner sequences OptimizeLoadout(Gather) before the
gather action. Mirrors LOADOUT_PENALTY in actions/combat.py:
  - Must stay STRICTLY ABOVE one swap's cost (SWAP_COST_PER_SLOT * 1 = 5.0):
    a gather re-arm swaps exactly the weapon slot, and at 5.0 a single-gather
    plan TIED with the un-swapped plan and never equipped the ferried tool
    (live 2026-07-05: 3-action helmet plan, copper_pickaxe stayed in the bag).
  - Must stay < SWAP_COST_PER_SLOT * 2 (10.0) so a hypothetical 2-slot swap is
    not forced on a single gather.
  - Must stay << _BANKED_REGATHER_PENALTY (100.0) so a banked-material withdraw
    still wins over re-gathering regardless of tool mismatch.
The penalty fires ONLY on GatherAction — never mid-combat."""


@dataclass
class GatherAction(Action):
    """Move to and gather a resource. Movement is folded into cost and execute."""

    tags: ClassVar[frozenset[str]] = frozenset({"gather", "produces_skill_xp"})

    resource_code: str
    quantity: int = 1
    """Units this edge mints in ONE planner node. A planner abstraction: the
    API gathers one unit per call with a cooldown, so N units are N cycles —
    the player holds the plan cursor until the batch lands (PlanCache
    .step_target), the same expansion idiom LevelSkill uses.

    Sized by the consuming goal from its own demand closure
    (`size_closure_gather`), never by the factory, which has no demand context.
    Default 1 reproduces the pre-batching edge exactly."""
    locations: frozenset[tuple[int, int]] = field(default_factory=frozenset, repr=False)
    # P1 (docs/PLAN_engagement_expansion.md): rare multi-drop targeting. When
    # set, the planner SIMULATES this gather as yielding the named secondary
    # drop (e.g. emerald_stone from copper_rocks @1/200) instead of the
    # primary. Deliberate abstraction — one sim-gather credits one unit, like
    # the fight xp projection; execution gathers the same tile and the
    # replan loop runs until the REAL count satisfies the goal.
    drop_item_override: str | None = None
    # P5b: access region of the resource tiles (see FightAction.travel_region).
    travel_region: str = "overworld"

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
    # Applied as `min(banked, quantity) * _BANKED_REGATHER_PENALTY` in `cost`:
    # only the units this batch actually shares with the bank are penalized,
    # not the whole batch and not a flat one-unit charge.
    _BANKED_REGATHER_PENALTY = 100.0

    def drop_item(self, game_data: GameData) -> str:
        """The item this gather actually yields: the targeted secondary drop
        when overridden, else the resource's primary drop, else the resource
        code itself."""
        return (self.drop_item_override
                or game_data.resource_drop_item(self.resource_code)
                or self.resource_code)

    @staticmethod
    def _inv(state: WorldState) -> GatherInv:
        """The `GatherInv` projection of `state` shared by `is_applicable`,
        `apply`, and `effective_quantity` — one construction site instead of
        three identical ones."""
        return GatherInv(used=state.inventory_used, cap=state.inventory_max,
                         item_count=state.inventory,
                         slots_used=state.inventory_slots_used,
                         slots_max=state.inventory_slots_max)

    def effective_quantity(self, state: WorldState, game_data: GameData) -> int:
        """`min(self.quantity, inventory headroom in units)` — the largest
        feasible batch NOW. 0 when not even one unit fits. Mirrors
        `CraftAction.effective_quantity`."""
        return gather_batch_size_pure(self._inv(state), self.quantity, self.drop_item(game_data))

    def learning_key(self) -> str:
        """Learned-cost key, deliberately QUANTITY-FREE. `repr` carries the
        quantity for display and plan identity, but keying learned costs on it
        would make every batch size a fresh, empty key and silently disable
        `learned_cost_pure` for every batched gather. The learned figure is a
        per-unit cost, scaled by quantity in `cost`."""
        if self.drop_item_override is not None:
            return f"Gather({self.resource_code}->{self.drop_item_override})"
        return f"Gather({self.resource_code})"

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if not self.locations:
            return False
        drop_item = self.drop_item(game_data)
        inv = self._inv(state)
        skill_req = game_data.resource_skill_level(self.resource_code)
        # The `effective_quantity(...) >= 1` conjunct is belt-and-braces, not
        # a live gate: `gather_is_applicable_pure(inv, _MIN_FREE_SLOTS, ...)`
        # already requires `cap - used >= _MIN_FREE_SLOTS (3)`, which implies
        # at least 1 unit of headroom, so `effective_quantity` (bounded by
        # that same headroom) can never be 0 once the first conjunct holds.
        # Kept explicit so a future reader doesn't have to re-derive that —
        # and so it stays correct if `_MIN_FREE_SLOTS` or the batch-size
        # rule ever diverge.
        if skill_req is None:
            return (gather_is_applicable_pure(inv, self._MIN_FREE_SLOTS, drop_item)
                    and self.effective_quantity(state, game_data) >= 1)
        skill, level = skill_req
        return (state.skills.get(skill, 1) >= level
                and gather_is_applicable_pure(inv, self._MIN_FREE_SLOTS, drop_item)
                and self.effective_quantity(state, game_data) >= 1)

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = nearest_or_error(state.x, state.y, self.locations, "gather")
        drop_item = self.drop_item(game_data)
        post = gather_apply_batch_pure(self._inv(state), drop_item,
                                       self.effective_quantity(state, game_data))
        new_inventory = dict(post.item_count)
        # Gathering NEVER advances an items-task: the server only counts items
        # when they are DELIVERED to the taskmaster (TaskTradeAction). Modelling
        # gather as +progress made FarmItems "satisfied" by a single gather, so
        # the bot gathered the task item forever without ever delivering, filled
        # its inventory, and then deadlocked (gather no longer applicable, no
        # plan). Only TaskTradeAction increments task_progress.
        # skill_xp is a server-snapshot baseline field (see WorldState docstring);
        # the planner never simulates it locally — apply preserves it. The next
        # real API call returns the updated server values. Gathering does NOT
        # raise skill levels in-search either; the planner-native skill grind is
        # a separate LevelSkill action leg.
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = nearest_or_error(state.x, state.y, self.locations, "gather")
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        static = (6.0 + dist) * self.quantity
        # Penalize re-gathering a material the bank already holds, so the
        # planner withdraws banked stock before re-gathering it (see
        # _BANKED_REGATHER_PENALTY). The penalty applies per banked unit's
        # worth: min(banked, quantity) units of THIS batch are covered by the
        # bank, so only those units carry the penalty — once the bank is
        # exhausted (or the batch outgrows it), the remaining deficit gathers
        # carry no penalty, preserving optimal handling of the unavoidable
        # shortfall.
        drop_item = self.drop_item(game_data)
        banked = (state.bank_items or {}).get(drop_item, 0)
        static += min(banked, self.quantity) * self._BANKED_REGATHER_PENALTY
        # Penalize gathering with a suboptimal tool, mirroring LOADOUT_PENALTY in
        # FightAction.cost: add GATHER_LOADOUT_PENALTY when pick_loadout(Gather)
        # differs from the current equipment in any slot, so the planner sequences
        # OptimizeLoadout(Gather) before the gather.  Fires only when the resource
        # has a known skill requirement (resources without skill data carry no
        # tool preference, so no penalty). One swap serves the whole batch, so
        # this is added once regardless of quantity.
        skill_req = game_data.resource_skill_level(self.resource_code)
        if skill_req is not None:
            skill, _ = skill_req
            optimal = pick_loadout_cached(Gather(skill), state, game_data)
            if any(state.equipment.get(slot) != code for slot, code in optimal.items()):
                static += GATHER_LOADOUT_PENALTY
        if history is None:
            return learned_cost_pure(static, 0.0, 1.0, has_history=False)
        # `default` must be a PER-UNIT figure (matched against `learned`,
        # which is per-unit and then scaled by quantity below): under 5
        # samples `action_cost` falls back to this default, so it must carry
        # the same banked/loadout penalties `static` does, not just the bare
        # `6.0 + dist`, or a low-sample quantity=1 gather would diverge from
        # the pre-batching cost the moment it picked up any history at all.
        learned = history.action_cost(self.learning_key(), default=(static / self.quantity),
                                      window=50) * self.quantity
        rate = history.success_rate(self.learning_key(), window=50)
        return learned_cost_pure(static, learned, rate, has_history=True)

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        dest = nearest_or_error(state.x, state.y, self.locations, "gather")
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
            raids=state.raids,
        )

    def __repr__(self) -> str:
        if self.drop_item_override is not None:
            return f"Gather({self.resource_code}->{self.drop_item_override}×{self.quantity})"
        return f"Gather({self.resource_code}×{self.quantity})"
