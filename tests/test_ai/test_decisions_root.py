"""The ROOT graph: one test per branch of every node in `ai/decisions/root.py`.

Nothing in production calls `resolve_root` yet (the flip is a later task of
`PLAN_wave3a_cutover`), so these tests ARE the whole consumer. They are built
on a real `CharacterObjective` over a small real `GameData` rather than on a
stand-in for `gear_targets_with_blockers`: a double returning the three
`GearTarget` shapes by hand would agree with `_classify_target` only for as
long as somebody kept it in step, and this graph's entire job is to read that
producer's output correctly. `_classify_target` emits FOUR shapes, not the
three spec §5.3 tabulates: skill-gated, attainable, blocked on a material, and
blocked on ITSELF. There is a test below for each.

The one doubled collaborator is `tier_progress.is_winnable` — a boolean oracle
over the combat model, monkeypatched so "the ladder is finished" and "a rung is
still open" are both reachable without building a winnable and an unwinnable
monster. That is the idiom `tests/test_ai/test_tier_progress.py` already uses
for the same two branches. Every test that patches it also puts a monster in
the band first: the bare `_gd()` has an EMPTY monster table, `tier_cleared` is
then `all([])`, and the patch would decide nothing — the branch would be
reached by an empty collection instead. Fix-round-1 found exactly that in two
of these tests.
"""
import pytest

import artifactsmmo_cli.ai.tiers.tier_progress as tier_progress
from artifactsmmo_cli.ai.decisions.root import (
    CanIClearMyTier,
    IsMyGearBehindMyTier,
    IsThereACombatTarget,
    IsThisTargetBlocked,
    RootWalk,
    WhichSlotIsFurthestBehind,
    _tier_gap,
    resolve_root,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, GearTarget
from artifactsmmo_cli.ai.tiers.tier_ladder import ladder, normal_band
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _ctx

# The five gear candidates below are chosen so that ONE slot lands in each of
# `_classify_target`'s outcomes, and so the tier gaps are not all equal:
#
#   shield_slot     iron_shield    gearcrafting 10 vs the character's 1 -> SKILL-gated
#   weapon_slot     ash_club       ash_plank <- ash_wood <- ash_tree     -> ATTAINABLE
#   helmet_slot     copper_helmet  no recipe, no drop, no vendor         -> its OWN blocker
#   leg_armor_slot  leather_legs   leather has no acquisition source     -> MATERIAL-gated
#   boots_slot      leather_boots  ditto, same material and quantity     -> MATERIAL-gated
#
# The last two deliberately collide on `ObtainItem("leather", 2)`, which is
# what makes the alternatives dedupe observable.
_LADDER_RUNGS = (1, 10)
_HIGH_LADDER_RUNGS = (10, 20)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "iron_shield": ItemStats(code="iron_shield", level=10, type_="shield",
                                 resistance={"earth": 20},
                                 crafting_skill="gearcrafting", crafting_level=10),
        "ash_club": ItemStats(code="ash_club", level=1, type_="weapon",
                              attack={"air": 4},
                              crafting_skill="weaponcrafting", crafting_level=1),
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   resistance={"water": 4}),
        "leather_legs": ItemStats(code="leather_legs", level=1, type_="leg_armor",
                                  resistance={"air": 3},
                                  crafting_skill="gearcrafting", crafting_level=1),
        "leather_boots": ItemStats(code="leather_boots", level=1, type_="boots",
                                   resistance={"fire": 3},
                                   crafting_skill="gearcrafting", crafting_level=1),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        "leather": ItemStats(code="leather", level=1, type_="resource"),
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource"),
    }
    gd._crafting_recipes = {
        "iron_shield": {"iron_bar": 6},
        "ash_club": {"ash_plank": 4},
        "ash_plank": {"ash_wood": 1},
        "leather_legs": {"leather": 2},
        "leather_boots": {"leather": 2},
    }
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


def _gd_two_ways_behind() -> GameData:
    """A second ladder, built for ONE question: what happens when two slots
    are behind by the SAME number of rungs but their targets sit on different
    rungs.

    Over `_gd()` that case cannot arise — every tied gap there is a tie in the
    target rung too (all four rung-1 targets sit in empty slots), so
    `_slot_order`'s middle key is never the one that decides and a mutant of
    it would survive. Here:

        weapon_slot  empty (rung 0)      -> iron_club   (rung 10)  gap 10
        boots_slot   iron_boots (rung 10) -> steel_boots (rung 20)  gap 10

    Same gap, different target rung, and the slots are in the OPPOSITE order
    to the schema tiebreak (weapon is index 0, boots is index 6), so the
    middle key is the only thing that can put boots first.
    """
    gd = GameData()
    gd._item_stats = {
        "iron_club": ItemStats(code="iron_club", level=10, type_="weapon",
                               attack={"air": 10}),
        "iron_boots": ItemStats(code="iron_boots", level=10, type_="boots",
                                resistance={"earth": 10}),
        "steel_boots": ItemStats(code="steel_boots", level=20, type_="boots",
                                 resistance={"earth": 30}),
    }
    return gd


