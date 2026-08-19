"""MaintainConsumablesGoal: cook/brew heal consumables to a stock floor (PLAN #6a).

Selected by the MAINTAIN_CONSUMABLES discretionary means when combat is the
active means and the bot is under-stocked on heals. Crafts the best heal its
skills can make (reusing recipe-closure gather/withdraw/craft actions) so the
bot has heals to DRINK MID-FIGHT.

Note the justification: NOT "instead of falling back on the slow Rest action".
Rest is no longer slow in general -- since the dynamic cost landed it is
max(3, ceil(missing%)) seconds and refills to FULL, so resting off damage
between fights is cheap and gather-crafting a heal to avoid it never pays. What
Rest cannot do is happen DURING a fight, which is the whole reason to carry
heals.
"""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.consumable_supply import (
    HEAL_STOCK_FLOOR,
    best_craftable_heal,
    heal_stock,
    maintain_consumables_fires,
)
from artifactsmmo_cli.ai.drop_fight_selection import select_drop_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.recipe_closure import gather_serves_closure
from artifactsmmo_cli.ai.requirement_projections import (
    demand_set,
    requirement_craftables,
)
from artifactsmmo_cli.ai.world_state import WorldState

MAINTAIN_CONSUMABLES_VALUE = 25.0
"""Discretionary combat-prep value: above the RECYCLE_SURPLUS / WAIT housekeeping
band so the bot stocks heals before idle chores, below GATHER_MATERIALS (50) and
the survival floor so it never preempts objective or survival work."""


