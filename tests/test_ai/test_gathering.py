"""Tests for GatherMaterialsGoal.relevant_actions — intermediate craft batching.

Covers:
- When a target needs >= 6 of a craftable intermediate and the raw materials
  are ample in inventory, the emitted intermediate CraftAction.quantity must
  be > 1 (inventory-bounded demand, not a hard-coded 1).
"""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.destructive_license import license_destructive_actions
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.selection_context import SelectionContext
from tests.test_ai.fixtures import make_state


def _gd_copper_dagger() -> GameData:
    """copper_dagger → copper_bar:6 (per dagger) → copper_ore:10 (per bar).

    Closure: copper_dagger (craftable, weaponcrafting lv1),
             copper_bar (craftable, mining lv1),
             copper_ore (raw; produced by copper_rocks resource).
    """
    gd = GameData()
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "copper_bar": ItemStats(
            code="copper_bar", level=1, type_="resource",
            crafting_skill="mining", crafting_level=1,
        ),
        "copper_dagger": ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {
        "copper_bar": {"copper_ore": 10},
        "copper_dagger": {"copper_bar": 6},
    }
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._workshop_locations = {"mining": (1, 5), "weaponcrafting": (3, 1)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    return gd


class TestIntermediateCraftSizedToDemand:
    """Intermediate CraftAction batched to inventory-bounded closure demand."""

    def test_intermediate_craft_quantity_gt_one_when_multiple_needed(self):
        """copper_dagger needs 6 copper_bars; 60 ore in inventory → CraftAction(copper_bar).quantity == 6."""
        gd = _gd_copper_dagger()
        # 60 ore in inventory: enough for 6 bars, leaving 40 free slots.
        state = make_state(
            inventory={"copper_ore": 60},
            inventory_max=100,
            bank_items={},
            skills={"mining": 5, "weaponcrafting": 5},
        )
        goal = GatherMaterialsGoal("copper_dagger", {"copper_dagger": 1})
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 1)])),
            CraftAction(code="copper_bar", workshop_location=(1, 5)),
            CraftAction(code="copper_dagger", workshop_location=(3, 1)),
        ]

        relevant = goal.relevant_actions(actions, state, gd)

        craft_bars = [
            a for a in relevant
            if isinstance(a, CraftAction) and a.code == "copper_bar"
        ]
        assert craft_bars, "expected CraftAction for copper_bar in relevant_actions"
        assert craft_bars[0].quantity > 1, (
            f"intermediate craft should be batched to demand, "
            f"got quantity={craft_bars[0].quantity}"
        )