def _objective(gd: GameData) -> CharacterObjective:
    return CharacterObjective(target_char_level=50, target_skill_levels={},
                              target_gear={}, _game_data=gd)


def _geared_state():
    """A character already wearing every candidate: no slot is behind."""
    base = make_state(level=15)
    equipment = dict(base.equipment)
    equipment.update(weapon_slot="ash_club", shield_slot="iron_shield",
                     helmet_slot="copper_helmet", leg_armor_slot="leather_legs",
                     boots_slot="leather_boots")
    return make_state(level=15, equipment=equipment)


def _target(**kw) -> GearTarget:
    base = dict(code="iron_shield", attainable=False, blocker=None)
    base.update(kw)
    return GearTarget(**base)


# ---------------------------------------------------------------------------
# The ladder the gap arithmetic is measured against
# ---------------------------------------------------------------------------

def test_the_fixture_ladder_is_the_two_rungs_the_gap_tests_assume():
    """Anti-vacuity: every gap number below is `rung - rung`, so a fixture
    whose ladder collapsed to one rung would make them all zero and the
    ordering tests would pass on a tie."""
    assert ladder(_gd()) == _LADDER_RUNGS
    assert ladder(_gd_two_ways_behind()) == _HIGH_LADDER_RUNGS


# ---------------------------------------------------------------------------
# IsMyGearBehindMyTier
# ---------------------------------------------------------------------------

def test_gear_behind_the_tier_routes_to_the_slot_walk():
    gd = _gd()
    walk = RootWalk()
    child = IsMyGearBehindMyTier(_objective(gd), walk).resolve(
        make_state(level=15), gd, _ctx(), None)
    assert isinstance(child, WhichSlotIsFurthestBehind)
    assert set(child.targets) == {"weapon_slot", "shield_slot", "helmet_slot",
                                  "leg_armor_slot", "boots_slot"}
    assert walk.trail == ["IsMyGearBehindMyTier"]


def test_no_gear_target_routes_to_the_combat_question():
    gd = _gd()
    child = IsMyGearBehindMyTier(_objective(gd), RootWalk()).resolve(
        _geared_state(), gd, _ctx(), None)
    assert isinstance(child, IsThereACombatTarget)


# ---------------------------------------------------------------------------
# WhichSlotIsFurthestBehind
# ---------------------------------------------------------------------------

def test_the_furthest_behind_slot_is_the_one_that_resolves():
    """shield_slot is 10 rungs behind (empty -> the level-10 rung); every
    other slot is 1. The head is the shield, and the other four are left in
    the walk as siblings."""
    gd = _gd()
    state = make_state(level=15)
    walk = RootWalk()
    node = IsMyGearBehindMyTier(_objective(gd), walk).resolve(state, gd, _ctx(), None)
    assert isinstance(node, WhichSlotIsFurthestBehind)
    child = node.resolve(state, gd, _ctx(), None)
    assert isinstance(child, IsThisTargetBlocked)
    assert child.slot == "shield_slot"
    assert [slot for slot, _ in walk.sibling_targets] == [
        "weapon_slot", "helmet_slot", "leg_armor_slot", "boots_slot"]


def test_equal_gaps_break_on_the_schema_slot_order_not_the_alphabet():
    """weapon/helmet/leg_armor/boots are all 1 rung behind with a rung-1
    target. Alphabetically that is boots, helmet, leg_armor, weapon; the
    schema declares weapon, shield, helmet, leg_armor, boots, and the schema
    order is what the walk uses."""
    gd = _gd()
    state = make_state(level=15)
    walk = RootWalk()
    node = WhichSlotIsFurthestBehind(
        _objective(gd).gear_targets_with_blockers(state, None), walk)
    node.resolve(state, gd, _ctx(), None)
    assert [slot for slot, _ in walk.sibling_targets] == [
        "weapon_slot", "helmet_slot", "leg_armor_slot", "boots_slot"]


def test_equal_gaps_prefer_the_HIGHER_rung_target():
    """The middle key of `_slot_order`. Both slots are 10 rungs behind; boots
    is chasing rung 20 and weapon rung 10, and boots must lead even though the
    schema puts weapon_slot first. Feeding the targets dict straight in is
    deliberate: this node's input IS a `dict[str, GearTarget]` and the claim
    under test is the ORDERING, not how the blocker fields were classified."""
    gd = _gd_two_ways_behind()
    base = make_state(level=25)
    state = make_state(level=25,
                       equipment=dict(base.equipment, boots_slot="iron_boots"))
    targets = {
        "weapon_slot": _target(code="iron_club", attainable=True),
        "boots_slot": _target(code="steel_boots", attainable=True),
    }
    assert _tier_gap("weapon_slot", targets["weapon_slot"], state, gd) == 10
    assert _tier_gap("boots_slot", targets["boots_slot"], state, gd) == 10
    walk = RootWalk()
    child = WhichSlotIsFurthestBehind(targets, walk).resolve(state, gd, _ctx(), None)
    assert isinstance(child, IsThisTargetBlocked)
    assert child.slot == "boots_slot"
    assert [slot for slot, _ in walk.sibling_targets] == ["weapon_slot"]


