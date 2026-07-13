"""CRAFT_RELIEF circuit breaker: when inventory pressure forces a decision
and the bot can craft a goal-item from current inventory WITH NET RELIEF
(inputs consumed > outputs produced), the guard ladder should pick
CraftRelief instead of routing to DepositInventory or DiscardOverstock —
and one activation should batch enough crafts to relieve the pressure.

Trace 2026-06-08 cycles 570-632 (locked below): the guard picked
cooked_gudgeon — a 1:1 recipe that frees ZERO units — and crafted x1
thirty-eight times, flapping CraftRelief<->PursueTask every 1-2 cycles."""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
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
    """Game data with the ash_wood->ash_plank recipe (10:1, woodcutting) —
    a net-relief recipe: each craft consumes 10 units and produces 1."""
    gd = GameData()
    gd._item_stats = {
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        "ash_plank": ItemStats(
            code="ash_plank", level=1, type_="resource",
            crafting_skill="woodcutting", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {"ash_plank": {"ash_wood": 10}}
    gd._workshop_locations = {"woodcutting": (2, 3)}
    gd._resource_locations = {"ash_tree": [(3, 0)]}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    fill_monster_stat_defaults(gd)
    return gd


def _gd_gudgeon() -> GameData:
    """Trace 2026-06-08: gudgeon->cooked_gudgeon is 1:1 (cooking) — one
    input unit consumed, one output unit produced, ZERO net relief."""
    gd = GameData()
    gd._item_stats = {
        "gudgeon": ItemStats(code="gudgeon", level=1, type_="resource"),
        "cooked_gudgeon": ItemStats(
            code="cooked_gudgeon", level=1, type_="consumable",
            crafting_skill="cooking", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {"cooked_gudgeon": {"gudgeon": 1}}
    gd._workshop_locations = {"cooking": (1, 1)}
    gd._resource_locations = {"gudgeon_fishing_spot": [(4, 2)]}
    gd._resource_drops = {"gudgeon_fishing_spot": "gudgeon"}
    gd._resource_skill = {"gudgeon_fishing_spot": ("fishing", 1)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    fill_monster_stat_defaults(gd)
    return gd


def _gd_copper() -> GameData:
    """copper_ore->copper_bar (10:1, mining) + copper_bar->copper_helmet
    (6 bars, gearcrafting): a net-relief task recipe plus a gear recipe
    whose closure consumes the task's reserved materials."""
    gd = GameData()
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "copper_bar": ItemStats(
            code="copper_bar", level=1, type_="resource",
            crafting_skill="mining", crafting_level=1,
        ),
        "copper_helmet": ItemStats(
            code="copper_helmet", level=1, type_="helmet",
            crafting_skill="gearcrafting", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {
        "copper_bar": {"copper_ore": 10},
        "copper_helmet": {"copper_bar": 6},
    }
    gd._workshop_locations = {"mining": (1, 5), "gearcrafting": (3, 1)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    fill_monster_stat_defaults(gd)
    return gd


def _gd_copper_gear() -> GameData:
    """copper_bar intermediate + two end-stage equippables (dagger 6 bars,
    boots 8 bars) for the 2026-06-13 starvation regression: relief used to
    craft the cheaper off-objective dagger and starve the boots root."""
    gd = GameData()
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                  crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {
        "copper_bar": {"copper_ore": 10},
        "copper_dagger": {"copper_bar": 6},
        "copper_boots": {"copper_bar": 8},
    }
    gd._workshop_locations = {"mining": (1, 5), "weaponcrafting": (2, 2),
                              "gearcrafting": (3, 1)}
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
        """Robby trace 2026-06-05: ash_wood, task=ash_plank(3/13).
        ash_plank<-10 ash_wood with craft_lvl=1; recipe inputs in inv =>
        candidate emitted, capped by simultaneously-craftable units (6);
        usage 60/104 is below the relief threshold so no relief cap binds.

        60 (not the trace's 67): the batch must CLEAR the ash_wood stack to be
        relief at all (`TestSlotHonestRelief`) — 6 crafts consume all 60, so
        slots go 1 -> 1. At 67 the same 6 crafts would strand 7 ash_wood and
        ADD the plank stack on top of it."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"ash_wood": 60}, inventory_max=104,
        )
        candidates = craft_relief_candidates(state, gd)
        assert len(candidates) == 1
        c = candidates[0]
        assert c == ReliefCandidate(
            item_code="ash_plank", quantity=6, priority_class=0,
        )

    def test_one_to_one_recipe_is_not_relief(self):
        """Trace 2026-06-08 cycles 570-632 LOCKED: 8 gudgeon on hand at 70%
        pressure, task=cooked_gudgeon — a 1:1 recipe relieves zero units, so
        it must NOT be a relief candidate (the old code crafted it x1
        thirty-eight times, ping-ponging (4,2)<->(1,1) per single item)."""
        gd = _gd_gudgeon()
        state = make_state(
            task_code="cooked_gudgeon", task_type="items",
            task_progress=0, task_total=38,
            inventory={"gudgeon": 8, "cooked_gudgeon": 6},  # 14/20 = 70%
            inventory_max=20,
        )
        assert state.inventory_used / state.inventory_max >= CRAFT_RELIEF_FRACTION
        assert craft_relief_candidates(state, gd) == []

    def test_relief_batch_is_raised_to_the_slot_honest_craft(self):
        """10 copper_ore -> 1 copper_bar frees 9 units per craft. At 80/100 the
        crafts needed to push usage strictly below the 70% threshold are 2
        (80 -> 62) — that is the FLOOR of the batch, not its value: stopping at
        x2 would strand 60 copper_ore in their stack and ADD a copper_bar stack
        (slots 1 -> 2). The batch is raised to the smallest SLOT-HONEST craft,
        x8, which consumes the ore stack whole (slots 1 -> 1, units 80 -> 8)."""
        gd = _gd_copper()
        state = make_state(
            task_code="copper_bar", task_type="items",
            task_progress=0, task_total=11,
            inventory={"copper_ore": 80}, inventory_max=100,
        )
        candidates = craft_relief_candidates(state, gd)
        assert candidates == [ReliefCandidate(
            item_code="copper_bar", quantity=8, priority_class=0,
        )]

    def test_quantity_bounded_by_simultaneously_craftable(self):
        """Below the pressure threshold no relief cap applies; the quantity
        is bounded by what the on-hand inputs can craft simultaneously
        (80 ore / 10 per craft = 8), not x1."""
        gd = _gd_copper()
        state = make_state(
            task_code="copper_bar", task_type="items",
            task_progress=0, task_total=11,
            inventory={"copper_ore": 80}, inventory_max=200,  # 40% used
        )
        candidates = craft_relief_candidates(state, gd)
        assert candidates == [ReliefCandidate(
            item_code="copper_bar", quantity=8, priority_class=0,
        )]

    def test_step_candidate_consuming_reserved_task_materials_excluded(self):
        """task=copper_bar(0/11) reserves the bar closure (11 bars, 110 ore).
        A step-chain candidate (copper_helmet) that eats 6 reserved bars
        without surplus is excluded by consumes_reserved; the task item itself
        stays a candidate (producing it IS the reserved pipeline)."""
        gd = _gd_copper()
        state = make_state(
            task_code="copper_bar", task_type="items",
            task_progress=0, task_total=11,
            inventory={"copper_bar": 6, "copper_ore": 80}, inventory_max=200,
            skills={"mining": 1, "gearcrafting": 1},
        )
        candidates = craft_relief_candidates(
            state, gd, step_items=frozenset({"copper_helmet"}),
        )
        assert [c.item_code for c in candidates] == ["copper_bar"]

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
        treats it as uncraftable rather than crashing.  Use a material
        (feather) that appears in no recipe so sole-output doesn't fire."""
        gd = _gd_ash_plank()
        gd._item_stats["phantom_item"] = ItemStats(
            code="phantom_item", level=1, type_="resource",
            crafting_skill="woodcutting", crafting_level=1,
        )
        # No entry in _crafting_recipes for phantom_item.
        # feather is not an input for any recipe in _gd_ash_plank, so
        # sole-output expansion is also inert here.
        state = make_state(
            task_code="phantom_item", task_type="items",
            task_progress=0, task_total=5,
            inventory={"feather": 67}, skills={"woodcutting": 1},
        )
        assert craft_relief_candidates(state, gd) == []

    def test_duplicate_code_across_task_and_step_considered_once(self):
        """When the same code is both the task item and a step-chain entry,
        the second `consider` short-circuits on the seen-set."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=0, task_total=13,
            inventory={"ash_wood": 20}, skills={"woodcutting": 1},
        )
        cands = craft_relief_candidates(
            state, gd, step_items=frozenset({"ash_plank"}),
        )
        # Only one ash_plank candidate, at the task priority (0), not step (1).
        ash = [c for c in cands if c.item_code == "ash_plank"]
        assert len(ash) == 1
        assert ash[0].priority_class == 0

    def test_task_item_ranks_above_step_intermediate_when_both_available(self):
        gd = _gd_ash_plank()
        gd._item_stats["wooden_shield"] = ItemStats(
            code="wooden_shield", level=1, type_="shield",
            crafting_skill="gearcrafting", crafting_level=1,
        )
        gd._crafting_recipes["wooden_shield"] = {"ash_plank": 6}
        # Both craftable: ash_plank (task, class 0) and wooden_shield (step, class 1).
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=0, task_total=13,
            inventory={"ash_wood": 20, "ash_plank": 6},
            skills={"gearcrafting": 1, "woodcutting": 1},
        )
        cands = craft_relief_candidates(
            state, gd, step_items=frozenset({"wooden_shield"}),
        )
        assert cands[0].item_code == "ash_plank"
        assert cands[0].priority_class == 0

    def test_end_stage_gear_is_not_a_relief_candidate(self):
        """Reported 2026-06-13 (copper_boots trace): even when an equippable is
        craftable from inventory, relief never assembles it — only the task
        item and step-chain intermediates qualify. copper_dagger/copper_boots
        are craftable from copper_bar but must NOT surface; the intermediate
        copper_bar does."""
        gd = _gd_copper_gear()
        state = make_state(
            inventory={"copper_bar": 6, "copper_ore": 80, "feather": 30},
            inventory_max=120,
            skills={"mining": 1, "weaponcrafting": 1, "gearcrafting": 1},
        )
        cands = craft_relief_candidates(
            state, gd, step_items=frozenset({"copper_bar"}),
        )
        codes = [c.item_code for c in cands]
        assert "copper_dagger" not in codes
        assert "copper_boots" not in codes
        assert codes == ["copper_bar"]


class TestCraftReliefGuard:
    def test_fires_above_threshold_with_craftable(self):
        """Guard predicate: inv >= CRAFT_RELIEF_FRACTION AND a SLOT-HONEST
        craftable candidate exists. With 80/104 (76.9%) and ash_wood->ash_plank
        ready (x8 consumes the whole stack), CRAFT_RELIEF must fire and rank
        ahead of DEPOSIT_FULL (which would also fire at 90%+) when applicable."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"ash_wood": 80}, inventory_max=104,
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

    def test_does_not_fire_when_only_candidate_is_one_to_one(self):
        """Trace 2026-06-08 LOCKED at guard level: at >= 70% pressure with
        only the 1:1 cooked_gudgeon recipe available, the net-relief gate
        leaves zero candidates and the guard must stay SILENT — real
        pressure is handled by DEPOSIT_FULL / DISCARD_HIGH at their own
        thresholds, not by zero-relief crafting."""
        gd = _gd_gudgeon()
        state = make_state(
            task_code="cooked_gudgeon", task_type="items",
            task_progress=0, task_total=38,
            inventory={"gudgeon": 8, "cooked_gudgeon": 6},  # 14/20 = 70%
            inventory_max=20,
        )
        guards = active_guards(state, gd, None, _ctx())
        assert GuardKind.CRAFT_RELIEF not in guards

    def test_preempts_deposit_full_in_ladder(self):
        """When CRAFT_RELIEF AND DEPOSIT_FULL both fire (inv >= 90% AND
        craftable from inv AND something else is bankable), CRAFT_RELIEF
        must appear first in the active guard ladder so the arbiter picks
        it first."""
        gd = _gd_ash_plank()
        # Add a depositable item (gold_ore — no task / no recipe / no keep)
        # so select_bank_deposits returns non-empty and DEPOSIT_FULL fires.
        gd._item_stats["gold_ore"] = ItemStats(code="gold_ore", level=1, type_="resource")
        gd._npc_sell_prices = {"merchant": {"gold_ore": 50}}
        gd._bank_capacity = 50  # bank has room so DEPOSIT_FULL can fire
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            # 80 ash_wood is a SLOT-HONEST batch (x8 clears the stack); the
            # gold_ore makes up the pressure and is the deposit candidate.
            inventory={"ash_wood": 80, "gold_ore": 14},
            # 94/104 = 90.4% >= DEPOSIT_FULL_FRACTION (0.90, raised from 0.80
            # per spec 2026-06-07 to stay strictly above the 0.85 deposit ramp).
            inventory_max=104,
            bank_items={},  # bank visited, 0 items used < capacity 50
        )
        guards = active_guards(state, gd, None, _ctx())
        assert GuardKind.CRAFT_RELIEF in guards
        assert GuardKind.DEPOSIT_FULL in guards
        assert guards.index(GuardKind.CRAFT_RELIEF) < guards.index(GuardKind.DEPOSIT_FULL)

    def test_objective_target_gear_does_not_trigger_craft_relief(self):
        """Regression 2026-06-13: ctx.target_gear is no longer forwarded to
        relief candidacy. copper_dagger is craftable from on-hand copper_bar
        and listed as objective target_gear, and pressure is above threshold —
        but CRAFT_RELIEF must NOT fire, because relief only assembles task
        items / step intermediates, never end-stage equippables."""
        gd = _gd_copper_gear()
        state = make_state(
            inventory={"copper_bar": 6, "feather": 80}, inventory_max=120,
            skills={"mining": 1, "weaponcrafting": 1, "gearcrafting": 1},
        )
        assert state.inventory_used / state.inventory_max >= CRAFT_RELIEF_FRACTION
        ctx = _ctx(target_gear=frozenset({"copper_dagger"}),
                   target_tools=frozenset())
        guards = active_guards(state, gd, None, ctx)
        assert GuardKind.CRAFT_RELIEF not in guards


class TestMapGuardCraftRelief:
    def test_map_guard_builds_craft_relief_goal_with_relief_batch(self):
        """map_guard wires the top candidate's batched quantity into the goal:
        at 70/90 (77.8%) ONE 10:1 craft already frees enough units to land below
        the threshold — but it would strand 60 ash_wood and add the plank stack,
        so the batch is the slot-honest x7 and the goal demands +7 ash_plank."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=3, task_total=13,
            inventory={"ash_wood": 70}, inventory_max=90,
        )
        goal = map_guard(GuardKind.CRAFT_RELIEF, gd, _ctx(), state)
        assert isinstance(goal, CraftReliefGoal)
        assert repr(goal) == "CraftRelief(ash_plank)"
        assert goal.desired_state(state, gd) == {"inventory": {"ash_plank": 7}}


class TestCraftReliefGoalApi:
    def test_value_is_guard_band_until_batch_crafted(self):
        gd = _gd_ash_plank()
        goal = CraftReliefGoal(target_item="ash_plank", initial_qty=3, batch=4)
        # Below initial_qty + batch → goal unsatisfied → guard-band value.
        below = make_state(inventory={"ash_plank": 6})
        assert not goal.is_satisfied(below)
        assert goal.value(below, gd) == 70.0
        # At initial_qty + batch → satisfied → zero value.
        at = make_state(inventory={"ash_plank": 7})
        assert goal.is_satisfied(at)
        assert goal.value(at, gd) == 0.0

    def test_default_batch_is_one_additional_unit(self):
        gd = _gd_ash_plank()
        goal = CraftReliefGoal(target_item="ash_plank", initial_qty=3)
        state = make_state(inventory={"ash_plank": 3})
        assert goal.desired_state(state, gd) == {"inventory": {"ash_plank": 4}}
        assert goal.is_satisfied(make_state(inventory={"ash_plank": 4}))

    def test_desired_state_requests_batch_additional_units(self):
        gd = _gd_ash_plank()
        goal = CraftReliefGoal(target_item="ash_plank", initial_qty=3, batch=4)
        state = make_state(inventory={"ash_plank": 3})
        assert goal.desired_state(state, gd) == {"inventory": {"ash_plank": 7}}

    def test_relevant_actions_rebatches_single_craft(self):
        """The factory's x1 (and task batch-K) CraftActions collapse to ONE
        craft at the goal's batch quantity; Move and recipe-input withdraws
        pass through; unrelated actions are dropped."""
        gd = _gd_ash_plank()
        goal = CraftReliefGoal(target_item="ash_plank", initial_qty=0, batch=4)
        actions = [
            CraftAction(code="ash_plank", quantity=1, workshop_location=(2, 3)),
            CraftAction(code="ash_plank", quantity=10, workshop_location=(2, 3)),
            CraftAction(code="cooked_gudgeon", quantity=1, workshop_location=(1, 1)),
            MoveAction(x=2, y=3),
            WithdrawItemAction(code="ash_wood", quantity=10,
                               bank_location=(4, 0), accessible=True),
            WithdrawItemAction(code="gudgeon", quantity=1,
                               bank_location=(4, 0), accessible=True),
            TaskTradeAction(code="ash_plank", quantity=10, taskmaster_location=(1, 2)),
        ]
        state = make_state(inventory={"ash_wood": 40})
        out = goal.relevant_actions(actions, state, gd)
        crafts = [a for a in out if isinstance(a, CraftAction)]
        assert len(crafts) == 1
        assert crafts[0].code == "ash_plank"
        assert crafts[0].quantity == 4
        assert any(isinstance(a, MoveAction) for a in out)
        withdraws = [a for a in out if isinstance(a, WithdrawItemAction)]
        assert [w.code for w in withdraws] == ["ash_wood"]
        assert not any(isinstance(a, TaskTradeAction) for a in out)

    def test_relevant_actions_keeps_craft_already_at_batch_quantity(self):
        """A CraftAction whose quantity already equals the batch is reused
        as-is (no copy)."""
        gd = _gd_ash_plank()
        goal = CraftReliefGoal(target_item="ash_plank", initial_qty=0, batch=1)
        craft = CraftAction(code="ash_plank", quantity=1, workshop_location=(2, 3))
        state = make_state(inventory={"ash_wood": 10})
        out = goal.relevant_actions([craft], state, gd)
        assert out == [craft]
        assert out[0] is craft


class TestStepMaterialRelief:
    """Run-13 trace 2026-06-12 08:40–08:43 (cycles 92–95): with the gather
    phase complete (60 ash on hand, plan already at the plank-craft phase)
    and inventory at 99/110 (90%), the guard ladder spent two bank trips
    freeing 2 then 1 junk units instead of crafting a plank that frees 9 —
    the active step goal's chain materials were invisible to relief
    candidacy (task/gear/tools only). `step_items` must surface them so
    CRAFT_RELIEF (above DEPOSIT_FULL in the ladder) does its documented
    craft-before-deposit job."""

    def test_step_items_surface_as_candidates(self):
        """Sole-output extension: ash_wood is the only input for ash_plank, so
        ash_plank now surfaces even without explicit step_items.  step_items
        deduplicates via the seen-set — no double entry."""
        gd = _gd_ash_plank()
        # 99/110 = 90% pressure; 60 ash = 6 plank crafts of net relief 9.
        state = make_state(inventory={"ash_wood": 60, "feather": 39},
                           inventory_max=110)
        # Sole-output fires ash_plank even without step_items now.
        bare = craft_relief_candidates(state, gd)
        assert [c.item_code for c in bare] == ["ash_plank"]
        cands = craft_relief_candidates(
            state, gd,
            step_items=frozenset({"ash_plank", "wooden_shield", "ash_wood"}))
        # step_items deduplicates: same sole candidate, no duplicates.
        assert [c.item_code for c in cands] == ["ash_plank"]

    def test_guard_fires_from_step_profile_before_deposit(self):
        """Sole-output extension: CRAFT_RELIEF fires even without a step_profile
        because ash_wood → ash_plank is the sole output; step_profile still
        works (and deduplicates via seen-set).

        The CRAFT_RELIEF precedes DEPOSIT_FULL ordering is a safety property
        that must hold unconditionally — the assertion must not be gated on
        whether DEPOSIT_FULL happens to fire.  State is constructed so that
        DEPOSIT_FULL is guaranteed to fire: bank accessible + room (bank_items={}
        + bank_capacity=100), ≥90% inventory pressure, and a depositble item
        (feather is not in the ash_plank recipe keep-set)."""
        gd = _gd_ash_plank()
        gd._bank_capacity = 100
        # 60 ash_wood + 39 feather = 99/110 = 90% pressure (>= DEPOSIT_FULL_FRACTION).
        # feather is not in the ash_plank recipe so it is a deposit candidate.
        state = make_state(inventory={"ash_wood": 60, "feather": 39},
                           inventory_max=110,
                           bank_items={})
        # Sole-output now fires CRAFT_RELIEF without step_profile too.
        assert GuardKind.CRAFT_RELIEF in active_guards(state, gd, None, _ctx())
        step_profile = {"wooden_shield": 1, "ash_plank": 6, "ash_wood": 60}
        guards = active_guards(state, gd, None, _ctx(), step_profile)
        assert GuardKind.CRAFT_RELIEF in guards
        # Craft-before-deposit: relief precedes DEPOSIT_FULL in ladder order.
        # DEPOSIT_FULL is guaranteed to fire given the state above — unconditional.
        assert GuardKind.DEPOSIT_FULL in guards
        assert (guards.index(GuardKind.CRAFT_RELIEF)
                < guards.index(GuardKind.DEPOSIT_FULL))

    def test_map_guard_craft_relief_sees_step_items(self):
        gd = _gd_ash_plank()
        state = make_state(inventory={"ash_wood": 60, "feather": 39},
                           inventory_max=110)
        goal = map_guard(GuardKind.CRAFT_RELIEF, gd, _ctx(), state,
                         step_profile={"ash_plank": 6})
        assert isinstance(goal, CraftReliefGoal)
        assert goal._target_item == "ash_plank"


class TestSlotHonestRelief:
    """The bag is SLOT-limited, so "relief" must be measured in SLOTS.

    Census repro (`goal_materials in_bag/liveness`, 2026-07-12): 16 ash_wood
    sit in ONE stack. Crafting 1 ash_plank consumes 10 and leaves 6 ash_wood
    + 1 ash_plank — TWO stacks. The quantity-only gate saw 9 units freed and
    called it relief, so CRAFT_RELIEF fired, INCREASED slot usage, preempted
    the DEPOSIT_FULL that would actually have relieved the bag (it out-ranks
    it in GUARD_ORDER), and ate the ash_wood `keep_in_bag` protects for the
    active goal. A craft is relief only when it does not ADD a stack."""

    def test_remainder_craft_is_not_relief(self):
        """THE CENSUS REPRO. 16 ash_wood (1 stack) -> craft x1 leaves 6 wood
        + 1 plank = 2 stacks. Slots 1 -> 2: NOT relief, no candidate — even
        though 9 quantity units are freed."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=0, task_total=13,
            inventory={"ash_wood": 16}, inventory_max=20,
            inventory_slots_max=20,
        )
        assert state.inventory_used / state.inventory_max >= CRAFT_RELIEF_FRACTION
        assert craft_relief_candidates(state, gd) == []

    def test_guard_stays_silent_on_a_remainder_craft(self):
        """Same state at the guard: CRAFT_RELIEF must NOT fire, so the ladder
        falls through to the DEPOSIT_FULL that actually frees the bag."""
        gd = _gd_ash_plank()
        gd._bank_capacity = 100
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=0, task_total=13,
            inventory={"ash_wood": 16}, inventory_max=20,
            inventory_slots_max=20, bank_items={},
        )
        guards = active_guards(state, gd, None, _ctx())
        assert GuardKind.CRAFT_RELIEF not in guards

    def test_whole_stack_craft_is_relief(self):
        """Exactly 10 ash_wood: the craft consumes the WHOLE stack, so the
        source slot is freed and the plank takes it — 1 stack -> 1 stack, and
        quantity drops 10 -> 1. THAT is relief."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=0, task_total=13,
            inventory={"ash_wood": 10}, inventory_max=12,
            inventory_slots_max=20,
        )
        assert craft_relief_candidates(state, gd) == [ReliefCandidate(
            item_code="ash_plank", quantity=1, priority_class=0,
        )]

    def test_batch_consuming_the_whole_stack_is_relief(self):
        """20 ash_wood -> 2 ash_plank, no remainder: still 1 stack. The batch
        is sized to the slot-honest craft (x2) even though the pressure-relief
        cap alone would have stopped at x1 (which would leave 10 ash_wood
        behind and ADD a stack)."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=0, task_total=13,
            inventory={"ash_wood": 20}, inventory_max=24,
            inventory_slots_max=20,
        )
        assert craft_relief_candidates(state, gd) == [ReliefCandidate(
            item_code="ash_plank", quantity=2, priority_class=0,
        )]

    def test_product_merging_into_an_existing_stack_is_relief(self):
        """The product takes NO new slot when a stack of it is already held,
        so even a remainder-leaving craft is slot-neutral (1 wood stack + 1
        plank stack, before and after) while quantity drops 9."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=0, task_total=13,
            inventory={"ash_wood": 16, "ash_plank": 1}, inventory_max=20,
            inventory_slots_max=20,
        )
        assert craft_relief_candidates(state, gd) == [ReliefCandidate(
            item_code="ash_plank", quantity=1, priority_class=0,
        )]

    def test_no_batch_can_clear_the_stack(self):
        """25 ash_wood: x1 leaves 15, x2 leaves 5 — NO batch clears the source
        stack, and the plank is a new one, so no quantity is slot-honest and
        the item is not a relief candidate at all."""
        gd = _gd_ash_plank()
        state = make_state(
            task_code="ash_plank", task_type="items",
            task_progress=0, task_total=13,
            inventory={"ash_wood": 25}, inventory_max=30,
            inventory_slots_max=20,
        )
        assert craft_relief_candidates(state, gd) == []


class TestSoleOutputMaterialRelief:
    def test_sole_output_material_is_a_candidate(self):
        """A held material whose ONLY craftable output is one item (copper_ore ->
        copper_bar) is a relief candidate even off the goal chain."""
        gd = GameData()
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}   # copper_ore's only output
        gd._item_stats = {
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                    crafting_skill="mining", crafting_level=1),
            "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        }
        gd._workshop_locations = {"mining": (1, 5)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        fill_monster_stat_defaults(gd)
        # 30 ore on hand (3 bars craftable, net relief 9 per craft); pressure at 75%
        state = make_state(inventory={"copper_ore": 30}, inventory_max=40,
                           skills={"mining": 5})
        cands = craft_relief_candidates(state, gd, step_items=frozenset())
        assert any(c.item_code == "copper_bar" for c in cands)

    def test_multi_output_material_not_sole_output(self):
        """A material that feeds >1 recipe is NOT a sole-output candidate."""
        gd = GameData()
        gd._crafting_recipes = {"bar_a": {"ore": 5}, "bar_b": {"ore": 5}}
        gd._item_stats = {
            "ore": ItemStats(code="ore", level=1, type_="resource"),
            "bar_a": ItemStats(code="bar_a", level=1, type_="resource",
                               crafting_skill="mining", crafting_level=1),
            "bar_b": ItemStats(code="bar_b", level=1, type_="resource",
                               crafting_skill="mining", crafting_level=1),
        }
        gd._workshop_locations = {"mining": (1, 5)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        fill_monster_stat_defaults(gd)
        # 30 ore on hand at 75% pressure — multi-output, must NOT appear
        state = make_state(inventory={"ore": 30}, inventory_max=40,
                           skills={"mining": 5})
        cands = craft_relief_candidates(state, gd, step_items=frozenset())
        assert not any(c.item_code in ("bar_a", "bar_b") for c in cands)

    def test_sole_output_skips_equippable_gear(self):
        """A held material whose SOLE recipe output is an equippable item (weapon/
        armor/etc.) must NOT be a craft-relief candidate — end-stage gear is
        excluded by the docstring guarantee ('End-stage gear/tools are NOT
        considered').  Previously the sole-output loop called consider() with no
        gear guard, re-opening the 17-copper-helmet over-craft class of bug."""
        gd = GameData()
        # reagent_x → sword_x is the only recipe consuming reagent_x.
        # sword_x is a weapon (equippable): type_ in ITEM_TYPE_TO_SLOTS.
        gd._crafting_recipes = {"sword_x": {"reagent_x": 6}}
        gd._item_stats = {
            "reagent_x": ItemStats(code="reagent_x", level=1, type_="resource"),
            "sword_x": ItemStats(code="sword_x", level=1, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=1),
        }
        gd._workshop_locations = {"weaponcrafting": (2, 2)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        fill_monster_stat_defaults(gd)
        # 30 reagent_x on hand (5 swords craftable); pressure at 75% (30/40).
        state = make_state(inventory={"reagent_x": 30}, inventory_max=40,
                           skills={"weaponcrafting": 5})
        cands = craft_relief_candidates(state, gd, step_items=frozenset())
        assert not any(c.item_code == "sword_x" for c in cands), (
            "sword_x is equippable gear — sole-output loop must skip it"
        )

    def test_zero_qty_material_skipped_by_sole_output(self):
        """A material present in inventory with qty=0 must not trigger
        sole-output expansion (guard on mat_qty <= 0)."""
        gd = GameData()
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
        gd._item_stats = {
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                    crafting_skill="mining", crafting_level=1),
            "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        }
        gd._workshop_locations = {"mining": (1, 5)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        fill_monster_stat_defaults(gd)
        # copper_ore qty=0: sole-output branch must skip it, no candidate.
        state = make_state(inventory={"copper_ore": 0}, inventory_max=40,
                           skills={"mining": 5})
        cands = craft_relief_candidates(state, gd, step_items=frozenset())
        assert cands == []


class TestArbiterEndToEnd:
    def test_arbiter_picks_craft_relief_over_deposit_with_batched_craft(self):
        """Full driver path: inv at 86.5%, ash_wood->ash_plank (10:1) ready;
        arbiter must return CraftReliefGoal whose plan crafts the WHOLE
        relief batch in one CraftAction, not one item per cycle. The batch is
        x9: it consumes the 90-ash_wood stack whole (slots 1 -> 1, units
        90 -> 9). Stopping at the x2 that alone clears the 70% quantity
        watermark would leave 70 ash_wood behind AND add a plank stack."""
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
        crafts = [a for a in plan if isinstance(a, CraftAction)]
        assert len(crafts) == 1
        assert crafts[0].code == "ash_plank"
        assert crafts[0].quantity == 9

    def test_planner_emits_one_batched_craft_not_n_singles(self):
        """8 crafts' worth of inputs on hand → the plan is ONE CraftAction
        x8, never 8 separate x1 crafts (trace 2026-06-08: 38 single crafts
        with up to 8 raw gudgeon on hand)."""
        gd = _gd_ash_plank()
        goal = CraftReliefGoal(target_item="ash_plank", initial_qty=0, batch=8)
        state = make_state(
            x=2, y=3,
            inventory={"ash_wood": 80}, inventory_max=104,
        )
        actions = [
            CraftAction(code="ash_plank", quantity=1, workshop_location=(2, 3)),
        ]
        plan = GOAPPlanner().plan(state, goal, actions, gd)
        assert plan, "expected a one-step batched craft plan"
        crafts = [a for a in plan if isinstance(a, CraftAction)]
        assert len(crafts) == 1
        assert crafts[0].quantity == 8