class MaintainConsumablesGoal(Goal):
    """Craft heal consumables up to HEAL_STOCK_FLOOR.

    Satisfied when the bot holds enough heals OR can craft nothing better — the
    same predicate the means tier fires on, so one activation drives the
    gather/craft chain until the floor is met."""

    def __init__(self, game_data: GameData) -> None:
        self._gd = game_data

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return 0.0 if self.is_satisfied(state) else MAINTAIN_CONSUMABLES_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return not maintain_consumables_fires(state, self._gd)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"heal_stock_maintained": True}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Recipe-closure actions for the chosen heal: a batched Craft of the
        heal (sized to the deficit), Crafts of its craftable intermediates,
        Gathers of its needed resources, Withdraws of any closure material in
        the bank, Moves — and the dropper FIGHT for any closure material that
        nothing else can produce. Same closure machinery GatherMaterials uses."""
        code = best_craftable_heal(state, game_data)
        if code is None:
            return []
        craftable_mats = requirement_craftables(
            game_data.requirement_graph.graph(), [code])
        # Withdraw-eligible codes: craftable intermediates + the heal itself;
        # every leaf material arrives via the closure-demand union below
        # (GAP-7: the per-resource primary-drop loop was redundant and, with
        # the widened needed_resources, would admit junk withdraws).
        withdrawable: set[str] = set(craftable_mats) | {code}
        chain = dict(demand_set(game_data.requirement_graph.graph(), [code]).quantities)
        withdrawable |= set(chain)

        deficit = max(1, HEAL_STOCK_FLOOR - heal_stock(state, game_data))
        batch_chain = dict(demand_set(
            game_data.requirement_graph.graph(), [code], {code: deficit}).quantities)
        result: list[Action] = []
        have_craft = False
        for a in actions:
            if isinstance(a, CraftAction) and a.code == code:
                if not have_craft:
                    have_craft = True
                    result.append(a if a.quantity == deficit
                                  else dataclasses.replace(a, quantity=deficit))
            elif isinstance(a, CraftAction) and a.code in craftable_mats:
                result.append(size_intermediate_craft(a, batch_chain, state, game_data))
            elif isinstance(a, GatherAction) and gather_serves_closure(
                    a.resource_code, a.drop_item_override,
                    game_data.resource_drops, chain):
                # GAP-7 admission precision: EFFECTIVE drop in the closure.
                result.append(a)
            elif (isinstance(a, WithdrawItemAction) and a.code in withdrawable) or isinstance(a, MoveAction):
                result.append(a)
            elif isinstance(a, RestAction):
                # THE FOURTH MISSING EDGE. A drop-farmed material needs several
                # kills, and `FightAction.apply` charges a flat `max_hp // 5` per
                # fight — so Lor (310 max hp) can fit exactly FOUR fights before
                # the hp floor and needs FIVE. Without a Rest inside the plan the
                # search stalls one kill short of a goal it can otherwise reach:
                # Fight x4, Rest, Fight, Craft satisfies it at depth 7, well
                # inside `max_depth` 15.
                #
                # Resting is normally the REST_FOR_COMBAT guard's job BETWEEN
                # cycles, which is why no goal admitted it. That works for a goal
                # whose plan is one leg; it cannot work for a goal that must reach
                # a stock target in one search, because `is_satisfied` is binary
                # and the planner needs a COMPLETE plan to return anything.
                result.append(a)
        return result + self._material_drop_fights(
            batch_chain, result, state, game_data, actions, code)

    def _material_drop_fights(
            self, batch_chain: dict[str, int], admitted: list[Action],
            state: WorldState, game_data: GameData, actions: list[Action],
            heal_code: str) -> list[Action]:
        """One dropper fight per closure material NOTHING ELSE CAN PRODUCE.

        GAP-6 RECURRING IN A SECOND GOAL. The filter above admits Craft, Gather,
        Withdraw and Move, and drops every FightAction — so a heal whose material
        is a pure MONSTER DROP had no acquisition edge and the goal could never
        plan. Measured live 2026-08-19 on three of five characters: MAINTAIN
        CONSUMABLES fired, `best_craftable_heal` returned `cooked_chicken` /
        `cooked_beef` / `cheese`, and `relevant_actions` came back with the Craft
        alone. `raw_chicken`, `raw_beef` and `milk_bucket` are gatherable from NO
        resource — they drop off chicken and cow — so the planner had a recipe and
        no way to fill it, and the rung fired with nothing to do every cycle.

        `best_craftable_heal` is the reason this is the goal's problem and not the
        predicate's: it deliberately does not require materials on hand, on the
        stated grounds that "the goal's recipe-closure actions let the planner
        gather/withdraw them". That was true of gatherable materials only.

        `select_drop_fight` is the proven wiring (`drop_fight_selection`, the live
        caller of the Lean-proved dropper argmin) and it returns None unless a
        winnable dropper exists, so a material with no route adds nothing and the
        goal stays honestly unplannable.

        `allow_grey=True`, on the same structural argument GAP-6 makes for an equip
        target: these materials drop off level-1 animals and are grey to every
        character that has one of these goals, so refusing grey would make this
        emission inert. The demand gate holds because the goal is satisfied by HEAL
        STOCK — a fight emitted here can never serve an xp-grind plan.
        """
        # A Craft or a Gather can be REPEATED, so either one covers any quantity
        # and settles the material. A WITHDRAW cannot: it is bounded by what the
        # bank holds. Robby's `milk_bucket` is the case — one banked unit against
        # a demand of five — and treating the withdraw as "served" left the goal
        # unplannable exactly as if no route had been emitted at all.
        craft_served = {a.code for a in admitted if isinstance(a, CraftAction)}
        bank = state.bank_items or {}
        out: list[Action] = []
        for material, needed in sorted(batch_chain.items()):
            if material == heal_code or material in craft_served:
                continue
            # THE BAG ONLY. Counting banked stock here suppressed the dropper
            # fight for a material the bank held but nothing could WITHDRAW —
            # measured live, Lor's bank had 116 `raw_chicken` and the licensed
            # pool carried no withdraw for it, so "the bank has it" removed the
            # one edge that actually planned and three of four characters went
            # back to no plan at all. Bank stock earns a SYNTHESIZED withdraw
            # below; it never earns a skip.
            if state.inventory.get(material, 0) >= needed:
                continue
            if any(isinstance(a, GatherAction) and gather_serves_closure(
                    a.resource_code, a.drop_item_override, game_data.resource_drops,
                    {material: needed}) for a in admitted):
                continue
            shortfall = needed - state.inventory.get(material, 0)
            banked = bank.get(material, 0)
            if banked > 0:
                # THE MATERIAL WAS IN THE BANK THE WHOLE TIME. Measured live:
                # Lor's bank held 116 `raw_chicken` against a demand of 5, and the
                # goal still could not plan — the licensed pool carries a
                # `WithdrawItemAction` only for codes the factory enumerated, and
                # a heal's raw material is not among them. `withdrawable` above
                # names the code, so the filter would admit the action; there was
                # simply no action to admit. Synthesize it, exactly as the fight
                # below is synthesized.
                #
                # The flags are COPIED from a withdraw the pool already carries
                # rather than assumed: that action is proof the bank is reachable
                # and accessible this cycle. With no such action there is no
                # evidence the bank can be used, and the dropper fight is the
                # honest route.
                template = next((a for a in actions
                                 if isinstance(a, WithdrawItemAction)), None)
                if template is not None:
                    out.append(WithdrawItemAction(
                        code=material, quantity=min(shortfall, banked),
                        bank_location=template.bank_location,
                        accessible=template.accessible))
                # NO `continue`: the dropper fight is emitted as well, and the
                # planner picks whichever is cheaper. Suppressing the fight
                # whenever the bank holds ANY of the material is what broke three
                # of four characters — the withdraw looked sufficient and the
                # fight was the only edge that actually planned.
            fight = select_drop_fight(material, actions, state, game_data,
                                      allow_grey=True)
            if fight is not None:
                out.append(fight)
                # Its companion swap, the same pairing GAP-6 needed (Task 6c in
                # `goals/progression`). `FightAction.is_applicable` carries a HARD
                # optimal-loadout gate, and the filter above admits no
                # OptimizeLoadout — so without this the emitted fight is
                # inapplicable whenever the worn loadout is not already the best
                # for that monster, and the goal stays exactly as unplannable as
                # it was before the fight was emitted at all. Self-guarding: the
                # swap is inapplicable once the loadout IS optimal.
                out.append(OptimizeLoadoutAction(
                    target_monster_code=fight.monster_code, game_data=game_data))
        return out

    def __repr__(self) -> str:
        return "MaintainConsumables"