class TestSecondaryDropAdmission:
    """GAP-7 (2026-07-08): gather admission is EFFECTIVE-drop precise and
    skill-gated. A rare secondary drop opens exactly its targeted override
    gather; a skill-closed source (which can never fire in-plan — skills are
    immutable during GOAP application) is excluded even when it is the
    rate-best source, so it cannot win the yield narrowing and displace a
    workable spot (the salmon_spot trap)."""

    @staticmethod
    def _gd_pearls() -> GameData:
        gd = GameData()
        gd._item_stats = {
            "small_pearls": ItemStats(code="small_pearls", level=1, type_="resource"),
            "bass": ItemStats(code="bass", level=1, type_="resource"),
            "salmon": ItemStats(code="salmon", level=1, type_="resource"),
        }
        gd._crafting_recipes = {}
        gd._resource_drops = {"bass_spot": "bass", "salmon_spot": "salmon"}
        gd._resource_drops_full = {
            "bass_spot": [("bass", 1, 1, 1), ("small_pearls", 300, 1, 1)],
            "salmon_spot": [("salmon", 1, 1, 1), ("small_pearls", 100, 1, 1)],
        }
        gd._resource_skill = {"bass_spot": ("fishing", 30),
                              "salmon_spot": ("fishing", 40)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        return gd

    def _actions(self):
        return [
            GatherAction(resource_code="bass_spot", locations=frozenset([(0, 1)])),
            GatherAction(resource_code="bass_spot", locations=frozenset([(0, 1)]),
                         drop_item_override="small_pearls"),
            GatherAction(resource_code="salmon_spot", locations=frozenset([(0, 2)]),
                         drop_item_override="small_pearls"),
        ]

    def test_override_gather_admitted_primary_variant_dropped(self):
        """Only the pearl-producing variant of the workable spot survives:
        the primary bass gather produces nothing the closure needs, and
        salmon_spot (fishing 40 > 30) is skill-closed."""
        gd = self._gd_pearls()
        state = make_state(skills={"fishing": 30})
        goal = GatherMaterialsGoal("small_pearls", {"small_pearls": 1})
        relevant = goal.relevant_actions(self._actions(), state, gd)
        gathers = [(a.resource_code, a.drop_item_override)
                   for a in relevant if isinstance(a, GatherAction)]
        assert gathers == [("bass_spot", "small_pearls")]

    def test_skill_open_source_wins_narrowing_when_reachable(self):
        """At fishing 40 both spots are open and the yield narrowing keeps
        the rate-best source (salmon_spot, 1/100 beats 1/300 — proven
        select_gather_source core, now judged on the EFFECTIVE drop)."""
        gd = self._gd_pearls()
        state = make_state(skills={"fishing": 40})
        goal = GatherMaterialsGoal("small_pearls", {"small_pearls": 1})
        relevant = goal.relevant_actions(self._actions(), state, gd)
        gathers = [(a.resource_code, a.drop_item_override)
                   for a in relevant if isinstance(a, GatherAction)]
        assert gathers == [("salmon_spot", "small_pearls")]


class TestRecycleAsAcquisition:
    """Recycle-as-acquisition, Task 5 (2026-07-13): a licensed RecycleAction
    whose recipe yields a closure material is a SOURCE for that material, and
    the WITHDRAW that feeds it must be admitted too — the source
    (fishing_net) is upstream of the ash_plank closure, so the closure-built
    `withdrawable` set alone would miss it.

    Live bug: GatherMaterials(ash_plank) chopped 50 ash_wood at 1/cycle while
    holding 7 fishing_net, whose recipe IS 6 ash_plank each. The goal admitted
    ZERO RecycleActions — even one injected into the pool was discarded,
    because `planner.py:124` re-filters every action through
    `relevant_actions` before search."""

    @staticmethod
    def _gd_ash_plank() -> GameData:
        gd = GameData()
        gd._item_stats = {
            "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
            "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource",
                                   crafting_skill="woodcutting", crafting_level=1),
            "fishing_net": ItemStats(code="fishing_net", level=1, type_="amulet",
                                     crafting_skill="gearcrafting", crafting_level=1),
            "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                    crafting_skill="weaponcrafting", crafting_level=1),
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        }
        gd._crafting_recipes = {
            "ash_plank": {"ash_wood": 10},
            "fishing_net": {"ash_plank": 6},
            # Recycles to copper_bar — NOT in the ash_plank closure — pins that
            # admission is closure-precise, not "any RecycleAction in the pool."
            "copper_axe": {"copper_bar": 6},
        }
        gd._resource_drops = {"ash_tree": "ash_wood"}
        gd._workshop_locations = {"woodcutting": (1, 1), "gearcrafting": (2, 1),
                                  "weaponcrafting": (3, 1)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        return gd

    def test_gather_goal_admits_a_licensed_recycle_source(self):
        """GatherMaterials(ash_plank) must see Recycle(fishing_net): its
        recipe IS ash_plank."""
        gd = self._gd_ash_plank()
        state = make_state(skills={"gearcrafting": 1, "woodcutting": 1})
        goal = GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 5})
        pool = [RecycleAction(code="fishing_net", quantity=1, workshop_location=(2, 1))]
        kept = goal.relevant_actions(pool, state, gd)
        assert [a.code for a in kept if isinstance(a, RecycleAction)] == ["fishing_net"]

    def test_gather_goal_admits_the_withdraw_that_feeds_the_recycle(self):
        """The recycle SOURCE is upstream of the material closure, so the
        closure-built `withdrawable` set misses it. Without this the
        bank->recycle chain is unplannable. The pool carries fishing_net's
        licensed RecycleAction too — a Withdraw for a source with NO licensed
        recycle in the pool is exactly what admission must no longer allow
        (that source can never be fed)."""
        gd = self._gd_ash_plank()
        state = make_state(skills={"gearcrafting": 1, "woodcutting": 1})
        goal = GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 5})
        pool = [
            WithdrawItemAction(code="fishing_net", quantity=1),
            RecycleAction(code="fishing_net", quantity=1, workshop_location=(2, 1)),
        ]
        kept = goal.relevant_actions(pool, state, gd)
        assert [a.code for a in kept if isinstance(a, WithdrawItemAction)] == ["fishing_net"]

    def test_gather_goal_ignores_an_unrelated_recycle(self):
        """copper_axe recycles to copper_bar, which is not in the ash_plank
        closure."""
        gd = self._gd_ash_plank()
        state = make_state(skills={"gearcrafting": 1, "woodcutting": 1})
        goal = GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 5})
        pool = [RecycleAction(code="copper_axe", quantity=1, workshop_location=(3, 1))]
        assert [a for a in goal.relevant_actions(pool, state, gd)
                if isinstance(a, RecycleAction)] == []

    def test_recycle_beats_gathering_on_cost(self):
        """The payoff: recycling the fishing_net hoard resolves the goal with
        FAR fewer than the 50 gathers a from-scratch chain would need
        (10 ash_wood per ash_plank x 5 ash_plank)."""
        gd = self._gd_ash_plank()
        state = make_state(x=0, y=0, skills={"gearcrafting": 1, "woodcutting": 1},
                          inventory={"fishing_net": 7}, inventory_max=100)
        ctx = SelectionContext(bank_accessible=True, bank_required_level=0,
                               bank_unlock_monster=None, initial_xp=0,
                               task_exchange_min_coins=1, combat_monster=None)
        raw_pool = [
            GatherAction(resource_code="ash_tree", locations=frozenset([(0, 1)])),
            CraftAction(code="ash_plank", workshop_location=(1, 1)),
            RecycleAction(code="fishing_net", quantity=1, workshop_location=(2, 1)),
        ]
        # Simulate the arriving pool exactly as StrategyArbiter.select produces
        # it: already licence-filtered, with bag_floor stamped onto any
        # surviving RecycleAction.
        pool = license_destructive_actions(raw_pool, state, gd, ctx)
        goal = GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 5})
        plan = GOAPPlanner().plan(state, goal, goal.relevant_actions(pool, state, gd),
                                  gd, budget_seconds=30.0)
        assert plan, "planner found no plan"
        assert any(isinstance(a, RecycleAction) for a in plan)
        assert sum(isinstance(a, GatherAction) for a in plan) < 10


