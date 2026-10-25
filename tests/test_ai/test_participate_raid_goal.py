"""ParticipateRaidGoal unit behaviour.

The goal shipped covered only by the l48 scenario pair -- an integration path.
That is how its `is_satisfied` contract ended up undocumented by any test even
though it was the single hardest thing to get right: a never-satisfied goal gives
A* no goal test, so the search runs to max_depth, returns no plan, and the
candidate is silently REJECTED. The raid was unselectable for exactly that reason
until the xp floor was added.
"""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from fractions import Fraction

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.arbiter_select import BAND_RAID
from artifactsmmo_cli.ai.combat import combat_terms
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.fight_terms_core import MAX_TURNS, FightExit
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.goals.participate_raid import (
    RAID_PARTICIPATION_VALUE,
    ParticipateRaidGoal,
)
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.raid_info import RaidInfo
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter, chosen_root_closure, raid_may_fight
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal, ObtainItem, ReachSkillLevel
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state

_RAID = "enchanted_fairy"
_BOSS = "pixie"


def _goal(xp_floor: int = 100) -> ParticipateRaidGoal:
    return ParticipateRaidGoal(raid_code=_RAID, monster_code=_BOSS, xp_floor=xp_floor)


def test_unsatisfied_at_the_floor():
    """One engagement is the unit of work, so the goal is open until XP moves."""
    assert _goal(xp_floor=100).is_satisfied(make_state(xp=100)) is False


def test_satisfied_once_xp_rises_above_the_floor():
    assert _goal(xp_floor=100).is_satisfied(make_state(xp=101)) is True


def test_unsatisfied_below_the_floor():
    """Defensive: a lower XP than the floor is not 'done'. Cannot happen in a
    forward plan, but the predicate must not read as satisfied by accident."""
    assert _goal(xp_floor=100).is_satisfied(make_state(xp=99)) is False


def test_relevant_actions_keeps_only_the_boss_fight():
    """The goal narrows to its OWN boss. Without this it would admit every fight
    in the catalog and plan an unrelated grind under a raid banner."""
    boss = FightAction(monster_code=_BOSS, locations=frozenset({(1, 0)}), learned_drops=LearnedDrops.empty())
    other = FightAction(monster_code="chicken", locations=frozenset({(2, 0)}), learned_drops=LearnedDrops.empty())
    catalog = [boss, other, MoveAction(x=0, y=0), RestAction()]
    out = _goal().relevant_actions(catalog, make_state(), GameData())
    assert out == [boss]


def test_relevant_actions_empty_when_the_boss_fight_is_absent():
    """The factory only emits the raid fight while the window is open, so a shut
    window leaves this goal with nothing -- it must not invent an action."""
    catalog = [FightAction(monster_code="chicken", locations=frozenset({(2, 0)}), learned_drops=LearnedDrops.empty())]
    assert _goal().relevant_actions(catalog, make_state(), GameData()) == []


def test_value_is_the_discretionary_constant():
    """Vestigial for routing (the arbiter selects by band position, not value)
    but pinned so it cannot drift into reading as a priority claim it cannot
    make -- it must stay below the survival floor."""
    assert _goal().value(make_state(), GameData()) == RAID_PARTICIPATION_VALUE
    assert RAID_PARTICIPATION_VALUE < 50.0


def test_repr_names_the_raid_not_the_boss():
    """Sticky commitment keys on repr, and the RAID is the thing whose window
    opens and shuts; two raids sharing a boss must not collide."""
    assert repr(_goal()) == f"ParticipateRaid({_RAID})"


def test_desired_state_is_empty_so_the_goal_test_is_is_satisfied():
    """Pairs with is_satisfied: the planner goal-tests via is_satisfied, so a
    non-empty desired_state here would add a second, divergent goal test."""
    assert _goal().desired_state(make_state(), GameData()) == {}


# ─── the two _raid_candidates gates, exercised directly ──────────────────────
# Both are refusals the raid design turns on, and both shipped uncovered: a raid
# with no known tile, and one the character cannot survive. A gate that is never
# exercised is a gate nobody has checked refuses anything.