def test_an_empty_slot_outranks_an_occupied_one_at_the_same_rung():
    """An empty slot counts as rung 0, strictly below the ladder's first rung
    — not `tier_of_level(0)`, which IS the first rung. Wearing a rung-1 item
    and targeting a rung-1 item is a gap of 0; wearing nothing is a gap of 1."""
    gd = _gd()
    target = _target(code="leather_boots", attainable=True)
    empty = make_state(level=15)
    worn = make_state(level=15,
                      equipment=dict(empty.equipment, boots_slot="leather_boots"))
    assert _tier_gap("boots_slot", target, empty, gd) == 1
    assert _tier_gap("boots_slot", target, worn, gd) == 0


def test_a_gear_target_absent_from_game_data_is_an_error_not_a_default_rung():
    gd = _gd()
    with pytest.raises(ValueError, match="no item stats in game data"):
        _tier_gap("boots_slot", _target(code="phantom_boots"),
                  make_state(level=15), gd)


# ---------------------------------------------------------------------------
# IsThisTargetBlocked — one test per arm of the FOUR GearTarget shapes
# ---------------------------------------------------------------------------

def _blocked(target: GearTarget, slot: str = "shield_slot", state=None):
    gd = _gd()
    return IsThisTargetBlocked(slot, target, RootWalk()).resolve(
        state if state is not None else make_state(level=15), gd, _ctx(), None)


def test_a_skill_gated_target_raises_the_skill_by_one():
    """gearcrafting 1 against a level-10 craft: the root is +1, not the
    target level — the graph re-derives every cycle and the increment
    advances on its own."""
    result = _blocked(_target(blocking_skill="gearcrafting",
                              blocking_skill_level=10))
    assert result == ReachSkillLevel(skill="gearcrafting", level=2)


def test_the_skill_gate_is_read_before_the_blocker_field():
    """A skill-gated target also carries `blocker=None`. Testing `blocker is
    None` first would report it as ATTAINABLE and the character would chase a
    craft it cannot perform."""
    result = _blocked(_target(code="iron_shield", blocking_skill="gearcrafting",
                              blocking_skill_level=10, blocker=None))
    assert not isinstance(result, ObtainItem)


def test_an_attainable_target_becomes_an_obtain_item_for_that_slot():
    result = _blocked(_target(code="ash_club", attainable=True, blocker=None),
                      slot="weapon_slot")
    assert result == ObtainItem(code="ash_club", quantity=1, slot="weapon_slot")


def test_a_material_gated_target_routes_to_the_material_at_its_recipe_quantity():
    result = _blocked(_target(code="leather_boots", blocker="leather"),
                      slot="boots_slot")
    assert result == ObtainItem(code="leather", quantity=2)


def test_a_target_that_is_its_own_blocker_routes_to_the_target_itself():
    """`_classify_target`'s last arm: no recipe (or none of the recipe is out
    of reach) and the item still is not attainable. There is no material to
    route to."""
    result = _blocked(_target(code="copper_helmet", blocker="copper_helmet"),
                      slot="helmet_slot")
    assert result == ObtainItem(code="copper_helmet", quantity=1,
                                slot="helmet_slot")


def test_a_blocker_that_is_not_in_the_recipe_is_an_error():
    with pytest.raises(ValueError, match="not in its recipe"):
        _blocked(_target(code="leather_boots", blocker="iron_bar"),
                 slot="boots_slot")


def test_a_blocker_on_an_uncraftable_target_is_an_error():
    with pytest.raises(ValueError, match="not in its recipe"):
        _blocked(_target(code="copper_helmet", blocker="leather"),
                 slot="helmet_slot")


# ---------------------------------------------------------------------------
# IsThereACombatTarget / CanIClearMyTier
# ---------------------------------------------------------------------------

def test_combat_target_root_is_the_already_satisfied_rung():
    """SPEC-AS-WRITTEN, and it is almost certainly wrong: `tier_of_level`
    returns the highest rung AT OR BELOW the character's level, so at level
    15 the root is `ReachCharLevel(10)` — a root the character has already
    met. Transcribed rather than repaired (see the module docstring of
    `ai/decisions/root.py`); this test exists so the flip task cannot change
    it without noticing."""
    gd = _gd()
    state = make_state(level=15)
    result = IsThereACombatTarget(RootWalk()).resolve(
        state, gd, _ctx(combat_monster="chicken"), None)
    assert result == ReachCharLevel(level=10)
    assert isinstance(result, ReachCharLevel) and result.is_satisfied(state, gd)


