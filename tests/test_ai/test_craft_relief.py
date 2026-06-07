"""CRAFT_RELIEF circuit breaker: when inventory pressure forces a decision
and the bot can craft a goal-item from current inventory, the guard ladder
should pick CraftRelief instead of routing to DepositInventory or
DiscardOverstock."""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.craft_relief import (
    ReliefCandidate,
    craft_relief_candidates,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.craft_relief import CraftReliefGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter, map_guard
from artifactsmmo_cli.ai.tiers.guards import (
    CRAFT_RELIEF_FRACTION,
    DEPOSIT_FULL_FRACTION,
    GuardKind,
    SelectionContext,
    active_guards,
)
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _gd_ash_plank() -> GameData:
    """Game data with the ash_wood->ash_plank recipe (1:1, woodcutting)."""
    gd = GameData()
    gd._item_stats = {
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        "ash_plank": ItemStats(
            code="ash_plank", level=1, type_="resource",
            crafting_skill="woodcutting", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {"ash_plank": {"ash_wood": 1}}
    gd._workshop_locations = {"woodcutting": (2, 3)}
    gd._resource_locations = {"ash_tree": [(3, 0)]}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    fill_monster_stat_defaults(gd)
    return gd


def _ctx(**overrides: object) -> SelectionContext:
    base: dict[str, object] = dict(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
    )
    base.update(overrides)
    return SelectionContext(**base)  # type: ignore[arg-type]


class TestCraftReliefCandidates:
    def test_task_item_with_materials_in_inventory_is_candidate(self):
        """Robby trace 2026-06-05: 67 ash_wood, task=ash_plank(3/13).
        ash_plank<-ash_wood at 1:1 with craft_lvl=1; player skill defaults
        to 1; recipe inputs in inv => candidate emitted, capped by
        remaining task units (10)."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"ash_wood": 67}, inventory_max=104,
        )
        candidates = craft_relief_candidates(state, gd)
        assert len(candidates) == 1
        c = candidates[0]
        assert c == ReliefCandidate(
            item_code="ash_plank", quantity=10, priority_class=0,
        )

    def test_no_candidate_when_materials_missing(self):
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"copper_ore": 50},
        )
        assert craft_relief_candidates(state, gd) == []

    def test_no_candidate_when_skill_insufficient(self):
        gd = _gd_ash_plank()
        gd._item_stats["ash_plank"] = ItemStats(
            code="ash_plank", level=1, type_="resource",
            crafting_skill="woodcutting", crafting_level=10,  # gates above default 1
        )
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"ash_wood": 67}, skills={"woodcutting": 1},
        )
        assert craft_relief_candidates(state, gd) == []

    def test_no_candidate_when_item_has_no_crafting_skill(self):
        """A task item whose stats carry no crafting_skill (a raw resource,
        not a craftable) can't be a relief candidate."""
        gd = _gd_ash_plank()
        # ash_wood itself is the task — it has no crafting_skill.
        state = make_state(
            task_code="ash_wood", task_type="items",
            task_progress=0, task_total=5,
            inventory={"ash_wood": 5},
        )
        assert craft_relief_candidates(state, gd) == []

    def test_no_candidate_when_item_has_skill_but_no_recipe(self):
        """Stats name a crafting_skill but no recipe is registered — guard
        treats it as uncraftable rather than crashing."""
        gd = _gd_ash_plank()
        gd._item_stats["phantom_item"] = ItemStats(
            code="phantom_item", level=1, type_="resource",
            crafting_skill="woodcutting", crafting_level=1,
        )
        # No entry in _crafting_recipes for phantom_item.
        state = make_state(
            task_code="phantom_item", task_type="items",
            task_progress=0, task_total=5,
            inventory={"ash_wood": 67}, skills={"woodcutting": 1},
        )
        assert craft_relief_candidates(state, gd) == []

    def test_target_tools_emit_priority_two_candidate(self):
        """A craftable target tool surfaces at priority_class 2."""
        gd = _gd_ash_plank()
        gd._item_stats["wooden_pickaxe"] = ItemStats(
            code="wooden_pickaxe", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        gd._crafting_recipes["wooden_pickaxe"] = {"ash_plank": 4}
        state = make_state(
            inventory={"ash_plank": 8}, skills={"weaponcrafting": 1},
        )
        cands = craft_relief_candidates(
            state, gd, target_tools=frozenset({"wooden_pickaxe"}),
        )
        assert any(c.item_code == "wooden_pickaxe" and c.priority_class == 2
                   for c in cands)

    def test_duplicate_code_across_task_and_gear_considered_once(self):
        """When the same code is both the task item and a target_gear entry,
        the second `consider` short-circuits on the seen-set."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=0, task_total=13,
            inventory={"ash_wood": 20}, skills={"woodcutting": 1},
        )
        cands = craft_relief_candidates(
            state, gd, target_gear=frozenset({"ash_plank"}),
        )
        # Only one ash_plank candidate, at the task priority (0), not gear (1).
        ash = [c for c in cands if c.item_code == "ash_plank"]
        assert len(ash) == 1
        assert ash[0].priority_class == 0

    def test_target_gear_emits_lower_priority_candidate(self):
        """Gear/tools rank below the task item but still surface when no task is
        active or task can't be crafted from inv."""
        gd = _gd_ash_plank()
        gd._item_stats["wooden_shield"] = ItemStats(
            code="wooden_shield", level=1, type_="shield",
            crafting_skill="gearcrafting", crafting_level=1,
        )
        gd._crafting_recipes["wooden_shield"] = {"ash_plank": 6}
        state = make_state(inventory={"ash_plank": 6}, skills={"gearcrafting": 1})
        cands = craft_relief_candidates(
            state, gd, target_gear=frozenset({"wooden_shield"}),
        )
        assert any(c.item_code == "wooden_shield" and c.priority_class == 1
                   for c in cands)

    def test_task_item_ranks_above_gear_when_both_available(self):
        gd = _gd_ash_plank()
        gd._item_stats["wooden_shield"] = ItemStats(
            code="wooden_shield", level=1, type_="shield",
            crafting_skill="gearcrafting", crafting_level=1,
        )
        gd._crafting_recipes["wooden_shield"] = {"ash_plank": 6}
        # Both craftable from inventory: ash_plank (task) and wooden_shield (gear).
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=0, task_total=13,
            inventory={"ash_wood": 20, "ash_plank": 6},
            skills={"gearcrafting": 1, "woodcutting": 1},
        )
        cands = craft_relief_candidates(
            state, gd, target_gear=frozenset({"wooden_shield"}),
        )
        assert cands[0].item_code == "ash_plank"
        assert cands[0].priority_class == 0


class TestCraftReliefGuard:
    def test_fires_above_threshold_with_craftable(self):
        """Guard predicate: inv >= CRAFT_RELIEF_FRACTION AND a craftable
        candidate exists. With 73/104 (70.2%) and ash_wood->ash_plank
        recipe ready, CRAFT_RELIEF must fire and rank ahead of
        DEPOSIT_FULL (which would also fire at 80%+) when applicable."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"ash_wood": 73}, inventory_max=104,
        )
        used = state.inventory_used / state.inventory_max
        assert used >= CRAFT_RELIEF_FRACTION
        assert used < DEPOSIT_FULL_FRACTION
        guards = active_guards(state, gd, None, _ctx())
        assert GuardKind.CRAFT_RELIEF in guards

    def test_does_not_fire_below_threshold(self):
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"ash_wood": 30}, inventory_max=104,  # 28.8%
        )
        guards = active_guards(state, gd, None, _ctx())
        assert GuardKind.CRAFT_RELIEF not in guards

    def test_does_not_fire_when_nothing_craftable(self):
        """Above threshold but no inventory materials match any goal recipe
        => guard stays inert and the ladder routes to DEPOSIT_FULL /
        DISCARD_HIGH as before."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"copper_ore": 80}, inventory_max=104,
        )
        guards = active_guards(state, gd, None, _ctx())
        assert GuardKind.CRAFT_RELIEF not in guards

    def test_preempts_deposit_full_in_ladder(self):
        """When CRAFT_RELIEF AND DEPOSIT_FULL both fire (inv >= 80% AND
        craftable from inv AND something else is bankable), CRAFT_RELIEF
        must appear first in the active guard ladder so the arbiter picks
        it first."""
        gd = _gd_ash_plank()
        # Add a depositable item (gold_ore — no task / no recipe / no keep)
        # so select_bank_deposits returns non-empty and DEPOSIT_FULL fires.
        gd._item_stats["gold_ore"] = ItemStats(code="gold_ore", level=1, type_="resource")
        gd._npc_sell_prices = {"merchant": {"gold_ore": 50}}
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"ash_wood": 84, "gold_ore": 10},
            # 94/104 = 90.4% >= DEPOSIT_FULL_FRACTION (0.90, raised from 0.80
            # per spec 2026-06-07 to stay strictly above the 0.85 deposit ramp).
            inventory_max=104,
        )
        guards = active_guards(state, gd, None, _ctx())
        assert GuardKind.CRAFT_RELIEF in guards
        assert GuardKind.DEPOSIT_FULL in guards
        assert guards.index(GuardKind.CRAFT_RELIEF) < guards.index(GuardKind.DEPOSIT_FULL)


