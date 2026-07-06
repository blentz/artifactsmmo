"""Grey-mob drop-farming policy + mechanism.

Robby at L12 could not farm feathers (chicken L1): FightAction's xpPositive
gate (proven ActionApplicability arm) zeroes fights >=10 levels down, so
mob-drop gathering from grey mobs was impossible in-model even though the
server still drops loot. Policy (user 2026-07-06): grey farming is allowed
IFF the drop serves a recipe AND the next-tier recipe of that recipe's
family is too far a skill-grind away (health_potion vs large_health_potion);
when the next tier is close, grind the skill instead of farming greys.
"""

import dataclasses

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.grey_farm import (
    GREY_FARM_NEXT_TIER_MARGIN,
    grey_farm_allowed,
)
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def make_state(level: int = 5, hp: int | None = None, max_hp: int = 100,
               skills: dict[str, int] | None = None,
               inventory: dict[str, int] | None = None,
               bank_items: dict[str, int] | None = None) -> WorldState:
    return WorldState(
        character="testchar", level=level, xp=0, max_xp=100,
        hp=hp if hp is not None else max_hp, max_hp=max_hp, gold=0,
        skills=skills or {}, x=0, y=0,
        inventory=inventory or {}, inventory_max=20,
        equipment=dict(_ALL_SLOTS), cooldown_expires=None,
        attack={"air": 10}, dmg=10,  # enough to be winnable vs the fixture chicken
        task_code=None, task_type=None, task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=bank_items, bank_gold=None, bank_capacity=None,
        pending_items=None,
    )


def fill_monster_stat_defaults(gd: GameData) -> None:
    for code in gd._monster_level:
        gd._monster_hp.setdefault(code, 0)
        gd._monster_attack.setdefault(code, {})
        gd._monster_resistance.setdefault(code, {})
        gd._monster_critical_strike.setdefault(code, 0)
        gd._monster_initiative.setdefault(code, 0)


def _gd(alchemy_next_tier_level: int | None = 20) -> GameData:
    """chicken (L1) drops feather; health_potion (alchemy 5) consumes feather;
    optionally a same-family next-tier recipe at `alchemy_next_tier_level`."""
    gd = GameData()
    gd._monster_locations = {"chicken": (1, 0)}
    gd._monster_level = {"chicken": 1}
    gd._monster_hp = {"chicken": 60}
    gd._monster_attack = {"chicken": {"air": 4}}
    gd._monster_drops = {"chicken": [("feather", 10, 1, 1)]}
    gd._item_stats = {
        "health_potion": ItemStats(code="health_potion", level=5, type_="utility",
                                   subtype="potion", hp_restore=30,
                                   crafting_skill="alchemy", crafting_level=5),
        "feather": ItemStats(code="feather", level=1, type_="resource", subtype="mob"),
    }
    gd._crafting_recipes = {"health_potion": {"feather": 2}}
    if alchemy_next_tier_level is not None:
        gd._item_stats["large_health_potion"] = ItemStats(
            code="large_health_potion", level=20, type_="utility", subtype="potion",
            hp_restore=120, crafting_skill="alchemy",
            crafting_level=alchemy_next_tier_level)
        gd._crafting_recipes["large_health_potion"] = {"sunflower": 4}
    fill_monster_stat_defaults(gd)
    return gd


class TestGreyFarmPolicy:
    def test_allowed_when_next_tier_far(self) -> None:
        """alchemy 5, next tier at 20 (gap 15 > margin): farm the greys."""
        gd = _gd(alchemy_next_tier_level=20)
        state = make_state(level=12, skills={"alchemy": 5})
        assert grey_farm_allowed("feather", state, gd) is True

    def test_disallowed_when_next_tier_close(self) -> None:
        """alchemy 18, next tier at 20 (within margin): grind the skill,
        don't farm greys for the obsolete recipe."""
        gd = _gd(alchemy_next_tier_level=20)
        state = make_state(level=12, skills={"alchemy": 18})
        assert grey_farm_allowed("feather", state, gd) is False

    def test_allowed_when_no_next_tier(self) -> None:
        """No higher same-family recipe exists: nothing to grind toward."""
        gd = _gd(alchemy_next_tier_level=None)
        state = make_state(level=12, skills={"alchemy": 30})
        assert grey_farm_allowed("feather", state, gd) is True

    def test_disallowed_when_no_recipe_consumes_the_drop(self) -> None:
        """Grey farming that serves no recipe is pure grind — never allowed."""
        gd = _gd()
        gd._crafting_recipes = {}
        state = make_state(level=12, skills={"alchemy": 5})
        assert grey_farm_allowed("feather", state, gd) is False

    def test_next_tier_family_ignores_other_effect_families(self) -> None:
        """A boost potion 2 levels up is NOT the next tier of a RESTORATIVE
        recipe: restorative targets only match restorative candidates."""
        gd = _gd(alchemy_next_tier_level=None)
        gd._item_stats["boost_potion"] = ItemStats(
            code="boost_potion", level=7, type_="utility", subtype="potion",
            hp_restore=0, combat_buff=10, crafting_skill="alchemy", crafting_level=7)
        gd._crafting_recipes["boost_potion"] = {"sunflower": 1}
        state = make_state(level=12, skills={"alchemy": 6})
        # boost at 7 is within margin of 6, but it's a different family:
        assert grey_farm_allowed("feather", state, gd) is True

    def test_allowed_for_purchase_currency_drop(self) -> None:
        """A drop that is the CURRENCY of an NPC purchase serves a demand the
        same way a recipe input does (Fight×N -> NpcBuy chains, Task #13:
        sandwhisper_coin @ sea_marauder buys greater_lifesteal_rune). There
        is no recipe tier to grind toward instead, so it is always farmable."""
        gd = _gd(alchemy_next_tier_level=None)
        gd._crafting_recipes = {}
        gd._npc_stock = {"trader": {"omni_rune": 3}}
        gd._npc_buy_currency = {"trader": {"omni_rune": "feather"}}
        gd._npc_locations = {"trader": (0, 0)}
        state = make_state(level=12, skills={})
        assert grey_farm_allowed("feather", state, gd) is True

    def test_boundary_exactly_margin_away_is_close(self) -> None:
        """gap == margin: still 'close' (grind it), > margin: farm."""
        gd = _gd(alchemy_next_tier_level=20)
        at_margin = make_state(level=12, skills={"alchemy": 20 - GREY_FARM_NEXT_TIER_MARGIN})
        beyond = make_state(level=12, skills={"alchemy": 20 - GREY_FARM_NEXT_TIER_MARGIN - 1})
        assert grey_farm_allowed("feather", at_margin, gd) is False
        assert grey_farm_allowed("feather", beyond, gd) is True


