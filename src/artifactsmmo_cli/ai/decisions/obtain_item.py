"""Six named `Decision`s for an `ObtainItem` step.

Transcribed verbatim from the `if isinstance(step, ObtainItem):` branch of
`strategy_driver.objective_step_goal` (originally lines 882-1006). Each class
below is one branch of that if-pile, chained in the order the if-pile
evaluated them -- EXCEPT for one deliberate reordering (PF-2, see
`.superpowers/sdd/PLAN_goal_decision_graph/progress.md`): `CanICraftCurrentTier`
(the crafting-skill gate, originally line 972) now runs BEFORE
`DoesTheRecipeNeedAMonsterDrop` (originally line 924). Measured against the
committed bundle: `_recipe_has_combat_drop_input` returns `True` for every
weapon recipe checked (12/12, including iron_sword<-feather and
battlestaff<-wolf_bone), so the original line 924 always returned first and
the skill gate at line 972 was unreachable for the entire weapon tree -- the
actual cause of the weaponcrafting freeze (11,434 LevelSkill actions, target
never above 10, 2026-08-16..2026-08-22). "I cannot craft this at all"
dominates "this chain is too big to plan in one go": hoisting is
behaviour-neutral when the skill is adequate (the hoisted branch falls
through to the monster-drop check exactly as line 924 ran today) and is the
intended change when it is not. `strategy_driver.objective_step_goal`'s
`ObtainItem` arm now IS `resolve_node(obtain_item_decision(step, root), ...)`
-- the if-pile it was transcribed from is gone, so there is no longer a
second, independent implementation to check parity against. See
`tests/test_ai/test_decisions_obtain_item.py::test_objective_step_goal_forwards_to_the_graph`
for the wiring pin (production forwards to this graph correctly) and
`test_a_skill_gated_root_raises_the_skill_by_one` for the PF-2 behaviour
change itself.
"""

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.decision import Decision
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gather_step_target import gather_step_target
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.currency_demand import analyze_currency_leaves
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.reach_currency import ReachCurrencyGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_item_routing import (
    _equippable_goal,
    _gather_step_target_is_root,
    _recipe_has_combat_drop_input,
)
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem
from artifactsmmo_cli.ai.world_state import WorldState


class CanIAffordTheCurrencyLeaf(Decision):
    """strategy_driver.py:898 (originally 896-900)."""

    name = "CanIAffordTheCurrencyLeaf"

    def __init__(self, step: ObtainItem, root: MetaGoal | None) -> None:
        self.step = step
        self.root = root

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision | Goal | None":
        # DEMAND ROUTING (C4 Task 6): if obtaining this item is BLOCKED on an
        # unaffordable currency-buy leaf in its recipe closure (e.g. satchel <-
        # jasper_crystal @ tasks_trader for 8 tasks_coin, with 0 tasks_coin), the
        # GatherMaterials/UpgradeEquipment goal built below is unplannable
        # (GatherMaterialsGoal.is_plannable fast-fails — currency_afford_plannable_pure).
        # Route to ReachCurrencyGoal to FUND the currency instead, so the arbiter
        # has a plannable funding goal to select. Once funded the leaf becomes
        # affordable and the next pass builds the craft path (buy + craft). Shares
        # the ONE closure walk with is_plannable (analyze_currency_leaves). Only a
        # tasks_coin-funded leaf yields a funding_target — a gold/event-only leaf is
        # `blocked` (is_plannable prunes it) but NOT routed here (ReachCurrencyGoal
        # mints only tasks_coin, so funding a gold leaf would chase an unreachable
        # goal).
        analysis = analyze_currency_leaves(
            {self.step.code: self.step.quantity}, state, game_data)
        if analysis.funding_target is not None:
            currency, amount = analysis.funding_target
            return ReachCurrencyGoal(currency=currency, target=amount)
        return IsTheStepTheEquippableItself(self.step, self.root)


class IsTheStepTheEquippableItself(Decision):
    """strategy_driver.py:903 (originally 901-905)."""

    name = "IsTheStepTheEquippableItself"

    def __init__(self, step: ObtainItem, root: MetaGoal | None) -> None:
        self.step = step
        self.root = root

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision | Goal | None":
        stats = game_data.item_stats(self.step.code)
        slots = ITEM_TYPE_TO_SLOTS.get(stats.type_) if stats is not None else None
        if slots:
            dest_slot = self.step.slot if self.step.slot is not None else slots[0]
            return _equippable_goal(self.step.code, dest_slot, state, game_data, ctx)
        return IsThisAnIntermediateOnAChain(self.step, self.root)


