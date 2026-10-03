"""Produce a material a SIBLING needs and bank it.

This is the goal that turns the demand board into actual production. Without
it, bank-first sourcing changes nothing: each character gathers exactly what
its own plan demands, crafts it, and leaves the bank empty, so a consumer
preferring WITHDRAW still finds nothing there.

`desired_state` targets BANKED quantity, not held quantity — the distinction
that keeps sibling demand from being consumed by the producer's own craft. That
separation is the whole reason this is a distinct goal rather than an inflation
of the character's own closure demand.

Priority is the clamped demand lift, the same construction `scalar_priority`
and `grind_character_xp` use: the band ceiling sits below the survival floor of
70, so a supply goal can NEVER outrank a survival guard by construction rather
than by tuning.
"""

import dataclasses
from fractions import Fraction

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.priority_band import clamp_into_band
from artifactsmmo_cli.ai.world_state import WorldState

SUPPLY_PRIORITY_FLOOR = 30.0
"""Minimum priority when active. Matches GrindCharacterXpGoal's floor so a
zero-demand supply goal never outranks ordinary progression."""

SUPPLY_PRIORITY_CEILING = 50.0
"""Upper bound. Stays under ReachSkillGoal (55) and the survival floor (70).
Deliberately overlaps GrindCharacterXpGoal's [30, 45] band so heavy sibling
demand CAN outrank marginal char-xp grinding, but never a skill gate."""

SUPPLY_DEMAND_GAIN = 1.0
"""Priority points per unit of unmet sibling demand."""