class TestDropFarmMechanism:
    def test_drop_farm_flag_bypasses_xp_gate(self) -> None:
        gd = _gd()
        state = make_state(level=12, skills={"alchemy": 5})  # chicken is grey at L12
        plain = FightAction(monster_code="chicken", locations=frozenset({(1, 0)}))
        assert plain.is_applicable(state, gd) is False
        farm = dataclasses.replace(plain, drop_farm=True)
        assert farm.is_applicable(state, gd) is True

    def test_drop_farm_does_not_bypass_other_gates(self) -> None:
        """The bypass is ONLY for the xp gate: hp floor still vetoes."""
        gd = _gd()
        state = make_state(level=12, hp=1, max_hp=100, skills={"alchemy": 5})
        farm = FightAction(monster_code="chicken", locations=frozenset({(1, 0)}),
                           drop_farm=True)
        assert farm.is_applicable(state, gd) is False

    def test_repr_is_unchanged_by_the_flag(self) -> None:
        """Learned-cost history keys on repr — the flag must not fork them."""
        plain = FightAction(monster_code="chicken", locations=frozenset({(1, 0)}))
        farm = dataclasses.replace(plain, drop_farm=True)
        assert repr(farm) == repr(plain)


class TestGatherEmitsDropFarmFights:
    def test_grey_dropper_plans_when_policy_allows(self) -> None:
        """GatherMaterials(feather) at L12 must plan Fight(chicken) as a
        drop-farm fight when the next tier is far — the live Robby stage-1
        stall (feathers only servable from bank stock)."""
        gd = _gd(alchemy_next_tier_level=20)
        state = make_state(level=12, skills={"alchemy": 5},
                           inventory={}, bank_items={})
        goal = GatherMaterialsGoal(target_item="feather", needed={"feather": 2})
        actions = [FightAction(monster_code="chicken", locations=frozenset({(1, 0)}))]
        plan = GOAPPlanner().plan(state, goal, actions, gd, budget_seconds=10.0)
        assert [repr(a) for a in plan] == ["Fight(chicken)", "Fight(chicken)"]

    def test_grey_dropper_not_emitted_when_next_tier_close(self) -> None:
        gd = _gd(alchemy_next_tier_level=20)
        state = make_state(level=12, skills={"alchemy": 19},
                           inventory={}, bank_items={})
        goal = GatherMaterialsGoal(target_item="feather", needed={"feather": 2})
        actions = [FightAction(monster_code="chicken", locations=frozenset({(1, 0)}))]
        relevant = goal.relevant_actions(actions, state, gd)
        assert not any(isinstance(a, FightAction) and a.is_applicable(state, gd)
                       for a in relevant)

    def test_in_band_dropper_is_not_flagged(self) -> None:
        """A dropper the character still earns xp from needs no bypass — the
        plain fight is kept (no drop_farm fork of its learned-cost key)."""
        gd = _gd(alchemy_next_tier_level=20)
        state = make_state(level=3, skills={"alchemy": 5},
                           inventory={}, bank_items={})
        goal = GatherMaterialsGoal(target_item="feather", needed={"feather": 2})
        fight = FightAction(monster_code="chicken", locations=frozenset({(1, 0)}))
        relevant = goal.relevant_actions([fight], state, gd)
        kept = [a for a in relevant if isinstance(a, FightAction)]
        assert kept and all(a.drop_farm is False for a in kept)