class IsThisAnIntermediateOnAChain(Decision):
    """strategy_driver.py:910 (originally 906-913, plus the line-1006
    fallback shared with the negative outcome of this branch)."""

    name = "IsThisAnIntermediateOnAChain"

    def __init__(self, step: ObtainItem, root: MetaGoal | None) -> None:
        self.step = step
        self.root = root

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision | Goal | None":
        # Intermediate step: if the chain root is an equippable, plan
        # against the root directly. UpgradeEquipmentGoal's planner
        # walks the recipe chain (craft intermediates + final + equip)
        # while GatherMaterialsGoal stops at the intermediate.
        if isinstance(self.root, ObtainItem) and self.root.code != self.step.code:
            root_stats = game_data.item_stats(self.root.code)
            if root_stats is not None:
                root_slots = ITEM_TYPE_TO_SLOTS.get(root_stats.type_)
                if root_slots:
                    return CanICraftCurrentTier(
                        self.step, self.root, root_stats, root_slots)
        return GatherMaterialsGoal(target_item=self.step.code,
                                   needed={self.step.code: self.step.quantity})


class CanICraftCurrentTier(Decision):
    """strategy_driver.py:972 (originally 933-1002). HOISTED per PF-2 to run
    BEFORE `DoesTheRecipeNeedAMonsterDrop` (originally line 924) -- see the
    module docstring for the measurement that forced this. "I cannot craft
    this at all" dominates "this chain is too big to plan in one go":
    chunking a chain whose final craft cannot run is work that cannot pay
    off."""

    name = "CanICraftCurrentTier"

    def __init__(self, step: ObtainItem, root: ObtainItem,
                root_stats: ItemStats, root_slots: list[str]) -> None:
        self.step = step
        self.root = root
        self.root_stats = root_stats
        self.root_slots = root_slots

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision | Goal | None":
        # Root craft SKILL-GATED: the final craft is blocked until the
        # crafting skill rises. The step's materials cannot pay off a craft
        # that cannot run -- raise the skill instead. This is the only link
        # from a skill-gated gear target to the skill it needs; before this
        # rewire it pointed at the sibling (`GatherMaterialsGoal(step)` --
        # gather materials for a craft that cannot run), and
        # `DoesTheRecipeNeedAMonsterDrop` masked it besides (PF-2): 11,434
        # LevelSkill(weaponcrafting->N) actions ran, target never once above
        # 10, dead on four characters since 2026-08-16.
        #
        # +1, not the target level: the graph re-derives from live state
        # every cycle, so the increment advances on its own and nothing has
        # to plan the whole climb to `crafting_level` in one shot.
        #
        # `self.root_stats` is never None here (M2): the only constructor
        # call site is `IsThisAnIntermediateOnAChain.resolve`, which only
        # builds this Decision inside `if root_stats is not None:`.
        if (self.root_stats.crafting_skill
                and state.skills.get(self.root_stats.crafting_skill, 1)
                < self.root_stats.crafting_level):
            current = state.skills.get(self.root_stats.crafting_skill, 1)
            return ReachSkillGoal(skill_name=self.root_stats.crafting_skill,
                                  target_level=current + 1)
        # Skill adequate: fall through to the monster-drop / depth-budget
        # chunking exactly as line 924 ran today.
        return DoesTheRecipeNeedAMonsterDrop(
            self.step, self.root, self.root_slots)