class SupplyBankGoal(Goal):
    """Bank `quantity` of `item_code` for the siblings that asked for it."""

    def __init__(self, item_code: str, quantity: int, demand: int) -> None:
        self._item_code = item_code
        self._quantity = quantity
        self._demand = demand

    def __repr__(self) -> str:
        return f"SupplyBank({self._item_code}x{self._quantity})"

    @property
    def max_depth(self) -> int:
        """Deep enough for the demand this goal was actually constructed with.

        The inherited base of 15 made this goal STRUCTURALLY unplannable in
        production (final review, Finding 1). `is_satisfied` targets an absolute
        BANKED count, and the only bank-increasing action the factory offers A*
        is `DepositAllAction` — so every satisfying plan is ~`demand` mints plus
        at least one deposit. `PlannerDepthBound.plan_length_le_max_depth` then
        guarantees NO plan exists once the demand exceeds ~14, while the demand
        actually published is a full `closure_demand(root, 1, ...)` — 80 gathers
        for copper_boots (progression.py:70). The goal would essentially never
        have planned.

        `_demand`, not `_quantity`, is the production scale: `_pick_supply_target`
        builds `quantity` as `supply_batch_target_pure(banked, demand)` — the
        next BATCH milestone above what is banked, clamped to `banked + demand`
        — so it stays an ABSOLUTE banked target that already counts stock
        nobody has to produce (a bank holding 500 still yields a `_quantity`
        past 500 with no extra action to plan), while `_demand` is the work
        actually left. The multiplier and the
        `max(100, ...)` floor are `GatherMaterialsGoal.max_depth`'s construction
        unchanged — the same "obtain N units of X" question, where a deep chain
        costs many actions per unit and the planner's time/node budget is meant
        to be the real cutoff."""
        return max(100, self._demand * 100)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        bonus = Fraction(self._demand) * Fraction(SUPPLY_DEMAND_GAIN)
        clamped = clamp_into_band(Fraction(SUPPLY_PRIORITY_FLOOR),
                                  Fraction(SUPPLY_PRIORITY_CEILING), bonus)
        return float(clamped)

    def is_satisfied(self, state: WorldState) -> bool:
        bank = state.bank_items
        if bank is None:
            return False
        return bank.get(self._item_code, 0) >= self._quantity

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"banked": {self._item_code: self._quantity}}

    def _deficit(self, state: WorldState) -> int:
        """Units that still have to be PRODUCED and banked.

        `state.bank_items is None` ("never visited this session") is read as
        zero here, and that is not the conflation `_pick_supply_target`
        refuses. This is a statement about the SEARCH, not about the world:
        `DepositAllAction.apply` rebuilds the bank from `dict(state.bank_items
        or {})`, so inside the planner an unvisited bank genuinely starts at
        zero and the full quantity genuinely has to be produced.

        NOT clamped at zero. `is_satisfied` is exactly `banked >= quantity`, so
        every caller that acts on this value has already excluded the
        non-positive case; a `max(0, ...)` here would be a second, unreachable
        guard on the same condition. The one place a zero can still arrive —
        `relevant_actions` on an already-satisfied goal, which the planner calls
        before it pops the root — is handled once, at `_production_goal`."""
        banked = (state.bank_items or {}).get(self._item_code, 0)
        return self._quantity - banked

    def _production_state(self, state: WorldState) -> WorldState:
        """`state` with the TARGET's own banked copies removed.

        Every reachability question below ("how much work is left", "which
        actions serve it") must be asked against a bank that does NOT already
        contain the thing being banked, because those copies cannot serve the
        deficit: withdrawing them and depositing them again is a null cycle.
        Left in, they poison exactly the machinery this delegates to — a bank
        holding 6 of a 10-unit target makes `fully_covered_materials` call the
        remaining 4 "fully covered", which PRUNES the target's own gather and
        leaves the planner nothing but Withdraw->Deposit. Every OTHER banked
        code is left intact: those are real, withdrawable inputs."""
        bank = state.bank_items
        if bank is None or self._item_code not in bank:
            return state
        return dataclasses.replace(
            state, bank_items={code: qty for code, qty in bank.items()
                               if code != self._item_code})

    def _production_goal(self, state: WorldState) -> GatherMaterialsGoal:
        """"Obtain `deficit` more units of the target" as the goal that already
        answers that question.

        `GatherMaterialsGoal(target_item=X, needed={X: n})` is the established
        raw-material form (strategy_driver.py:487/773/774), and its
        `relevant_actions` is the tuned closure scoping this goal needs
        verbatim: closure crafts sized to demand, closure gathers with
        bank-aware pruning, withdraws for banked inputs, scoped `LevelSkill`
        for craft- and gather-skill gates, monster-drop fights with their
        loadout companion, NPC-buy leaves, and the deposit tag this goal's own
        final leg rides on. Reusing it is the one-obtain-model discipline this
        repo already paid for twice; a private copy would be a second
        production model to keep in sync.

        `max(1, ...)` keeps the delegate well-formed when the deficit is zero
        (a satisfied goal the planner still calls `relevant_actions` on before
        it pops the root): a `needed` of 0 is a degenerate demand for the
        closure walk, and the action set it would return is never used."""
        return GatherMaterialsGoal(target_item=self._item_code,
                                   needed={self._item_code: max(1, self._deficit(state))})

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Scope the search to the target's craft/gather closure + the deposit,
        MINUS any withdraw of the target itself.

        Without this the goal planned against the whole ~1800-action pool with
        no heuristic — an unscoped Dijkstra, run on every cycle the goal was
        reached. See `_production_goal` for why the
        scoping is delegated rather than copied, and `_production_state` for
        why the bank is asked the question minus the target's own copies.

        THE TARGET'S OWN WITHDRAW IS REFUSED (live livelock, trace
        2026-08-04 01:11 R2D2, 38 of 83 cycles spent on no-op bank traffic).
        This goal's success condition is "the item is IN THE BANK", so sourcing
        that same item FROM the bank is definitionally a no-op: `Withdraw` moves
        `q` from bank to bag and the closing `DepositAll` moves it straight
        back, leaving `state.bank_items[item]` exactly where it started.

        `_production_state` does NOT prevent it, and neither does any state
        projection, because the incentive is a COST, not a precondition:

        1. The delegate's `withdrawable` set is built from `craftable_mats |
           set(self._needed)` — recipe structure, not bank contents — and
           `_production_goal` puts the target in `needed`. So stripping the
           target's banked copies from the state hands the delegate a bank
           without them, and the target's `WithdrawItemAction` is admitted
           anyway.
        2. `GOAPPlanner.plan` uses the projection only for `relevant_actions`;
           A* then searches from the REAL state, where
           `GatherAction.cost` adds `_BANKED_REGATHER_PENALTY` (100.0) to EVERY
           gather while any of the drop item is banked. Draining the bank first
           (2.0 per withdraw) buys that 100.0 back on every subsequent gather,
           so "withdraw the whole banked stock, gather, deposit it all again"
           is genuinely the LEAST-COST satisfying plan — A* is answering the
           question it was asked. The penalty is right for every consumer goal;
           it is exactly backwards for the one goal that is trying to PUT the
           item there.

        Only the target is excluded. Every other banked code stays withdrawable
        — supplying a crafted bar from banked ore is real production, not a
        null cycle, and that withdraw is the delegate's whole point.

        NO `heuristic` override accompanies this. The default 0.0 is Dijkstra —
        trivially admissible AND consistent — and `Goal.heuristic`'s contract
        makes any override a correctness obligation
        (`Formal/PlannerAdmissibility.lean`), not a tuning knob. The obvious
        candidate, the delegate's `forced_craft_grind` landmark, is admissible
        for a goal satisfied by HOLDING the target; this goal is satisfied by
        BANKING it, and the deposit leg moves the target out of inventory —
        the exact place `forced_craft_grind`'s owned-credit could make h jump,
        and where an over-estimate would hide. Not confident it is consistent,
        so it is not added; the action scoping above is what bounds the search.
        """
        admitted = self._production_goal(state).relevant_actions(
            actions, self._production_state(state), game_data)
        return [action for action in admitted
                if not (isinstance(action, WithdrawItemAction)
                        and action.code == self._item_code)]