class TestMapGuardCraftRelief:
    def test_map_guard_builds_craft_relief_goal(self):
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"ash_wood": 75}, inventory_max=104,
        )
        goal = map_guard(GuardKind.CRAFT_RELIEF, gd, _ctx(), state)
        assert isinstance(goal, CraftReliefGoal)
        assert repr(goal) == "CraftRelief(ash_plank)"


class TestCraftReliefGoalApi:
    def test_value_is_guard_band_until_one_more_unit_crafted(self):
        gd = _gd_ash_plank()
        goal = CraftReliefGoal(target_item="ash_plank", initial_qty=3)
        # Below initial_qty + 1 → goal unsatisfied → guard-band value.
        below = make_state(inventory={"ash_plank": 3})
        assert not goal.is_satisfied(below)
        assert goal.value(below, gd) == 70.0
        # At initial_qty + 1 → satisfied → zero value.
        at = make_state(inventory={"ash_plank": 4})
        assert goal.is_satisfied(at)
        assert goal.value(at, gd) == 0.0

    def test_desired_state_requests_one_additional_unit(self):
        gd = _gd_ash_plank()
        goal = CraftReliefGoal(target_item="ash_plank", initial_qty=3)
        state = make_state(inventory={"ash_plank": 3})
        assert goal.desired_state(state, gd) == {"inventory": {"ash_plank": 4}}


