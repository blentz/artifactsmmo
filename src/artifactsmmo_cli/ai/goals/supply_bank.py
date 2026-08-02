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
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.min_plan_length import min_plan_length
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

    # Exempt from the doomed-memo (Goal.memo_exempt): this goal's plannability
    # and satisfaction both hinge on dimensions the memo's (char level, skill
    # levels) signature cannot see. `is_satisfied` reads bank CONTENTS
    # directly, and the memo key is `repr(goal)` — `SupplyBank({item_code}x
    # {quantity})` — which does NOT include `demand`, so two constructions for
    # the SAME item/quantity but DIFFERENT (rising) sibling demand collide on
    # one memo entry. A transient no-plan (e.g. the gather/craft chain briefly
    # unreachable — missing ingredient, cooldown, bank full) would then be
    # memoized as doomed under the unchanged (level, skills) signature and
    # suppress this means for up to 160 cycles, even after a sibling's demand
    # spikes or the blocking material lands in the bank from ANOTHER
    # character's cycle — neither of which bumps the signature. This is the
    # same class of problem GrindCharacterXPGoal solved (HP/inventory churn
    # invisible to the signature); see Goal.memo_exempt.
    #
    # RECONSIDERED (final review, Finding 1): kept True. The review's objection
    # was not to the exemption itself but to what an unsuppressible goal COST —
    # an unscoped Dijkstra over the full ~1800-action pool every cycle the goal
    # was reached. That cost is now removed at its source by `relevant_actions`
    # (closure-scoped) and `is_plannable` (depth-reachability), not by letting a
    # stale doomed verdict silence the fleet's only supply producer for up to
    # 160 cycles. Both original justifications are unchanged and still hold, so
    # dropping the exemption would trade a bounded CPU cost for a correctness
    # regression.
    memo_exempt = True

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
        builds the goal as `quantity = banked + demand`, so a bank already
        holding 500 of the item would inflate `_quantity` (and hence the search
        space) without a single extra action to plan. The multiplier and the
        `max(100, ...)` floor are `GatherMaterialsGoal.max_depth`'s construction
        unchanged — the same "obtain N units of X" question, where a deep chain
        costs many actions per unit and the planner's time/node budget is meant
        to be the real cutoff. `is_plannable` below keeps that generosity honest
        by refusing the search outright when even this depth cannot hold the
        chain."""
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

    def is_plannable(self, state: WorldState, game_data: GameData,
                     history: LearningStore | None = None) -> bool:
        """Refuse the search when it provably cannot succeed.

        Two independent bounds, both sound (they fail ONLY when no plan of
        length <= `max_depth` can exist, per `Goal.is_plannable`'s contract):

        1. The delegate's own currency-leaf gate — a recipe leaf that can only
           be BOUGHT, in a currency the character cannot cover, has no
           acquisition edge in the admitted action set, so no plan reaches it.
        2. Depth reachability, the bound `UpgradeEquipmentGoal.is_plannable`
           uses: obtaining `deficit` units from raw materials needs at least
           `min_plan_length` actions (PROVED lower bound,
           `Formal.PlanModel.min_plan_length_le_plan`), and the planner never
           returns a plan longer than `max_depth`
           (`Formal.PlannerDepthBound.plan_length_le_max_depth`).

        `equip=False` and no `+1` for the deposit leg, deliberately: the real
        plan must also pay at least one deposit, so this bound is LOOSER than
        the truth. A loose lower bound can only over-admit (waste a search),
        never over-prune (discard a reachable plan) — and `min_plan_length` is
        the term that carries a proof, so nothing is claimed here beyond it."""
        if self.is_satisfied(state):
            return True
        produce = self._production_state(state)
        if not self._production_goal(state).is_plannable(produce, game_data, history):
            return False
        owned: dict[str, int] = dict(state.inventory)
        for code, qty in (produce.bank_items or {}).items():
            owned[code] = owned.get(code, 0) + qty
        return min_plan_length(
            self._item_code, self._deficit(state), game_data.crafting_recipes,
            owned, game_data.max_gather_yield, equip=False,
        ) <= self.max_depth

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Scope the search to the target's craft/gather closure + the deposit.

        Without this the goal planned against the whole ~1800-action pool with
        no heuristic — an unscoped Dijkstra, and (being `memo_exempt`) one that
        no doomed-memo could ever suppress. See `_production_goal` for why the
        scoping is delegated rather than copied, and `_production_state` for
        why the bank is asked the question minus the target's own copies.

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
        return self._production_goal(state).relevant_actions(
            actions, self._production_state(state), game_data)