def _raid_info() -> RaidInfo:
    now = datetime.now(timezone.utc)
    return RaidInfo(code=_RAID, name=_RAID, monster=_BOSS, status="active",
                    next_start_at=now + timedelta(days=1), remaining_hp=5000,
                    total_hp=10000, window_ends_at=now + timedelta(hours=1))


def _raid_gd(*, tiles: bool, hurts: bool) -> GameData:
    gd = GameData()
    gd._item_stats = {"x": ItemStats(code="x", level=1, type_="resource")}
    gd._monster_level = {_BOSS: 40}
    gd._monster_hp = {_BOSS: 100}
    gd._monster_attack = {_BOSS: {"air": 400 if hurts else 1}}
    gd._monster_resistance = {_BOSS: {}}
    if tiles:
        gd.world.raid_locations = {_RAID: [(-4, 10)]}
    fill_monster_stat_defaults(gd)
    return gd


_PIECE = GearPiece("shield_slot", "boss_shield", 0, Fraction(1), Fraction(10), SourceKind.DROP)
"""A missing `L*` piece."""
_MISSING = GearObjective("wolf", {"shield_slot": "boss_shield"}, Fraction(1), (_PIECE,))
_HELD = GearObjective("wolf", {"shield_slot": "boss_shield"}, Fraction(1), ())


def _candidates(gd, state, objective: GearObjective | None = None,
                chosen_root: MetaGoal | None = None):
    return StrategyArbiter._raid_candidates(
        StrategyArbiter.__new__(StrategyArbiter), state, gd,
        replace(NO_PROFILE_CONTEXT, gear_objective=objective), chosen_root)


def test_raid_with_no_known_tile_is_not_offered():
    state = make_state(level=48, hp=1000, max_hp=1000,
                       attack={"air": 50}, raids=[_raid_info()])
    assert _candidates(_raid_gd(tiles=False, hurts=False), state) == []


def test_unsurvivable_raid_is_not_offered():
    """A boss that would drop the character below the critical floor in one
    engagement: rest first, do not go."""
    state = make_state(level=48, hp=1000, max_hp=1000,
                       attack={"air": 50}, raids=[_raid_info()])
    assert _candidates(_raid_gd(tiles=True, hurts=True), state) == []


def test_survivable_raid_with_a_tile_is_offered():
    """Non-vacuity: the same shape that passes both gates DOES produce a goal,
    so the two refusals above are measuring the gates and not a broken fixture."""
    state = make_state(level=48, hp=1000, max_hp=1000,
                       attack={"air": 50}, raids=[_raid_info()])
    out = _candidates(_raid_gd(tiles=True, hurts=False), state)
    assert [repr(g) for g in out] == [f"ParticipateRaid({_RAID})"]


def test_a_weak_unkillable_raid_boss_is_offered():
    """A raid is won by surviving all 100 turns OR finishing the boss
    (`raid_participation`: upstream's win condition; the boss's HP pool is
    shared across accounts). So a boss the character cannot finish inside
    `MAX_TURNS` is not a loss: here 50 air a hit into 600,000 HP is far over
    the cap (`combat_terms` exits `OVER_CAP`), and the boss's 1 air a hit for
    the capped 100 turns leaves the character above the floor, so the raid is
    offered. Plan B Task 1, ruling BD: the uncapped estimate (1 x 12,000 rounds)
    refused it."""
    gd = _raid_gd(tiles=True, hurts=False)
    gd._monster_hp = {_BOSS: 600_000}
    state = _survivable_state()
    assert combat_terms(state, gd, _BOSS).exit is FightExit.OVER_CAP
    assert expected_damage_per_fight(state, gd, _BOSS) == 1 * MAX_TURNS
    out = _candidates(gd, state)
    assert [repr(g) for g in out] == [f"ParticipateRaid({_RAID})"]