class TestArbiterEndToEnd:
    def test_arbiter_picks_craft_relief_over_deposit(self):
        """Full driver path: inv at 87%, ash_wood->ash_plank recipe ready;
        arbiter must return CraftReliefGoal, not DepositInventoryGoal.
        Pre-circuit-breaker the trace showed DEPOSIT_FULL winning and the
        bot trekking to the bank instead of crafting."""
        gd = _gd_ash_plank()
        state = make_state(
            x=2, y=3,  # already at the woodcutting workshop tile
            level=3, hp=130, max_hp=130, xp=0, max_xp=350,
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"ash_wood": 90}, inventory_max=104,
        )
        actions = [
            CraftAction(code="ash_plank", quantity=1, workshop_location=(2, 3)),
            CraftAction(code="ash_plank", quantity=10, workshop_location=(2, 3)),
            TaskTradeAction(code="ash_plank", quantity=10, taskmaster_location=(1, 2)),
        ]
        arbiter = StrategyArbiter(GOAPPlanner(), history=None)

        class _FakeDecision:
            chosen_step = None
        goal, plan, _tried = arbiter.select(_FakeDecision(), state, gd, actions, _ctx())
        assert isinstance(goal, CraftReliefGoal)
        assert plan, "expected a craft plan"
        # The first action must be a Craft of the target item (Move folded in
        # via workshop_location for already-on-tile states).
        assert any(isinstance(a, CraftAction) and a.code == "ash_plank" for a in plan)