def test_no_combat_target_asks_whether_the_tier_is_clear():
    gd = _gd()
    child = IsThereACombatTarget(RootWalk()).resolve(
        make_state(level=15), gd, _ctx(combat_monster=None), None)
    assert isinstance(child, CanIClearMyTier)


def test_a_finished_ladder_resolves_to_the_trunk_milestone(monkeypatch):
    """The chicken is REQUIRED, not decoration: on the bare `_gd()` the
    monster table is empty, `normal_band(gd, 1)` is `()` and `tier_cleared` is
    `all([])`, so `next_uncleared_tier` already returns None and the patch
    below decides nothing. With a monster in the band the patch is what flips
    the branch. Fix-round-1."""
    gd = _gd()
    gd._monster_level = {"chicken": 1}
    gd._monster_type = {"chicken": "normal"}
    assert normal_band(gd, 1) == ("chicken",)
    monkeypatch.setattr(tier_progress, "is_winnable", lambda s, g, c, h: True)
    result = CanIClearMyTier(RootWalk()).resolve(
        make_state(level=15), gd, _ctx(), None)
    assert result == ReachCharLevel(level=20)


def test_an_open_rung_with_nothing_to_do_is_an_honest_wall(monkeypatch):
    """Gear wants nothing, no monster in the band is winnable, and a rung is
    still open. There is no root — reported as None, not dressed up."""
    gd = _gd()
    gd._monster_level = {"chicken": 1}
    gd._monster_type = {"chicken": "normal"}
    monkeypatch.setattr(tier_progress, "is_winnable", lambda s, g, c, h: False)
    assert CanIClearMyTier(RootWalk()).resolve(
        make_state(level=15), gd, _ctx(), None) is None


# ---------------------------------------------------------------------------
# resolve_root — the whole walk
# ---------------------------------------------------------------------------

def test_resolve_root_walks_gear_to_the_skill_gate_and_names_the_path():
    gd = _gd()
    resolution = resolve_root(make_state(level=15), gd, _objective(gd), _ctx(), None)
    assert resolution.root == ReachSkillLevel(skill="gearcrafting", level=2)
    assert resolution.trail == ("IsMyGearBehindMyTier", "WhichSlotIsFurthestBehind",
                                "IsThisTargetBlocked")


def test_the_siblings_become_the_alternatives_with_the_trunk_last():
    """leg_armor and boots are both blocked on two `leather`, so they resolve
    to the SAME `ObtainItem` and appear once."""
    gd = _gd()
    resolution = resolve_root(make_state(level=15), gd, _objective(gd), _ctx(), None)
    assert resolution.alternatives == (
        ObtainItem(code="ash_club", quantity=1, slot="weapon_slot"),
        ObtainItem(code="copper_helmet", quantity=1, slot="helmet_slot"),
        ObtainItem(code="leather", quantity=2),
        ReachCharLevel(level=20),
    )


def test_converting_a_sibling_does_not_pollute_the_trail():
    """The four siblings are each resolved through `IsThisTargetBlocked` to
    become MetaGoals. Those visits use a throwaway walk, so the trail names
    only the nodes the real walk went through."""
    gd = _gd()
    resolution = resolve_root(make_state(level=15), gd, _objective(gd), _ctx(), None)
    assert resolution.trail.count("IsThisTargetBlocked") == 1


def test_the_chosen_root_is_never_repeated_as_its_own_alternative(monkeypatch):
    gd = _gd()
    gd._monster_level = {"chicken": 1}      # see the trunk test: without a
    gd._monster_type = {"chicken": "normal"}  # monster the patch is inert
    monkeypatch.setattr(tier_progress, "is_winnable", lambda s, g, c, h: True)
    resolution = resolve_root(_geared_state(), gd, _objective(gd), _ctx(), None)
    assert resolution.root == ReachCharLevel(level=20)
    assert resolution.alternatives == ()
    assert resolution.trail == ("IsMyGearBehindMyTier", "IsThereACombatTarget",
                                "CanIClearMyTier")


def test_a_wall_still_offers_the_trunk_as_an_alternative(monkeypatch):
    gd = _gd()
    gd._monster_level = {"chicken": 1}
    gd._monster_type = {"chicken": "normal"}
    monkeypatch.setattr(tier_progress, "is_winnable", lambda s, g, c, h: False)
    resolution = resolve_root(_geared_state(), gd, _objective(gd), _ctx(), None)
    assert resolution.root is None
    assert resolution.alternatives == (ReachCharLevel(level=20),)