class DoesTheRecipeNeedAMonsterDrop(Decision):
    """strategy_driver.py:924 (originally 914-932). Reached only once
    `CanICraftCurrentTier` has confirmed the crafting skill is adequate
    (PF-2 hoist). Absorbs the depth-budget chunking that previously lived in
    the second half of `CanICraftCurrentTier` (originally 977-1002), since
    that logic only applies once a skill-adequate craft is in reach."""

    name = "DoesTheRecipeNeedAMonsterDrop"

    def __init__(self, step: ObtainItem, root: ObtainItem,
                root_slots: list[str]) -> None:
        self.step = step
        self.root = root
        self.root_slots = root_slots

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision | Goal | None":
        # Recipe with a MONSTER-DROP input (feather <- chicken): planning the
        # whole craft+equip chain EXPLODES — the GOAP A* must interleave
        # fights, gathers, crafts and travel across the chicken spawn /
        # resource node / workshop, which times out (live: feather_coat 57k
        # nodes, depth 23, plan_len 0). The recipe is deterministic but the
        # search is not. Collect inputs INCREMENTALLY: route to the flat
        # actionable step (gather wood / craft plank / hunt chickens for
        # feathers, one at a time). Each flat GatherMaterials plans within
        # budget — GatherMaterials(feather) emits Fight(chicken) and is a flat
        # hunt — and once every input is in hand the final craft is shallow.
        if _recipe_has_combat_drop_input(self.root.code, game_data):
            return GatherMaterialsGoal(target_item=self.step.code,
                                       needed={self.step.code: self.step.quantity})
        dest_slot = self.root.slot if self.root.slot is not None else self.root_slots[0]
        owned: dict[str, int] = dict(state.inventory)
        for code, qty in (state.bank_items or {}).items():
            owned[code] = owned.get(code, 0) + qty
        upgrade = UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                       committed_target=(self.root.code, dest_slot))
        # Pursue the committed gear root one PLANNABLE CHUNK at a time — never
        # hand the whole craft+equip chain to the A* at once. The old code
        # returned the whole-chain `upgrade` whenever `upgrade.is_plannable`,
        # but is_plannable means "achievable ever", NOT "the A* finds it within
        # max_depth". A from-scratch copper_boots chain is ~96 actions (80 ore
        # gathers + 8 bar crafts + boots + equip) ≫ max_depth 32, so the one-shot
        # plan returned plan_len 0 and the bot abandoned boots for chicken grind
        # (trace 2026-06-21). A depth
        # predicate can't save it either: min_plan_length is only a LOWER bound
        # (omits travel + the final assembly), so `<= max_depth` never PROVES the
        # plan fits. So we always chunk: when the step is an intermediate, route
        # to the deepest flat gather (gather_step_target), which plans within
        # budget and makes incremental progress; once the materials accumulate
        # the strategy's actionable_step advances to the next recipe level, and
        # when every input is in hand the step becomes the root itself (handled
        # by the equippable branch above as a shallow craft+equip). The root
        # objective commitment is unchanged — only its EXECUTION is chunked.
        #
        # Root chain depth-UNREACHABLE (from-scratch deep recipe). The
        # old fallback GatherMaterials(root, root's DIRECT recipe) needs a
        # plan that gathers min_gathers(root) raw units THROUGH the deep
        # recipe — the GOAP search over gather/deposit/craft interleavings
        # EXPLODES (live: 1M+ nodes, 90s timeout, plan_len 0, then
        # fall-through; the gear chain never progresses). Route instead to
        # the strategy's DEEPEST actionable step (the raw base material),
        # whose gather is FLAT and budget-feasible and makes incremental
        # progress; once it accumulates the next recipe level becomes the
        # actionable step. Sound: the step is a prerequisite ON the root's
        # path and never harder than the root (gather_step_target +
        # formal/Formal/StepDispatch.lean gatherTarget_*).
        #
        # gather_step_target can also decide the ROOT's own gather cost
        # already fits the depth budget and return it BY NAME — its own
        # module docstring states that as a precondition of THIS call
        # site ("the caller plans the root chain directly"), not
        # license to wrap the root in a second GatherMaterials pass
        # over itself (see `_gather_step_target_is_root`, shared with
        # `_gather_goal_for_unreachable_equippable`, for the mechanism
        # and the measured cost of getting this wrong). `upgrade` above
        # is already the root's reachable-root goal to fall through to.
        tgt_code, tgt_qty = gather_step_target(
            self.root.code, self.step.code, self.step.quantity,
            game_data.crafting_recipes, owned, upgrade.max_depth,
            game_data.max_gather_yield)
        return DoesTheChainFitTheDepthBudget(self.root, tgt_code, tgt_qty, upgrade)


class DoesTheChainFitTheDepthBudget(Decision):
    """strategy_driver.py:1003 (originally 1003-1005)."""

    name = "DoesTheChainFitTheDepthBudget"

    def __init__(self, root: ObtainItem, tgt_code: str, tgt_qty: int,
                upgrade: UpgradeEquipmentGoal) -> None:
        self.root = root
        self.tgt_code = tgt_code
        self.tgt_qty = tgt_qty
        self.upgrade = upgrade

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision | Goal | None":
        if _gather_step_target_is_root(self.tgt_code, self.root.code):
            return self.upgrade
        return GatherMaterialsGoal(target_item=self.tgt_code,
                                   needed={self.tgt_code: self.tgt_qty})


def obtain_item_decision(step: ObtainItem, root: MetaGoal | None) -> Decision:
    """The entry node for an `ObtainItem` step: the first branch of the
    original if-pile."""
    return CanIAffordTheCurrencyLeaf(step, root)