def test_an_offered_raid_is_filed_at_the_raid_band():
    """`_append_raid_candidates` files every offered raid at `BAND_RAID`, above
    the fallback steps (wave 3a fix-round 1). Pinned directly since ruling R
    (2026-10-18): the l48 raid pole that used to reach it end to end refuses
    pixie on real stats."""
    state = make_state(level=48, hp=1000, max_hp=1000,
                       attack={"air": 50}, raids=[_raid_info()])
    candidates: list = []
    StrategyArbiter._append_raid_candidates(StrategyArbiter.__new__(StrategyArbiter),
                                            candidates, state,
                                            _raid_gd(tiles=True, hurts=False),
                                            NO_PROFILE_CONTEXT, None)
    assert [(c.repr_, c.band) for c in candidates] == [(f"ParticipateRaid({_RAID})", BAND_RAID)]


# --- ruling AJ: a raid is an XP fight, so it waits for L* -------------------

def _survivable_state():
    return make_state(level=48, hp=1000, max_hp=1000,
                      attack={"air": 50}, raids=[_raid_info()])


def test_a_missing_piece_keeps_the_raid_off_the_walk():
    """Final review F2: while a piece of `L*` is missing a survivable raid is
    not offered at all — not merely filed behind the step, where an
    unplannable or turn-spent step handed the cycle to it."""
    gd = _raid_gd(tiles=True, hurts=False)
    root = ObtainItem("boss_shield", 1, slot="shield_slot")
    assert _candidates(gd, _survivable_state(), _MISSING, root) == []


def test_a_held_objective_offers_the_raid():
    gd = _raid_gd(tiles=True, hurts=False)
    out = _candidates(gd, _survivable_state(), _HELD, None)
    assert [repr(g) for g in out] == [f"ParticipateRaid({_RAID})"]


def test_the_raid_is_offered_when_its_boss_drops_the_chosen_piece():
    """The raid IS the chosen piece's route: its boss drops the walk's root."""
    gd = _raid_gd(tiles=True, hurts=False)
    gd._monster_drops = {_BOSS: [("boss_shield", 10, 1, 1)]}
    root = ObtainItem("boss_shield", 1, slot="shield_slot")
    out = _candidates(gd, _survivable_state(), _MISSING, root)
    assert [repr(g) for g in out] == [f"ParticipateRaid({_RAID})"]


def test_raid_may_fight_reads_the_objective_and_the_route():
    drops = [("boss_shield", 10, 1, 1)]
    shield = ObtainItem("boss_shield", 1, slot="shield_slot")
    closure = frozenset({"boss_shield"})
    assert raid_may_fight(None, None, [], frozenset())
    assert raid_may_fight(_HELD, None, [], frozenset())
    assert not raid_may_fight(_MISSING, None, drops, frozenset())
    assert not raid_may_fight(_MISSING, shield, [], closure)
    assert not raid_may_fight(_MISSING, ObtainItem("other", 1), drops, frozenset({"other"}))
    assert raid_may_fight(_MISSING, shield, drops, closure)


def _piece_gd(recipe: dict[str, int]):
    """The raid world plus a craftable `boss_shield` whose recipe is `recipe`."""
    gd = _raid_gd(tiles=True, hurts=False)
    gd._monster_drops = {_BOSS: [("boss_blade_shard", 10, 1, 1)]}
    gd._item_stats["boss_shield"] = ItemStats(code="boss_shield", level=5, type_="shield")
    gd._item_stats["boss_blade_shard"] = ItemStats(code="boss_blade_shard", level=1,
                                                   type_="resource")
    gd._crafting_recipes = {"boss_shield": dict(recipe)}
    gd._crafting_skill = {"boss_shield": "gearcrafting"}
    gd._crafting_level = {"boss_shield": 5}
    return gd


def test_a_raid_dropping_a_material_of_the_piece_may_fight():
    """The boss drops a recipe INPUT of the chosen piece, not the piece."""
    gd = _piece_gd({"boss_blade_shard": 2})
    root = ObtainItem("boss_shield", 1, slot="shield_slot")
    assert chosen_root_closure(root, _survivable_state(), gd, NO_PROFILE_CONTEXT) == {
        "boss_shield", "boss_blade_shard"}
    out = _candidates(gd, _survivable_state(), _MISSING, root)
    assert [repr(g) for g in out] == [f"ParticipateRaid({_RAID})"]