def _forged_plate_gd() -> GameData:
    """forged_plate: craft-only, gearcrafting-gated at level 20, built from a
    gatherable iron_ore leaf (mirrors test_forced_craft_grind._gd /
    test_goals._fire_bow_gd — craft-only, skill-gated, unowned target). No
    resource drop / monster drop / NPC vendor exists for forged_plate ITSELF,
    so `obtain_sources` names no non-CRAFT route for it and the grind is
    forced whenever the skill gate is unmet."""
    gd = GameData()
    gd._item_stats = {
        "forged_plate": ItemStats(code="forged_plate", level=20, type_="body_armor",
                                  crafting_skill="gearcrafting", crafting_level=20),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"forged_plate": {"iron_ore": 10}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    gd._bank_location = (3, 0)
    gd._taskmaster_location = (1, 1)
    return gd


def test_gather_materials_heuristic_is_forced_grind_cost():
    """A GatherMaterials goal whose target_item is a craft-only, skill-gated,
    unowned craftable returns the forced LevelSkill.cost; 0 otherwise."""
    gd = _forged_plate_gd()  # forged_plate: craft-only, gearcrafting 20
    goal = GatherMaterialsGoal(target_item="forged_plate",
                               needed={"forged_plate": 1})
    under = make_state(skills={"gearcrafting": 12})
    assert goal.heuristic(under, gd) == \
        LevelSkill(skill="gearcrafting", target_level=20).cost(under, gd)
    met = make_state(skills={"gearcrafting": 20})
    assert goal.heuristic(met, gd) == 0.0