def test_an_unrelated_raid_still_waits():
    gd = _piece_gd({"x": 2})
    root = ObtainItem("boss_shield", 1, slot="shield_slot")
    assert _candidates(gd, _survivable_state(), _MISSING, root) == []


def test_a_root_with_no_item_has_an_empty_closure():
    gd = _piece_gd({"x": 2})
    assert chosen_root_closure(None, _survivable_state(), gd, NO_PROFILE_CONTEXT) == frozenset()


def _grind_gd() -> GameData:
    """The `test_gather_demand._gd` shape: `iron_gloves` is a level-1
    gearcrafting recipe over iron_bar -> iron_ore, so a gearcrafting@1
    character's grind target is `iron_gloves`; `iron_nails` is the in-level
    mining recipe a mining climb would seed with, were it not a gathering skill."""
    gd = _raid_gd(tiles=True, hurts=False)
    gd._item_stats.update({
        "iron_gloves": ItemStats(code="iron_gloves", level=1, type_="gloves",
                                 crafting_skill="gearcrafting", crafting_level=1),
        "iron_bar": ItemStats(code="iron_bar", level=10, type_="resource",
                              crafting_skill="mining", crafting_level=10),
        "iron_ore": ItemStats(code="iron_ore", level=10, type_="resource"),
        "iron_nails": ItemStats(code="iron_nails", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
    })
    gd._crafting_recipes = {"iron_gloves": {"iron_bar": 1}, "iron_bar": {"iron_ore": 10},
                            "iron_nails": {"iron_ore": 1}}
    gd._resource_drops_full = {"iron_rocks": [("iron_ore", 100, 1, 1)]}
    gd._resource_skill = {"iron_rocks": ("mining", 10)}
    gd.world.workshop_locations = {"mining": (0, 0), "gearcrafting": (0, 1)}
    gd.recipes_catalog.locations = {"iron_rocks": [(1, 0)]}
    return gd


def test_a_skill_root_is_seeded_with_its_grind_target():
    """A `ReachSkillLevel` names no item; its closure is that of the item the
    character would craft for the rung, and a boss dropping a material of it
    is the route."""
    gd = _grind_gd()
    gd._monster_drops = {_BOSS: [("iron_ore", 10, 1, 1)]}
    state = make_state(level=48, hp=1000, max_hp=1000, attack={"air": 50},
                       skills={"mining": 1, "gearcrafting": 1}, raids=[_raid_info()])
    root = ReachSkillLevel("gearcrafting", 10)
    ctx = replace(TIMED_NO_PROFILE_CONTEXT, gear_objective=_MISSING)
    assert chosen_root_closure(root, state, gd, ctx) == {
        "iron_gloves", "iron_bar", "iron_ore"}
    out = StrategyArbiter._raid_candidates(
        StrategyArbiter.__new__(StrategyArbiter), state, gd, ctx, root)
    assert [repr(g) for g in out] == [f"ParticipateRaid({_RAID})"]


def test_a_gathering_skill_root_has_an_empty_closure():
    """A mining climb's XP comes from gathering, so no craft feeds it and a
    boss dropping the mining grind target's materials is no route."""
    gd = _grind_gd()
    gd._monster_drops = {_BOSS: [("iron_ore", 10, 1, 1)]}
    state = make_state(level=48, hp=1000, max_hp=1000, attack={"air": 50},
                       skills={"mining": 1, "gearcrafting": 1}, raids=[_raid_info()])
    root = ReachSkillLevel("mining", 2)
    ctx = replace(TIMED_NO_PROFILE_CONTEXT, gear_objective=_MISSING)
    assert chosen_root_closure(root, state, gd, ctx) == frozenset()
    assert StrategyArbiter._raid_candidates(
        StrategyArbiter.__new__(StrategyArbiter), state, gd, ctx, root) == []


def test_a_skill_root_with_no_grind_target_has_an_empty_closure():
    gd = _raid_gd(tiles=True, hurts=False)
    state = make_state(level=48, skills={"gearcrafting": 1})
    ctx = replace(TIMED_NO_PROFILE_CONTEXT, gear_objective=_MISSING)
    assert chosen_root_closure(ReachSkillLevel("gearcrafting", 5), state, gd, ctx) == frozenset()
